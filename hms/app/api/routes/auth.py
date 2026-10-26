from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_optional_current_user
from app.core.roles import UserRole
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.models.user import User
from app.schemas.token import Token, RefreshTokenRequest
from app.schemas.user import UserItem, UserRegister, AdminInitRequest
from app.schemas.common import ItemResponse, ActionResponse
from app.services import user_service, role_service, token_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _token_response(user: User, access_token: str, refresh_token: str, message: str) -> dict:
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }
    return {
        "success": True,
        "message": message,
        "data": payload,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }

@router.post("/login", response_model=Token, summary="OAuth2 compatible login (Form-encoded)")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 password login compatible with Swagger UI's 'Authorize' button.
    Accepts `username` (email) and `password` as form data.
    Returns a short-lived stateless access_token and a database-tracked refresh_token.
    """
    user = user_service.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role_name = user.role.name if user.role else "customer"
    access_token = create_access_token(subject=user.id, role=role_name)
    refresh_token = create_refresh_token(subject=user.id)
    token_service.store_refresh_token(db=db, user_id=user.id, refresh_token_str=refresh_token)

    return _token_response(user, access_token, refresh_token, "Login successful")

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED, summary="Register new user")
def register(
    user_in: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account. Defaults to 'customer' role if no role_id is provided.
    Immediately returns an access token and database-persisted refresh token.
    """
    user = user_service.register_user(db=db, user_data=user_in)
    role_name = user.role.name if user.role else "customer"
    access_token = create_access_token(subject=user.id, role=role_name)
    refresh_token = create_refresh_token(subject=user.id)
    token_service.store_refresh_token(db=db, user_id=user.id, refresh_token_str=refresh_token)

    return _token_response(user, access_token, refresh_token, "User registered successfully")

@router.post("/refresh", response_model=Token, summary="Refresh access token using a valid refresh token")
def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Exchange a valid refresh token for a brand new access token and rotated refresh token.
    Performs token reuse detection, revocation check, and expiration check against PostgreSQL.
    """
    user, new_access_token, new_refresh_token = token_service.verify_and_rotate_refresh_token(
        db=db,
        refresh_token_str=refresh_data.refresh_token
    )
    return _token_response(user, new_access_token, new_refresh_token, "Token refreshed successfully")

@router.post("/logout", response_model=ActionResponse, summary="Log out session (via refresh token or Bearer token)")
def logout(
    refresh_data: RefreshTokenRequest | None = None,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Log out:
    - If a `refresh_token` JSON body is passed, revokes that specific token.
    - If logged in with `Authorization: Bearer <token>`, revokes the user's active session.
    """
    if refresh_data and refresh_data.refresh_token:
        revoked = token_service.revoke_refresh_token(db=db, refresh_token_str=refresh_data.refresh_token)
        return {
            "success": True,
            "message": "Successfully logged out. Refresh token revoked." if revoked else "Refresh token already revoked or invalid.",
            "data": {"revoked": revoked}
        }
    elif current_user:
        token_service.revoke_latest_user_token(db=db, user_id=current_user.id)
        return {
            "success": True,
            "message": "Successfully logged out. Active session revoked.",
            "data": {"user": current_user.email}
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide either a 'refresh_token' in the request body or authenticate using 'Authorization: Bearer <token>'."
        )

@router.post("/logout-me", response_model=ActionResponse, summary="Instant one-click logout for currently authenticated user")
def logout_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Instantly logs out the current authenticated user by revoking their active refresh session.
    Requires only your Bearer access token — no request body needed!
    """
    token_service.revoke_latest_user_token(db=db, user_id=current_user.id)
    return {
        "success": True,
        "message": "Successfully logged out. Your active session has been terminated.",
        "data": {"user": current_user.email}
    }

@router.post("/logout-all", response_model=ActionResponse, summary="Log out from all devices / sessions")
def logout_all_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke all active refresh tokens for the authenticated user across all devices.
    """
    count = token_service.revoke_all_user_tokens(db=db, user_id=current_user.id)
    return {
        "success": True,
        "message": f"Successfully logged out of all devices ({count} active sessions terminated).",
        "data": {"revoked_count": count}
    }

@router.get("/me", response_model=ItemResponse[UserItem], summary="Get current logged-in user profile")
def read_current_user(current_user: User = Depends(get_current_user)):
    """
    Fetch the profile of the currently authenticated user.
    """
    return {
        "success": True,
        "message": "Current user profile retrieved successfully",
        "data": current_user
    }

@router.get("/roles", response_model=ActionResponse, summary="List all available system roles and their IDs")
def list_roles_public(db: Session = Depends(get_db)):
    """
    Publicly accessible list of available HMS roles and their UUIDs.
    Frontends and developers can use this to discover role IDs.
    """
    roles = role_service.ensure_default_roles(db)
    return {
        "success": True,
        "message": "Roles retrieved successfully",
        "data": {
            "roles": [
                {
                    "id": str(role.id),
                    "name": role.name
                }
                for role in roles.values()
            ]
        }
    }

@router.post("/init-roles", response_model=ActionResponse, summary="Initialize default HMS roles in database")
def initialize_roles(db: Session = Depends(get_db)):
    """
    Helper utility to seed default roles (admin, manager, receptionist, customer).
    Returns each role name along with its database UUID.
    Safe to run multiple times (idempotent).
    """
    seeded = role_service.ensure_default_roles(db)
    return {
        "success": True,
        "message": "Default roles initialized successfully.",
        "data": {
            "roles": [
                {
                    "id": str(r.id),
                    "name": r.name
                }
                for r in seeded.values()
            ]
        }
    }

@router.post("/init-admin", response_model=Token, summary="Bootstrap the initial super-admin account")
def initialize_admin(
    admin_data: AdminInitRequest = None,
    db: Session = Depends(get_db)
):
    """
    Initialize the very first system administrator account.
    - If an admin account already exists in the database, this endpoint rejects the request for security.
    - If no admin exists, it seeds default roles, creates the first admin user, and returns their active JWT access token.
    """
    if admin_data is None:
        admin_data = AdminInitRequest()

    admin_role = role_service.get_or_create_role(db, UserRole.ADMIN.value)

    # Check if ANY active admin user exists
    existing_admin = db.query(User).filter(
        User.role_id == admin_role.id,
        User.deleted_at.is_(None)
    ).first()

    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An administrator account already exists ({existing_admin.email}). Please log in."
        )

    # Check if email is in use
    existing_user = db.query(User).filter(
        User.email == admin_data.email.strip().lower(),
        User.deleted_at.is_(None)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )

    new_admin = User(
        name=admin_data.name.strip(),
        email=admin_data.email.strip().lower(),
        password_hash=get_password_hash(admin_data.password),
        phone=admin_data.phone,
        role_id=admin_role.id,
        hotel_id=None
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    access_token = create_access_token(subject=new_admin.id, role=UserRole.ADMIN.value)
    refresh_token = create_refresh_token(subject=new_admin.id)
    token_service.store_refresh_token(db=db, user_id=new_admin.id, refresh_token_str=refresh_token)

    return _token_response(new_admin, access_token, refresh_token, "Admin account initialized successfully")

