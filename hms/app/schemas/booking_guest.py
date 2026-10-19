from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class BookingGuestBase(BaseModel):
    booking_id: UUID = Field(description="Valid value for booking id.", examples=[""])
    guest_id: UUID = Field(description="Valid value for guest id.", examples=[""])
    booking_room_id: UUID | None = Field(default=None, description="Optional room assignment for this companion.")

class BookingGuestCreate(BookingGuestBase):
    pass

from datetime import datetime

class BookingGuestItem(BookingGuestBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BookingGuestUpdate(BaseModel):
    booking_id: UUID | None = Field(default=None, description="Valid value for booking id.", examples=[""])
    guest_id: UUID | None = Field(default=None, description="Valid value for guest id.", examples=[""])
    booking_room_id: UUID | None = Field(default=None, description="Optional room assignment for this companion.")

class BookingGuestListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    booking_guests: list[BookingGuestItem]

    model_config = ConfigDict(from_attributes=True)
