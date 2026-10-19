from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import guest as guest_schema
from app.services import guest_service


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


class GuestSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"
router = APIRouter(prefix="/guests", tags=["Guests"])

@router.post("", response_model=guest_schema.GuestListResponse, status_code=status.HTTP_201_CREATED)
def create_guest(guest: Annotated[guest_schema.GuestCreate, Form()], db: Session = Depends(get_db)):
    return {"guests": [guest_service.create_guest(db=db, guest=guest)]}

@router.get("", response_model=guest_schema.GuestListResponse)
def read_guests(
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    email: str | None = Query(default=None),
    email_op: StringFilterOperator | None = Query(default=None),
    phone: str | None = Query(default=None),
    id_document_number: str | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: GuestSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List guests with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return guest_service.get_guests(db=db, query_params=query_params)

@router.get("/{id}", response_model=guest_schema.GuestListResponse)
def guest_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"guests": [guest_service.get_guest_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=guest_schema.GuestListResponse)
def update_guest(id: uuid.UUID, update_data: Annotated[guest_schema.GuestUpdate, Form()], db: Session = Depends(get_db)):
    return {"guests": [guest_service.update_guest(db, id, update_data)]}

@router.delete("/{id}", response_model=guest_schema.GuestListResponse)
def delete_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"guests": [guest_service.delete_guest(db, id)]}

@router.post("/{id}/restore", response_model=guest_schema.GuestListResponse)
def restore_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted guest and their reviews.
    """
    return {"guests": [guest_service.restore_guest(db, id)]}
