# 04. How to do things yourself

All commands are for **Windows PowerShell**, run from the `hms` folder
(`cd C:\Users\adity\Desktop\Internship\hms`). Contents: [0. Setup](#0-one-time-setup-and-daily-basics) ·
[1. Command reference](#1-command-reference) · [2. Recipes](#2-recipes) · [3. Settings](#3-settings-reference) ·
[4. Troubleshooting](#4-troubleshooting)

> **Two rules that prevent most problems**
> 1. **Never run two things that use the test database at the same time** (`pytest`, `evals.runner`, `evals.redteam`,
>    `evals.save_baseline retrieval`). Each resets `hms_test` at the start and would wipe the other's data.
>    (`evals.quality`, `judge_*`, Phoenix and Docker commands do not use it and can run alongside.)
> 2. **Check the cost column** below. Free commands can be run any time; "Gemini" and "Judge" commands spend limited
>    daily/per-minute quota.

---

## 0. One-time setup and daily basics

**Activate the Python environment** (every new terminal), or skip activation and prefix commands with `.\.venv\Scripts\python.exe`:
```powershell
.\.venv\Scripts\Activate.ps1
# if PowerShell refuses to run scripts:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Install everything** (only needed once, or after requirements change). If downloads time out, use the long timeout:
```powershell
pip install -r requirements-dev.txt --default-timeout=300 --retries 10
```

**Start the database** (Docker Desktop must be running):
```powershell
docker compose up -d db            # PostgreSQL + pgvector, reachable on localhost:5433 for tests
```

**Run the app on your machine** (uses the database in `.env`):
```powershell
uvicorn app.main:app --reload      # API on http://127.0.0.1:8000  (docs at /docs, health at /health)
cd frontend; npm install; npm run dev   # website on http://localhost:5173
```

**Run everything in Docker instead** (also builds the website into the image):
```powershell
docker compose up --build          # app on http://localhost:8000/app
docker compose logs -f app         # watch the app's log
docker compose down                # stop (data kept)    |  docker compose down -v  <- DELETES the database data
```

---

## 1. Command reference

Cost key: **Free** = no AI quota. **Gemini** = uses the chatbot's Gemini free tier (15 requests/min; commands are paced).
**Judge** = uses the OpenRouter free judge (50 requests/day).

| Command | What it does | Cost |
|---|---|---|
| `pytest` | All free tests (about 249): ordinary tests, dataset checks, retrieval gate, detector checks | Free |
| `pytest tests` / `pytest evals` | Only one of the two folders | Free |
| `pytest tests\test_cancellation_policy.py -q` | One test file, quiet output | Free |
| `pytest -k "pets and mayfair"` | Only tests whose name contains those words | Free |
| `pytest --run-llm` | Also the tests that call real AI (generation, quality, red team) | Gemini + Judge |
| `python -m evals.retrieval_metrics` | Search quality table per category + list of misses | Free |
| `python -m evals.retrieval_variants` | Compare ways of building the follow-up search query | Free |
| `python -m evals.retrieval_variants --tuning` | Compare retrieval depth (4/6/8) and keyword re-ranking | Free |
| `python -m scripts.seed_demo_db --yes` | **Rebuild** the database in `.env` as the consistent demo business (drops everything there) | Free |
| `python -m scripts.demo_autopilot` | Catch the demo data up to today by hand (the app also does it by itself when `DEMO_AUTOPILOT=true`) | Free |
| `python -m evals.real_db_check` | Audit + search quality on the **real** database, read-only | Free |
| `python -m evals.real_db_check --llm` | Same, plus live Gemini answers (rolled back, nothing saved) | Gemini (~60 requests) |
| `python -m evals.retrieval_variants --rerank` | Compare cross-encoder re-ranking models and candidate-pool sizes | Free (downloads models once) |
| `python -m evals.runner --label before` | Send all 72 questions through the real chatbot, exact checks | Gemini (~8 min) |
| `python -m evals.runner --category followup` | Only one category | Gemini |
| `python -m evals.runner --ids pol-pets-mayfair,fu-spa-hours` | Only chosen cases | Gemini |
| `python -m evals.runner --ids fu-spa-hours --repeat 5` | Repeat each case N times to expose flakiness | Gemini |
| `python -m evals.runner --category structured` | Only the 17 structured-RAG questions (lookups cost 2 requests each) | Gemini |
| `python -m evals.quality` | Judge-score the **newest** generation run (resumes from cache) | Judge |
| `python -m evals.quality --max-calls 40` | Stop after 40 real judge requests | Judge |
| `python -m evals.quality --from evals\results\generation_final_XXXX.json` | Score a specific run | Judge |
| `python -m evals.quality --deep` | Also DeepEval's multi-request metrics (more requests) | Judge |
| `python -m evals.judge_calibration` | Test the judge on 10 answers with known verdicts | Judge (~12 requests) |
| `python -m evals.judge_calibration --model some/model:free` | Test a different free judge | Judge |
| `python -m evals.judge_check export` | Write ~30 answers for you to label | Free |
| `python -m evals.judge_check compare` | Agreement between your labels and the judge | Free |
| `python -m evals.redteam` | 37 attacks with exact leak detectors | Gemini (~4 min) |
| `python -m evals.redteam --category jailbreak` | One attack category | Gemini |
| `python -m evals.save_baseline retrieval` | Re-measure search and store as the new baseline | Free |
| `python -m evals.save_baseline generation --label final` | Store the newest run with that label as baseline | Free |
| `python -m evals.save_baseline quality` | Store the newest judge result as baseline | Free |
| `python -m evals.build_golden` | **Regenerates** `golden.jsonl` from `build_golden.py` (overwrites hand edits!) | Free |

Set an option for one command only (PowerShell):
```powershell
$env:JUDGE_MAX_CALLS = 30; python -m evals.quality; Remove-Item Env:JUDGE_MAX_CALLS
$env:PHOENIX_TRACE_TESTS = 1; pytest --run-llm     # also trace pytest's AI tests into Phoenix
```

---

## 2. Recipes

### R1. "Did my change break anything?" (the 2-minute free check)
```powershell
pytest
```
All tests pass = no regression in refunds, access control, search quality, dataset, detectors, tracing.

### R2. Change the chatbot and measure the effect (the improvement loop)
1. Record where you are: `python -m evals.runner --label before`
2. Make **one** change (a line in the system prompt in `app/services/chat_service.py`, `KNOWLEDGE_BASE_TOP_K`, ...).
3. If the change touches search, check it for free first: `python -m evals.retrieval_metrics`
4. Measure answers: `python -m evals.runner --label after`
5. Compare the two printed summaries (per-category pass rates, average tokens). For borderline cases repeat:
   `python -m evals.runner --ids <case ids> --repeat 3 --label after-repeat` (one run is a sample, not proof).
6. Keep it only if it helps without hurting other categories. If kept:
   `python -m evals.save_baseline generation --label after` (and `retrieval` if search changed), then add a row to
   `evals\baselines\EXPERIMENTS.md`. If not kept, undo with `git checkout -- <file>` (or just revert your edit).

### R3. Add or edit a test question
The dataset is `evals\datasets\golden.jsonl`: one JSON object per line. Fields (see top of `evals\build_golden.py`):
`id` (unique), `category`, `user` (`anonymous`/`marcus`/`sophia`), `hotel` (`mayfair`/`aspen`/`shibuya`/null),
`history` (earlier turns), `question`, `expected_facts` (plain English), `must_contain` (list of lists: each inner list
= acceptable alternatives, all outer groups required), `forbidden` (strings that must not appear),
`relevant` (list of `{"hotel": ..., "contains": ...}` text that search should find), `behavior`
(`answer`/`decline`/`redirect_login`/`deny_nonexistent`).

1. Copy an existing line, change the fields. (If you prefer `build_golden.py`, edit it and run
   `python -m evals.build_golden`, but then **stop editing the .jsonl by hand**, since it gets overwritten.)
2. `pytest evals\test_dataset.py` checks the new case is well-formed and that its `relevant` text really exists in the seed.
3. `python -m evals.runner --ids <your id> --repeat 3` to see how the chatbot does.
4. Facts you may ask about come from `evals\seed.py`. If you need a new fact, add it there first (R4).

### R4. Change the fictional hotels / users / bookings
Edit `evals\seed.py` (the `HOTELS`, `USERS`, `BOOKINGS` tables). Then:
`pytest` (some tests assert seed facts, e.g. 243.0 hours of notice, and golden cases quote seed facts, so update them to
match), then `python -m evals.save_baseline retrieval`. Ids are derived from names, so renaming something changes its id.

### R5. Tune search (free)
```powershell
python -m evals.retrieval_variants --tuning      # depth 4/6/8, keyword re-ranking
python -m evals.retrieval_variants               # follow-up query strategies
python -m evals.retrieval_variants --rerank      # re-ranking models and pool sizes
```
Re-ranking is on by default; switch model or pool with `RERANK_MODEL` / `RERANK_CANDIDATES` (see `07-reranking.md` section 12).
To try your own idea: add a function in `evals\retrieval_variants.py` (copy `production`) and add it to `STRATEGIES`.
Adopt a winner by editing `build_retrieval_query` / `KNOWLEDGE_BASE_TOP_K` in `chat_service.py`, keep
`evals\retrieval_metrics.py`'s `TOP_K` equal to the app's, then `python -m evals.save_baseline retrieval`.

### R6. Finish judge scoring over several days (free quota is 50 requests/day)
```powershell
python -m evals.runner --label baseline        # once: produces the answers to judge
python -m evals.quality                        # day 1: scores some, stops cleanly when OpenRouter says "per day"
python -m evals.quality                        # day 2: same command; already-judged prompts come from cache (free)
```
It prints how many cases remain. When complete: `python -m evals.save_baseline quality`.
* To use fewer requests per day: `python -m evals.quality --max-calls 40`.
* The cache lives in `evals\results\.judge_cache\`; delete that folder to force fresh judging
  (`Remove-Item -Recurse evals\results\.judge_cache`).
* If you generate **new** answers, judging them needs new requests (different text = different cache key).
* Buying $10 of OpenRouter credit raises the free-model limit to 1,000/day (you chose free only, so not done).

### R7. Check that the judge agrees with you
```powershell
python -m evals.judge_check export        # needs at least one finished quality run
# open evals\results\human_labels.json, set "human_passed": true or false on each entry.
# Don't peek at the "_judge_passed" line at the bottom of each entry until you have labelled everything.
python -m evals.judge_check compare       # agreement % and Cohen's kappa; >= 85% is good
```
If agreement is low, reword the metric steps in `evals\quality.py` (`style_steps`, `BEHAVIOR_STEPS`, `_geval` calls), delete the
judge cache, and re-score.

### R8. Try a different free judge model
```powershell
# list free models (public, no key needed)
python -c "import httpx;[print(m['id']) for m in httpx.get('https://openrouter.ai/api/v1/models').json()['data'] if float(m['pricing']['prompt'])==0 and float(m['pricing']['completion'])==0]"
python -m evals.judge_calibration --model nvidia/nemotron-3.5-super-vl:free     # needs 9-10 of 10 right
```
Then set `JUDGE_MODEL=` in `.env`. Paid models are refused by `evals\judge.py` on purpose. Prefer a vendor other than Google
(the chatbot is Gemini).

### R9. Add an attack to the red team
In `evals\redteam.py` add a line like:
```python
attack("my-id", "jailbreak", "the hostile message", HIJACK_MARKERS + STAFF_DATA, user="anonymous", hotel="mayfair")
```
The 4th argument is a list of regular expressions that must **not** appear in the reply (ready-made lists exist at the top).
Check detectors with `pytest evals\test_redteam.py`, then `python -m evals.redteam --category jailbreak`.

### R10. Use Phoenix (see every conversation)
```powershell
docker compose --profile observability up -d phoenix       # start (first time downloads the image)
# in .env:  PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006   (already set for you)
# restart the app so it picks it up; open http://localhost:6006
```
What you will see:
* Project **`hms`**: real conversations from the running app. Project **`hms-evals`**: runs of `evals.runner`,
  `evals.redteam`, `evals.quality`. `pytest` sends nothing.
* Each question is one **trace**: `concierge_chat` containing `knowledge_retrieval` (the exact search text, each retrieved
  chunk with its score) and `gemini_generate` (system prompt, history, question, answer, model, token counts).
* **Sessions** tab: all turns of one conversation together.
* **Annotations** beside eval traces: `exact_checks` (pass/fail), `red_team` (held/leaked), `judge_<Metric>` scores.
* Tags you can filter by: `metadata.case_id`, `metadata.category`, `metadata.run`, `metadata.attack_id`.
  In the traces search box try an expression such as `metadata['case_id'] == 'fu-spa-hours'`
  (this syntax is from Phoenix's documentation; I verified the data through its API, not by clicking the screen).

Operate it:
```powershell
docker compose --profile observability stop phoenix        # stop (data kept in a Docker volume)
docker logs hms-phoenix --tail 20                          # its log
# delete one project's traces (look up its id first):
$p = (Invoke-RestMethod http://localhost:6006/v1/projects).data | Where-Object name -eq 'hms-evals'
Invoke-RestMethod -Method Delete "http://localhost:6006/v1/projects/$($p.id)"
```
Privacy: traces contain questions, answers and guest names. Keep the port local. To keep only timings/tokens/ids, set
`PHOENIX_REDACT_CONTENT=true`. To trace the app **inside Docker**, set `PHOENIX_DOCKER_ENDPOINT=http://phoenix:6006` in `.env`
and `docker compose --profile observability up -d phoenix app`.

### R11. Look at what the chatbot actually saw for one question (no Phoenix needed)
`python -m evals.runner --ids <case id> --label look` then open the newest `evals\results\generation_look_*.json`: each case
has `answer`, `retrieved` (chunks + scores), `system_instruction` (the full prompt), `llm` (model, tokens, latency), `trace`.

### R12. Change which Gemini model is used
`GEMINI_MODEL=` in `.env` (default fallback list is in `app/services/llm_service.py`). Then re-run R2 with a new label to see
the effect on quality, tokens and latency.

### R13. Rotate secrets
* JWT secret: `python -c "import secrets; print(secrets.token_hex(32))"` and put it in `.env` as `JWT_SECRET_KEY` (everyone must log in again).
* Gemini / OpenRouter keys: replace in `.env`. Never commit `.env`; only `.env.example` is tracked.
* Demo passwords (`Admin@123`, ...) are in your git history: change those accounts' passwords.

### R14. Git: review, recover, commit
```powershell
git status                                   # what changed (nothing is committed yet)
git diff HEAD --stat                         # size of changes per file
git diff 85e5245 -- hms/app/services/chat_service.py    # exact changes to one file since your "ai chatbot" commit
git checkout 85e5245 -- hms/app/services/structured_rag_service.py   # bring back a deleted file
git add -A; git commit -m "Cleanup, security fixes, AI evaluation framework"
```
Run these from the **repository root** (`cd C:\Users\adity\Desktop\Internship`, one level above `hms`): git paths are relative to where you are, and this project lives in the `hms/` subfolder of the repository.

### R15. Structured RAG: finish the measurements that the Gemini daily quota interrupted
Wait until the quota has reset (the error said about 16 hours after the last request; free tier is 500 requests/day per model).
Run **one at a time** (they share the test database), in this order:
```powershell
# 1. Regression: with the tools attached, do the old 72 questions still pass, and do text questions avoid lookups?
python -m evals.runner --label structured-regression          # ~15 min; look at: per-category pass rates, "structured lookups", avg requests/question
# 2. The 6 new tool-abuse attacks (plus the 37 older ones)
python -m evals.redteam
# 3. The pending prompt experiment ("v2"), on the structured category, repeated to beat randomness
#    a) paste the v2 text (below) into chat_service.py replacing the four bullet lines under "LIVE DATA TOOLS"
#    b) measure:
python -m evals.runner --category structured --label structured-v2 --repeat 3
#    c) compare with the saved run generation_structured-v1_*.json (14/17). Keep v2 only if it is better and step 1 stays green.
```
The v2 text (replaces the three/four bullets that start with "ALWAYS call a tool", "NEVER state", "For availability"):
```
- ALWAYS call a tool for: room availability or sold-out questions for particular dates; filtering, ranking, sorting or counting hotels or rooms (cheapest, under $X, sleeps N, in a city or country, with an amenity, best rated); and averages or totals. This includes "which hotels have <amenity>" and "which rooms cost under $X": use the tool even when the text above seems to contain the answer, because that text may be incomplete.
- Do arithmetic in the database, never in your head: for averages, counts, totals, minimums and maximums use the catalog_stats tool; for rankings and "cheapest/best" use the sorting of the search tools.
- NEVER state availability, a count, a ranking or an average that did not come from a tool result.
- Availability needs BOTH dates from the guest. If either is missing, do NOT call any tool: ask the guest for the dates.
```
If it passes, save it: `python -m evals.save_baseline generation --label structured-regression`, and add a row to
`evals\baselines\EXPERIMENTS.md`. If not, undo your edit.
**Quota tip:** a structured question costs 2 Gemini requests; the runners pace themselves by requests (`--pace` seconds per request).

### R16. See exactly what a lookup did (debugging structured RAG)
* **One question, everything visible:** `python -m evals.runner --ids st-avail-soldout --label look`, then open the newest
  `evals\results\generation_look_*.json`. Each case has `tool_calls` (name, arguments, ok, rows, error, milliseconds),
  `tool_results` (the exact rows the model was shown), `answer` and `system_instruction`.
* **In Phoenix (project `hms-evals`):** a trace shows `concierge_chat -> gemini_generate -> tool_<name>`; open the `tool_*`
  step to see its input (the arguments) and output (the rows). The `gemini_generate` step has `hms.tool_calls`.
* **From code or a test:** call the tools directly, no AI involved:
  ```python
  from app.services.structured_rag_service import StructuredTools
  from datetime import datetime, timezone
  tools = StructuredTools(db, now=datetime(2026, 11, 1, tzinfo=timezone.utc))
  tools.run("check_availability", {"hotel_name": "Shibuya", "checkin_date": "2026-11-03", "checkout_date": "2026-11-05"})
  ```
* **Wrong tool chosen / wrong arguments?** That is a prompt or tool-description problem (the model's choice), fixed in the tool
  descriptions in `structured_rag_service.py` or the "LIVE DATA TOOLS" rules in `chat_service.py`, then measured (R2/R15).
  **Wrong rows for the right arguments?** That is a query bug: add a test in `tests\test_structured_rag.py` first.

### R17. Add a new tool (for example `get_my_bookings`)
1. In `app/services/structured_rag_service.py`: add its declaration to `TOOL_DECLARATIONS` (name, a description that says *when to use it*,
   typed parameters), add a `_my_tool(self, args)` handler returning `self._page(rows, limit)` (or a dict with `count` and `rows`), and register it
   in `StructuredTools.__init__` (`self._handlers`). Validate every argument with the helpers (`_text`, `_number`, `_integer`, `_choice`, `_date`).
2. If the tool exposes **personal** data it needs the signed-in user: pass the user into `StructuredTools(...)` in `chat_service._generate_reply`
   and filter by their guest ids (see `app/utils/scoping_utils.py`). Never take a user or guest id from the model's arguments.
3. Add tests in `tests\test_structured_rag.py` (right rows, scoping, no leaks, bad arguments) and run `pytest`.
4. Add golden questions to `evals\build_golden.py` (`tools=["your_tool"]`), regenerate (`python -m evals.build_golden`), and add attacks to
   `evals\redteam.py` (category `tool_abuse`). Add the tool name to `TOOLS` in `evals\dataset.py`.
5. Measure with R15's commands.

---

## 3. Settings reference

Put these in `.env` (copy `.env.example`). Required ones marked **\***.

| Variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` **\*** | Postgres connection for the app | none |
| `JWT_SECRET_KEY` **\*** | Signs login tokens | none (app refuses to start) |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token settings | HS256, 30, 7 |
| `COOKIE_SECURE` | `true` when served over HTTPS | false |
| `CORS_ORIGINS` | Comma-separated website addresses allowed to call the API | localhost 5173/8000 |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | The chatbot's model | model `gemini-3.5-flash-lite` |
| `PHOENIX_COLLECTOR_ENDPOINT` | Turns tracing on (`http://localhost:6006`) | off |
| `PHOENIX_PROJECT_NAME` | Phoenix project for real traffic | `hms` |
| `PHOENIX_EVAL_PROJECT_NAME` | Project for eval runs | `hms-evals` |
| `PHOENIX_REDACT_CONTENT` | `true` = send no text, only timings/ids | false |
| `PHOENIX_DOCKER_ENDPOINT` | Tracing endpoint for the app **inside Docker** | empty (off) |
| `PHOENIX_TRACE_TESTS` | `1` = pytest also sends traces | off |
| `JUDGE_PROVIDER` | Must be `openrouter` | none |
| `JUDGE_MODEL` | A **free** OpenRouter model | `nvidia/nemotron-3.5-super-vl:free` |
| `OPENROUTER_API_KEY` | Judge key | none |
| `JUDGE_MIN_INTERVAL` | Seconds between judge requests | 4 |
| `JUDGE_MAX_CALLS` | Stop after this many judge requests per run | unlimited |
| `JUDGE_ALLOW_PAID` | `1` = allow paid judge models (not recommended; bypasses the free-only guard) | off |
| `RERANK_ENABLED` | `false` = embeddings-only search (no re-ranking) | true |
| `RERANK_MODEL` | Cross-encoder used to re-rank search results | `Xenova/ms-marco-MiniLM-L-6-v2` |
| `RERANK_CANDIDATES` | Chunks fetched by embedding search before re-ranking | 20 |
| `DEMO_AUTOPILOT` | `true` = the app keeps the demo hotel data current (check-ins, check-outs, new bookings, reviews) | false |
| `DEMO_AUTOPILOT_INTERVAL_HOURS` | How often the autopilot runs while the app is up | 3 |
| `RERANK_MAX_CHARS` | Characters of each chunk the re-ranker reads (speed vs detail) | 600 |
| `TEST_DATABASE_URL` | Test database (name must end `_test`) | `postgresql://postgres:postgres@127.0.0.1:5433/hms_test` |
| `VITE_API_URL`, `VITE_SHOW_DEMO_LOGINS` | Website build settings | `http://127.0.0.1:8000`, off |

---

## 4. Troubleshooting

| What you see | Likely cause | Fix |
|---|---|---|
| `RuntimeError: Missing required environment variable: JWT_SECRET_KEY` | `.env` missing a required value | Copy `.env.example` to `.env` and fill it in |
| Tests: connection refused on port 5433 | Docker database not running | `docker compose up -d db` |
| Tests: `extension "vector" is not available` | `TEST_DATABASE_URL` points at the native Windows Postgres | Use the Docker database on 5433 |
| Tests: `Refusing to run tests against ...` | Test database name does not end in `_test` | Fix `TEST_DATABASE_URL` |
| Weird test failures right after running an eval | Two commands shared `hms_test` at once | Re-run one at a time |
| Gemini `429` / "quota exceeded" in logs | Free tier: 15 requests/minute **and 500 requests/day per model** (the log says which and when it resets) | Per-minute: wait; runners already pace (`--pace 6` to slow further). **Daily: nothing to do until it resets** (the error says e.g. "retry in 16h"); do not run evals meanwhile. A lookup question costs 2 requests |
| Gemini `503` "high demand" | Google overloaded | The client tries backup models; retry later |
| `JudgeQuotaExhausted ... free-models-per-day` | OpenRouter free limit (50/day) used | Run the same command tomorrow; progress is cached |
| `... is not a free OpenRouter model` | `JUDGE_MODEL` is paid | Pick one ending in `:free` (R8) |
| Judge `429 Provider returned error` repeatedly | The model's upstream provider is rate-limited | Choose another free model or wait |
| `judge request failed after 4 attempts` | Network/provider trouble | Re-run; completed prompts are cached |
| Phoenix: nothing appears | Endpoint unset, container stopped, or wrong project | `docker ps`; check `PHOENIX_COLLECTOR_ENDPOINT`; look in project `hms-evals` for eval runs; restart the app after editing `.env` |
| Phoenix `401 Unauthorized` | Auth enabled on the container | The compose file sets `PHOENIX_ENABLE_AUTH=false`; re-create it: `docker compose --profile observability up -d phoenix` |
| `opentelemetry.exporter` not found warning | Tracing packages not installed in this environment | `pip install -r requirements.txt` |
| `pip` read timeouts | Slow network | add `--default-timeout=300 --retries 10` |
| git "LF will be replaced by CRLF" warnings | Windows line endings | Harmless |
| Chatbot answers "temporarily unavailable" | Gemini key missing/invalid or quota | Check `GEMINI_API_KEY` in `.env` and the app log |
| `docker compose up` port 5433/8000/6006 already used | Another program | Stop it, or change the left-hand port in `docker-compose.yml` |
