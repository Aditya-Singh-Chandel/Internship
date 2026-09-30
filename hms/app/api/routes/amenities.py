import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import amenity as amenity_schema
from app.services import amenity_service

router = APIRouter(prefix="/amenities", tags=["Amenities"])

@router.post("", response_model=amenity_schema.AmenityListResponse, status_code=status.HTTP_201_CREATED)
def create_amenity(amenity: Annotated[amenity_schema.AmenityCreate, Form()], db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.create_amenity(db=db, amenity=amenity)]}

@router.get("", response_model=amenity_schema.AmenityListResponse)
def read_amenities(hotel_id: UUID | None = None, room_type_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"amenities": amenity_service.get_amenities(db=db, hotel_id=hotel_id, room_type_id=room_type_id)}
@router.get("/{id}", response_model=amenity_schema.AmenityListResponse)
def amenity_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.get_amenity_by_id(db, id)]}

@router.put("/{id}", response_model=amenity_schema.AmenityListResponse)
def update_amenity(id: uuid.UUID, update_data: Annotated[amenity_schema.AmenityUpdate, Form()], db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.update_amenity(db, id, update_data)]}

@router.delete("/{id}", response_model=amenity_schema.AmenityListResponse)
def delete_amenity(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.delete_amenity(db, id)]}
