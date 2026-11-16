# 02. Every file: what it is and why it exists

Paths are relative to the `hms/` folder. **NEW** = created by us, **CHANGED** = existed and we edited it,
**DELETED** = removed. Anything not listed here (for example `app/models/*`, most routes) was not touched.

Contents: [A. Backend](#a-backend-app) · [B. Configuration and Docker](#b-configuration-docker-and-project-files) ·
[C. Frontend](#c-frontend) · [D. Ordinary tests](#d-ordinary-tests-tests) · [E. The evaluation system](#e-the-evaluation-system-evals) ·
[F. Deleted files](#f-deleted-files)

---

## A. Backend (`app/`)

### `app/main.py` (CHANGED)
The FastAPI application: middleware, error handlers, routes, and serving the built website.
* CORS origins now come from settings (`CORS_ORIGINS`), not a hard-coded list.
* Logging is configured (`logging.basicConfig`), so `logger.info` lines appear.
* The catch-all 500 handler **logs the full error on the server** and returns only a generic message
  (`"details": null`). Before, it returned `str(exc)`, which could expose SQL or paths.
* New `GET /health` runs `SELECT 1` against the database: use it for "is the app alive?" checks (Docker uses it).
* Removed the fallback that tried to serve the un-built raw `frontend/` folder (it could not work with Vite);
  the built site is served from `frontend/dist` when it exists.
* Unchanged: the list of routers, `create_all()` at startup.

### `app/core/config.py` (CHANGED)
The `Settings` object read by the rest of the app.
* `DATABASE_URL` and `JWT_SECRET_KEY` are **required**: if missing the app stops with a clear message. (Before, a
  built-in secret was used, which was a security hole.)
* New settings: `COOKIE_SECURE` (set true under HTTPS) and `CORS_ORIGINS` (comma-separated).
* Re-ranking settings: `RERANK_ENABLED` (true), `RERANK_MODEL`, `RERANK_CANDIDATES` (30).

### `app/core/database.py` (CHANGED)
Creates the SQLAlchemy engine/session. Now reads `settings.DATABASE_URL` (one source of truth) and enables
`pool_pre_ping` (drops dead connections instead of erroring).

### `app/core/tracing.py` (NEW)
Optional Phoenix/OpenTelemetry tracing, **off unless `PHOENIX_COLLECTOR_ENDPOINT` is set**. Key parts:
* `span(name, kind, input)`: context manager that records a step. `kind` is an OpenInference kind (CHAIN, RETRIEVER, LLM).
  A harmless no-op when tracing is off. The yielded object has `.set(key, value)`, `.span_id`, `.trace_id`.
* `attributes(**facts)`: attaches searchable facts (like `case_id`) to every span opened inside the block.
* `flush()`: send everything now. `annotate_span(...)`: attach a pass/fail label to a finished trace in Phoenix (retries
  briefly because Phoenix ingests spans a moment after receiving them).
* Settings: `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME`, `PHOENIX_REDACT_CONTENT`.
* Safety: missing packages or an unreachable Phoenix are logged, never raised.

### `app/api/routes/auth.py` (CHANGED)
Login, register, refresh, logout, `init-admin`. Changes: the refresh-token cookie's `secure` flag now comes from
`settings.COOKIE_SECURE`; `init-admin` now **requires** a request body (the admin password has no default any more).

### `app/api/routes/chat.py` (CHANGED)
The chat endpoints. **Removed** `POST /chat/llm-config` and `GET /chat/llm-status` (open to anyone; could replace the
API key and leaked part of it). `GET /chat/sessions/{id}/messages` now returns 403 unless the session belongs to the
caller (anonymous sessions have no owner and stay readable only by id, as before).

### `app/api/routes/documents.py` (CHANGED)
Knowledge-base endpoints under `/hotels/{hotel_id}/documents`.
* Upload, text, sync, **list** and delete all require staff **and** call `resolve_and_verify_hotel_id`, so staff can act
  only on their own hotel (owners on theirs; admins anywhere).
* Upload size capped at 10 MB (HTTP 413); `access_level` validated; list uses `limit` 1-100.
* The public search endpoint no longer pretends to use the caller's identity (it only ever returned public chunks).

### `app/schemas/chat.py` (CHANGED)
`ChatMessageRequest.message` now has `max_length=2000` (stops giant messages burning quota).

### `app/schemas/document.py` (CHANGED)
`access_level` is now `Literal["public", "staff_only", "resident_only"]`, so invalid values get a 422.

### `app/schemas/user.py` (CHANGED)
* `UserRegister` lost its `role_id`, `role_name` and `hotel_id` fields: **public sign-up cannot choose a role**.
* `AdminInitRequest.password` is now required (min 8 characters), with no default.

### `app/services/user_service.py` (CHANGED)
`register_user` always creates a **customer** (owners and staff are created by an admin/owner through the user-management
endpoints).

### `app/services/rerank_service.py` (NEW)
Second search stage. Lazily loads a cross-encoder (`settings.RERANK_MODEL`, default `Xenova/ms-marco-MiniLM-L-6-v2`) via
fastembed, scores each (question, hotel name + title + chunk) pair, stores `rerank_score` (sigmoid of the model's output, 0..1)
and returns the best `top_k`. Any failure (download, load, scoring) returns the vector order unchanged and logs it.
Explained in `07-reranking.md`.

### `app/services/document_service.py` (CHANGED)
* The synced reviews chunk keeps the overall rating from all reviews but lists only the 8 most recent comments.
`search_chunks` is now two stages: `_vector_search` (the previous search, unchanged) fetches `RERANK_CANDIDATES` (30) chunks,
then `rerank_service.rerank` keeps the best `top_k`. `rerank=None/True/False` follows the setting or forces it (evals use it).
`delete_document(db, hotel_id, document_id)` now also filters by `hotel_id`, so a document can only be deleted through its
own hotel's URL (404 otherwise).

### `app/services/llm_service.py` (CHANGED)
The Gemini REST client (`call_gemini_cloud_api`).
* API key sent in the `x-goog-api-key` header, not the URL (URLs end up in logs).
* New optional `usage` argument: fills model, latency and token counts (used by evaluation and tracing).
* Generic user-facing 503 message (upstream error text is only logged).
* Removed two unused helpers (`classify_intent_with_gemini`, `synthesize_with_gemini`), the `.env`-reloading code, and a
  line that overrode `max_tokens`.
* **Structured RAG tool loop.** `call_gemini_cloud_api` accepts `tools` (Gemini function declarations) and `tool_runner(name, args)`.
  If the model answers with function calls instead of text, each is run, the results are returned, and this repeats up to 3 rounds
  (then the model is forced to answer). The model's own reply is echoed back unchanged (Gemini 3 needs its `thoughtSignature`), a
  crashing runner is reported to the model rather than raised, and token counts in `usage` add up over all requests
  (`usage["requests"]`, `usage["tool_rounds"]`). The retry/fallback logic moved into `_post_with_fallback`. With no tools nothing changes.

### `app/services/structured_rag_service.py` (NEW; the name is reused, the content is new)
Structured RAG for the chatbot, see `docs/06-structured-rag.md`. `TOOL_DECLARATIONS` is the menu shown to Gemini (4 tools).
`StructuredTools(db, now, scope_hotel_id)` runs them: `run(name, args)` validates, executes inside a database SAVEPOINT, traces a
`tool_<name>` span, records the call in `.calls`, and returns `{"ok": true, ...rows}` or `{"ok": false, "error": ...}` (never raises).
Handlers: `_search_hotels`, `_search_room_types`, `_check_availability` (uses `room_type_availability`), `_catalog_stats`.
Helpers: `_like` (escapes `%`/`_`), `_text`, `_number`, `_integer`, `_choice`, `_date`, `ToolError`. Limits: 10 rows, 30 nights, 5 rooms.

### `app/services/room_type_service.py` (CHANGED)
New `room_type_availability(db, room_type_id, checkin, checkout) -> (total rooms, free rooms)`: the free-room calculation that used to be
inline in `get_room_types`, extracted unchanged so the website endpoint and the chatbot share one implementation.

### `app/services/chat_service.py` (CHANGED, the heart of the AI concierge)
* `build_knowledge_base_context` sends each retrieved chunk **whole** (it used to cut at 350 characters) and uses the
  re-rank score for citations; the retrieval trace records both scores.
Function by function:

| Function | What it does |
|---|---|
| `get_or_create_session` | Finds/creates a chat session. **A session owned by someone else is never reused** (privacy fix). |
| `list_user_sessions`, `get_session_history` | Chat history queries (unchanged). |
| `_BULLET_PREFIX` ... `_HOURS_THRESHOLD`, `_to_hours` | The regular expressions the refund parser uses. |
| `_parse_cancellation_tiers(policy_text)` | **Rewritten.** Turns free text like "100% refund at least 72 hours before; 50% between 24 and 72; non-refundable within 24" into a list of (minimum notice hours, refund fraction). Handles bullets, one-paragraph policies, "Full refund" without `%`, days or hours, and "non-refundable" with no time. |
| `evaluate_dynamic_cancellation_policy` | Uses the tiers to decide the refund for a given notice. Falls back to a 48h/24h default only if the text has no readable tiers. |
| `parse_checkin_time` | **New.** Reads the hotel's own published check-in time from its policies (skips "early check-in"). Returns None if absent: **no guessing**. |
| `notice_hours_before_checkin` | **New.** Hours until check-in using that time; None if unknown (certain "already past" only if the date is past). |
| `build_hotel_catalog_context` | Puts hotels, rooms, prices, policies, reviews into the prompt text (unchanged). |
| `build_user_booking_context` | The signed-in guest's bookings and refund eligibility (now uses the real check-in time and accepts `now=`). Visitors get guidance only: for cancellation/refund questions the bot must **explain the hotel's policy first**, and mention sign-in only for a specific booking. |
| `build_retrieval_query` | **New.** The text used to search the knowledge base: if the message is short (<= 8 words) or leans on earlier context ("it", "that", "and"), the guest's previous message is prepended. |
| `KNOWLEDGE_BASE_TOP_K = 8` | **New constant.** Chunks retrieved per question (was 4). |
| `build_knowledge_base_context` | Searches and formats the retrieved chunks; now also returns the raw chunks. |
| `send_chat_message` | **Public entry point.** Wraps `_generate_reply` in a root trace span; sets `session.id`, `user.id`, hotel; with `debug=True` adds the trace ids. |
| `_generate_reply` | **The pipeline:** validate; get/create session; load history; save the guest message; build catalog + booking + knowledge context; build the system prompt (now with **today's date** and the **LIVE DATA TOOLS rules**); call Gemini **with the structured tools** (traced as retrieval, generation and `tool_*` spans); add citations (**live-data citations first**); save the reply with the lookups in `tool_calls_json`; optionally attach the `debug` block (including `tool_calls` with exact results). |
| `MAX_CITATIONS = 10` | Citation cap (was 8; with 8 retrieved chunks the live-data citation would have been cut off). |
| `build_hotel_catalog_context` (changed) | The review line no longer calls the mean of the latest 3 reviews "Verified Guest Rating"; it is labelled a sample and points to `search_hotels` for the true average. |
| (removed) | Four unused "backwards-compatibility wrapper" functions. |

---

## B. Configuration, Docker and project files

### `.env` (CHANGED, **yours, not in git**)
We rotated `JWT_SECRET_KEY` (without printing it) and, at your request, set `JUDGE_MODEL=nvidia/nemotron-3.5-super-vl:free`.
You added `PHOENIX_COLLECTOR_ENDPOINT`, `JUDGE_PROVIDER` and `OPENROUTER_API_KEY` yourself. Never commit this file.

### `.env.example` (CHANGED)
The template listing every setting, including the optional Phoenix and judge settings (commented out). Copy it to `.env`.

### `requirements.txt` (CHANGED)
Runtime dependencies, grouped and **pinned**. Added `httpx` (the chatbot needs it but it was missing), `numpy`, and the
optional `opentelemetry-sdk` / `opentelemetry-exporter-otlp-proto-http` (Phoenix tracing).

### `requirements-dev.txt` (NEW)
`-r requirements.txt` plus `pytest` and `deepeval`. Install with `pip install -r requirements-dev.txt`.

### `pytest.ini` (NEW)
Test folders (`tests`, `evals`), a `llm` marker for tests that call real AI services (skipped unless `--run-llm`).

### `conftest.py` (NEW)
Shared pytest setup, read automatically. It:
1. Points the app at the **test database** (`TEST_DATABASE_URL`, default `postgresql://postgres:postgres@127.0.0.1:5433/hms_test`),
   creates it if missing, and **aborts if its name does not end in `_test`**.
2. Provides fixtures: `seeded_db` (fresh schema + seed once per session), `db` (a session per test), `client` (FastAPI test client).
3. Routes tracing: eval runs go to Phoenix project `hms-evals`; plain pytest sends no traces.
4. Adds the `--run-llm` option and skips `llm`-marked tests without it.
Note: it resets the schema by dropping `public` (not `drop_all`) because `users` and `hotels` reference each other.
`evals/runner.py`, `redteam.py` etc. also `import conftest` for step 1 and 3.

### `Dockerfile` (CHANGED)
Multi-stage: stage 1 (Node 22) builds the React app; stage 2 (Python 3.12) installs dependencies, copies **only** `app/`
and the built site, runs as a non-root `appuser`, caches the embedding model in `/tmp/fastembed_cache`.

### `docker-compose.yml` (CHANGED)
* `db` (pgvector/pgvector:pg16): host port **127.0.0.1:5433** (only your machine; 5433 because a native Postgres often owns 5432).
* `app`: loads `.env`; overrides `DATABASE_URL` to the `db` service; fastembed cache volume; healthcheck on `/health`;
  `PHOENIX_COLLECTOR_ENDPOINT` set from `PHOENIX_DOCKER_ENDPOINT` (empty = tracing off in Docker).
* `phoenix` (profile `observability`, image `arizephoenix/phoenix:version-21.0.0`): port 127.0.0.1:6006, auth off
  (local only), data volume, healthcheck.

### `.dockerignore`, `.gitignore` (CHANGED)
Keep secrets, caches, `node_modules`, `frontend/dist`, `evals/results/` out of images and git.

### `README.md` (CHANGED)
The project README: layout, setup, configuration table, testing and evaluation commands, Phoenix instructions.

---

## B2. Scripts (`scripts/`, NEW)

### `scripts/seed_demo_db.py` (NEW)
Rebuilds the database in `DATABASE_URL` from scratch (drops all tables, recreates them from the models) and fills it
with a consistent working demo: hotels, rooms, policies, staff, customers, ~2,400 bookings with date-correct statuses,
reviews and the knowledge base. Checks its own output (no double booking, totals, statuses, refund and check-in parsing)
and fails loudly. Refuses a `*_test` database. Run: `python -m scripts.seed_demo_db --yes`. See `08-real-database.md`.

### `scripts/demo_autopilot.py` (NEW)
Keeps the demo data current: each run catches up check-outs, check-ins (with no-shows), room allocation, new bookings,
cancellations and reviews for every day since the last run. Started by `app/main.py` (lifespan) when `DEMO_AUTOPILOT=true`;
manual run: `python -m scripts.demo_autopilot`. Tested by a 120-day time-travel simulation (`08-real-database.md`).

### `scripts/demo_content.py` (NEW)
The content for the seed: every fact about each hotel written once (policies and documents are generated from it), staff,
customers, name pools for generated guests, review phrases.

## C. Frontend

### `frontend/src/components/AuthModal.jsx` (CHANGED)
The "quick fill demo roles" buttons (which contain the admin password) now show only in development builds or when
`VITE_SHOW_DEMO_LOGINS=true`. Otherwise the passwords would ship inside the public JavaScript.

(Everything else in `frontend/` is unchanged. Deleted template files are listed in section F.)

---

## D. Ordinary tests (`tests/`)

Run with `pytest tests`. They use the test database and need no AI quota.

| File | Tests | What it proves |
|---|---|---|
| `tests/test_cancellation_policy.py` | 30 | Refund tiers for each seed hotel and for the real "Peak Season" text; boundaries (exactly 72h, 71.9h); stays already started; unreadable policies fall back to 48h/24h; blanket "non-refundable"; numbered and bulleted formats |
| `tests/test_access_control.py` | 21 | Hotel-scoped documents (list/write/delete, wrong-hotel URL, bad access level, 10 MB cap); public search never returns the staff-only canary; registration always makes a customer even if you ask for owner/admin; `init-admin` needs a password and refuses when an admin exists; the key-changing endpoints are gone; chat history is owner-only; session hijacking blocked; message length cap; `/health`; 500s leak nothing |
| `tests/test_chat_context.py` | 24 | Visitors see no reservation data; each guest sees only their own; the frozen clock and the hotel's own check-in time give exact notice hours (243.0 / 26.0); parsing check-in times from many wordings; "unknown" when a hotel publishes none (no invented refund figure); search stays within hotel and public chunks; the `debug` payload appears only when asked |
| `tests/test_judge_limits.py` | 17 | The judge's safety net with a **fake network**: rate limiter spacing, cache, call budget, per-minute 429 waited out, daily 429 stops the run and stays stopped, retries for 5xx/empty/timeouts, malformed JSON retried once, free-only guard, configuration errors |
| `tests/test_structured_rag.py` | 52 | The four tools against hand-computed seed answers (sold-out single-room suite, partial availability, checkout day not a night, price/capacity filters, amenity at hotel- and room-level, true average ratings, Tokyo average $565, overall 4.33), argument validation, hostile text matches nothing and drops nothing, hotel scoping, no guest/staff data in results, recorded calls, the menu matches the handlers |
| `tests/test_gemini_tool_loop.py` | 12 | The Gemini client's tool loop with a scripted fake Gemini: no-lookup costs one request, one round trip (verbatim echo incl. thoughtSignature), parallel calls in order, a model that never stops asking is cut off, a crashing tool, fallback models, empty/thought replies, 503 handling, key in header |
| `tests/test_structured_rag_chat.py` | 8 | The whole chat path with a fake Gemini that uses the real tools: tools and today's date in the prompt, results from the real database, saved/cited/exposed in `debug`, failed lookups, hotel scoping, no guest data, a crashing lookup keeps the guest's message, lookups appear as child spans |
| `tests/test_tracing.py` | 13 | Span nesting and kinds, `metadata` facts only inside their block, redaction drops text but keeps numbers, annotation payload matches Phoenix's API and is retried/gives up quietly, tracing failure never breaks chat, one question = one trace with chat messages, session and user ids, no staff secret or user email in spans |
| `tests/test_rerank.py` | 9 | Re-ranking with a fake model: reorders by cross-encoder score and cuts to top_k, keeps the vector score and adds a 0..1 `rerank_score`, reads title + text, falls back to vector order when the model fails or cannot load, wide pool then top_k, `rerank=False` never calls the model; one check with the real model |
| `tests/test_seed.py` | 1 | The seed data loads (3 hotels, 3 bookings, embeddings present, staff-only canary only in staff-only chunks) |

---

## E. The evaluation system (`evals/`)

See also `evals/README.md`. Files in the order you would use them:

### Test world
* **`evals/seed.py` (NEW).** Builds the deterministic world: 3 hotels (Mayfair London, Aspen Lodge, Shibuya Tokyo) with
  room types, prices, policies, amenities and an FAQ each; 7 users (admin, owner, manager, 2 receptionists, 2 customers);
  3 bookings; the staff-only memo containing `STAFF-ONLY-CANARY-7731`. **For structured RAG it also has physical rooms** (`ROOM_COUNTS`:
  23 rooms, single-room suites are easy to sell out) **and 6 past completed stays with reviews** (`REVIEWS`: true averages
  Shibuya 5.0, Mayfair 4.5, Aspen 3.5). All ids come from `uuid5(name)` so they are stable;
  `FROZEN_NOW = 2026-11-01 12:00 UTC`. Helper `sid("hotel:mayfair")` gives an id. Login password for all test users:
  `Test@1234`.
* **`evals/datasets/golden.jsonl` (NEW).** The 89 questions (one JSON object per line): the original 72 plus 17 `structured` ones
  (availability on given dates, rankings, counts, averages, price filters, relative dates, follow-ups, missing/past dates). Two new
  fields: `expected_tools` (which lookup must succeed; `"a|b"` = either) and `forbid_tools` (text questions must not trigger lookups).
* **`evals/build_golden.py` (NEW).** Python that *generated* `golden.jsonl` (cases written as function calls, easier to
  read). Documents the field meanings at the top. **Warning:** running it overwrites `golden.jsonl`; once you start editing
  the `.jsonl` by hand, stop using it.
* **`evals/dataset.py` (NEW).** Loads the JSONL into `Case` objects; `check_answer()` is the exact checker (each
  must-contain group needs one alternative; no forbidden text); `check_tools()` checks the structured-RAG behaviour (the expected
  lookup succeeded; text questions made none); maps `marcus`/`sophia` to emails.
* **`evals/test_dataset.py` (NEW, 147 tests).** Validates the dataset itself: well-formed, unique ids, every category
  present, every retrieval label matches text that exists, forbidden never also required, the checker works.

### Measuring
* **`evals/retrieval_metrics.py` (NEW).** hit, hit@1, MRR, recall, precision per category, with a pluggable retriever; the
  default retriever mirrors the chatbot (history-aware query, top 8). CLI prints a table and saves to `evals/results/`.
* **`evals/retrieval_variants.py` (NEW).** Compares search strategies on the same labelled cases (previous-turn variants;
  `--tuning` compares depth 4/6/8 and keyword re-ranking; `--llm` adds an LLM rewrite). Read-only.
* **`evals/runner.py` (NEW).** Sends the dataset through the **real chatbot**: pre-loads each case's history, calls
  `send_chat_message(debug=True)`, applies the exact checks (answer text **and** tool use), saves answers/prompts/chunks/tokens/
  latency and, for lookups, `tool_calls` and the exact `tool_results`. Paced **per Gemini request** (4.5 s each; a lookup question
  makes 2) for the free tier, retries a transient error once, `--repeat N`, `--ids`, `--category`, `--label`. The summary reports
  lookup counts and average Gemini requests per question. Also tags each trace in Phoenix and attaches the `exact_checks` label.
* **`evals/judge.py` (NEW).** The grading model client (OpenRouter, free models only): rate limiter, disk cache in
  `evals/results/.judge_cache/`, call budget, daily-quota stop, malformed-JSON retry, `get_judge()` reads `.env`.
* **`evals/quality.py` (NEW).** DeepEval scoring of a saved run: Correctness, Behavior, GroundedPrices, Style (one request
  each), `--deep` adds Faithfulness, AnswerRelevancy, KnowledgeRetention, RoleAdherence. Interleaves categories so a
  stopped run is still representative; labels traces in Phoenix. Live-database results are included in the context the judge
  sees (otherwise a correct price quoted from a lookup would look invented).
* **`evals/judge_calibration.py` (NEW).** 10 answers with known verdicts to test a judge model before trusting it.
* **`evals/judge_check.py` (NEW).** Export ~30 answers, you label them pass/fail (without peeking at the judge's verdict stored in the same file), then
  `compare` computes agreement and Cohen's kappa between you and the judge.
* **`evals/redteam.py` (NEW).** 43 attacks with exact leak detectors (37 original + 6 `tool_abuse`: SQL injection in a tool argument,
  "run this SQL", e-mail exfiltration through the stats tool, an invented destructive tool, a system prompt hidden in an argument, a
  wildcard dump); labels traces `held`/`leaked`.
* **`evals/save_baseline.py` (NEW).** One command to store the current scores as the new baseline.

### Gates (pytest)
* **`evals/test_retrieval.py` (NEW).** Free. Retrieval must not drop below the saved baseline; direct questions always find
  their source; follow-ups >= 90%.
* **`evals/test_generation.py` (NEW, opt-in `--run-llm`).** Runs the dataset against Gemini; no errors, pass rate not
  below baseline, security cases never leak, visitors never see reservations.
* **`evals/test_quality.py` (NEW, opt-in).** Judge-scored quality not below baseline (skips with a message if the free
  quota stops the run).
* **`evals/test_redteam.py` (NEW).** Free part: the attack list and detectors are sound (12 tests); opt-in part (2 tests): no attack
  gets through.

### Records
* **`evals/baselines/*.json` (NEW).** The saved scores the gates compare against (`retrieval`, `generation`, `quality`).
* **`evals/baselines/EXPERIMENTS.md` (NEW).** The measured before/after of each improvement.
* **`evals/results/` (git-ignored).** Every run's output, plus the judge cache.
* **`evals/README.md` (NEW).** The short operating guide.

---

## F. Deleted files

All recoverable: `git checkout 85e5245 -- <path>` (path relative to the repository root, i.e. starting with `hms/`).

| Deleted | Why |
|---|---|
| `scratch/*.py` (13 files) and the top-level `scratch/` | One-off debugging scripts containing passwords like `Admin@123` |
| `app/legacy_admin.html` | 4,297-line old admin page, referenced nowhere |
| `app/services/structured_rag_service.py` | Text-to-SQL service, never called, unsafe design (LLM-written SQL guarded by regex) |
| `frontend/README.md`, `frontend/public/*.svg`, `frontend/src/assets/*` | Vite template leftovers, referenced nowhere |
| `test_suite.py` (earlier, from your working tree) | Already deleted before we started |

(We also removed four unused compatibility wrappers inside `chat_service.py` and two unused helpers inside `llm_service.py`;
those are edits, not file deletions.)
