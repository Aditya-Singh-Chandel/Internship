"""
Compares ways of building the knowledge-base search query for follow-up questions, on the same labelled cases.
Only conversations with earlier turns can differ between strategies, so the comparison runs on those.

    python -m evals.retrieval_variants            # free strategies (no LLM)
    python -m evals.retrieval_variants --llm      # also an LLM rewrite (11+ Gemini calls, paced)
    python -m evals.retrieval_variants --tuning   # retrieval depth and keyword re-ranking
    python -m evals.retrieval_variants --rerank   # cross-encoder models and candidate-pool sizes (local, no LLM)

Reads the test database as seeded by the last eval run; it never writes to it.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conftest  # noqa: E402,F401  (points the app at the test database before importing it)

from app.core.database import session_maker  # noqa: E402
from app.services import chat_service, document_service, llm_service  # noqa: E402
from evals.dataset import Case, load_golden  # noqa: E402
from evals.retrieval_metrics import TOP_K, evaluate_retrieval  # noqa: E402


def _search(db, case: Case, query: str, top_k: int):
    # rerank=False: these strategies compare query construction on the first stage alone
    return document_service.search_chunks(db, query=query, hotel_id=case.hotel_id, top_k=top_k, access_level="public", rerank=False)


def _users(case):
    return [t["content"] for t in case.history if t["role"] == "user"]


def message_only(db, case, top_k=TOP_K):
    return _search(db, case, case.question, top_k)


def production(db, case, top_k=TOP_K):
    return _search(db, case, chat_service.build_retrieval_query(case.question, case.history), top_k)


def previous_two_user_turns(db, case, top_k=TOP_K):
    return _search(db, case, " ".join(_users(case)[-2:] + [case.question]), top_k)


def previous_user_and_assistant(db, case, top_k=TOP_K):
    return _search(db, case, " ".join([t["content"] for t in case.history[-2:]] + [case.question]), top_k)


def always_previous_user(db, case, top_k=TOP_K):
    return _search(db, case, " ".join(_users(case)[-1:] + [case.question]), top_k)


def llm_rewrite(db, case, top_k=TOP_K):
    if not case.history:
        return _search(db, case, case.question, top_k)
    convo = "\n".join(f"{t['role']}: {t['content']}" for t in case.history)
    rewritten = llm_service.call_gemini_cloud_api(
        prompt=f"Conversation:\n{convo}\n\nLast user message: {case.question}\n\n"
               "Rewrite the last user message as one standalone search query that names the topic and hotel it refers to. "
               "Output only the query.",
        system_instruction="You rewrite chat messages into standalone search queries.",
        temperature=0.0, max_tokens=100,
    )
    time.sleep(4.5)  # stay under the free-tier request limit
    return _search(db, case, rewritten.strip(), top_k)


STRATEGIES = {
    "message only (today)": message_only,
    "previous user turn, when short/anaphoric": production,
    "previous user turn, always": always_previous_user,
    "previous two user turns": previous_two_user_turns,
    "previous user + assistant turn": previous_user_and_assistant,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--tuning", action="store_true", help="compare retrieval depth and keyword re-ranking on all labelled cases")
    parser.add_argument("--rerank", action="store_true", help="compare cross-encoder re-rankers and candidate-pool sizes")
    args = parser.parse_args()
    if args.rerank:
        return rerank_main()
    if args.tuning:
        return tuning_main()
    strategies = dict(STRATEGIES)
    if args.llm:
        strategies["LLM rewrite"] = llm_rewrite

    cases = [c for c in load_golden() if c.history and c.relevant]
    print(f"{len(cases)} follow-up cases with retrieval labels, top-{TOP_K}\n")
    print(f"{'strategy':<42}{'hit':>6}{'hit@1':>7}{'MRR':>6}{'recall':>8}")
    with session_maker() as db:
        for name, retriever in strategies.items():
            overall = evaluate_retrieval(db, cases, retriever=retriever)["overall"]
            print(f"{name:<42}{overall['hit']:>6.2f}{overall['hit@1']:>7.2f}{overall['mrr']:>6.2f}{overall['recall']:>8.2f}")



# ---------------------------------------------------------------- depth and keyword re-ranking (whole labelled set)
def _keyword_overlap(query: str, content: str) -> float:
    """Same formula the Python fallback search uses: share of query words that occur in the chunk."""
    tokens = set(query.lower().split())
    text = content.lower()
    return sum(1 for t in tokens if t in text) / max(len(tokens), 1)


def hybrid_rerank(db, case, top_k=TOP_K, pool=30):
    """Vector search for a wider pool, then re-rank by 0.7 * semantic + 0.3 * keyword overlap (as the fallback path does)."""
    query = chat_service.build_retrieval_query(case.question, case.history)
    hits = _search(db, case, query, pool)
    for h in hits:
        h["similarity_score"] = round(0.7 * h["similarity_score"] + 0.3 * _keyword_overlap(query, h["content"]), 4)
    return sorted(hits, key=lambda h: -h["similarity_score"])[:top_k]


def tuning_main() -> None:
    cases = [c for c in load_golden() if c.relevant]
    print(f"{len(cases)} labelled cases (all categories), search query built by the production rule\n")
    print(f"{'setting':<46}{'hit':>6}{'hit@1':>7}{'MRR':>6}{'recall':>8}{'prec':>6}")
    rows = [("top-4, vector only (today)", production, 4), ("top-6, vector only", production, 6), ("top-8, vector only", production, 8),
            ("top-4, vector + keyword re-rank", hybrid_rerank, 4), ("top-6, vector + keyword re-rank", hybrid_rerank, 6),
            ("top-8, vector + keyword re-rank", hybrid_rerank, 8)]
    with session_maker() as db:
        for name, retriever, k in rows:
            o = evaluate_retrieval(db, cases, retriever=retriever, k=k)["overall"]
            print(f"{name:<46}{o['hit']:>6.2f}{o['hit@1']:>7.2f}{o['mrr']:>6.2f}{o['recall']:>8.2f}{o['precision']:>6.2f}")


# ---------------------------------------------------------------- cross-encoder re-ranking (whole labelled set)
RERANK_MODELS = [
    "Xenova/ms-marco-MiniLM-L-6-v2",
    "Xenova/ms-marco-MiniLM-L-12-v2",
    "jinaai/jina-reranker-v1-turbo-en",
    "BAAI/bge-reranker-base",
]


def _production_search(rerank: bool):
    def retriever(db, case, top_k=TOP_K):
        query = chat_service.build_retrieval_query(case.question, case.history)
        return document_service.search_chunks(db, query=query, hotel_id=case.hotel_id, top_k=top_k,
                                              access_level="public", rerank=rerank)
    return retriever


def rerank_main() -> None:
    from app.core.config import settings
    from app.services import rerank_service

    cases = [c for c in load_golden() if c.relevant]
    print(f"{len(cases)} labelled cases, production search query, top-{TOP_K}\n")
    print(f"{'setting':<52}{'hit':>6}{'hit@1':>7}{'MRR':>6}{'recall':>8}{'ms/query':>10}")
    rows = [("vector only (no re-rank)", None, None)]
    rows += [(f"{m.split('/')[-1]}, pool 30", m, 30) for m in RERANK_MODELS]
    rows += [(f"{RERANK_MODELS[0].split('/')[-1]}, pool {p}", RERANK_MODELS[0], p) for p in (15, 50)]
    with session_maker() as db:
        for name, model, pool in rows:
            if model:
                settings.RERANK_MODEL, settings.RERANK_CANDIDATES = model, pool
                if rerank_service.get_model() is None:
                    print(f"{name:<52}  (model failed to load)")
                    continue
                _production_search(True)(db, cases[0])  # warm-up: first ONNX call is slow
            start = time.perf_counter()
            o = evaluate_retrieval(db, cases, retriever=_production_search(model is not None))["overall"]
            ms = (time.perf_counter() - start) * 1000 / len(cases)
            print(f"{name:<52}{o['hit']:>6.2f}{o['hit@1']:>7.2f}{o['mrr']:>6.2f}{o['recall']:>8.2f}{ms:>10.0f}")


if __name__ == "__main__":
    main()
