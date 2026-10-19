from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from app.schemas.booking_item import BookingItemCreate, BookingItemResponse

BookingStatus = Literal["pending", "confirmed", "in_house", "cancelled", "completed"]

class BookingBase(BaseModel):
    hotel_id: UUID = Field(description="Hotel ID for this reservation.", examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    guest_id: UUID = Field(description="Valid value for primary booker guest ID.", examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    checkin_date: date = Field(description="Format: YYYY-MM-DD. Must be today or a future date.")
    checkout_date: date = Field(description="Format: YYYY-MM-DD. Must be after checkin_date.")
    total_amount: Decimal | None = Field(default=None, ge=0, description="Total cost in decimal format. If omitted, auto-calculated from room types and duration.")
    status: BookingStatus = Field(default="confirmed", description="Current status: pending, confirmed, in_house, cancelled, completed.")
    special_requests: str | None = Field(default=None, description="Detailed notes or special requests.")

class BookingCreate(BookingBase):
    items: list[BookingItemCreate] = Field(min_length=1, description="List of room types and quantities to book in this reservation.")

class BookingDetailItem(BookingBase):
    id: UUID
    created_at: datetime
    deleted_at: datetime | None = None
    booking_items: list[BookingItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

class BookingResponse(BookingDetailItem):
    pass

class BookingUpdate(BaseModel):
    hotel_id: UUID | None = Field(default=None, description="Hotel ID for this reservation.")
    guest_id: UUID | None = Field(default=None, description="Valid value for guest ID.")
    checkin_date: date | None = Field(default=None, description="Format: YYYY-MM-DD.")
    checkout_date: date | None = Field(default=None, description="Format: YYYY-MM-DD.")
    total_amount: Decimal | None = Field(default=None, ge=0, description="Total cost in decimal format.")
    status: BookingStatus | None = Field(default=None, description="Current status.")
    special_requests: str | None = Field(default=None, description="Detailed notes or description.")

class BookingListResponse(BaseModel):
    total: int = 1
    page: int = 1
    limit: int = 10
    total_pages: int = 1

    bookings: list[BookingDetailItem]

    model_config = ConfigDict(from_attributes=True)
