from typing import Annotated
from enum import Enum
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_staff
from app.models.booking_guest import BookingGuest
from app.models.user import User
from app.utils.scoping_utils import staff_hotel_scope, ensure_booking_in_scope
from app.schemas import booking_guest as bg_schema
from app.schemas.common import ActionResponse, SortOrder
from app.services import booking_guest_service


def _check_booking_guest_scope(db: Session, bg_id: UUID, current_user: User):
    """The companion record must belong to a booking at a hotel this user manages."""
    bg = db.query(BookingGuest).filter(BookingGuest.id == bg_id).first()
    if not bg:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")
    ensure_booking_in_scope(db, current_user, bg.booking_id)


class BookingGuestSortBy(str, Enum):
    booking_id = "booking_id"
    guest_id = "guest_id"


router = APIRouter(prefix="/booking-guests", tags=["Booking Guests"], dependencies=[Depends(require_staff)])

@router.post("", response_model=bg_schema.BookingGuestItemResponse, status_code=status.HTTP_201_CREATED)
def create_booking_guest(
    booking_guest: Annotated[bg_schema.BookingGuestCreate, Form()],
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_booking_in_scope(db, current_user, booking_guest.booking_id)
    item = booking_guest_service.create_booking_guest(db=db, booking_guest=booking_guest)
    return {"success": True, "message": "Booking guest created successfully", "data": item}

@router.get("", response_model=bg_schema.BookingGuestPaginatedResponse)
def read_booking_guests(
    booking_id: UUID | None = Query(default=None),
    guest_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: BookingGuestSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    List booking guests with advanced filtering and sorting (only bookings of the hotels you manage).
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "current_user")}
    scope = staff_hotel_scope(db, current_user)
    if scope is not None:
        query_params["_hotel_ids"] = scope
    return booking_guest_service.get_booking_guests(db=db, query_params=query_params)

@router.get("/{id}", response_model=bg_schema.BookingGuestItemResponse)
def booking_guest_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    _check_booking_guest_scope(db, id, current_user)
    item = booking_guest_service.get_booking_guest_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Booking guest retrieved successfully", "data": item}

@router.put("/{id}", response_model=bg_schema.BookingGuestItemResponse)
def update_booking_guest(
    id: UUID,
    update_data: Annotated[bg_schema.BookingGuestUpdate, Form()],
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    _check_booking_guest_scope(db, id, current_user)
    if update_data.booking_id:
        ensure_booking_in_scope(db, current_user, update_data.booking_id)
    item = booking_guest_service.update_booking_guest(db, id, update_data)
    return {"success": True, "message": "Booking guest updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_booking_guest(id: UUID, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    _check_booking_guest_scope(db, id, current_user)
    item = booking_guest_service.delete_booking_guest(db, id)
    return {"success": True, "message": "Booking guest deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=bg_schema.BookingGuestItemResponse)
def restore_booking_guest(id: UUID, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking guest.
    """
    _check_booking_guest_scope(db, id, current_user)
    item = booking_guest_service.restore_booking_guest(db, id)
    return {"success": True, "message": "Booking guest restored successfully", "data": item}

