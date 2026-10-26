import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from app.core.config import settings

def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password using bcrypt with auto-generated salt.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt password hash.
    """
    if not hashed_password or not plain_password:
        return False

    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(subject: str | Any, role: str | None = None, expires_delta: timedelta | None = None) -> str:
    """
    Generate a signed JWT access token containing subject (user_id), role, token_type='access',
    unique jti, and expiration.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "role": str(role) if role else None,
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    Generate a signed long-lived JWT refresh token containing subject (user_id),
    token_type='refresh', unique jti, and expiration.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(subject),
        "token_type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Raises jwt.PyJWTError if expired, invalid, or if token_type is 'refresh'.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("token_type") == "refresh":
        raise jwt.PyJWTError("Invalid token type: expected access token, received refresh token")
    return payload

def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a JWT refresh token.
    Raises jwt.PyJWTError if expired, invalid, or if token_type is not 'refresh'.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("token_type") != "refresh":
        raise jwt.PyJWTError("Invalid token type: expected refresh token, received access token")
    return payload
