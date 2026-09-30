import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List, Annotated
from uuid import UUID
from app.api.deps import get_db
from app.schemas import booking_guest as bg_schema
from app.services import booking_guest_service

router = APIRouter(prefix="/booking-guests", tags=["Booking Guests"])

@router.post("", response_model=bg_schema.BookingGuestListResponse, status_code=status.HTTP_201_CREATED)
def create_booking_guest(booking_guest: Annotated[bg_schema.BookingGuestCreate, Form()], db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.create_booking_guest(db=db, booking_guest=booking_guest)]}

@router.get("/{booking_id}", response_model=bg_schema.BookingGuestListResponse)
def read_booking_guests(booking_id: UUID, db: Session = Depends(get_db)):
    return {"booking_guests": booking_guest_service.get_booking_guests(db=db, booking_id=booking_id)}
@router.get("/{id}", response_model=bg_schema.BookingGuestListResponse)
def booking_guest_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.get_booking_guest_by_id(db, id)]}

@router.put("/{id}", response_model=bg_schema.BookingGuestListResponse)
def update_booking_guest(id: uuid.UUID, update_data: Annotated[bg_schema.BookingGuestUpdate, Form()], db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.update_booking_guest(db, id, update_data)]}

@router.delete("/{id}", response_model=bg_schema.BookingGuestListResponse)
def delete_booking_guest(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"booking_guests": [booking_guest_service.delete_booking_guest(db, id)]}
