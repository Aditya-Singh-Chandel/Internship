import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import policy as policy_schema
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["Policies"])

@router.post("", response_model=policy_schema.PolicyListResponse, status_code=status.HTTP_201_CREATED)
def create_policy(policy: Annotated[policy_schema.PolicyCreate, Form()], db: Session = Depends(get_db)):
    return {"policies": [policy_service.create_policy(db=db, policy=policy)]}

@router.get("", response_model=policy_schema.PolicyListResponse)
def read_policies(hotel_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"policies": policy_service.get_policies(db=db, hotel_id=hotel_id)}
@router.get("/{id}", response_model=policy_schema.PolicyListResponse)
def policy_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"policies": [policy_service.get_policy_by_id(db, id)]}

@router.put("/{id}", response_model=policy_schema.PolicyListResponse)
def update_policy(id: uuid.UUID, update_data: Annotated[policy_schema.PolicyUpdate, Form()], db: Session = Depends(get_db)):
    return {"policies": [policy_service.update_policy(db, id, update_data)]}

@router.delete("/{id}", response_model=policy_schema.PolicyListResponse)
def delete_policy(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"policies": [policy_service.delete_policy(db, id)]}
