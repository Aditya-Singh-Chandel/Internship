from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

BookingRoomStatus = Literal["assigned", "confirmed", "checked_in", "checked_out", "completed", "cancelled"]

class BookingRoomBase(BaseModel):
    booking_item_id: UUID | None = Field(default=None, description="Booking line item ID.")
    booking_id: UUID | None = Field(default=None, description="Master booking ID.")
    room_id: UUID | None = Field(default=None, description="Physical room assigned (door number).")
    guest_id: UUID | None = Field(default=None, description="Resident guest for this specific room.")
    status: BookingRoomStatus = Field(default="confirmed", description="Per-room status: confirmed, checked_in, checked_out, completed, cancelled.")
    checkin_date: date | None = Field(default=None, description="Format: YYYY-MM-DD. Defaults to master booking checkin_date if omitted.")
    checkout_date: date | None = Field(default=None, description="Format: YYYY-MM-DD. Defaults to master booking checkout_date if omitted.")
    checked_in_at: datetime | None = Field(default=None, description="Timestamp of physical check-in.")
    checked_out_at: datetime | None = Field(default=None, description="Timestamp of physical check-out.")
    room_rate: Decimal | None = Field(default=None, ge=0, description="Cost allocated for this room. Defaults to line item unit_price if omitted.")

class BookingRoomCreate(BookingRoomBase):
    pass

class BookingRoomUpdate(BaseModel):
    booking_item_id: UUID | None = Field(default=None)
    room_id: UUID | None = Field(default=None)
    guest_id: UUID | None = Field(default=None)
    status: BookingRoomStatus | None = Field(default=None)
    checkin_date: date | None = Field(default=None)
    checkout_date: date | None = Field(default=None)
    checked_in_at: datetime | None = Field(default=None)
    checked_out_at: datetime | None = Field(default=None)
    room_rate: Decimal | None = Field(default=None, ge=0)

class BookingRoomItem(BookingRoomBase):
    id: UUID
    checkin_date: date
    checkout_date: date
    room_number: str | None = None
    floor: int | None = None
    guest_name: str | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

from app.schemas.common import ItemResponse, PaginatedResponse

BookingRoomItemResponse = ItemResponse[BookingRoomItem]
BookingRoomPaginatedResponse = PaginatedResponse[BookingRoomItem]

class BulkRoomAssignmentItem(BaseModel):
    booking_item_id: UUID = Field(description="ID of the line item to fulfill.")
    room_id: UUID = Field(description="Physical room ID (door number).")
    guest_id: UUID = Field(description="Resident guest ID staying in this room.")

class BulkRoomAssignmentRequest(BaseModel):
    booking_id: UUID | None = Field(default=None, description="Optional master booking ID for extra scoping.")
    assignments: list[BulkRoomAssignmentItem] = Field(min_length=1, description="List of room assignments to make.")
