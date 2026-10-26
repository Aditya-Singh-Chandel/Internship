from typing import Annotated
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_manager
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.core.roles import UserRole
from app.utils.scoping_utils import verify_review_access, get_or_create_guest_for_user
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
    - Customers: guest_id is automatically injected from their logged-in account if omitted.
    - Customers can ONLY review a booking that they completed personally.
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"

    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        # Auto-provision/inject guest_id if omitted
        if not review.guest_id:
            guest = get_or_create_guest_for_user(db, current_user)
            review.guest_id = guest.id
        else:
            # Verify guest belongs to this user
            guest = db.query(Guest).filter(Guest.id == review.guest_id, Guest.deleted_at.is_(None)).first()
            if not guest or (guest.email and guest.email.strip().lower() != current_user.email.strip().lower()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only submit reviews using your own verified guest identity."
                )

        # Verify booking belongs to this guest
        booking = db.query(Booking).filter(Booking.id == review.booking_id, Booking.deleted_at.is_(None)).first()
        if not booking or booking.guest_id != guest.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only review a booking that belongs to your guest profile."
            )

    item = review_service.create_review(db=db, review=review)
    return {"success": True, "message": "Review submitted successfully", "data": item}

@router.get("", response_model=review_schema.ReviewPaginatedResponse)
def read_reviews(
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
