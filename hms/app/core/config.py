import os
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}. See .env.example.")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


class Settings:
    DATABASE_URL: str = _require_env("DATABASE_URL")

    # JWT & Auth configuration (no default secret: a committed fallback lets anyone forge tokens)
    JWT_SECRET_KEY: str = _require_env("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))        # 7 days

    # Set to true when served over HTTPS so the refresh cookie is never sent in plain text
    COOKIE_SECURE: bool = _env_bool("COOKIE_SECURE", False)

    # Comma-separated list of frontend origins allowed to call the API
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if origin.strip()
    ]

    # Knowledge-base re-ranking (app/services/rerank_service.py): vector search fetches RERANK_CANDIDATES chunks,
    # then a local cross-encoder re-orders them and keeps the best top_k. Set RERANK_ENABLED=false to skip it.
    RERANK_ENABLED: bool = _env_bool("RERANK_ENABLED", True)
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
    RERANK_CANDIDATES: int = int(os.getenv("RERANK_CANDIDATES", "20"))
    # The re-ranker reads only the first N characters of each chunk (title included). Long chunks (e.g. the reviews list)
    # otherwise pad the whole batch to 512 tokens: on the real database 600 was both faster and more accurate than no cap.
    RERANK_MAX_CHARS: int = int(os.getenv("RERANK_MAX_CHARS", "600"))

    # Demo database autopilot (scripts/demo_autopilot.py): does the daily check-ins, check-outs, room allocation, new
    # bookings and reviews a live hotel would have, so demo data never goes stale. Off unless set; never on *_test DBs.
    DEMO_AUTOPILOT: bool = _env_bool("DEMO_AUTOPILOT", False)
    DEMO_AUTOPILOT_INTERVAL_HOURS: float = float(os.getenv("DEMO_AUTOPILOT_INTERVAL_HOURS", "3"))

settings = Settings()
