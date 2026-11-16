# Project guide: start here

This folder explains everything that was done to the GrandStay HMS project in the review, cleanup and AI-evaluation
work: **what** changed, **why**, **how we approached it**, and **how to do any of it yourself**. It is written to be
read later, by someone who was not in the conversation.

> **Just want the AI evaluation system?** Read [`AI-EVALUATION-GUIDE.md`](AI-EVALUATION-GUIDE.md): one self-contained
> guide covering how it works, how it was built, how to set it up and run it, and the checklist to finish it.

## Reading order

| Read | When | What you get |
|---|---|---|
| [`AI-EVALUATION-GUIDE.md`](AI-EVALUATION-GUIDE.md) | to understand and run the AI evaluation end to end | Everything about `evals/` in one place, with current status (2026-11-13) |
| [`01-the-story.md`](01-the-story.md) | first, once | The whole journey from scratch, in order: the review, the cleanup, the evaluation plan, every phase, every surprise and decision |
| [`02-every-file.md`](02-every-file.md) | when you wonder "what is this file?" | Every file we added, changed or deleted: purpose, key contents, how it connects to others |
| [`03-every-change.md`](03-every-change.md) | when you wonder "why does the code do this?" | A numbered log of each change: the problem, the fix, where it lives, and the test that proves it |
| [`04-how-to.md`](04-how-to.md) | whenever you want to *do* something | Commands and step-by-step recipes (run tests, add a test question, change the prompt and measure it, use Phoenix, fix common errors) |
| [`06-structured-rag.md`](06-structured-rag.md) | to understand the structured-RAG feature | What structured RAG is, whether the code did it before, how the 4 database tools work, the safety rules, what was verified and what could not be |
| [`07-reranking.md`](07-reranking.md) | to understand how search finds the right text | Beginner-friendly deep dive: embeddings, why they misrank, cross-encoder re-ranking, why the embedding model can't do it twice, the code, the measurements |
| [`08-real-database.md`](08-real-database.md) | before using or testing the real database | What was wrong in it, how `scripts/seed_demo_db.py` rebuilds it consistently, the logins, and how `evals/real_db_check.py` tests the chatbot on it without changing it |
| [`05-concepts.md`](05-concepts.md) | when a word is unfamiliar | Plain-language glossary: RAG, embeddings, hit@k, MRR, faithfulness, judge, rate limit, trace... |

Also relevant, inside the evaluation folder: [`../evals/README.md`](../evals/README.md) (short operating guide) and
[`../evals/baselines/EXPERIMENTS.md`](../evals/baselines/EXPERIMENTS.md) (the measured before/after of each improvement).

## The 60-second version

* **The project** is a hotel booking system: FastAPI + PostgreSQL (with the pgvector extension) + a React website, plus an
  **AI concierge** chatbot (Google Gemini) that answers guests using hotel data and uploaded documents (this pattern is
  called RAG, see the glossary).
* **Step 1, review.** We read the code and found security holes (open endpoints, a hard-coded secret, a data leak between
  chat users), bugs, and clutter.
* **Step 2, cleanup.** We fixed the important problems and deleted what was not needed (debug scripts, an unused
  text-to-SQL service, template files). About 6,400 lines removed.
* **Step 3, evaluation.** Because "does the chatbot work well?" cannot be answered by looking at a few chats, we built a
  measuring system: automated tests, 89 test questions with known answers, search-quality metrics, an LLM judge,
  43 attack tests, and a trace viewer (Phoenix). We then used the numbers to **find and fix real weaknesses** (follow-up
  questions, refund maths, a missed document chunk).
* **Result.** Exact checks went from 62-63/65 to 72/72; follow-up search from 55% to 100%; 37/37 attacks held;
  343 automated tests pass. Later we added **structured RAG** (the chatbot answers availability, ranking, counting and averaging
  questions from live database queries instead of pasted text): see `06-structured-rag.md`.
* **Re-ranking.** Search now runs in two stages: the embedding model finds 30 candidates, a local cross-encoder re-orders
  them and the best 8 go to Gemini. The right text is ranked first for 89% of labelled questions (was 80%; follow-ups
  55% → 82%). See `07-reranking.md`.
* **Real database.** The development database was full of contradictions and test junk; it is now rebuilt by
  `scripts/seed_demo_db.py` as a consistent working hotel business (10 hotels, ~2,400 bookings, staff, guests, documents)
  and tested read-only by `evals/real_db_check.py`. An autopilot (`scripts/demo_autopilot.py`, `DEMO_AUTOPILOT=true`) does the
  daily check-ins, check-outs and new bookings, so the data never goes stale. See `08-real-database.md`.

## Where things are (map of the project folder `hms/`)

```
hms/
├── app/                     the backend (FastAPI)            -> see 02-every-file.md "Backend"
│   ├── api/routes/          HTTP endpoints
│   ├── core/                settings, database, security, tracing
│   ├── models/ schemas/     database tables / request-response shapes
│   ├── services/            business logic, incl. the AI concierge (chat_service.py)
│   └── utils/
├── frontend/                the React website
├── tests/                   ordinary automated tests (no AI calls)
├── evals/                   the AI evaluation system
│   ├── datasets/golden.jsonl    the 89 test questions
│   ├── baselines/               saved scores the tests compare against
│   └── results/                 output of each run (git-ignored)
├── docs/                    this guide
├── conftest.py              shared test setup (test database!)
├── Dockerfile, docker-compose.yml, .env, .env.example, requirements*.txt, pytest.ini, README.md
```

## Legend used in the other documents

* **NEW**: created during this work. **CHANGED**: existed, we modified it. **DELETED**: removed (still recoverable from git).
* **Proven by:** names the automated test that checks the behaviour, so you can run it yourself.

## What is verified and what is not (honest list)

Verified by running it:
* All 360 automated tests (9 more are opt-in because they spend limited AI quota).
* Re-ranking: measured on the 46 labelled search questions (hit@1 0.80 → 0.89, MRR 0.87 → 0.94), 4 models compared.
  On live Gemini, the 46 knowledge-base questions pass 46/46 with re-ranking and whole chunks (one run; the full 89 and
  `--repeat 3` not yet run).
* Full 89-question regression with everything above (re-ranking, whole chunks, scope fix): 86/89, all categories 100%
  except structured 14/17 (the known tool-routing misses). Real database, 55 live questions: 55/55, nothing saved.
* Fixed: Gemini saw only the first 350 characters of each chunk (lost 20-67% of real document/review text). Tested and
  rejected: 4 chunks instead of 8 (unsafe for cross-hotel questions with 10 hotels). See `03-every-change.md` A6, A7.
* The real chatbot against the original 72 questions (72/72 exact checks, *before* structured RAG was added), repeated 3x on the
  hardest 15 (45/45).
* 37 attack tests against the real chatbot (before structured RAG was added).
* Structured RAG on live Gemini: 17 structured questions, 14/17 exact checks (see `06-structured-rag.md`).
* Phoenix: traces, sessions, labels beside traces, restart persistence, behaviour when it is stopped.
* The free LLM judge: 10/10 on a calibration set; 15 real cases scored, all passed.

**Not verified after structured RAG was added (the Gemini free daily quota ran out):** the full 89-question regression with the
tools attached, the 6 new tool-abuse attacks on live Gemini, and a tightened prompt that was written but reverted unmeasured.
Commands to finish are in `04-how-to.md` recipe R15.

Not (fully) verified, so treat with care:
* **The judge has scored only 15 of 72 cases** (the free OpenRouter quota is 50 requests/day). The rest completes over
  a few days; see `04-how-to.md`.
* DeepEval's multi-request metrics (`--deep`: Faithfulness, AnswerRelevancy, KnowledgeRetention, RoleAdherence) are
  written but have never been run against the judge.
* The judge was calibrated on the *Correctness* metric only. Ask it to be checked against your own judgement with
  `python -m evals.judge_check`.
* The Phoenix web pages were checked through its API, not by looking at the screen.
* Docker: the image **builds** (429 MB) and was inspected (runs as a non-root user, contains the built React app, all
  dependencies import, no tests/secrets inside), but a full `docker compose up` run of the new setup was not done, to avoid
  replacing your running container. Do it yourself with `docker compose up --build` (see `04-how-to.md`).
* Nothing is committed to git: you review and commit.
