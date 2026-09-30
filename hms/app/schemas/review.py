from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class ReviewBase(BaseModel):
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])
    guest_id: UUID = Field(description="Valid value for guest id.", examples=[""])
    booking_id: UUID = Field(description="Valid value for booking id.", examples=[""])
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, description="Valid value for comment.", examples=[""])

class ReviewCreate(ReviewBase):
    pass

class ReviewItem(ReviewBase):
    id: UUID
    created_at: datetime

class ReviewListResponse(BaseModel):
    reviews: list[ReviewItem]

class ReviewUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    guest_id: UUID | None = Field(default=None, description="Valid value for guest id.", examples=[""])
    booking_id: UUID | None = Field(default=None, description="Valid value for booking id.", examples=[""])
    rating: int | None = Field(default=None, description="Valid value for rating.", examples=[""])
    comment: str | None = Field(default=None, description="Valid value for comment.", examples=[""])
