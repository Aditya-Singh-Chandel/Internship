import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # JWT & Auth configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "70f636ea7848576aa60346195014824346a044fcaf70a3ee97a020cfa27a45b9")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))        # 7 days

settings = Settings()
