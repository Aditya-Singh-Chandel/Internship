from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class AmenityBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class AmenityCreate(AmenityBase):
    pass

from datetime import datetime

class AmenityItem(AmenityBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AmenityUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class AmenityListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    amenities: list[AmenityItem]

    model_config = ConfigDict(from_attributes=True)

class BulkAmenityItem(BaseModel):
    name: str = Field(description="Amenity name.", examples=["Free Wi-Fi"])

class BulkAmenityCreate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Hotel ID if property-level amenities.")
    room_type_id: UUID | None = Field(default=None, description="Room Type ID if room-level amenities.")
    amenities: list[BulkAmenityItem] = Field(min_length=1, description="List of amenities to create.")
