from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import review as review_schema
from app.services import review_service


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


class ReviewSortBy(str, Enum):
    rating = "rating"
    created_at = "created_at"
router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("", response_model=review_schema.ReviewListResponse, status_code=status.HTTP_201_CREATED)
def create_review(review: Annotated[review_schema.ReviewCreate, Form()], db: Session = Depends(get_db)):
    return {"reviews": [review_service.create_review(db=db, review=review)]}

@router.get("", response_model=review_schema.ReviewListResponse)
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
    List reviews with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return review_service.get_reviews(db=db, query_params=query_params)

@router.get("/{id}", response_model=review_schema.ReviewListResponse)
def review_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"reviews": [review_service.get_review_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=review_schema.ReviewListResponse)
def update_review(id: uuid.UUID, update_data: Annotated[review_schema.ReviewUpdate, Form()], db: Session = Depends(get_db)):
    return {"reviews": [review_service.update_review(db, id, update_data)]}

@router.delete("/{id}", response_model=review_schema.ReviewListResponse)
def delete_review(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"reviews": [review_service.delete_review(db, id)]}

@router.post("/{id}/restore", response_model=review_schema.ReviewListResponse)
def restore_review(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted review.
    """
    return {"reviews": [review_service.restore_review(db, id)]}
