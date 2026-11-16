"""
Shared pytest setup for tests/ and evals/.

Everything runs against a separate PostgreSQL database ending in `_test` (created on demand, wiped at the
start of every session). The app reads DATABASE_URL when it is imported, so it is pointed at the test
database here, before any `app` import, and the run aborts if the name does not end in `_test`.
"""
import os
import sys

import psycopg2
import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()  # picks up JWT_SECRET_KEY / GEMINI_API_KEY from .env; DATABASE_URL is overridden below

# The tests run against the Docker pgvector database (published on host port 5433 by docker-compose.yml),
# the same search path a deployed app uses. Override with TEST_DATABASE_URL if yours differs.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5433/hms_test")
_test_url = make_url(TEST_DATABASE_URL)
TEST_DB_NAME = _test_url.database

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-production")
os.environ["DEMO_AUTOPILOT"] = "false"  # tests own their data; the demo autopilot must never touch it

# Tracing: eval runs (python -m evals.runner, evals.redteam, ...) go to their OWN Phoenix project so they never mix with
# real conversations; plain pytest runs send nothing (fake test conversations would only be noise). Set
# PHOENIX_TRACE_TESTS=1 to see pytest's LLM tests in Phoenix as well.
os.environ["PHOENIX_PROJECT_NAME"] = os.getenv("PHOENIX_EVAL_PROJECT_NAME", "hms-evals")
if "pytest" in os.path.basename(sys.argv[0]).lower() or "pytest" in " ".join(sys.argv[:2]).lower():
    if os.getenv("PHOENIX_TRACE_TESTS") != "1":
        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = ""


def _ensure_test_database() -> None:
    admin = psycopg2.connect(
        dbname="postgres", user=_test_url.username, password=_test_url.password,
        host=_test_url.host, port=_test_url.port,
    )
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    admin.close()


_ensure_test_database()

from app.core.database import db_class, engine, session_maker  # noqa: E402  (must come after the env override)
import app.main  # noqa: E402,F401  (registers every model on db_class.metadata)

assert engine.url.database.endswith("_test"), f"Refusing to run tests against {engine.url.database!r}"


@pytest.fixture(scope="session")
def seeded_db():
    """Fresh schema + the deterministic seed data from evals/seed.py, shared by the whole session."""
    from evals.seed import seed_database

    # users <-> hotels reference each other, so drop_all() cannot order the drops: reset the whole schema instead
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db_class.metadata.create_all(bind=engine)
    with session_maker() as db:
        seed_database(db)
    return True


@pytest.fixture()
def db(seeded_db):
    with session_maker() as session:
        yield session
        session.rollback()


@pytest.fixture(scope="session")
def client(seeded_db):
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def pytest_addoption(parser):
    parser.addoption("--run-llm", action="store_true", default=False, help="also run tests that call the real Gemini API")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-llm"):
        return
    skip = pytest.mark.skip(reason="calls the real LLM: pass --run-llm to include it")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)
