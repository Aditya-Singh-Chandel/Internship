from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import booking_guest as bg_schema
from app.services import booking_guest_service


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


class BookingGuestSortBy(str, Enum):
    booking_id = "booking_id"
    guest_id = "guest_id"
router = APIRouter(prefix="/booking-guests", tags=["Booking Guests"])

@router.post("", response_model=bg_schema.BookingGuestListResponse, status_code=status.HTTP_201_CREATED)
def create_booking_guest(booking_guest: Annotated[bg_schema.BookingGuestCreate, Form()], db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.create_booking_guest(db=db, booking_guest=booking_guest)]}

@router.get("", response_model=bg_schema.BookingGuestListResponse)
def read_booking_guests(
    booking_id: UUID | None = Query(default=None),
    guest_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: BookingGuestSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List booking guests with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return booking_guest_service.get_booking_guests(db=db, query_params=query_params)

@router.get("/{id}", response_model=bg_schema.BookingGuestListResponse)
def booking_guest_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"booking_guests": [booking_guest_service.get_booking_guest_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=bg_schema.BookingGuestListResponse)
def update_booking_guest(id: uuid.UUID, update_data: Annotated[bg_schema.BookingGuestUpdate, Form()], db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.update_booking_guest(db, id, update_data)]}

@router.delete("/{id}", response_model=bg_schema.BookingGuestListResponse)
def delete_booking_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.delete_booking_guest(db, id)]}

@router.post("/{id}/restore", response_model=bg_schema.BookingGuestListResponse)
def restore_booking_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking guest.
    """
    return {"booking_guests": [booking_guest_service.restore_booking_guest(db, id)]}
