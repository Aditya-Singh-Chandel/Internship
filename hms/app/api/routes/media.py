import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List
from uuid import UUID
from app.api.deps import get_db
from app.schemas import media as media_schema
from app.services import media_service

router = APIRouter(prefix="/media", tags=["Media"])

@router.post("", response_model=media_schema.MediaListResponse, status_code=status.HTTP_201_CREATED)
def create_media(media: Annotated[media_schema.MediaCreate, Form()], db: Session = Depends(get_db)):
    return {"media": [media_service.create_media(db=db, media=media)]}

@router.get("", response_model=media_schema.MediaListResponse)
def read_media(hotel_id: UUID | None = None, room_type_id: UUID | None = None, db: Session = Depends(get_db)):
    return {"media": media_service.get_media(db=db, hotel_id=hotel_id, room_type_id=room_type_id)}
@router.get("/{id}", response_model=media_schema.MediaListResponse)
def media_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"media": [media_service.get_media_by_id(db, id)]}

@router.put("/{id}", response_model=media_schema.MediaListResponse)
def update_media(id: uuid.UUID, update_data: Annotated[media_schema.MediaUpdate, Form()], db: Session = Depends(get_db)):
    return {"media": [media_service.update_media(db, id, update_data)]}

@router.delete("/{id}", response_model=media_schema.MediaListResponse)
def delete_media(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"media": [media_service.delete_media(db, id)]}
