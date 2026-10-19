from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from decimal import Decimal

class RoomTypeBase(BaseModel):
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    base_price: Decimal = Field(..., ge=0, description="Valid value for base price.", examples=[""])
    guests_allowed: int = Field(..., ge=1, description="Valid value for guests allowed.", examples=[""])
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])

class RoomTypeCreate(RoomTypeBase):
    pass

from datetime import datetime

class RoomTypeItem(RoomTypeBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    description: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
    base_price: Decimal | None = Field(default=None, ge=0, description="Valid value for base price.", examples=[""])
    guests_allowed: int | None = Field(default=None, ge=1, description="Valid value for guests allowed.", examples=[""])
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])

class RoomTypeListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    room_types: list[RoomTypeItem]

    model_config = ConfigDict(from_attributes=True)
