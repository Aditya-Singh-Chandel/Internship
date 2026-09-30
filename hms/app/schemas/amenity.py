from pydantic import BaseModel, Field
from uuid import UUID

class AmenityBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])

class AmenityCreate(AmenityBase):
    pass

class AmenityItem(AmenityBase):
    id: UUID

class AmenityListResponse(BaseModel):
    amenities: list[AmenityItem] = Field(description="Valid value for amenities.", examples=[""])

class AmenityUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
