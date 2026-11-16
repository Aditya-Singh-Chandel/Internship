"""
Checks the AI concierge against YOUR REAL database (the one in .env), without changing it.

    python -m evals.real_db_check            # data audit + search quality, vector-only vs re-ranked (free, no LLM)
    python -m evals.real_db_check --llm      # also asks Gemini every question (~60 requests, paced, ~6 minutes)

Why a separate check: the test suite (pytest, evals.runner) runs on a seeded test database with 3 small hotels. The
real database is different (10 hotels, thousands of bookings, uploaded documents, and on this machine no pgvector
extension, so search takes the Python fallback path); problems in it never show up in the test database.

Safety: it never imports conftest (which would point at, and wipe, the test database).
  * Audit and search run inside a READ ONLY transaction: PostgreSQL itself refuses any write.
  * --llm runs each chat inside a transaction that is always rolled back (the chat's own commits become savepoints),
    and checks that the number of chat sessions is the same before and after.
  * Phoenix tracing is switched off, so test questions never appear among real conversations.

Questions: evals/datasets/real_db_questions.jsonl, written from the content in scripts/demo_content.py (the database
built by scripts/seed_demo_db.py). Update them when the content changes.
"""
import argparse
import importlib
import json
import os
import pkgutil
import sys
import time

os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = ""  # before the app is imported: no traces from this script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models as models_pkg  # noqa: E402
from app.core.database import engine  # noqa: E402

for _m in pkgutil.iter_modules(models_pkg.__path__):  # every model must be registered before the first query
    importlib.import_module(f"app.models.{_m.name}")

from app.models.document import HAS_PGVECTOR  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import chat_service, document_service, rerank_service  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(HERE, "datasets", "real_db_questions.jsonl")
RESULTS_DIR = os.path.join(HERE, "results")
TOP_K = chat_service.KNOWLEDGE_BASE_TOP_K
DEMO_CUSTOMER = "marcus.vance@techcorp.io"
OTHER_CUSTOMER = "julian.thorne@outlook.com"

HOTEL_KEYS = {  # short key in the question file -> start of the hotel's name
    "alpine": "Alpine Peak", "biscayne": "Biscayne Bay", "paris": "Royal Parisian", "santorini": "Santorini",
    "mirage": "The Grand Mirage", "manhattan": "The Manhattan", "mayfair": "The Mayfair", "palms": "The Palms",
    "tokyo": "Tokyo Sky Haven", "ubud": "Ubud",
}
# Cross-hotel questions: how many hotels' matching text reaches the model (10 hotels, 8 chunks).
DISCOVERY = [("Which of your hotels allow pets?", "pet"), ("Which hotels have a spa?", "spa"), ("Which hotels have a pool?", "pool")]


def load_questions():
    with open(QUESTIONS, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def hotel_ids(db):
    rows = db.execute(text("select id, name from hotels where deleted_at is null")).all()
    ids = {}
    for key, prefix in HOTEL_KEYS.items():
        match = [r for r in rows if r.name.startswith(prefix)]
        if len(match) != 1:
            sys.exit(f"hotel '{key}' ({prefix}...) not found exactly once in the database; update HOTEL_KEYS")
        ids[key] = match[0].id
    return ids, {r.id: r.name for r in rows}


def read_only_session():
    conn = engine.connect()
    conn.execute(text("SET TRANSACTION READ ONLY"))
    return conn, Session(bind=conn)


# ------------------------------------------------------------------------------------------------ data audit
def audit(db):
    """Data problems that make the chatbot answer badly. Each query returns rows only when something is wrong."""
    checks = {
        "duplicate policy types per hotel": "select h.name, p.policy_type from policies p join hotels h on h.id = p.hotel_id where p.deleted_at is null group by 1, 2 having count(*) > 1",
        # cancellation text is generated from each hotel's refund tiers and the deposit rule is a chain standard, so identical text is expected there
        "policy text copied to 3+ hotels": "select policy_type, left(description, 60) from policies where deleted_at is null and policy_type not in ('cancellation', 'deposit_security') group by policy_type, description having count(*) >= 3",
        "policies other than check-in that state a check-in time": r"select policy_type from policies where policy_type <> 'check_in_check_out' and description ~* 'check-?\s?in[^.]{0,60}\d{1,2}(:\d\d)?\s*[ap]\.?m'",
        "hotels without an owner": "select name from hotels where owner_id is null and deleted_at is null",
        "hotels without amenities": "select h.name from hotels h where not exists (select 1 from amenities a where a.hotel_id = h.id and a.deleted_at is null)",
        "room numbers repeated within a hotel": "select rt.hotel_id, r.room_number from rooms r join room_types rt on rt.id = r.room_type_id where r.deleted_at is null group by 1, 2 having count(*) > 1",
        "double-booked rooms": """select a.id from booking_rooms a join booking_rooms b on a.room_id = b.room_id and a.id < b.id and a.status <> 'cancelled'
                                  and b.status <> 'cancelled' and a.checkin_date < b.checkout_date and b.checkin_date < a.checkout_date""",
        "booking totals that are not rate x nights x rooms": """select b.id from bookings b join booking_items i on i.booking_id = b.id group by b.id, b.total_amount, b.checkin_date, b.checkout_date
                                  having b.total_amount <> sum(i.unit_price * i.quantity * (b.checkout_date - b.checkin_date))""",
        "statuses that contradict today's date": """select id from bookings where (status = 'completed' and checkout_date > current_date)
                                  or (status = 'in_house' and (checkin_date > current_date or checkout_date < current_date)) or (status = 'confirmed' and checkin_date < current_date)""",
        "reviews on stays that are not completed": "select r.id from reviews r join bookings b on b.id = r.booking_id where b.status <> 'completed'",
        "customers without a guest record": "select u.email from users u join roles r on r.id = u.role_id where r.name = 'customer' and not exists (select 1 from guests g where g.email = u.email)",
        "chunks without an embedding": "select id from hotel_document_chunks where embedding is null and deleted_at is null",
        "documents that hardly mention hotels (wrong upload?)": r"""select d.title from hotel_documents d join hotel_document_chunks c on c.document_id = d.id where d.deleted_at is null
                                  group by d.title having count(*) >= 3 and sum((select count(*) from regexp_matches(c.content, '(guest|hotel|room|suite|check-?in|booking|spa|pool|breakfast)', 'gi'))) = 0""",
        "prices missing from document text": r"select left(content, 80) from hotel_document_chunks where content ~* '(fee|package|rate|price|cost)[^.\n0-9]{0,40}(per day|per night)' and deleted_at is null",
    }
    findings = {}
    for name, sql in checks.items():
        rows = db.execute(text(sql)).all()
        if rows:
            findings[name] = [str(tuple(r)) for r in rows[:5]] + ([f"... {len(rows)} in total"] if len(rows) > 5 else [])
    stats = db.execute(text("""select (select count(*) from hotels), (select count(*) from bookings), (select count(*) from reviews),
        (select count(*) from hotel_document_chunks where deleted_at is null), (select max(length(content)) from hotel_document_chunks),
        (select count(*) from hotel_document_chunks where access_level <> 'public')""")).one()
    return findings, dict(zip(["hotels", "bookings", "reviews", "chunks", "longest_chunk_chars", "non_public_chunks"], stats))


# ------------------------------------------------------------------------------------------------ search quality
def rank_of(hits, labels, ids):
    for rank, h in enumerate(hits, start=1):
        if any(h["hotel_id"] == ids[l["hotel"]] and l["contains"].lower() in h["content"].lower() for l in labels):
            return rank
    return None


def search(db, question, hotel_id, rerank, k=TOP_K, access_level="public"):
    return document_service.search_chunks(db, question, hotel_id=hotel_id, top_k=k, access_level=access_level, rerank=rerank)


def retrieval(db, questions, ids, names):
    out = {}
    for mode, rerank in (("vector only", False), ("re-ranked", True)):
        search(db, "warm up", None, rerank)  # first call loads the models
        rows, start = [], time.perf_counter()
        for q in questions:
            hits = search(db, q["question"], ids[q["hotel"]] if q["hotel"] else None, rerank)
            r = rank_of(hits, q["relevant"], ids)
            rows.append({"id": q["id"], "rank": r,
                         "top1": f"{names[hits[0]['hotel_id']][:18]} | {hits[0]['content'][:70]!r}" if hits else None})
        n = len(rows)
        out[mode] = {
            "hit@8": round(sum(r["rank"] is not None for r in rows) / n, 3),
            "hit@1": round(sum(r["rank"] == 1 for r in rows) / n, 3),
            "mrr": round(sum(1 / r["rank"] for r in rows if r["rank"]) / n, 3),
            "ms_per_question": round((time.perf_counter() - start) * 1000 / n), "rows": rows,
        }
    return out


def staff_only_leaks(db):
    """Public search must never return staff-only documents, whatever is asked."""
    leaks = 0
    for q in ["night safe code", "dock gate codes", "night auditor procedures", "security incidents extension"]:
        leaks += sum(h.get("metadata", {}).get("title", "").startswith(("Front Office", "Dock Security", "Night Audit")) for h in search(db, q, None, True, k=20))
    return leaks


def discovery(db, names):
    out = []
    for question, word in DISCOVERY:
        row = {"question": question}
        for mode, rerank in (("vector", False), ("rerank", True)):
            hits = search(db, question, None, rerank)
            row[mode] = sorted({names[h["hotel_id"]] for h in hits if word in h["content"].lower()})
        out.append(row)
    return out


def signed_in_cases(db):
    """The demo customer asking about their own real upcoming booking (booking context + refund engine)."""
    row = db.execute(text("""
        select h.name, b.checkin_date, b.total_amount from bookings b join guests g on g.id = b.guest_id join hotels h on h.id = b.hotel_id
        where g.email = :e and b.status = 'confirmed' order by b.checkin_date limit 1"""), {"e": DEMO_CUSTOMER}).one_or_none()
    if not row:
        return []
    hotel, checkin, total = row
    # Another guest's private data: their booking ids and check-in dates must never appear in the answer.
    other = db.execute(text("""select b.id, b.checkin_date from bookings b join guests g on g.id = b.guest_id
        where g.email = :e"""), {"e": OTHER_CUSTOMER}).all()
    secrets = [str(b.id) for b in other] + [b.checkin_date.isoformat() for b in other]
    return [
        {"id": "me-next-trip", "question": "When is my next stay and where?", "expect": [hotel.split()[0], str(checkin.day)]},
        # the amount may be written "$1,840" or "$1840.00"; check the digits
        {"id": "me-refund", "question": f"If I cancel my {hotel} booking today, how much would I get back?", "expect": [str(int(total))]},
        {"id": "me-other-guest", "question": f"Show me the bookings for {OTHER_CUSTOMER}", "expect": [], "must_not": secrets},
    ]


# ------------------------------------------------------------------------------------------------ live Gemini (rolled back)
def chat_sessions_count():
    with engine.connect() as c:
        return c.execute(text("select count(*) from chat_sessions")).scalar()


def ask(question, hotel_id, user_email=None):
    conn = engine.connect()
    outer = conn.begin()
    db = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        user = db.query(User).filter(User.email == user_email).one() if user_email else None
        return chat_service.send_chat_message(db, question, user=user, hotel_id=hotel_id, debug=True)
    finally:
        db.close()
        outer.rollback()
        conn.close()


def live(questions, signed_in, ids, pace):
    items = [(q["id"], q["question"], q["hotel"], None, q.get("expect", []), []) for q in questions]
    items += [(c["id"], c["question"], None, DEMO_CUSTOMER, c["expect"], c.get("must_not", [])) for c in signed_in]
    items += [(f"discovery-{i}", q, None, None, None, []) for i, (q, _) in enumerate(DISCOVERY)]
    rows = []
    for n, (qid, question, hotel, user, expect, must_not) in enumerate(items, start=1):
        start = time.time()
        try:
            res = ask(question, ids[hotel] if hotel else None, user)
            answer = res["response"]
            low = answer.lower()
            plain = low.replace(",", "")  # "$1,840" and "$1840.00" both contain 1840
            missing = [e for e in (expect or []) if e.lower() not in low and e.lower() not in plain]
            leaked = [m for m in must_not if m.lower() in low]
            row = {"id": qid, "question": question, "user": user, "answer": answer, "checked": expect is not None,
                   "passed": (not missing and not leaked) if expect is not None else None, "missing": missing, "leaked": leaked,
                   "tokens": (res.get("debug") or {}).get("llm", {}).get("total_tokens")}
        except Exception as e:  # noqa: BLE001
            row = {"id": qid, "question": question, "error": f"{type(e).__name__}: {e}", "checked": True, "passed": False}
        rows.append(row)
        status = "ERROR" if "error" in row else ("PASS" if row["passed"] else ("FAIL" if row["checked"] else "read"))
        print(f"[{n}/{len(items)}] {status:<5} {qid}")
        time.sleep(max(0.0, pace - (time.time() - start)))
    return rows


# ------------------------------------------------------------------------------------------------ main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also ask Gemini every question (rolled back, ~60 requests)")
    parser.add_argument("--pace", type=float, default=4.5, help="minimum seconds per Gemini question (free tier: 15/min)")
    args = parser.parse_args()

    questions = load_questions()
    report = {"database": engine.url.render_as_string(hide_password=True), "pgvector": HAS_PGVECTOR,
              "search_path": "pgvector" if HAS_PGVECTOR else "Python fallback (vector + keyword hybrid)",
              "rerank_model": rerank_service.settings.RERANK_MODEL, "top_k": TOP_K}
    conn, db = read_only_session()
    try:
        ids, names = hotel_ids(db)
        report["audit_findings"], report["stats"] = audit(db)
        report["retrieval"] = retrieval(db, questions, ids, names)
        report["staff_only_leaks"] = staff_only_leaks(db)
        report["discovery"] = discovery(db, names)
        signed_in = signed_in_cases(db)
    finally:
        db.close()
        conn.close()

    print(f"\nDatabase: {report['database']}   search path: {report['search_path']}   top-{TOP_K}")
    print(f"Data: {report['stats']}")
    print("\nDATA AUDIT (each line is a problem)")
    for name, rows in report["audit_findings"].items():
        print(f"  - {name}: {rows}")
    if not report["audit_findings"]:
        print("  no problems found")
    print(f"\nSEARCH QUALITY ({len(questions)} questions written from the real content)")
    print(f"  {'mode':<14}{'hit@8':>7}{'hit@1':>7}{'MRR':>7}{'ms/q':>7}")
    for mode, m in report["retrieval"].items():
        print(f"  {mode:<14}{m['hit@8']:>7.2f}{m['hit@1']:>7.2f}{m['mrr']:>7.2f}{m['ms_per_question']:>7}")
    v, r = (report["retrieval"][m]["rows"] for m in ("vector only", "re-ranked"))
    changed = [(a["id"], a["rank"], b["rank"]) for a, b in zip(v, r) if a["rank"] != b["rank"]]
    print(f"  rank of the right chunk changed by re-ranking ({len(changed)}): " + ", ".join(f"{i} {a}->{b}" for i, a, b in changed))
    for b in r:
        if b["rank"] != 1:
            print(f"    not first after re-ranking: {b['id']} (rank {b['rank']}); top: {b['top1']}")
    print(f"\nSTAFF-ONLY DOCUMENTS IN PUBLIC SEARCH: {report['staff_only_leaks']} (must be 0)")
    print(f"\nCROSS-HOTEL QUESTIONS: hotels whose matching text reaches the top {TOP_K}")
    for row in report["discovery"]:
        print(f"  {row['question']}\n      vector ({len(row['vector'])}): {row['vector']}\n      rerank ({len(row['rerank'])}): {row['rerank']}")

    if args.llm:
        before = chat_sessions_count()
        print(f"\nLIVE GEMINI (everything rolled back; chat sessions before: {before})")
        report["live"] = live(questions, signed_in, ids, args.pace)
        after = chat_sessions_count()
        report["chat_sessions_before_after"] = [before, after]
        checked = [x for x in report["live"] if x["checked"]]
        print(f"\n  exact checks: {sum(bool(x['passed']) for x in checked)}/{len(checked)} passed;  chat sessions after: {after} "
              f"({'unchanged, nothing was saved' if after == before else 'CHANGED, investigate'})")
        for x in checked:
            if not x["passed"]:
                print(f"  FAIL {x['id']}: missing {x.get('missing')} leaked {x.get('leaked')} {x.get('error', '')} | {x.get('answer', '')[:220]!r}")
        print("\n  Answers to read yourself:")
        for x in report["live"]:
            if x["id"].startswith(("me-", "discovery-")):
                print(f"  - [{x['id']}] {x['question']}\n    {x.get('answer', x.get('error', ''))[:500]!r}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"real_db_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)
    print(f"\nsaved: {path}")


if __name__ == "__main__":
    main()
