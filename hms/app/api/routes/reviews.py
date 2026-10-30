from typing import Annotated
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_db, get_current_user, require_manager
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.booking_room import BookingRoom
from app.models.booking_guest import BookingGuest
from app.core.roles import UserRole
from app.utils.scoping_utils import verify_review_access, get_or_create_guest_for_user, get_user_guest_ids
from app.schemas import review as review_schema
from app.schemas.common import ActionResponse, SortOrder, NumericFilterOperator
from app.services import review_service

from enum import Enum

class ReviewSortBy(str, Enum):
    rating = "rating"
    created_at = "created_at"

router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("", response_model=review_schema.ReviewItemResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review: Annotated[review_schema.ReviewCreate, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a hotel review:
    - Automatically links the review to the verified guest identity of the signed-in user.
    - Validates that the signed-in user is associated with this booking (as primary booker,
      resident room guest, or companion guest).
    - If user is signed in under a different identity (e.g. manager or different guest), returns
      an informative 403 Forbidden explaining the account mismatch.
    """
    booking = db.query(Booking).options(
        joinedload(Booking.guest),
        joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms).joinedload(BookingRoom.guest)
    ).filter(Booking.id == review.booking_id, Booking.deleted_at.is_(None)).first()

    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")

    # Find all guest profiles corresponding to current user
    user_guest_ids = get_user_guest_ids(db, current_user)
    primary_guest = get_or_create_guest_for_user(db, current_user)
    if primary_guest.id not in user_guest_ids:
        user_guest_ids.append(primary_guest.id)

    user_email = current_user.email.strip().lower()

    # Determine if user is associated with this booking
    is_primary = (booking.guest_id in user_guest_ids) or (
        booking.guest and booking.guest.email and booking.guest.email.strip().lower() == user_email
    )

    room_resident_guest_id = None
    for bi in (booking.booking_items or []):
        for br in (bi.booking_rooms or []):
            if br.guest_id in user_guest_ids:
                room_resident_guest_id = br.guest_id
                break
            if br.guest and br.guest.email and br.guest.email.strip().lower() == user_email:
                room_resident_guest_id = br.guest_id
                break

    companion_guest = db.query(BookingGuest).filter(
        BookingGuest.booking_id == booking.id,
        BookingGuest.guest_id.in_(user_guest_ids),
        BookingGuest.deleted_at.is_(None)
    ).first()

    if is_primary:
        effective_guest_id = booking.guest_id
    elif room_resident_guest_id:
        effective_guest_id = room_resident_guest_id
    elif companion_guest:
        effective_guest_id = companion_guest.guest_id
    else:
        booking_guest_name = booking.guest.name if booking.guest else "another guest"
        booking_guest_email = booking.guest.email if booking.guest else "a different email address"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You are signed in as '{current_user.email}', but this reservation was booked by '{booking_guest_name}' ({booking_guest_email}). Only the verified resident guest who completed this stay can submit a review."
        )

    # Set review.guest_id to the verified resident guest on this booking
    review.guest_id = effective_guest_id

    item = review_service.create_review(db=db, review=review)
    return {"success": True, "message": "Review submitted successfully", "data": item}

@router.get("", response_model=review_schema.ReviewPaginatedResponse)
def read_reviews(
    hotel_id: UUID | None = Query(default=None, description="Filter reviews for a specific hotel"),
    guest_id: UUID | None = Query(default=None),
    booking_id: UUID | None = Query(default=None),
    rating: int | None = Query(default=None),
    rating_op: NumericFilterOperator | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: ReviewSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    Public catalog: List reviews with advanced filtering and sorting.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return review_service.get_reviews(db=db, query_params=query_params)

@router.get("/{id}", response_model=review_schema.ReviewItemResponse)
def review_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    """Public: View review by ID."""
    item = review_service.get_review_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Review retrieved successfully", "data": item}

@router.put("/{id}", response_model=review_schema.ReviewItemResponse)
def update_review(
    id: UUID,
    update_data: Annotated[review_schema.ReviewUpdate, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update review:
    - Authors can edit their own reviews.
    - Managers/Admins can edit reviews.
    """
    review = review_service.get_review_by_id(db, id)
    verify_review_access(db, review, current_user, action="edit")
    item = review_service.update_review(db, id, update_data)
    return {"success": True, "message": "Review updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_review(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete review:
    - Authors can delete their own reviews.
    - Managers & Admins can moderate/delete any review.
    """
    review = review_service.get_review_by_id(db, id)
    verify_review_access(db, review, current_user, action="delete")
    item = review_service.delete_review(db, id)
    return {"success": True, "message": "Review deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=review_schema.ReviewItemResponse, dependencies=[Depends(require_manager)])
def restore_review(id: UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted review. (Managers & Admins only)
    """
    item = review_service.restore_review(db, id)
    return {"success": True, "message": "Review restored successfully", "data": item}
