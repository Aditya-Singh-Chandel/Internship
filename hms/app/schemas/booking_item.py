from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from app.schemas.booking_room import BookingRoomItem

class BookingItemBase(BaseModel):
    room_type_id: UUID = Field(description="Room category ID for this line item.")
    quantity: int = Field(default=1, ge=1, le=50, description="Number of rooms requested for this room category.")
    unit_price: Decimal | None = Field(default=None, ge=0, description="Frozen nightly rate per room. Defaults to RoomType.base_price if omitted.")

class BookingItemCreate(BookingItemBase):
    pass

class BookingItemUpdate(BaseModel):
    room_type_id: UUID | None = Field(default=None)
    quantity: int | None = Field(default=None, ge=1, le=50)
    unit_price: Decimal | None = Field(default=None, ge=0)

from app.schemas.room_type import RoomTypeItem

class BookingItemResponse(BaseModel):
    id: UUID
    booking_id: UUID
    room_type_id: UUID
    quantity: int
    unit_price: Decimal
    created_at: datetime | None = None
    deleted_at: datetime | None = None
    booking_rooms: list[BookingRoomItem] = []
    room_type: RoomTypeItem | None = None

    model_config = ConfigDict(from_attributes=True)


from app.schemas.common import ItemResponse, PaginatedResponse

BookingItemItemResponse = ItemResponse[BookingItemResponse]
BookingItemPaginatedResponse = PaginatedResponse[BookingItemResponse]
