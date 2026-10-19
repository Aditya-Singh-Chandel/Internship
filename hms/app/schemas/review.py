from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

class ReviewBase(BaseModel):
    guest_id: UUID = Field(description="Valid value for guest id.", examples=[""])
    booking_id: UUID = Field(description="Valid value for booking id.", examples=[""])
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, description="Valid value for comment.", examples=[""])

class ReviewCreate(ReviewBase):
    pass

class ReviewItem(ReviewBase):
    id: UUID
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewUpdate(BaseModel):
    guest_id: UUID | None = Field(default=None, description="Valid value for guest id.", examples=[""])
    booking_id: UUID | None = Field(default=None, description="Valid value for booking id.", examples=[""])
    rating: int | None = Field(default=None, description="Valid value for rating.", examples=[""])
    comment: str | None = Field(default=None, description="Valid value for comment.", examples=[""])

class ReviewListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    reviews: list[ReviewItem]

    model_config = ConfigDict(from_attributes=True)
