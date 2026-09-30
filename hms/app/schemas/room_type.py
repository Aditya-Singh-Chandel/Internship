from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal

class RoomTypeBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    base_price: Decimal = Field(description="Valid value for base price.", examples=[""])
    guests_allowed: int = Field(description="Valid value for guests allowed.", examples=[""])
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])

class RoomTypeCreate(RoomTypeBase):
    pass

class RoomTypeItem(RoomTypeBase):
    id: UUID

class RoomTypeListResponse(BaseModel):
    room_types: list[RoomTypeItem]

class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    base_price: Decimal | None = Field(default=None, description="Valid value for base price.", examples=[""])
    guests_allowed: int | None = Field(default=None, description="Valid value for guests allowed.", examples=[""])
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
