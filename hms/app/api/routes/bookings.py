from typing import Annotated
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import booking as booking_schema
from app.schemas.booking import BookingStatus
from app.services import booking_service

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

class BookingSortBy(str, Enum):
    checkin_date = "checkin_date"
    checkout_date = "checkout_date"
    total_amount = "total_amount"
    created_at = "created_at"
    status = "status"

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("", response_model=booking_schema.BookingListResponse, status_code=status.HTTP_201_CREATED)
def create_booking(booking: booking_schema.BookingCreate, db: Session = Depends(get_db)):
    """
    Creates a master booking together with all requested room type line items in a single atomic request.
    """
    return {"bookings": [booking_service.create_booking(db=db, booking=booking)]}

@router.get("", response_model=booking_schema.BookingListResponse)
def read_bookings(
    hotel_id: UUID | None = Query(default=None),
    guest_id: UUID | None = Query(default=None),
    rooms_count: int | None = Query(default=None, ge=1),
    rooms_count_op: NumericFilterOperator | None = Query(default=None),
    checkin_date: date | None = Query(default=None),
    checkin_date_op: NumericFilterOperator | None = Query(default=None),
    checkout_date: date | None = Query(default=None),
    checkout_date_op: NumericFilterOperator | None = Query(default=None),
    total_amount: Decimal | None = Query(default=None),
    total_amount_op: NumericFilterOperator | None = Query(default=None),
    status: BookingStatus | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    month_op: NumericFilterOperator | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000),
    year_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: BookingSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List bookings with advanced filtering and sorting.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return booking_service.get_bookings(db=db, query_params=query_params)

@router.get("/{id}", response_model=booking_schema.BookingListResponse)
def booking_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"bookings": [booking_service.get_booking_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=booking_schema.BookingListResponse)
def update_booking(
    id: uuid.UUID,
    update_data: Annotated[booking_schema.BookingUpdate, Form()],
    db: Session = Depends(get_db)
):
    """
    Update booking details using form-data.
    """
    return {"bookings": [booking_service.update_booking(db, id, update_data)]}

@router.delete("/{id}", response_model=booking_schema.BookingListResponse)
def delete_booking(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"bookings": [booking_service.delete_booking(db, id)]}

@router.post("/{id}/restore", response_model=booking_schema.BookingListResponse)
def restore_booking(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking and its cascadingly deleted items, rooms, guests, and reviews.
    """
    return {"bookings": [booking_service.restore_booking(db, id)]}
