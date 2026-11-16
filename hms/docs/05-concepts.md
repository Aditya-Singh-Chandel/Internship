# 05. Concepts explained simply

Alphabetical within each group. Each entry says what it is, why it matters here, and where it appears in this project.

## The chatbot and how it finds answers

**LLM (large language model).** A program trained on huge amounts of text that writes replies. Here: **Google Gemini**
(the chatbot) and, separately, an OpenRouter model (the judge).

**Prompt / system prompt.** The text sent to the LLM. The *system prompt* holds the rules and the facts it may use. In
this project it is assembled in `chat_service._generate_reply`: rules (be concise, never reveal instructions, etc.) +
the hotel catalog + the signed-in guest's bookings + retrieved document text. The LLM only "knows" what is in the prompt.

**RAG (retrieval-augmented generation).** Instead of hoping the LLM remembers your hotel facts, you first **retrieve**
relevant text from your own data and put it in the prompt, then let the LLM **generate** an answer from it. Our chatbot
is a RAG system. Two things can fail: retrieval (wrong text found) and generation (right text, wrong answer).

**Embedding.** A list of numbers (384 for the model we use, `bge-small-en-v1.5` via *fastembed*) that captures the
*meaning* of a piece of text. Similar meanings give similar numbers. Code: `app/services/embedding_service.py`.

**Vector search / pgvector.** Finding the stored chunks whose embeddings are closest to the question's embedding. *pgvector*
is a PostgreSQL extension that does this inside the database. Without it (your native Windows Postgres) the app falls
back to doing the maths in Python; the two paths behave slightly differently, which is why tests use the Docker database.

**Chunk.** A short piece of a document (about 500 characters) stored with its embedding. Documents are split into chunks
so search can return just the relevant part. Table `hotel_document_chunks`.

**Top-k.** How many chunks are returned. Ours is `KNOWLEDGE_BASE_TOP_K = 8`.

**Hybrid search / keyword re-ranking.** Mixing vector similarity with plain word overlap. We tested it and it made results
slightly worse here, so it is not used. Not to be confused with cross-encoder re-ranking, below.

**Bi-encoder vs cross-encoder.** A *bi-encoder* (our embedding model) turns each text into a vector separately; texts are
compared by vector closeness. Fast, because stored chunks are embedded once in advance, but it matches topics rather than
answers. A *cross-encoder* reads the question and a chunk **together** and outputs one relevance score: much more
accurate, but it must run once per chunk per question, so it is used only on a short list.

**Re-ranking (two-stage retrieval).** Embedding search fetches 30 candidates, then a cross-encoder
(`Xenova/ms-marco-MiniLM-L-6-v2`) re-orders them and the best 8 go to Gemini. Code: `app/services/rerank_service.py`.
Full explanation: `07-reranking.md`.

**Query rewriting.** Changing the user's question into a better search text. For follow-ups ("What time does it open?")
we add the previous question. Code: `build_retrieval_query`.

**Structured vs unstructured data.** *Unstructured* = free text (policies, FAQs, descriptions): found by meaning with embeddings.
*Structured* = rows with fixed fields (prices, dates, ratings, room counts): answered by database queries (filter, sort, count, average).

**Structured RAG.** RAG over structured data: at question time the system *queries the database* and the model answers from the
exact rows. Needed for availability, "cheapest", "highest rated", counts and averages, which similarity search cannot do.
Ours: four tools in `app/services/structured_rag_service.py`. Full explanation: `06-structured-rag.md`.

**Context stuffing.** Pasting all the data into every prompt (what the catalog did). Simple, but costly, unselective and not scalable.

**Function calling / tool use.** The model is shown a menu of functions with typed parameters and may answer "call this function with
these arguments" instead of text; our code runs it and returns the result; the model then writes the final answer. A question
needing no function costs one request; one needing a lookup costs two.

**Text-to-SQL.** The model writes a SQL query itself. Flexible but hard to make safe. We use *tools* instead: the model only picks
a tool and arguments, and the queries are fixed and parameterized.

**Parameterized query / bound parameter.** Values travel to the database separately from the SQL text, so they can never be
interpreted as SQL. This is what makes `'; DROP TABLE hotels;--` harmless as an argument. (LIKE wildcards `%` and `_` are escaped too.)

**SQL injection.** Smuggling SQL commands inside input. Defeated by bound parameters (and, in this project, by never letting the model write SQL).

**SAVEPOINT.** A mini-transaction inside a transaction: if a lookup fails, only its own work is rolled back, not the guest's pending message.

**Grounding.** Making the LLM answer from supplied facts rather than from imagination. A *grounded* answer can be traced
to the prompt; a *hallucination* (invented fact) cannot.

**Citation.** The list of sources shown with an answer.

**Session.** One conversation (a `chat_sessions` row). Its messages give the chatbot memory of earlier turns.

**Rate limit / quota.** A cap on how many requests a service accepts. Gemini free tier: 15 per minute. OpenRouter free
models: ~20 per minute and **50 per day**. Exceeding gives HTTP **429**. Much of our evaluation design (pacing, caching,
resuming) exists to live within these caps.

## Measuring search (Phase 3)

**Golden dataset.** A fixed set of questions with known right answers, used to compare versions of the system fairly.
Ours: `evals/datasets/golden.jsonl`, 72 questions.

**Retrieval label.** A note on a question saying *which text should be found* (`relevant`). A retrieved chunk "counts" if
it belongs to that hotel and contains that text.

**hit@k (hit).** Fraction of questions where at least one relevant chunk is in the top k. Ours: 1.00 at k=8.

**hit@1.** Fraction where the *first* result is relevant. Ours: 0.89 overall with re-ranking (0.80 before; follow-ups 0.55 → 0.82).

**MRR (mean reciprocal rank).** Average of 1 / (position of the first relevant chunk). Rewards putting the right chunk
higher: position 1 scores 1.0, position 2 scores 0.5, position 4 scores 0.25.

**Recall.** Of all the relevant items for a question, how many were retrieved.

**Precision.** Of the chunks retrieved, how many were relevant. Low precision is normal and acceptable when you fetch 8
chunks to be sure one is right; the LLM ignores irrelevant ones.

## Measuring answers (Phase 4)

**Exact check.** A rule-based check with no AI: required words (with alternatives) and forbidden words. Cheap, repeatable,
but can be fooled (a vague answer containing the right word passes).

**LLM judge.** A second LLM that reads a question and an answer and scores it against criteria. Needed for nuance, but it
is itself random, costs quota, and tends to be lenient with answers from its own family. Ours: a *free* OpenRouter model from
NVIDIA (different vendor from the chatbot).

**Calibration.** Testing the judge on answers whose correct verdict you already know. Ours: 10/10.

**Agreement / Cohen's kappa.** How often the judge and a human agree, and a stricter version corrected for chance.
`python -m evals.judge_check`.

**DeepEval.** The Python library providing the scoring metrics and the test-case objects (`LLMTestCase`,
`ConversationalTestCase`). We plug our own judge into it.

**G-Eval.** A DeepEval metric where you describe, in plain English steps, what a good answer is; the judge follows the
steps and returns a 0-1 score. Our *Correctness*, *Behavior*, *GroundedPrices* and *Style* are G-Evals.

**Faithfulness.** DeepEval's built-in metric: is every claim in the answer supported by the supplied context? (Several judge
requests per answer; behind `--deep`.)

**Answer relevancy.** Does the answer actually address the question? (`--deep`.)

**Knowledge retention / role adherence.** Conversation-level metrics: does the bot remember what was said earlier, and
does it stay in its role as a hotel concierge? (`--deep`, follow-up cases.)

**Hallucination.** The LLM stating something that is not in the data (an invented price, a hotel that does not exist).
Targeted by *GroundedPrices*, the "fake entity" test cases, and the Faithfulness metric.

**Flaky / non-deterministic.** The same input can give a different output each run (the chatbot uses temperature 0.3).
So one run is only a sample; `--repeat 3` shows how stable a result is.

**Baseline.** The saved scores of the current good version. A change is judged against it. Stored in `evals/baselines/`.

**Regression.** A score getting worse after a change. The pytest gates fail when scores drop below the baseline.

**Free tier / cache / budget / resume.** How the judge copes with 50 requests/day: it remembers every answer on disk
(*cache*), can be told a maximum number of requests (*budget*), and when the daily limit hits it stops, keeps results,
and continues next day from where it left off (*resume*).

## Safety (Phase 6)

**Prompt injection.** Text in a user message (or a document) that tries to override the bot's rules ("ignore all previous
instructions...").

**Jailbreak.** A prompt designed to make the bot abandon its restrictions (role-play as "DAN", "developer mode").

**Prompt extraction / system prompt leak.** Tricking the bot into revealing its hidden instructions.

**Canary.** A unique fake secret (`STAFF-ONLY-CANARY-7731`) planted in data the public must never see. If it ever appears in
an answer, we know access control failed. Cheap and unambiguous.

**Red teaming.** Attacking your own system on purpose to find weaknesses before others do. `evals/redteam.py`.

**Detector.** A regular expression that recognises a failure (e.g. a password hash `$2b$...`, "has been cancelled").

**RBAC (role-based access control).** Permissions by role: admin, owner, manager, receptionist, customer. Code:
`app/api/deps.py`, `app/core/roles.py`, and hotel scoping in `app/utils/scoping_utils.py`.

**JWT.** The signed token a user receives at login and sends with each request. Anyone with the *secret key* can forge one,
which is why a hard-coded secret was a critical flaw.

## Observability (Phase 5)

**Trace / span.** A *trace* is the record of one question's journey; a *span* is one step in it (search, model call).
Spans nest: `concierge_chat` contains `knowledge_retrieval` and `gemini_generate`.

**OpenTelemetry (OTel) / OpenInference.** OTel is the industry standard for sending traces. OpenInference adds names for AI
steps (RETRIEVER, LLM, ...) and fields (`llm.token_count.total`, `retrieval.documents.N.document.content`) so tools like
Phoenix can display them well.

**Arize Phoenix.** The free open-source web app that receives and shows the traces: `http://localhost:6006`.

**Project (Phoenix).** A folder of traces. Ours: `hms` (real use) and `hms-evals` (evaluation runs).

**Annotation.** A label attached to a trace in Phoenix, e.g. `exact_checks = pass` or `judge_Correctness = 0.9`.

**Session (Phoenix).** All turns of one conversation, grouped by `session.id`.

**Redaction.** Removing the text from traces, leaving only numbers and ids (`PHOENIX_REDACT_CONTENT=true`).

## Project and tooling words

**Frozen clock.** Passing a fixed "now" so date-dependent answers (refund eligibility) do not change from day to day.

**Seed data.** The fixed fictional hotels/users/bookings the tests build (`evals/seed.py`).

**Fixture.** A pytest helper that prepares something for tests (a database session, a test client). In `conftest.py`.

**Marker (`llm`).** A label on tests that call real AI; skipped unless you pass `--run-llm`.

**Docker / compose / volume / profile.** Docker runs programs in isolated containers; `docker-compose.yml` describes
several together; a *volume* keeps data between restarts; a *profile* makes a service optional (Phoenix needs
`--profile observability`).

**Healthcheck.** A small command Docker runs to know whether a service is really working (`/health` for the app,
`/healthz` for Phoenix).

**Pinned dependency.** An exact version in `requirements.txt` (`fastapi==0.141.1`) so installs are reproducible.

**Migration (Alembic).** A tracked way to change database tables over time. **Not set up yet**; right now the app calls
`create_all()`, which creates missing tables but never alters existing ones.
