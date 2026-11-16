"""
Retrieval quality for the knowledge base, with no LLM involved.

A retrieved chunk counts as relevant to a case if it belongs to a labelled hotel and contains the labelled text.
Metrics (per case, then averaged by category):
  hit@k        1 if any relevant chunk is in the top k
  MRR          1 / rank of the first relevant chunk (0 if none retrieved)
  recall@k     share of the case's relevance labels covered by the top-k chunks
  precision@k  share of the top-k chunks that are relevant to at least one label

Run a report:   python -m evals.retrieval_metrics
"""
import json
import os
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conftest  # noqa: E402,F401

from app.services import document_service
from evals.dataset import Case, load_golden

TOP_K = 8  # what send_chat_message uses (chat_service.KNOWLEDGE_BASE_TOP_K)

Retriever = Callable[..., List[Dict]]


def default_retriever(db, case: Case, top_k: int = TOP_K) -> List[Dict]:
    """Exactly what the chatbot does: the history-aware search query, public chunks, scoped to the chat's hotel."""
    from app.services.chat_service import build_retrieval_query

    query = build_retrieval_query(case.question, case.history)
    return document_service.search_chunks(db, query=query, hotel_id=case.hotel_id, top_k=top_k, access_level="public")


def _matches(chunk: Dict, label: Dict[str, str], hotel_ids: Dict[str, object]) -> bool:
    return chunk["hotel_id"] == hotel_ids[label["hotel"]] and label["contains"].lower() in chunk["content"].lower()


def score_case(case: Case, chunks: List[Dict], k: int = TOP_K) -> Dict[str, float]:
    from evals.seed import sid

    hotel_ids = {key: sid(f"hotel:{key}") for key in {r["hotel"] for r in case.relevant}}
    top = chunks[:k]
    first_rank: Optional[int] = None
    covered = set()
    relevant_chunks = 0
    for rank, chunk in enumerate(top, start=1):
        hits = [i for i, label in enumerate(case.relevant) if _matches(chunk, label, hotel_ids)]
        if hits:
            relevant_chunks += 1
            covered.update(hits)
            first_rank = first_rank or rank
    return {
        "hit": 1.0 if first_rank else 0.0,
        "hit@1": 1.0 if first_rank == 1 else 0.0,
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        "recall": len(covered) / len(case.relevant),
        "precision": relevant_chunks / len(top) if top else 0.0,
    }


def evaluate_retrieval(db, cases: Optional[List[Case]] = None, retriever: Retriever = default_retriever, k: int = TOP_K) -> Dict:
    """Scores every labelled case; returns {"overall": {...}, "by_category": {...}, "cases": [...]}."""
    cases = [c for c in (cases or load_golden()) if c.relevant]
    rows = []
    for case in cases:
        chunks = retriever(db, case, top_k=k)
        rows.append({
            "id": case.id, "category": case.category, "question": case.question,
            **score_case(case, chunks, k),
            "retrieved": [{"hotel": c["hotel_name"], "score": c["similarity_score"], "text": c["content"][:90]} for c in chunks[:k]],
        })
    metrics = ["hit", "hit@1", "mrr", "recall", "precision"]

    def mean(subset):
        return {m: round(sum(r[m] for r in subset) / len(subset), 3) for m in metrics} | {"n": len(subset)}

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    return {"k": k, "overall": mean(rows), "by_category": {c: mean(v) for c, v in sorted(by_cat.items())}, "cases": rows}


def format_report(report: Dict) -> str:
    lines = [f"Retrieval @ top-{report['k']}  (hit = any relevant chunk retrieved)", ""]
    lines.append(f"{'category':<14}{'n':>3}  {'hit':>5} {'hit@1':>6} {'MRR':>6} {'recall':>7} {'prec':>6}")
    for name, m in [*report["by_category"].items(), ("OVERALL", report["overall"])]:
        lines.append(f"{name:<14}{m['n']:>3}  {m['hit']:>5.2f} {m['hit@1']:>6.2f} {m['mrr']:>6.2f} {m['recall']:>7.2f} {m['precision']:>6.2f}")
    misses = [r for r in report["cases"] if not r["hit"]]
    if misses:
        lines += ["", f"Misses ({len(misses)}):"]
        for r in misses:
            lines.append(f"  - {r['id']}: {r['question']!r}")
            for hit in r["retrieved"][:2]:
                lines.append(f"      got [{hit['hotel']}] {hit['text']!r}")
    return "\n".join(lines)


def save_report(report: Dict, name: str = "retrieval") -> str:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return path


if __name__ == "__main__":
    from app.core.database import session_maker
    from evals.seed import seed_database
    from sqlalchemy import text

    with session_maker() as session:
        count = session.execute(text("SELECT count(*) FROM hotels")).scalar() if session.bind.dialect.has_table(session.connection(), "hotels") else 0
        if not count:
            seed_database(session)
        result = evaluate_retrieval(session)
    print(format_report(result))
    print("\nsaved:", save_report(result))
