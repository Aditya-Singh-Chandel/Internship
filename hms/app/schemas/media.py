from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class MediaBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    image_url: str = Field(description="Valid value for image url.", examples=[""])
    is_primary: bool | None = Field(default=False, description="Valid value for is primary.", examples=[""])

class MediaCreate(MediaBase):
    pass

from datetime import datetime

class MediaItem(MediaBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MediaUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    image_url: str | None = Field(default=None, description="Valid value for image url.", examples=[""])
    is_primary: bool | None = Field(default=None, description="Valid value for is primary.", examples=[""])

class MediaListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    media: list[MediaItem]

    model_config = ConfigDict(from_attributes=True)

class BulkMediaItem(BaseModel):
    image_url: str = Field(description="Valid URL for image.", examples=["https://example.com/photo.jpg"])
    is_primary: bool | None = Field(default=False, description="Whether this image is primary for the entity.")

class BulkMediaCreate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Hotel ID if property-level media.")
    room_type_id: UUID | None = Field(default=None, description="Room Type ID if room-level media.")
    media: list[BulkMediaItem] = Field(min_length=1, description="List of media items to create.")
