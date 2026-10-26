from typing import Annotated
from enum import Enum
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_staff
from app.schemas import booking_guest as bg_schema
from app.schemas.common import ActionResponse, SortOrder
from app.services import booking_guest_service


class BookingGuestSortBy(str, Enum):
    booking_id = "booking_id"
    guest_id = "guest_id"


router = APIRouter(prefix="/booking-guests", tags=["Booking Guests"], dependencies=[Depends(require_staff)])

@router.post("", response_model=bg_schema.BookingGuestItemResponse, status_code=status.HTTP_201_CREATED)
def create_booking_guest(booking_guest: Annotated[bg_schema.BookingGuestCreate, Form()], db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
    """
    List booking guests with advanced filtering and sorting.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k != "db"}
    return booking_guest_service.get_booking_guests(db=db, query_params=query_params)

@router.get("/{id}", response_model=bg_schema.BookingGuestItemResponse)
def booking_guest_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = booking_guest_service.get_booking_guest_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Booking guest retrieved successfully", "data": item}

@router.put("/{id}", response_model=bg_schema.BookingGuestItemResponse)
def update_booking_guest(id: UUID, update_data: Annotated[bg_schema.BookingGuestUpdate, Form()], db: Session = Depends(get_db)):
    item = booking_guest_service.update_booking_guest(db, id, update_data)
    return {"success": True, "message": "Booking guest updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_booking_guest(id: UUID, db: Session = Depends(get_db)):
    item = booking_guest_service.delete_booking_guest(db, id)
    return {"success": True, "message": "Booking guest deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=bg_schema.BookingGuestItemResponse)
def restore_booking_guest(id: UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking guest.
    """
    item = booking_guest_service.restore_booking_guest(db, id)
    return {"success": True, "message": "Booking guest restored successfully", "data": item}

