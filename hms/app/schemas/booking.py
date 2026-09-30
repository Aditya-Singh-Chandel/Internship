from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

class BookingBase(BaseModel):
    guest_id: UUID = Field(description="Valid value for guest id.", examples=[""])
    hotel_id: UUID = Field(description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID = Field(description="Valid value for room type id.", examples=[""])
    assigned_room_id: UUID | None = Field(default=None, description="Valid value for assigned room id.", examples=[""])
    checkin_date: date = Field(description="Format: YYYY-MM-DD. Must be a date in the future.", examples=[""])
    checkout_date: date = Field(description="Format: YYYY-MM-DD. Must be a date in the future.", examples=[""])
    total_amount: Decimal | None = Field(default=None, description="Total cost in decimal format.", examples=[""])
    status: str | None = Field(default="confirmed", description="Current status (e.g., active, completed, confirmed).", examples=[""])
    special_requests: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])

class BookingCreate(BookingBase):
    pass

class BookingItem(BookingBase):
    id: UUID
    created_at: datetime

class BookingListResponse(BaseModel):
    bookings: list[BookingItem]

class BookingUpdate(BaseModel):
    guest_id: UUID | None = Field(default=None, description="Valid value for guest id.", examples=[""])
    hotel_id: UUID | None = Field(default=None, description="Valid value for hotel id.", examples=[""])
    room_type_id: UUID | None = Field(default=None, description="Valid value for room type id.", examples=[""])
    assigned_room_id: UUID | None = Field(default=None, description="Valid value for assigned room id.", examples=[""])
    checkin_date: date | None = Field(default=None, description="Format: YYYY-MM-DD. Must be a date in the future.", examples=[""])
    checkout_date: date | None = Field(default=None, description="Format: YYYY-MM-DD. Must be a date in the future.", examples=[""])
    total_amount: Decimal | None = Field(default=None, description="Total cost in decimal format.", examples=[""])
    status: str | None = Field(default=None, description="Current status (e.g., active, completed, confirmed).", examples=[""])
    special_requests: str | None = Field(default=None, description="Detailed notes or description. Leading and trailing whitespaces will be stripped.", examples=[""])
