from typing import Annotated
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, status, Form, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import booking_room as br_schema
from app.services import booking_room_service

router = APIRouter(prefix="/booking-rooms", tags=["Booking Rooms"])

@router.post("", response_model=br_schema.BookingRoomListResponse, status_code=status.HTTP_201_CREATED)
def create_booking_room(
    booking_room: Annotated[br_schema.BookingRoomCreate, Form()],
    db: Session = Depends(get_db)
):
    """
    Assign a single physical room to a line item using form-data.
    """
    return {"booking_rooms": [booking_room_service.create_booking_room(db, booking_room)]}

@router.post("/bulk", response_model=br_schema.BookingRoomListResponse, status_code=status.HTTP_201_CREATED)
def bulk_assign_rooms(
    payload: br_schema.BulkRoomAssignmentRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk assigns multiple physical room numbers to line items in a single atomic request.
    """
    assigned = booking_room_service.bulk_assign_rooms(db=db, req=payload)
    return {"booking_rooms": assigned}

@router.get("", response_model=br_schema.BookingRoomListResponse)
def read_booking_rooms(
    booking_id: UUID | None = Query(default=None),
    booking_item_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    room_id: UUID | None = Query(default=None),
    guest_id: UUID | None = Query(default=None),
    status: br_schema.BookingRoomStatus | None = Query(default=None),
    checkin_date: date | None = Query(default=None),
    checkout_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    db: Session = Depends(get_db)
):
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return booking_room_service.get_booking_rooms(db, query_params)

@router.get("/{id}", response_model=br_schema.BookingRoomListResponse)
def get_booking_room_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"booking_rooms": [booking_room_service.get_booking_room_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=br_schema.BookingRoomListResponse)
def update_booking_room(
    id: uuid.UUID,
    update_data: Annotated[br_schema.BookingRoomUpdate, Form()],
    db: Session = Depends(get_db)
):
    """
    Update a single booking room assignment using form-data.
    """
    return {"booking_rooms": [booking_room_service.update_booking_room(db, id, update_data)]}

@router.patch("/{id}/checkin", response_model=br_schema.BookingRoomListResponse)
def checkin_room(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Check-in this specific room and resident guest independently.
    Sets status to 'checked_in', records checked_in_at timestamp, marks Room occupied,
    and updates parent booking status to 'in_house'.
    """
    return {"booking_rooms": [booking_room_service.check_in_booking_room(db, id)]}

@router.patch("/{id}/checkout", response_model=br_schema.BookingRoomListResponse)
def checkout_room(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Check-out this specific room independently.
    Sets status to 'checked_out', records checked_out_at timestamp, and frees the Room.
    If all rooms in master booking are checked out, marks master booking completed.
    """
    return {"booking_rooms": [booking_room_service.check_out_booking_room(db, id)]}

@router.delete("/{id}", response_model=br_schema.BookingRoomListResponse)
def delete_booking_room(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"booking_rooms": [booking_room_service.delete_booking_room(db, id)]}

@router.post("/{id}/restore", response_model=br_schema.BookingRoomListResponse)
def restore_booking_room(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking room and its associated companion guests.
    """
    return {"booking_rooms": [booking_room_service.restore_booking_room(db, id)]}
