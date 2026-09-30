import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import room as room_schema
from app.services import room_service

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.post("", response_model=room_schema.RoomListResponse, status_code=status.HTTP_201_CREATED)
def create_room(room: Annotated[room_schema.RoomCreate, Form()], db: Session = Depends(get_db)):
    return {"rooms": [room_service.create_room(db=db, room=room)]}

@router.get("", response_model=room_schema.RoomListResponse)
def read_rooms(room_type_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"rooms": room_service.get_rooms(db=db, room_type_id=room_type_id)}
@router.get("/{id}", response_model=room_schema.RoomListResponse)
def room_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"rooms": [room_service.get_room_by_id(db, id)]}

@router.put("/{id}", response_model=room_schema.RoomListResponse)
def update_room(id: uuid.UUID, update_data: Annotated[room_schema.RoomUpdate, Form()], db: Session = Depends(get_db)):
    return {"rooms": [room_service.update_room(db, id, update_data)]}

@router.delete("/{id}", response_model=room_schema.RoomListResponse)
def delete_room(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"rooms": [room_service.delete_room(db, id)]}
