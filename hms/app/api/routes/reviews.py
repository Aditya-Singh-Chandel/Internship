import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import review as review_schema
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("", response_model=review_schema.ReviewListResponse, status_code=status.HTTP_201_CREATED)
def create_review(review: Annotated[review_schema.ReviewCreate, Form()], db: Session = Depends(get_db)):
    return {"reviews": [review_service.create_review(db=db, review=review)]}

@router.get("", response_model=review_schema.ReviewListResponse)
def read_reviews(hotel_id: UUID | None = None, guest_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"reviews": review_service.get_reviews(db=db, hotel_id=hotel_id, guest_id=guest_id)}
@router.get("/{id}", response_model=review_schema.ReviewListResponse)
def review_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"reviews": [review_service.get_review_by_id(db, id)]}

@router.put("/{id}", response_model=review_schema.ReviewListResponse)
def update_review(id: uuid.UUID, update_data: Annotated[review_schema.ReviewUpdate, Form()], db: Session = Depends(get_db)):
    return {"reviews": [review_service.update_review(db, id, update_data)]}

@router.delete("/{id}", response_model=review_schema.ReviewListResponse)
def delete_review(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"reviews": [review_service.delete_review(db, id)]}
