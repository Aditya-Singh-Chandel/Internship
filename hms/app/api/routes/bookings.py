from typing import Annotated
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_staff
from app.models.user import User
from app.models.guest import Guest
from app.core.roles import UserRole
from app.utils.scoping_utils import get_user_guest_ids, verify_booking_access, get_or_create_guest_for_user
from app.schemas import booking as booking_schema
from app.schemas.booking import BookingStatus
from app.schemas.common import ActionResponse, SortOrder, NumericFilterOperator
from app.services import booking_service
from app.models.room_type import RoomType

from enum import Enum

class BookingSortBy(str, Enum):
    checkin_date = "checkin_date"
    checkout_date = "checkout_date"
    total_amount = "total_amount"
    created_at = "created_at"
    status = "status"

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("", response_model=booking_schema.BookingItemResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking: booking_schema.BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a master booking.
    - Customers: guest_id is automatically injected from their logged-in account if omitted.
                 hotel_id is automatically inferred from selected room items if omitted.
    - Staff (manager/receptionist): hotel_id is automatically injected from their assigned hotel if omitted.
    - Admins: unrestricted.
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"

    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        # Auto-provision/inject guest_id if omitted
        if not booking.guest_id:
            guest = get_or_create_guest_for_user(db, current_user)
            booking.guest_id = guest.id
        else:
            # Verify guest_id belongs to the customer
            guest = db.query(Guest).filter(Guest.id == booking.guest_id, Guest.deleted_at.is_(None)).first()
            if not guest or (guest.email and guest.email.strip().lower() != current_user.email.strip().lower()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only create bookings under your own verified guest account."
                )

        # Auto-infer hotel_id from selected room items if omitted
        if not booking.hotel_id:
            if booking.items:
                rt = db.query(RoomType).filter(RoomType.id == booking.items[0].room_type_id, RoomType.deleted_at.is_(None)).first()
                if not rt:
                    raise HTTPException(status_code=404, detail="Selected room type does not exist.")
                booking.hotel_id = rt.hotel_id
            else:
                raise HTTPException(status_code=400, detail="hotel_id must be provided or at least one room type item must be selected.")

    elif role_name in [UserRole.RECEPTIONIST.value, UserRole.MANAGER.value]:
        assigned_hotel_id = getattr(current_user, "hotel_id", None)
        if assigned_hotel_id:
            if not booking.hotel_id:
                booking.hotel_id = assigned_hotel_id
            elif booking.hotel_id != assigned_hotel_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only create bookings for your assigned hotel."
                )

    item = booking_service.create_booking(db=db, booking=booking)
    return {"success": True, "message": "Booking created successfully", "data": item}

@router.get("", response_model=booking_schema.BookingPaginatedResponse)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List bookings with ownership scoping:
    - Customers: automatically filtered to ONLY see their own bookings.
    - Receptionist/Manager: filtered to their assigned hotel if configured.
    - Admin: can see all bookings across all hotels.
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user", "role_name")}

    # Scoping for Customer: only their own bookings
    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        user_guest_ids = get_user_guest_ids(db, current_user)
        if not user_guest_ids:
            return {
                "success": True,
                "message": "Bookings retrieved successfully",
                "data": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }
        query_params["guest_id"] = user_guest_ids[0]

    # Scoping for Staff: lock to assigned hotel if configured
    elif role_name in [UserRole.RECEPTIONIST.value, UserRole.MANAGER.value]:
        assigned_hotel = getattr(current_user, "hotel_id", None)
        if assigned_hotel:
            query_params["hotel_id"] = assigned_hotel

    return booking_service.get_bookings(db=db, query_params=query_params)

@router.get("/{id}", response_model=booking_schema.BookingItemResponse)
def booking_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get booking by ID:
    - Customers can only view their own bookings.
    - Staff can only view bookings for their assigned hotel (if assigned).
    - Admins have full access.
    """
    booking = booking_service.get_booking_by_id(db, id, include_deleted=include_deleted)
    verify_booking_access(db, booking, current_user, action="view")
    return {"success": True, "message": "Booking retrieved successfully", "data": booking}

@router.put("/{id}", response_model=booking_schema.BookingItemResponse)
def update_booking(
    id: UUID,
    update_data: Annotated[booking_schema.BookingUpdate, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update booking details:
    - Customers can update special requests on their own bookings.
    - Staff can update any allowed fields for bookings at their assigned hotel.
    """
    booking = booking_service.get_booking_by_id(db, id)
    verify_booking_access(db, booking, current_user, action="update")

    role_name = current_user.role.name.lower() if current_user.role else "customer"
    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        data_dict = update_data.model_dump(exclude_unset=True)
        disallowed = {"status", "total_amount", "hotel_id", "guest_id"}
        if any(k in data_dict for k in disallowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers can only update special requests or personal notes."
            )

    item = booking_service.update_booking(db, id, update_data)
    return {"success": True, "message": "Booking updated successfully", "data": item}

@router.patch("/{id}/cancel", response_model=booking_schema.BookingItemResponse)
def cancel_booking(
    id: UUID,
    cancel_data: booking_schema.BookingCancelRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel an active booking (partial state transition):
    - Customers: can only cancel their own upcoming bookings.
    - Staff / Managers: can cancel bookings for their assigned hotel.
    - Owners: can cancel bookings for hotels they own.
    - Admins: unrestricted.
    Immediately releases room availability back to hotel inventory.
    """
    booking = booking_service.get_booking_by_id(db, id)
    verify_booking_access(db, booking, current_user, action="cancel")

    role_name = current_user.role.name.lower() if current_user.role else "customer"
    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        if booking.checkin_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a booking that has already started or passed."
            )

    reason = cancel_data.reason if cancel_data else None
    item = booking_service.cancel_booking(db, id, reason=reason)
    return {"success": True, "message": "Booking cancelled successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_booking(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel or delete booking:
    - Customers can cancel their own upcoming bookings.
    - Staff/Admin can cancel bookings for their assigned hotel.
    """
    booking = booking_service.get_booking_by_id(db, id)
    verify_booking_access(db, booking, current_user, action="cancel")

    role_name = current_user.role.name.lower() if current_user.role else "customer"
    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        if booking.checkin_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a booking that has already started or passed."
            )

    item = booking_service.delete_booking(db, id)
    return {"success": True, "message": "Booking deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=booking_schema.BookingItemResponse, dependencies=[Depends(require_staff)])
def restore_booking(id: UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted booking. (Staff only)
    """
    item = booking_service.restore_booking(db, id)
    return {"success": True, "message": "Booking restored successfully", "data": item}
