from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.core.database import session_maker
from app.core.security import decode_access_token
from app.core.roles import UserRole, RoleGroup
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def get_db():
    db = session_maker()
    try:
        yield db
    finally:
        db.close()

# ----------------- Authentication -----------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception
        user_uuid = UUID(user_id)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.id == user_uuid, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise credentials_exception

    return user

def get_optional_current_user(
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db)
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return (
            db.query(User)
            .options(joinedload(User.role))
            .filter(User.id == UUID(user_id), User.deleted_at.is_(None))
            .first()
        )
    except (jwt.PyJWTError, ValueError):
        return None

# ----------------- Authorization / RBAC -----------------
def require_roles(allowed_roles: list[str | UserRole]):
    """
    Higher-order dependency function enforcing Role-Based Access Control (RBAC).
    Returns a dependency function that validates whether the authenticated user has an authorized role.
    """
    normalized_roles = [
        r.value.lower() if isinstance(r, UserRole) else str(r).lower()
        for r in allowed_roles
    ]

    def role_verifier(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.role or current_user.role.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no active role assigned."
            )

        user_role_name = (current_user.role.name or "").strip().lower()
        if user_role_name not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {normalized_roles}. Your role is '{user_role_name}'."
            )
        return current_user

    return role_verifier

# Pre-configured RBAC dependencies for clean use in route signatures:
require_admin = require_roles(RoleGroup.ADMIN_ONLY)
require_owner = require_roles(RoleGroup.OWNER_ADMIN)         # Admin or Owner (can create and own hotels)
require_manager = require_roles(RoleGroup.MANAGEMENT)       # Admin, Owner, or Manager (hotel configuration)
require_staff = require_roles(RoleGroup.STAFF)             # Admin, Owner, Manager, or Receptionist (operations)
require_authenticated = require_roles(RoleGroup.AUTHENTICATED) # Any logged-in user