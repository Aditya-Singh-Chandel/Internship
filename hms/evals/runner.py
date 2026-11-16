"""
Runs golden-dataset cases through the real chatbot (real Gemini calls) and records answer, retrieved context,
prompt, latency and token usage for each, plus the deterministic pass/fail checks.

    python -m evals.runner                     # all cases
    python -m evals.runner --category policy   # one category
    python -m evals.runner --ids pol-pets-mayfair,fu-pets-fee
    python -m evals.runner --label after-rewrite   # tag the result file, e.g. for before/after comparisons

Needs GEMINI_API_KEY (from .env). Results go to evals/results/generation_<label>_<timestamp>.json.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conftest  # noqa: E402,F401  (points the app at the test database before importing it)

from app.core.database import session_maker  # noqa: E402
from app.models.chat import ChatMessage, ChatSession  # noqa: E402
from app.models.user import User  # noqa: E402
from app.core import tracing  # noqa: E402
from app.services import chat_service  # noqa: E402
from evals.dataset import Case, check_answer, check_tools, load_golden  # noqa: E402
from evals.seed import FROZEN_NOW  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def run_case(db, case: Case, label: str = "run") -> Dict:
    """Plays one case: pre-loads earlier turns into a fresh chat session, sends the question, collects debug info."""
    user = db.query(User).filter(User.email == case.user_email).first() if case.user_email else None
    session = ChatSession(user_id=user.id if user else None, hotel_id=case.hotel_id, title=case.id)
    db.add(session)
    db.flush()
    start = FROZEN_NOW - timedelta(minutes=len(case.history) + 1)
    for i, turn in enumerate(case.history):
        db.add(ChatMessage(session_id=session.id, role=turn["role"], content=turn["content"], created_at=start + timedelta(minutes=i)))
    db.commit()

    began = time.perf_counter()
    try:
        # the facts below become searchable "metadata" on the trace in Phoenix (project hms-evals)
        with tracing.attributes(case_id=case.id, category=case.category, run=label, expected_behavior=case.behavior):
            result = chat_service.send_chat_message(
                db, case.question, user=user, session_id=session.id, hotel_id=case.hotel_id, debug=True, now=FROZEN_NOW
            )
    except Exception as exc:  # a failed call is a result, not a crash
        db.rollback()
        return {"id": case.id, "category": case.category, "error": f"{type(exc).__name__}: {getattr(exc, 'detail', exc)}",
                "passed": False, "failures": ["request failed"], "wall_s": round(time.perf_counter() - began, 2)}

    answer = result["response"]
    dbg = result["debug"]
    calls = dbg.get("tool_calls", [])
    failures = check_answer(case, answer) + check_tools(case, calls)
    return {
        "id": case.id, "category": case.category, "behavior": case.behavior, "question": case.question,
        "answer": answer, "passed": not failures, "failures": failures,
        "retrieved": [{"hotel": c["hotel_name"], "score": c["similarity_score"], "text": c["content"]} for c in dbg["retrieved_chunks"]],
        "llm": dbg["llm"], "wall_s": round(time.perf_counter() - began, 2),
        "system_instruction": dbg["system_instruction"],
        # structured RAG: which lookups the model made, and the exact rows it was shown (the judge needs them as context)
        "tool_calls": [{k: c[k] for k in ("name", "args", "ok", "rows", "error", "ms")} for c in calls],
        "tool_results": [c["result"] for c in calls],
        "trace": dbg.get("trace"),   # {"trace_id", "span_id"} when Phoenix tracing is on
    }


def summarize(rows: List[Dict]) -> Dict:
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    tokens = [r["llm"]["total_tokens"] for r in rows if r.get("llm", {}).get("total_tokens")]
    latency = sorted(r["llm"]["total_latency_s"] for r in rows if r.get("llm", {}).get("total_latency_s"))
    return {
        "n": len(rows), "passed": sum(r["passed"] for r in rows), "errors": sum(1 for r in rows if "error" in r),
        "pass_rate": round(sum(r["passed"] for r in rows) / len(rows), 3) if rows else 0,
        "by_category": {c: {"n": len(v), "pass_rate": round(sum(r["passed"] for r in v) / len(v), 3)} for c, v in sorted(by_cat.items())},
        "avg_tokens": round(sum(tokens) / len(tokens)) if tokens else None,
        # structured RAG cost: how many questions used lookups, and the extra Gemini requests that caused
        "questions_with_lookups": sum(1 for r in rows if r.get("tool_calls")),
        "lookup_calls": sum(len(r.get("tool_calls", [])) for r in rows),
        "avg_gemini_requests": round(sum(r.get("llm", {}).get("requests", 1) for r in rows) / len(rows), 2) if rows else None,
        "latency_p50_s": latency[len(latency) // 2] if latency else None,
        "latency_p95_s": latency[min(len(latency) - 1, int(len(latency) * 0.95))] if latency else None,
    }


def format_summary(summary: Dict, rows: List[Dict]) -> str:
    lines = [f"Deterministic checks: {summary['passed']}/{summary['n']} passed ({summary['pass_rate']:.0%}), {summary['errors']} errors",
             f"avg tokens/question: {summary['avg_tokens']}   latency p50: {summary['latency_p50_s']}s   p95: {summary['latency_p95_s']}s",
             f"structured lookups: {summary['lookup_calls']} calls in {summary['questions_with_lookups']} questions   "
             f"avg Gemini requests/question: {summary['avg_gemini_requests']}", ""]
    for cat, m in summary["by_category"].items():
        lines.append(f"  {cat:<14}{m['pass_rate']:>6.0%}   (n={m['n']})")
    failed = [r for r in rows if not r["passed"]]
    if failed:
        lines += ["", f"Failures ({len(failed)}):"]
        for r in failed:
            lines.append(f"  - {r['id']}: {'; '.join(r['failures'])}")
            if r.get("answer"):
                lines.append(f"      answer: {r['answer'][:220]!r}")
            if r.get("error"):
                lines.append(f"      error: {r['error'][:200]}")
    return "\n".join(lines)


PACE_SECONDS = 4.5  # keeps us under Gemini's free tier limit of 15 requests per minute


def run_all(cases: Optional[List[Case]] = None, label: str = "baseline", pace: float = PACE_SECONDS) -> Dict:
    cases = cases or load_golden()
    rows = []
    with session_maker() as db:
        for i, case in enumerate(cases, start=1):
            began = time.perf_counter()
            row = run_case(db, case, label)
            if "error" in row:  # a transient provider error is not a quality result: wait out the window and retry once
                print(f"      retrying {case.id} after: {row['error'][:80]}", flush=True)
                time.sleep(30)
                row = run_case(db, case, label)
            rows.append(row)
            # pace by Gemini REQUESTS, not cases: a question that uses lookups makes 2+ requests (free tier: 15 per minute)
            requests_used = row.get("llm", {}).get("requests", 1)
            time.sleep(max(0.0, max(pace, requests_used * pace) - (time.perf_counter() - began)))
            print(f"[{i:>2}/{len(cases)}] {'PASS' if row['passed'] else 'FAIL'} {case.id}", flush=True)
    report = {"label": label, "summary": summarize(rows), "cases": rows}
    report["annotated_in_phoenix"] = annotate_in_phoenix(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"generation_{label}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    report["path"] = path
    return report


def annotate_in_phoenix(rows: List[Dict]) -> int:
    """Puts each case's exact-check verdict next to its trace in Phoenix (a no-op when tracing is off)."""
    if not tracing.enabled():
        return 0
    tracing.flush()
    done = 0
    for row in rows:
        span_id = (row.get("trace") or {}).get("span_id")
        if tracing.annotate_span(span_id, "exact_checks", label="pass" if row["passed"] else "fail", score=1.0 if row["passed"] else 0.0,
                                 explanation="; ".join(row["failures"]) or "all exact checks passed",
                                 metadata={"case_id": row["id"], "category": row["category"]}):
            done += 1
    print(f"labelled {done} traces in Phoenix project {tracing.project_name()!r}")
    return done


def _prepare_database() -> None:
    """Fresh schema + seed so every run starts from identical data."""
    from sqlalchemy import text
    from app.core.database import db_class, engine
    from evals.seed import seed_database

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db_class.metadata.create_all(bind=engine)
    with session_maker() as db:
        seed_database(db)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category")
    parser.add_argument("--ids")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS, help="minimum seconds per case (rate limiting)")
    parser.add_argument("--repeat", type=int, default=1, help="run every selected case this many times to expose run-to-run flakiness")
    args = parser.parse_args()

    cases = load_golden()
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [c for c in cases if c.id in wanted]
    if not cases:
        sys.exit("no cases selected")

    _prepare_database()
    report = run_all(cases * max(1, args.repeat), args.label, args.pace)
    print("\n" + format_summary(report["summary"], report["cases"]))
    if args.repeat > 1:
        tally = {}
        for r in report["cases"]:
            ok, total = tally.get(r["id"], (0, 0))
            tally[r["id"]] = (ok + r["passed"], total + 1)
        print("\nReliability across repeats (passes / runs):")
        for cid, (ok, total) in sorted(tally.items(), key=lambda kv: kv[1][0] / kv[1][1]):
            if ok < total:
                print(f"  {cid:<28}{ok}/{total}  <- {'flaky' if ok else 'always fails'}")
        print(f"  {sum(1 for ok, t in tally.values() if ok == t)} of {len(tally)} cases passed every time")
    print("\nsaved:", report["path"])


if __name__ == "__main__":
    main()
