import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import room_type as room_type_schema
from app.services import room_type_service

router = APIRouter(prefix="/room-types", tags=["Room Types"])

@router.post("", response_model=room_type_schema.RoomTypeListResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(room_type: Annotated[room_type_schema.RoomTypeCreate, Form()], db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.create_room_type(db=db, room_type=room_type)]}

@router.get("", response_model=room_type_schema.RoomTypeListResponse)
def read_room_types(hotel_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"room_types": room_type_service.get_room_types(db=db, hotel_id=hotel_id)}
@router.get("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def room_type_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.get_room_type_by_id(db, id)]}

@router.put("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def update_room_type(id: uuid.UUID, update_data: Annotated[room_type_schema.RoomTypeUpdate, Form()], db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.update_room_type(db, id, update_data)]}

@router.delete("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def delete_room_type(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.delete_room_type(db, id)]}
