import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Numeric, Date, DateTime, ForeignKey, Uuid, Boolean
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Booking(db_class):
    __tablename__ = "bookings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    guest_id = Column(Uuid, ForeignKey("guests.id"), nullable=False)
    checkin_date = Column(Date, nullable=False)
    checkout_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=True)
    status = Column(String, default="confirmed") 
    special_requests = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    hotel = relationship("Hotel")
    guest = relationship("Guest")
    booking_guests = relationship("BookingGuest", back_populates="booking")
    booking_items = relationship("BookingItem", back_populates="booking")