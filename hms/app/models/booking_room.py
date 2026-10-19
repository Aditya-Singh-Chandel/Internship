import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Uuid, Boolean
from sqlalchemy.orm import relationship
from app.core.database import db_class

class BookingRoom(db_class):
    __tablename__ = "booking_rooms"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_item_id = Column(Uuid, ForeignKey("booking_items.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Uuid, ForeignKey("rooms.id"), nullable=True)
    guest_id = Column(Uuid, ForeignKey("guests.id"), nullable=False)
    status = Column(String, default="confirmed", nullable=False)  # confirmed | checked_in | checked_out | cancelled
    checkin_date = Column(Date, nullable=False)
    checkout_date = Column(Date, nullable=False)
    checked_in_at = Column(DateTime, nullable=True)
    checked_out_at = Column(DateTime, nullable=True)
    room_rate = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    booking_item = relationship("BookingItem", back_populates="booking_rooms")
    room = relationship("Room")
    guest = relationship("Guest")
