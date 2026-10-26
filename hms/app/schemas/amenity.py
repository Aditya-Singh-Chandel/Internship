from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class AmenityBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class AmenityCreate(AmenityBase):
    pass

class AmenityItem(AmenityBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AmenityUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

from app.schemas.common import ItemResponse, PaginatedResponse

AmenityItemResponse = ItemResponse[AmenityItem]
AmenityPaginatedResponse = PaginatedResponse[AmenityItem]

class BulkAmenityItem(BaseModel):
    name: str = Field(description="Amenity name.", examples=["Free Wi-Fi"])

class BulkAmenityCreate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Hotel ID if property-level amenities.")
    room_type_id: UUID | None = Field(default=None, description="Room Type ID if room-level amenities.")
    amenities: list[BulkAmenityItem] = Field(min_length=1, description="List of amenities to create.")
