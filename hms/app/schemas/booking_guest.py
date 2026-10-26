from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class BookingGuestBase(BaseModel):
    booking_id: UUID = Field(description="Valid value for booking id.", examples=[""])
    guest_id: UUID = Field(description="Valid value for guest id.", examples=[""])
    booking_room_id: UUID | None = Field(default=None, description="Optional room assignment for this companion.")

class BookingGuestCreate(BookingGuestBase):
    pass

class BookingGuestItem(BookingGuestBase):
    id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BookingGuestUpdate(BaseModel):
    booking_id: UUID | None = Field(default=None, description="Valid value for booking id.", examples=[""])
    guest_id: UUID | None = Field(default=None, description="Valid value for guest id.", examples=[""])
    booking_room_id: UUID | None = Field(default=None, description="Optional room assignment for this companion.")

from app.schemas.common import ItemResponse, PaginatedResponse

BookingGuestItemResponse = ItemResponse[BookingGuestItem]
BookingGuestPaginatedResponse = PaginatedResponse[BookingGuestItem]
