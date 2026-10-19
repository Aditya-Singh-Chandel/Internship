import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Numeric, ForeignKey, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class BookingItem(db_class):
    __tablename__ = "booking_items"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id = Column(Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    room_type_id = Column(Uuid, ForeignKey("room_types.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    booking = relationship("Booking", back_populates="booking_items")
    room_type = relationship("RoomType")
    booking_rooms = relationship("BookingRoom", back_populates="booking_item")
