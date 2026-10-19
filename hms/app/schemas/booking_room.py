from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

BookingRoomStatus = Literal["confirmed", "checked_in", "checked_out", "completed", "cancelled"]

class BookingRoomBase(BaseModel):
    booking_item_id: UUID = Field(description="Booking line item ID.")
    room_id: UUID | None = Field(default=None, description="Physical room assigned (door number).")
    guest_id: UUID = Field(description="Resident guest for this specific room.")
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
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class BookingRoomListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    booking_rooms: list[BookingRoomItem]

    model_config = ConfigDict(from_attributes=True)

class BulkRoomAssignmentItem(BaseModel):
    booking_item_id: UUID = Field(description="ID of the line item to fulfill.")
    room_id: UUID = Field(description="Physical room ID (door number).")
    guest_id: UUID = Field(description="Resident guest ID staying in this room.")

class BulkRoomAssignmentRequest(BaseModel):
    booking_id: UUID | None = Field(default=None, description="Optional master booking ID for extra scoping.")
    assignments: list[BulkRoomAssignmentItem] = Field(min_length=1, description="List of room assignments to make.")
