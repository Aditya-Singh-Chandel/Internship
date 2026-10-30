from typing import Annotated
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_staff
from app.models.user import User
from app.models.booking import Booking
from app.models.booking_room import BookingRoom
from app.models.booking_item import BookingItem
from app.schemas import booking_room as br_schema
from app.schemas.common import ItemResponse, ActionResponse
from app.services import booking_room_service

router = APIRouter(prefix="/booking-rooms", tags=["Booking Rooms"], dependencies=[Depends(require_staff)])

def _check_booking_room_ownership(db: Session, br_id: UUID, current_user: User):
    if not current_user.hotel_id:
        return
    br = db.query(BookingRoom).filter(BookingRoom.id == br_id).first()
    if not br:
        raise HTTPException(status_code=404, detail="Booking room not found.")
    booking = db.query(Booking).filter(Booking.id == br.booking_id).first()
    if booking and booking.hotel_id != current_user.hotel_id:
        raise HTTPException(status_code=403, detail="Access denied. You can only manage rooms for your assigned hotel.")

@router.post("", response_model=br_schema.BookingRoomItemResponse, status_code=status.HTTP_201_CREATED)
def create_booking_room(
    booking_room: Annotated[br_schema.BookingRoomCreate, Form()],
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Assign a single physical room to a line item using form-data.
    """
    target_booking_id = booking_room.booking_id
    if not target_booking_id and booking_room.booking_item_id:
        item = db.query(BookingItem).filter(BookingItem.id == booking_room.booking_item_id).first()
        if item:
            target_booking_id = item.booking_id

    if current_user.hotel_id and target_booking_id:
        booking = db.query(Booking).filter(Booking.id == target_booking_id).first()
        if booking and booking.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only manage bookings for your assigned hotel.")
    item = booking_room_service.create_booking_room(db, booking_room)
    return {"success": True, "message": "Booking room assigned successfully", "data": item}

@router.post("/bulk", response_model=ItemResponse[list[br_schema.BookingRoomItem]], status_code=status.HTTP_201_CREATED)
def bulk_assign_rooms(
    payload: br_schema.BulkRoomAssignmentRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Bulk assigns multiple physical room numbers to line items in a single atomic request.
    """
    if current_user.hotel_id and payload.assignments:
        first_item = db.query(BookingItem).filter(BookingItem.id == payload.assignments[0].booking_item_id).first()
        booking = first_item.booking if first_item else None
        if booking and booking.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only manage bookings for your assigned hotel.")
    assigned = booking_room_service.bulk_assign_rooms(db=db, req=payload)
    return {"success": True, "message": f"{len(assigned)} rooms assigned successfully", "data": assigned}

@router.get("", response_model=br_schema.BookingRoomPaginatedResponse)
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
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    return booking_room_service.get_booking_rooms(db, query_params)

@router.get("/{id}", response_model=br_schema.BookingRoomItemResponse)
def get_booking_room_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.get_booking_room_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Booking room retrieved successfully", "data": item}

@router.put("/{id}", response_model=br_schema.BookingRoomItemResponse)
def update_booking_room(
    id: UUID,
    update_data: Annotated[br_schema.BookingRoomUpdate, Form()],
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Update a single booking room assignment using form-data.
    """
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.update_booking_room(db, id, update_data)
    return {"success": True, "message": "Booking room updated successfully", "data": item}

@router.patch("/{id}/checkin", response_model=br_schema.BookingRoomItemResponse)
def checkin_room(
    id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Check-in this specific room and resident guest independently.
    Sets status to 'checked_in', records checked_in_at timestamp, marks Room occupied,
    and updates parent booking status to 'in_house'.
    """
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.check_in_booking_room(db, id)
    return {"success": True, "message": "Room checked in successfully", "data": item}

@router.patch("/{id}/checkout", response_model=br_schema.BookingRoomItemResponse)
def checkout_room(
    id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Check-out this specific room independently.
    Sets status to 'checked_out', records checked_out_at timestamp, and frees the Room.
    If all rooms in master booking are checked out, marks master booking completed.
    """
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.check_out_booking_room(db, id)
    return {"success": True, "message": "Room checked out successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_booking_room(
    id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.delete_booking_room(db, id)
    return {"success": True, "message": "Booking room deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=br_schema.BookingRoomItemResponse)
def restore_booking_room(
    id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted booking room and its associated companion guests.
    """
    _check_booking_room_ownership(db, id, current_user)
    item = booking_room_service.restore_booking_room(db, id)
    return {"success": True, "message": "Booking room restored successfully", "data": item}
