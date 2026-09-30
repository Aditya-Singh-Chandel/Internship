import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List, Annotated
from app.api.deps import get_db
from app.schemas import guest as guest_schema
from app.services import guest_service

router = APIRouter(prefix="/guests", tags=["Guests"])

@router.post("", response_model=guest_schema.GuestListResponse, status_code=status.HTTP_201_CREATED)
def create_guest(guest: Annotated[guest_schema.GuestCreate, Form()], db: Session = Depends(get_db)):
    return {"guests": [guest_service.create_guest(db=db, guest=guest)]}

@router.get("", response_model=guest_schema.GuestListResponse)
def read_guests(db: Session = Depends(get_db)):
    return {"guests": guest_service.get_guests(db=db)}
@router.get("/{id}", response_model=guest_schema.GuestListResponse)
def guest_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"guests": [guest_service.get_guest_by_id(db, id)]}

@router.put("/{id}", response_model=guest_schema.GuestListResponse)
def update_guest(id: uuid.UUID, update_data: Annotated[guest_schema.GuestUpdate, Form()], db: Session = Depends(get_db)):
    return {"guests": [guest_service.update_guest(db, id, update_data)]}

@router.delete("/{id}", response_model=guest_schema.GuestListResponse)
def delete_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"guests": [guest_service.delete_guest(db, id)]}
