from pydantic import BaseModel, Field
from uuid import UUID

class RoomBase(BaseModel):
    room_type_id: UUID = Field(description="Valid value for room type id.", examples=[""])
    room_number: str = Field(description="Assigned room number or identifier.", examples=[""])
    floor: str | None = Field(default=None, description="Floor number or identifier.", examples=[""])
    status: str | None = Field(default="available", description="Current status (e.g., active, completed, confirmed).", examples=[""])

class RoomCreate(RoomBase):
    pass

class RoomItem(RoomBase):
    id: UUID

class RoomListResponse(BaseModel):
    rooms: list[RoomItem]

class RoomUpdate(BaseModel):
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    room_number: str | None = Field(default=None, description="Assigned room number or identifier.", examples=[""])
    floor: str | None = Field(default=None, description="Floor number or identifier.", examples=[""])
    status: str | None = Field(default=None, description="Current status (e.g., active, completed, confirmed).", examples=[""])
