import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List, Annotated
from app.api.deps import get_db
from app.schemas import hotel as hotel_schema
from app.services import hotel_service

router = APIRouter(prefix="/hotels", tags=["Hotels"])

@router.post("", response_model=hotel_schema.HotelListResponse, status_code=status.HTTP_201_CREATED)
def create_hotel(hotel: Annotated[hotel_schema.HotelCreate, Form()], db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.create_hotel(db=db, hotel=hotel)]}

@router.get("", response_model=hotel_schema.HotelListResponse)
def read_hotels(db: Session = Depends(get_db)):
    return {"hotels": hotel_service.get_hotels(db=db)}
@router.get("/{id}", response_model=hotel_schema.HotelListResponse)
def hotel_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.get_hotel_by_id(db, id)]}

@router.put("/{id}", response_model=hotel_schema.HotelListResponse)
def update_hotel(id: uuid.UUID, update_data: Annotated[hotel_schema.HotelUpdate, Form()], db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.update_hotel(db, id, update_data)]}

@router.delete("/{id}", response_model=hotel_schema.HotelListResponse)
def delete_hotel(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.delete_hotel(db, id)]}
