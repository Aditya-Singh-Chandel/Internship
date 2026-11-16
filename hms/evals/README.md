# AI evaluation for the GrandStay concierge

> **Full guide to this folder:** [`../docs/AI-EVALUATION-GUIDE.md`](../docs/AI-EVALUATION-GUIDE.md) (how it works, how it was built, setup, running, results, extending, status checklist).
> The wider project guide (story, every file, every change, recipes, glossary) is in [`../docs/README.md`](../docs/README.md). This page is the short operating guide.

This folder measures how good the chatbot is, so every change to it can be judged by numbers instead of by feel.

## The idea in one minute

The chatbot (`app/services/chat_service.py`) works in four steps:

1. **Retrieve**: search the hotel knowledge base for text relevant to the question.
2. **Ground**: put the hotel catalog, the guest's bookings and the retrieved text into a prompt.
3. **Generate**: Gemini writes the answer from that prompt.
4. **Cite**: attach sources.

Things can go wrong at each step, and they are different problems, so they are measured separately:

| Question | Tool | Needs an LLM judge? |
|---|---|---|
| Is the code that does arithmetic and access control right? | `tests/` | no |
| Did search find the right text? | `retrieval_metrics.py` | no |
| Does the answer contain the right facts and avoid forbidden ones? | `runner.py` exact checks | no |
| Is the answer correct, grounded, concise, well-behaved in nuance? | `quality.py` (DeepEval) | yes (a free model) |
| Can an attacker make it leak or misbehave? | `redteam.py` | no |
| What happened inside one conversation? | Phoenix tracing | no |

Everything that can be checked exactly is checked exactly. The judge model is used only for what exact checks cannot decide.

## Setup facts that matter

* **Separate database.** Tests and evals use `hms_test` on the Docker pgvector database (host port 5433), wiped and re-seeded each run. Your development data is never touched. `conftest.py` aborts if the database name does not end in `_test`.
* **Frozen world.** `seed.py` builds 3 fictional hotels with deliberately *different* answers to the same questions (pets, smoking, check-in time, cancellation), users, bookings and a staff-only document containing a canary string. All dates are relative to a frozen clock (2026-11-01 12:00 UTC), so results do not drift.
* **Free quotas drive the design.** Gemini free tier: 15 requests/min. OpenRouter free models: 20/min and **50 per day** until credits are bought. Everything is paced, cached and resumable for that reason.

## Files

| File | Purpose |
|---|---|
| `seed.py` | The deterministic test world described above |
| `datasets/golden.jsonl` | 72 hand-written questions (11 categories) with expected facts, exact checks and retrieval labels. Generated from `build_golden.py`, but edit the `.jsonl` directly if you like |
| `dataset.py` | Loads the dataset; `check_answer()` is the exact checker (alternatives per fact, forbidden strings) |
| `test_dataset.py` | Checks the dataset itself: every retrieval label must point at text that really exists in the seeded knowledge base |
| `retrieval_metrics.py` | hit@k, first-hit rate, MRR, recall, precision, per category. Pluggable retriever |
| `retrieval_variants.py` | Compares search strategies on the same labelled cases (`--tuning` for depth and re-ranking) |
| `runner.py` | Sends the dataset through the real chatbot (paced, one retry), records answer, prompt, retrieved chunks, tokens, latency. `--repeat N` exposes flakiness |
| `judge.py` | The grading model client: free models only, rate limiter, disk cache, call budget, daily-quota stop, JSON retry |
| `quality.py` | DeepEval metrics scored by the judge |
| `judge_calibration.py` | 10 answers with known verdicts: is this judge trustworthy? |
| `judge_check.py` | You label ~30 answers; measures how often the judge agrees with you |
| `redteam.py` | 43 attacks (incl. 6 against the structured-RAG tools) with exact leak detectors |
| `test_*.py` | Pytest gates for all of the above (LLM-calling ones need `--run-llm`) |
| `baselines/` | Saved scores the gates compare against, plus `EXPERIMENTS.md` |
| `results/` | Output of every run (git-ignored), including the judge cache |

## Commands

```
pytest                                   # free: unit tests, dataset checks, retrieval gate, detector checks
pytest --run-llm                         # also real-Gemini checks and the red team (uses quota)

python -m evals.retrieval_metrics        # search quality report
python -m evals.retrieval_variants --tuning
python -m evals.runner --label my-change # real answers + exact checks   (--repeat 3, --category policy, --ids a,b)
python -m evals.quality                  # judge-score the latest run    (--max-calls 40, --deep)
python -m evals.judge_calibration        # is the judge any good?
python -m evals.judge_check export       # then label, then: ... compare
python -m evals.redteam                  # attack the chatbot
```

## The improvement loop

1. `python -m evals.runner --label before` (baseline).
2. Change ONE thing (a prompt line, `top_k`, a chunk size).
3. `python -m evals.retrieval_metrics` (free) and `python -m evals.runner --label after --repeat 3` on the affected cases.
4. Keep it only if the numbers improve without hurting other categories. Write it down in `baselines/EXPERIMENTS.md`.

Model output is random. One passing run proves little; one failing run proves little. Repeat before concluding.

## Known limits (be honest about them)

* **Judge quota.** At 50 requests/day a full judge pass (~180 requests) takes about four days; it resumes from cache, so just re-run the same command daily. Buying $10 of OpenRouter credit lifts the limit to 1000/day (not done: you asked for free only).
* **Judge scope so far.** Only the first 15 cases were judge-scored (every category represented, all passed). `--deep` metrics (Faithfulness, AnswerRelevancy, KnowledgeRetention, RoleAdherence) are wired but have not yet been run against the judge.
* **Judge trust.** Calibrated 10/10 on Correctness, not yet on the Style/Behavior metrics. Run `judge_check` and label 30 answers yourself.
* **Substring checks can be fooled.** `fu-onsen-tattoo` once "passed" because the vague reply contained the word "private". That is what the judge is for.
* **Small dataset.** 72 cases from one author: good for catching regressions, not a statistical proof of quality.
* **No timezone** is stored per hotel, so refund notice is computed against UTC; near a cutoff it can be off by the hotel's UTC offset.
