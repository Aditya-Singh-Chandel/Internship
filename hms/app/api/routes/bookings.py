import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import booking as booking_schema
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("", response_model=booking_schema.BookingListResponse, status_code=status.HTTP_201_CREATED)
def create_booking(booking: Annotated[booking_schema.BookingCreate, Form()], db: Session = Depends(get_db)):
    return {"bookings": [booking_service.create_booking(db=db, booking=booking)]}

@router.get("", response_model=booking_schema.BookingListResponse)
def read_bookings(guest_id: UUID | None = None, hotel_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"bookings": booking_service.get_bookings(db=db, guest_id=guest_id, hotel_id=hotel_id)}
@router.get("/{id}", response_model=booking_schema.BookingListResponse)
def booking_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"bookings": [booking_service.get_booking_by_id(db, id)]}

@router.put("/{id}", response_model=booking_schema.BookingListResponse)
def update_booking(id: uuid.UUID, update_data: Annotated[booking_schema.BookingUpdate, Form()], db: Session = Depends(get_db)):
    return {"bookings": [booking_service.update_booking(db, id, update_data)]}

@router.delete("/{id}", response_model=booking_schema.BookingListResponse)
def delete_booking(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"bookings": [booking_service.delete_booking(db, id)]}
