from pydantic import BaseModel, Field
from uuid import UUID

class MediaBase(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    image_url: str = Field(description="Valid value for image url.", examples=[""])
    is_primary: bool | None = Field(default=False, description="Valid value for is primary.", examples=[""])

class MediaCreate(MediaBase):
    pass

class MediaItem(MediaBase):
    id: UUID

class MediaListResponse(BaseModel):
    media: list[MediaItem] = Field(description="Valid value for media.", examples=[""])

class MediaUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    image_url: str | None = Field(default=None, description="Valid value for image url.", examples=[""])
    is_primary: bool | None = Field(default=None, description="Valid value for is primary.", examples=[""])
