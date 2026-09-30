import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List, Annotated
from app.api.deps import get_db
from app.schemas import user as user_schema
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=user_schema.UserListResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: Annotated[user_schema.UserCreate, Form()], db: Session = Depends(get_db)):
    return {"users": [user_service.create_user(db=db, user=user)]}

@router.get("", response_model=user_schema.UserListResponse)
def read_users(db: Session = Depends(get_db)):
    return {"users": user_service.get_users(db=db)}
@router.get("/{id}", response_model=user_schema.UserListResponse)
def user_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"users": [user_service.get_user_by_id(db, id)]}

@router.put("/{id}", response_model=user_schema.UserListResponse)
def update_user(id: uuid.UUID, update_data: Annotated[user_schema.UserUpdate, Form()], db: Session = Depends(get_db)):
    return {"users": [user_service.update_user(db, id, update_data)]}

@router.delete("/{id}", response_model=user_schema.UserListResponse)
def delete_user(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"users": [user_service.delete_user(db, id)]}
