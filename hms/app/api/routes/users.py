from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import user as user_schema
from app.services import user_service


from enum import Enum

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class StringFilterOperator(str, Enum):
    eq = "eq"
    like = "like"

class NumericFilterOperator(str, Enum):
    eq = "eq"
    lt = "lt"
    gt = "gt"
    lte = "lte"
    gte = "gte"


class UserSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"
router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=user_schema.UserListResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: Annotated[user_schema.UserCreate, Form()], db: Session = Depends(get_db)):
    return {"users": [user_service.create_user(db=db, user=user)]}

@router.get("", response_model=user_schema.UserListResponse)
def read_users(
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    email: str | None = Query(default=None),
    email_op: StringFilterOperator | None = Query(default=None),
    phone: str | None = Query(default=None),
    role_id: UUID | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: UserSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List users with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return user_service.get_users(db=db, query_params=query_params)

@router.get("/{id}", response_model=user_schema.UserListResponse)
def user_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"users": [user_service.get_user_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=user_schema.UserListResponse)
def update_user(id: uuid.UUID, update_data: Annotated[user_schema.UserUpdate, Form()], db: Session = Depends(get_db)):
    return {"users": [user_service.update_user(db, id, update_data)]}

@router.delete("/{id}", response_model=user_schema.UserListResponse)
def delete_user(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"users": [user_service.delete_user(db, id)]}

@router.post("/{id}/restore", response_model=user_schema.UserListResponse)
def restore_user(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted user.
    """
    return {"users": [user_service.restore_user(db, id)]}
