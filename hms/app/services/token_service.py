import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

def hash_token(token: str) -> str:
    """
    Compute SHA-256 hash of a token string for safe database storage.
    Plaintext tokens are never stored in the database.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def store_refresh_token(db: Session, user_id: UUID, refresh_token_str: str) -> RefreshToken:
    """
    Decode expiration from the JWT refresh token, compute its SHA-256 hash,
    and persist the record in the database.
    """
    payload = decode_refresh_token(refresh_token_str)
    exp_timestamp = payload.get("exp")
    if exp_timestamp:
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_record = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(refresh_token_str),
        expires_at=expires_at,
        revoked_at=None
    )
    db.add(token_record)
    db.commit()
    db.refresh(token_record)
    return token_record

def verify_and_rotate_refresh_token(db: Session, refresh_token_str: str) -> tuple[User, str, str]:
    """
    Industry-Standard Refresh Token Verification & Rotation with Reuse Detection:
    1. Validates cryptographic signature and claims (sub, exp, token_type='refresh').
    2. Hashes token and looks up the active record in the database.
    3. If token is revoked (revoked_at is not None): Immediately revokes all user sessions (theft protection).
    4. If expired: Rejects.
    5. Rotates token: Marks old token revoked (revoked_at=now), creates & persists new refresh token + new access token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(refresh_token_str)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_uuid = UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    token_hash = hash_token(refresh_token_str)
    token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not token_record:
        # Token signature valid but never registered or purged from DB
        raise credentials_exception

    # Security: Token Reuse Detection
    if token_record.revoked_at is not None:
        # A revoked token was submitted again. This strongly indicates token theft!
        # Countermeasure: Revoke ALL active tokens belonging to this user to protect their account.
        revoke_all_user_tokens(db, user_uuid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security Alert: Revoked refresh token reused. All sessions have been terminated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Expiration check
    now = datetime.now(timezone.utc)
    token_exp = token_record.expires_at
    if token_exp.tzinfo is None:
        token_exp = token_exp.replace(tzinfo=timezone.utc)

    if now > token_exp:
        token_record.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user
    user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.id == user_uuid, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists or is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token Rotation: Revoke current refresh token with timestamp
    token_record.revoked_at = now

    # Issue fresh tokens
    role_name = user.role.name if user.role else "customer"
    new_access_token = create_access_token(subject=user.id, role=role_name)
    new_refresh_token = create_refresh_token(subject=user.id)

    # Store new refresh token in DB
    new_payload = decode_refresh_token(new_refresh_token)
    new_exp_ts = new_payload.get("exp")
    new_expires_at = datetime.fromtimestamp(new_exp_ts, tz=timezone.utc) if new_exp_ts else now

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_token),
        expires_at=new_expires_at,
        revoked_at=None
    )
    db.add(new_token_record)
    db.commit()

    return user, new_access_token, new_refresh_token

def revoke_refresh_token(db: Session, refresh_token_str: str) -> bool:
    """
    Revoke a single refresh token (used by logout).
    Returns True if found and revoked, False otherwise.
    """
    try:
        token_hash = hash_token(refresh_token_str)
        token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(timezone.utc)
            db.commit()
            return True
        return False
    except Exception:
        return False

def revoke_latest_user_token(db: Session, user_id: UUID) -> bool:
    """
    Revoke the most recent active refresh token for a user (used by 'logout-me').
    Returns True if an active token was revoked, False otherwise.
    """
    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .order_by(RefreshToken.created_at.desc())
        .first()
    )
    if token:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False

def revoke_all_user_tokens(db: Session, user_id: UUID) -> int:
    """
    Revoke all active refresh tokens for a user (used by logout-all or security alerts).
    Returns the count of revoked tokens.
    """
    now = datetime.now(timezone.utc)
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({"revoked_at": now})
    )
    db.commit()
    return count

