# 01. The story: from scratch to now

This is the whole journey in the order it happened, with the reasoning at each step. Skim the headings first; read the
parts you care about.

---

## 0. Where we started

The project is a hotel management and booking system:

* **Backend:** FastAPI (Python) with PostgreSQL. Users have roles (admin, owner, manager, receptionist, customer).
* **Frontend:** a React website (Vite) with a guest side and an operations portal for staff.
* **AI concierge:** a chatbot on the website. A guest types a question; the backend looks up relevant hotel information
  and asks Google Gemini to write an answer. Hotel staff can upload documents (PDF, Word, Excel, text) that the
  chatbot then "knows".

When we began, most of the AI work was freshly written and **uncommitted** (about 45 changed or new files). The git
history had earlier commits for auth, Docker and cleanup. Shortly after we started, you committed it as
"ai chatbot" (commit `85e5245`), which is the reference point for everything we changed afterwards: you can always see
our changes with `git diff 85e5245`.

---

## 1. The review: "find errors and things to improve"

**Approach.** Before changing anything, read the code that matters most (settings, authentication, the chat and
document endpoints, the AI services, Docker files, `.env`) and look for: security problems, bugs, things that are
unused, and missing basics.

**What we found** (most urgent first):

1. **A real API key sat in `.env`** (correctly git-ignored, but worth rotating if it ever leaked) and the **JWT secret**
   (the key that signs login tokens) was *hard-coded in the code and in `docker-compose.yml`*, so anyone who read the
   public repository could forge an admin login.
2. **`POST /chat/llm-config` had no login check.** Anyone could replace the Gemini API key and model and it even rewrote
   `.env` on disk. `GET /chat/llm-status` leaked part of the key.
3. **Documents were not scoped to a hotel.** A receptionist from hotel A could delete hotel B's documents; the document
   list was public (and showed staff-only documents).
4. **Anyone could register as a hotel owner** by sending `role_name: "owner"`.
5. **The AI wrote SQL and ran it** (a text-to-SQL service), guarded only by regular expressions: an unsafe design.
6. **Error responses leaked internals** (`str(exception)` returned to the browser).
7. **Chat privacy hole** (found while reading deeper): if you knew a signed-in user's chat `session_id`, you could send
   it anonymously and the chatbot would answer *as that user*, including their bookings.
8. **Clutter:** 13 debug scripts containing passwords, an old 4,300-line HTML admin page, Vite template images.
9. **Basics missing:** no tests, `httpx` (needed by the chatbot) not in `requirements.txt`, loose dependency versions,
   Docker image running as root, no health endpoint.

You then asked us to fix what is "really important and required" and delete what is not.

---

## 2. The cleanup ("sanitize the codebase")

**Approach.**

* *Safety first.* Before deleting anything we confirmed everything was in git (you had committed), so any deletion is
  recoverable (`git checkout 85e5245 -- <path>`).
* *Fix what is dangerous; delete what is dead; leave working code alone.* We did not rewrite features.
* *Verify with real checks:* compile everything, import the app, call endpoints against your database, build the frontend.

**What was done** (full detail with before/after in `03-every-change.md`):

* Secrets: new random JWT secret written to `.env`; the app now **refuses to start** without `JWT_SECRET_KEY` and
  `DATABASE_URL` (no more built-in fallbacks).
* Closed the open endpoints (deleted the key-changing ones), scoped every document operation to the caller's hotel,
  capped uploads at 10 MB, restricted public sign-up to the customer role, made the first-admin password mandatory.
* Fixed the chat privacy hole (a session owned by someone else is never reused; history is owner-only).
* 500 errors now log details on the server and tell the browser nothing.
* Moved cookie security and allowed origins into settings; added a `/health` endpoint.
* Deleted the debug scripts, the legacy HTML page, the unused text-to-SQL service and template leftovers.
* Docker: multi-stage image that builds the React app, runs as a normal user, pinned dependencies, `.env` passed into
  the container, database port limited to your own machine.
* Wrote a real `README.md`.

**Result:** 42 files changed, ~6,400 lines deleted, the 73-endpoint app still imports, the frontend still builds, and
live checks showed the holes were closed (e.g. a receptionist deleting another hotel's document got `403`).

---

## 3. Choosing how to evaluate an AI chatbot

You had studied four tools (Ragas, TruLens, Arize Phoenix, DeepEval) and asked for a plan covering *everything*
available, "irrespective of me knowing or not knowing them".

**First, understand the system being tested.** We traced `send_chat_message` and found four steps:

1. *Retrieve*: embed the question (turn it into numbers) and find the most similar document chunks.
2. *Ground*: put the hotel catalog, the guest's bookings and the retrieved text into one big prompt.
3. *Generate*: Gemini writes the answer.
4. *Cite*: attach sources.

Each step can fail in its own way (search misses the right text; the prompt is wrong; the model invents a price; the
model leaks a secret), so **each is measured separately**. That idea shaped everything.

**The tool decision** (compared against all the options we knew):

| Tool | Decision | Why |
|---|---|---|
| **DeepEval** | **Use** | Works with plain Python (no LangChain needed), runs inside pytest, has the metrics we need and custom "G-Eval" rules written in plain English |
| **Arize Phoenix** | **Use** | Shows every conversation as a trace; one Docker container; free; open source |
| **Plain Python + pytest** | **Use, the foundation** | Anything that can be checked *exactly* should be (refund arithmetic, who can access what, search hit rate): cheaper, faster, no randomness |
| Ragas | Skip | Overlaps DeepEval; would give a second, conflicting set of scores |
| TruLens | Skip | Overlaps both with less benefit |
| Langfuse / LangSmith / Braintrust | Skip | Heavier (Langfuse needs several services) or paid / hosted |
| DeepTeam / promptfoo (red teaming) | Replaced | We wrote a free static attack suite with exact detectors instead, because the judge's free quota is tiny |

**The golden rule we followed:** *use exact checks wherever possible; use an LLM judge only for what exact checks
cannot decide.* An LLM judge is slower, costs quota, is itself random, and can be too lenient.

**The plan** had eight phases (0-7): make the system testable; plain tests; a golden question set; search metrics;
answer-quality metrics; tracing; attack testing; an improvement loop.

---

## 4. Building it, phase by phase (with the surprises)

### Phase 0: make the chatbot observable and testable

* `send_chat_message(..., debug=True)` now also returns **what the model saw**: the full prompt, the retrieved chunks,
  the exact search text, the model name, token counts and latency. The web endpoint never sets it, so users cannot see it.
* `now=` lets a test **freeze the clock**. Refund answers depend on today's date, so without this scores would drift
  daily.
* The Gemini client records model, latency and tokens.

### Phase 1: ordinary tests, and a separate test database

* **Rule: tests never touch your real data.** They use a separate database named `hms_test`, wiped every run;
  `conftest.py` aborts if the database name does not end in `_test`.
* **A deterministic world** (`evals/seed.py`): three fictional hotels (London, Aspen, Tokyo) that deliberately answer the
  same questions *differently* (pets allowed in one, forbidden in the others; different check-in times; different
  cancellation rules), four kinds of staff, two customers with bookings, and a staff-only document containing a
  secret "canary" string. If that canary ever appears in a public answer, access control failed.
* **Surprise 1: two Postgres servers.** Your `.env` pointed to a native Windows Postgres *without* pgvector (so the code
  used a slower Python search path), while Docker had a pgvector database on the same port. They behave differently. We
  asked you; you chose to measure the **Docker pgvector path** (what a deployed app uses), so we moved Docker's host
  port to 5433.
* **Surprise 2: real bugs.** Tests written to describe *correct* refund behaviour failed 9 of 24 times. The refund
  calculator (which tells guests how much money they get back) had three defects: it ate the leading digits of
  `50% refund` lines; it ignored "Full refund" written without a `%`; and it read only one tier per paragraph. One of the
  broken texts is real data in your database ("Peak Season Policy..."). We rewrote the parser; 30 tests now pin it.
* **Surprise 3: my own bug.** A line I added (`time.perf_counter()`) clashed with an existing import
  (`from datetime import time`) and would have crashed every chat reply. A test caught it before anything shipped.
* Result: 62 tests then; **106 ordinary tests** by the end.

### Phase 2: the golden dataset

72 hand-written questions in 11 categories (policy, FAQ, pricing, discovery, personal bookings, refunds, follow-ups,
non-existent things, off-topic, security, opinion). Each has:
the question; who asks (anonymous / Marcus / Sophia) and which hotel the widget is scoped to; earlier conversation turns
if it is a follow-up; **expected facts** in plain English; **must-contain** groups (alternatives, e.g. "3 PM" or
"3:00 PM"); **forbidden** strings (e.g. another hotel's price); and **retrieval labels** (which seeded text *should* be
found). A test (`evals/test_dataset.py`) verifies every label points at text that really exists, so a typo cannot silently
corrupt scores. We added 7 follow-up cases midway because 4 were too few to tell a real fix from luck.

### Phase 3: search metrics (no AI involved)

For each question, did the right chunk come back, and how high? Metrics: *hit* (anywhere in the top k), *hit@1*
(first place), *MRR* (rewards higher ranks), *recall*, *precision*. **First baseline: 95% hit overall, but follow-up
questions only 50-55%**, and the right chunk was first only 9% of the time. This pointed straight at the cause: a
follow-up like "What time does it open?" was searched on its own, so the system did not know *what* opens.

### Phase 4: answer quality with DeepEval

Two layers:
1. **Exact checks** (`runner.py`): run the questions through the *real* chatbot and check required/forbidden text.
   First real run: 63/65.
2. **Judge scoring** (`quality.py`): DeepEval metrics scored by a second LLM ("judge"): Correctness (against the expected
   facts), Behavior (decline / redirect to login / deny non-existent things), GroundedPrices (no invented numbers), Style
   (concise, no unasked policy talk, greets signed-in guests by name). Optional `--deep` adds DeepEval's built-in
   Faithfulness, AnswerRelevancy and conversation metrics.

**The judge saga** (important because it shaped the design):

* You supplied an OpenRouter key and asked for **free models only**.
* The first judge run failed completely with `429 Too Many Requests`. Cause: four parallel workers fired DeepEval's many
  sub-requests in bursts. We also learned your account is on the free tier: **50 free-model requests per day** and
  ~20 per minute. Your chosen `gemma-4-31b` model was additionally rate-limited by Google upstream (and is the same
  vendor as the chatbot, which makes a lenient judge more likely).
* So before any big run we built protections into `evals/judge.py`: a shared rate limiter, an on-disk cache (never pay
  for the same question twice), a call budget, a clean stop when the daily quota is gone (partial results kept, resume
  tomorrow for free), a retry for malformed JSON, and a hard refusal of any non-free model. 17 tests cover these with a
  fake network.
* We cut requests per case from ~10 to ~2.7: fixed evaluation steps (DeepEval otherwise spends an extra request
  inventing them), the four style rules merged into one request, heavier metrics behind `--deep`.
* **Choosing the model by testing, not guessing:** `evals/judge_calibration.py` scores 10 answers with known verdicts.
  Gemma managed 2 verdicts before being rate-limited. **`nvidia/nemotron-3.5-super-vl:free` scored 10/10** (after adding the
  JSON retry) and is from a different vendor than the chatbot. We set that in your `.env`.
* The first judge run scored 15 cases (every category represented): all passed; then OpenRouter's daily limit stopped it
  gracefully. That is the designed behaviour.

**A lesson in why exact checks alone are not enough.** `fu-onsen-tattoo` "passed" in the baseline only because the
chatbot's vague reply happened to contain the word "private" ("private relaxation options"). The real fact (visible
tattoos are welcome in the private family baths) never reached the guest. A judge, not a substring check, catches that.

### Phase 5: Phoenix tracing

Phoenix runs as a Docker service (optional profile, pinned to v21.0.0). Every question becomes **one trace**: a root span
with children "knowledge_retrieval" (what was searched, which chunks, which scores) and "gemini_generate" (the chat
messages, model, tokens). Later we made it fully functional: see section 6.

### Phase 6: attack testing

`evals/redteam.py`: 37 attacks (prompt extraction, jailbreaks/role-play, staff-data theft, other guests' data, SQL and
credential requests, off-topic misuse, fake authority, instructions hidden in questions) with **exact leak detectors**
(the canary, fragments of the system prompt, password hashes, other guests' emails, code blocks, "I have cancelled it"
claims). It needs no judge, so it costs no judge quota. **37/37 held**; we read the replies to make sure that was real
refusal and not blind detectors.

### Phase 7: the improvement loop

The method: baseline, change **one** thing, measure, keep only if better, write it down
(`evals/baselines/EXPERIMENTS.md`). Rules we followed: model output is random, so one run proves little (we added
`--repeat N`); free tools first (search metrics need no AI).

| Change | Evidence | Decision |
|---|---|---|
| Add the previous user message to the search for short / "it, that, and..." follow-ups | follow-up hit 0.55 to 0.91 (offline) | **kept**, no extra AI call |
| LLM rewrite of the query instead | would add a Gemini call to every turn on a 15/min free tier | rejected on cost |
| Keyword re-ranking (as the Python fallback does) | overall hit 0.98 to 0.94 | **rejected, it was worse** |
| Retrieve 8 chunks instead of 4 | hit 0.98 to 1.00 (found the buried tattoo FAQ); +~20% prompt tokens | **kept** |
| Cancellation questions from signed-out visitors: explain the policy first, mention sign-in only for a specific booking (**your request**) | `pol-cancel-shibuya` failed 2 of 3 earlier runs; 3 of 3 passes now | **kept** |
| Read each hotel's real check-in time instead of assuming 14:00 (**your request**) | notice hours were wrong by 1-2 h; hotels check in at 14:00-16:00 | **kept**; "unknown" when no time is published |

**End state:** 72/72 exact checks, 45/45 on the hardest 15 questions repeated 3 times, retrieval 100% in every category.

---

## 5. How we worked (principles you can reuse)

1. **Look before you change.** Read the real code and data; do not guess.
2. **Safety net first.** Everything recoverable from git; tests on a separate database.
3. **Measure, change one thing, measure again.** Never trust a feeling or a single run.
4. **Exact checks before LLM judges.** Judges are for nuance only.
5. **Respect the free quotas.** Pace calls, cache results, make runs resumable, stop cleanly.
6. **Fix root causes, and keep the proof.** Each fix has a test or a measured number.
7. **Be honest about limits.** Every document lists what is not verified.

---

## 6. Phoenix: making it fully functional (the last stage)

Phoenix was already receiving traces, but "fully functional" needed more:

* **Problem found:** our pytest runs were sending fake test conversations into the real `hms` project. **Fix:** eval runs
  go to their own project **`hms-evals`**; plain pytest sends nothing (set `PHOENIX_TRACE_TESTS=1` to include it). We
  deleted the polluted `hms` project (all of it was our test data).
* **Phoenix 21 requires a token by default** (our first export got `401`). For local use we set
  `PHOENIX_ENABLE_AUTH=false`, bound to `127.0.0.1` only; documented the trade-off (traces contain prompts and names).
* **Chat view:** the LLM span now carries the messages as `llm.input_messages.*` / `llm.output_messages.*`, so Phoenix
  shows system prompt, history, question and answer as a conversation.
* **Sessions:** the root span has `session.id` and `user.id` (never the email), so one conversation = one session.
* **Eval results inside Phoenix:** after a run, each trace gets an *annotation*: `exact_checks` pass/fail from the runner,
  `red_team` held/leaked from the attack suite, and `judge_<metric>` scores from the judge. Each trace is also tagged with
  searchable `metadata.case_id`, `metadata.category`, `metadata.run`.
* **Redaction:** `PHOENIX_REDACT_CONTENT=true` keeps timings/tokens/ids but drops every piece of text.
* **Failing safe:** if Phoenix is down the chatbot still answers (we stopped the container and proved it); exporting
  happens in a background thread and errors are only logged.
* **Docker:** a healthcheck on the Phoenix service; the app container gets its own endpoint setting
  (`PHOENIX_DOCKER_ENDPOINT`), because `localhost` inside a container means the container itself.
* 13 new tests cover the span structure, redaction, annotation payloads and retries, and failing safe.

---

## 6b. Re-ranking: putting the right text first

**Why.** The search metrics showed the right chunk was almost always *somewhere* in the 8 sent to Gemini (hit 1.00) but
often not *first* (hit@1 0.80; follow-ups 0.55, pricing 0.33). The cause is structural: the embedding model summarises
each chunk into 384 numbers before any question exists, so it matches *topics*, not *answers*.

**What.** A second model, a **cross-encoder re-ranker** (`Xenova/ms-marco-MiniLM-L-6-v2`, 80 MB, runs on CPU through the
already-installed fastembed). It reads the question and each of the top 30 chunks together, scores how well the chunk
answers the question, and keeps the best 8. Unlike the rejected keyword re-ranking (Phase 7), it learned relevance from data.

**How we chose.** Four re-rankers compared on the same 46 labelled questions. The bigger ones won by one question at 1.2
to 4 times the time, so the smallest was kept.

**Result.** hit@1 0.80 → 0.89, MRR 0.87 → 0.94, follow-ups 0.55 → 0.82, pricing 0.33 → 0.67; 6 questions moved, all up;
~0.2-0.5 s extra CPU per question, no API cost. Falls back to the old order if the model is unavailable. Also found: with
re-ranking every labelled answer is already in the top 3 (see the follow-ups below for what that led to). Full explanation for beginners: `07-reranking.md`.

**Two follow-ups.** (1) Writing the guide revealed that Gemini saw only the first **350 characters** of each chunk. In the app
database that hid 20% of uploaded-document text and 67% of review text, and the test data (all chunks under 350) could not show it.
Fixed: the whole chunk is sent. (2) Sending 4 chunks instead of 8 passed all 46 knowledge-base questions on live Gemini
(-5% tokens) but was **rejected**: with 10 real hotels, a cross-hotel question needs more than 4 chunks, and the 3-hotel
test world cannot catch that.

---

## 7. Where things stand, and what is left

> **Update:** structured RAG was added after this section was first written: see `06-structured-rag.md`. The counts below
> (72 questions, 37 attacks, 249 tests) are the state *before* it; now: 89 questions, 43 attacks, 343 tests.

**Done and measured:** everything above.

**Open items** (also in `README.md` "verified / not verified"):

* Finish judge scoring of the remaining ~57 cases: run `python -m evals.quality` once a day (it resumes from cache).
* Label ~30 answers yourself and run `python -m evals.judge_check compare` to see how often the free judge agrees with you.
* Run `python -m evals.quality --deep` when quota allows, to exercise DeepEval's multi-request metrics.
* Hotels store no timezone, so refund notice is computed in UTC; near a cutoff it can be off by the hotel's UTC offset.
  Fixing it properly needs a timezone column on `hotels`.
* Still recommended from the first review but **not done**: database migrations (Alembic), rate limiting on login and chat,
  hotel-scoping review of the older routes we only skimmed (hotels, bookings, media), and changing the demo account
  passwords that exist in your public git history.
* The Gemini free tier (15 requests/minute) would also limit the live chatbot under real load.
* Re-ranking: re-measure Gemini's answers with it on (`python -m evals.runner --repeat 3`), test the candidate pool with
  real uploaded documents (`07-reranking.md` section 13). The 46 knowledge-base questions pass 46/46 on live Gemini.
* Nothing is committed. Review with `git status` / `git diff HEAD`, then commit.
