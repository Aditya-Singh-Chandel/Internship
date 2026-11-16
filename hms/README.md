# GrandStay HMS

Hotel management and booking system: FastAPI + PostgreSQL (pgvector) backend, React (Vite) frontend, and a Gemini-powered AI concierge grounded in hotel data and uploaded documents (RAG).

## Project layout

```
app/
  api/routes/   HTTP endpoints (auth, hotels, rooms, bookings, documents, chat, ...)
  core/         settings, database engine, security (JWT, bcrypt), roles
  models/       SQLAlchemy tables
  schemas/      Pydantic request/response models
  services/     business logic, incl. chat (RAG), document ingestion, embeddings, Gemini client
  utils/        query helpers, per-hotel access scoping, document parsers
frontend/       React app (guest site + operations portal)
scripts/        demo database: seed (seed_demo_db.py), hotel content (demo_content.py), daily autopilot
tests/, evals/  automated tests and AI evaluation (see below)
docs/           beginner-friendly guide to the whole system
```

## How the AI concierge answers

1. **Knowledge base (RAG):** hotel documents and policies are cut into ~500-character chunks and embedded locally
   (`BAAI/bge-small-en-v1.5`). A question fetches the 20 closest chunks, then a local cross-encoder re-ranker
   (`Xenova/ms-marco-MiniLM-L-6-v2`) re-orders them and the best few are sent to Gemini in full. See `docs/07-reranking.md`.
2. **Structured RAG:** for live data (availability, prices, rankings, the signed-in guest's own bookings) Gemini calls
   read-only database tools. See `docs/06-structured-rag.md`.
3. Staff-only documents and other guests' data are filtered out before anything reaches the model.

## Setup

1. Copy `.env.example` to `.env` and fill in:
   - `JWT_SECRET_KEY`: required. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - `GEMINI_API_KEY`: required for the AI concierge
2. Start everything with Docker:
   ```
   docker compose up --build
   ```
   - API and docs: http://localhost:8000/docs
   - Web app: http://localhost:8000/app
   - Health check: http://localhost:8000/health
3. Fill the database with the demo hotels (10 hotels with rooms, staff, bookings, reviews and a knowledge base):
   ```
   docker compose exec app python -m scripts.seed_demo_db --yes
   ```
   This **drops everything** in the target database first. Demo logins are listed in `docs/08-real-database.md`.
   With `DEMO_AUTOPILOT=true` in `.env` the app then does the daily check-ins, check-outs, new bookings and reviews by
   itself, so the data never goes stale.

### Local development (without the app container)

```
docker compose up -d db
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed_demo_db --yes   # demo data into DATABASE_URL (drops it first)
uvicorn app.main:app --reload

cd frontend
npm install
npm run dev        # http://localhost:5173
```

The first admin account is created with `POST /auth/init-admin` (only works while no admin exists). Public sign-up always creates a customer account; owners and staff are created by an admin or owner.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `JWT_SECRET_KEY` | Signing key for access/refresh tokens (required) |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `COOKIE_SECURE` | `true` when served over HTTPS |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | AI concierge model access |
| `RERANK_ENABLED`, `RERANK_MODEL`, `RERANK_CANDIDATES`, `RERANK_MAX_CHARS` | Knowledge-base re-ranking (on by default) |
| `DEMO_AUTOPILOT`, `DEMO_AUTOPILOT_INTERVAL_HOURS` | Keep the demo data current (off by default; never on `*_test` databases) |
| `PHOENIX_COLLECTOR_ENDPOINT` | Optional tracing of the AI concierge in Arize Phoenix |
| `VITE_API_URL` (frontend) | API base URL, default `http://127.0.0.1:8000` |
| `VITE_SHOW_DEMO_LOGINS` (frontend) | `true` to show demo-account quick-fill buttons in a production build |

## Tests and AI evaluation

```
pip install -r requirements-dev.txt
docker compose up -d db                          # tests use the Docker pgvector database on host port 5433
pytest                                           # unit + API tests and the free evals (no LLM calls)
pytest --run-llm                                 # also runs the real-Gemini checks (costs tokens)
```

Tests never touch your development data: they create and wipe a separate `hms_test` database
(`TEST_DATABASE_URL` overrides the default `postgresql://postgres:postgres@127.0.0.1:5433/hms_test`).

| Path | What it is |
|---|---|
| `tests/` | Plain tests: refund calculation, access control, what the chatbot may see |
| `evals/seed.py` | Three fictional hotels, users and bookings with a frozen clock, so results are reproducible |
| `evals/datasets/golden.jsonl` | 89 questions with expected facts, exact checks and retrieval labels |
| `evals/retrieval_metrics.py` | hit@k / MRR / recall for the knowledge base (`python -m evals.retrieval_metrics`) |
| `evals/runner.py` | Runs the golden set through the real chatbot (`python -m evals.runner --label my-change`) |
| `evals/quality.py`, `evals/judge.py` | DeepEval scoring by a free OpenRouter judge model (rate-limited, cached, resumable) |
| `evals/redteam.py` | 43 attacks (prompt extraction, jailbreaks, staff-data theft, SQL, fake authority, tool abuse) with exact leak detectors |
| `app/services/structured_rag_service.py` | Structured RAG: 4 database query tools the chatbot can call (availability, search, rankings, stats); see `docs/06-structured-rag.md` |
| `evals/real_db_check.py` | Read-only audit + retrieval/chat checks against the real demo database (`python -m evals.real_db_check`) |
| `evals/baselines/` | Saved scores that tests compare against, so regressions fail; `EXPERIMENTS.md` logs every measured change |
| `evals/results/` | Output of each run (not committed) |

**New here? Start with [`docs/README.md`](docs/README.md)**: the full guide to everything that was changed (the story from scratch,
every file, every change, commands and recipes, and a glossary).

Full guide to the evaluation system: [`evals/README.md`](evals/README.md).

### Watching the AI concierge in Phoenix (optional)

```
docker compose --profile observability up -d phoenix     # then set PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006 in .env
```

Open http://localhost:6006: every question appears as one trace (search, then Gemini) with the retrieved text,
prompt size, model and token counts. Phoenix runs without login and only on your machine; traces contain guest
names and prompts, so do not expose that port.
