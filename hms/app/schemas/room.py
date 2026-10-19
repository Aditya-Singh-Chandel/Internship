from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID
from enum import Enum

class RoomStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"
    cleaned = "cleaned"

class RoomBase(BaseModel):
    room_type_id: UUID = Field(description="Valid value for room type id.", examples=[""])
    room_number: str = Field(description="Assigned room number or identifier.", examples=[""])
    floor: int | None = Field(default=None, ge=-10, le=200, description="Floor number as an integer.", examples=[1])
    status: RoomStatus | None = Field(default=RoomStatus.available, description="Current status (e.g., available, occupied, maintenance, cleaned).", examples=[""])

    @field_validator("room_number", mode="before")
    @classmethod
    def validate_room_number(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("room_number cannot be empty or whitespace only.")
        return v

    @field_validator("floor", mode="before")
    def validate_floor_empty(cls, v):
        if v == "" or v is None:
            return None
        return v

class RoomCreate(RoomBase):
    pass

from datetime import datetime

class RoomItem(RoomBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RoomUpdate(BaseModel):
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    room_number: str | None = Field(default=None, description="Assigned room number or identifier.", examples=[""])
    floor: int | None = Field(default=None, ge=-10, le=200, description="Floor number as an integer.", examples=[1])
    status: RoomStatus | None = Field(default=None, description="Current status (e.g., active, completed, confirmed).", examples=[""])

    @field_validator("room_number", mode="before")
    @classmethod
    def validate_room_number(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("room_number cannot be empty or whitespace only.")
        return v

    @field_validator("floor", mode="before")
    @classmethod
    def validate_floor_empty(cls, v):
        if v == "" or v is None:
            return None
        return v

class RoomListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    rooms: list[RoomItem]

    model_config = ConfigDict(from_attributes=True)

class BulkRoomItem(BaseModel):
    room_number: str = Field(description="Assigned room number or identifier.", examples=["101"])
    floor: int | None = Field(default=None, ge=-10, le=200, description="Floor number as an integer.", examples=[1])
    status: RoomStatus = Field(default=RoomStatus.available, description="Status: available, occupied, maintenance, cleaned. Defaults to 'available'.")

    @field_validator("room_number", mode="before")
    @classmethod
    def validate_room_number(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("room_number cannot be empty or whitespace only.")
        return v

    @field_validator("floor", mode="before")
    @classmethod
    def validate_floor_empty(cls, v):
        if v == "" or v is None:
            return None
        return v

class BulkRoomCreate(BaseModel):
    room_type_id: UUID = Field(description="Room category ID for all rooms in this batch.")
    rooms: list[BulkRoomItem] = Field(min_length=1, description="List of rooms to create.")
