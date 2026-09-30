from pydantic import BaseModel, Field
from uuid import UUID

class BookingGuestBase(BaseModel):
    booking_id: UUID = Field(description="Valid value for booking id.", examples=[""])
    guest_name: str = Field(description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    age: int | None = Field(default=None, description="Age of the guest.", examples=[""])

class BookingGuestCreate(BookingGuestBase):
    pass

class BookingGuestItem(BookingGuestBase):
    id: UUID

class BookingGuestListResponse(BaseModel):
    booking_guests: list[BookingGuestItem]

class BookingGuestUpdate(BaseModel):
    booking_id: UUID | None = Field(default=None, description="Valid value for booking id.", examples=[""])
    guest_name: str | None = Field(default=None, description="Letters, numbers, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 255 chars after trimming.", examples=[""])
    age: int | None = Field(default=None, description="Age of the guest.", examples=[""])
