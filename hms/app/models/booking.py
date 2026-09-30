import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Numeric, Date, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Booking(db_class):
    __tablename__ = "bookings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    guest_id = Column(Uuid, ForeignKey("guests.id"), nullable=False)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    room_type_id = Column(Uuid, ForeignKey("room_types.id"), nullable=False)
    assigned_room_id = Column(Uuid, ForeignKey("rooms.id"), nullable=True)
    checkin_date = Column(Date, nullable=False)
    checkout_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=True)
    status = Column(String, default="confirmed") 
    special_requests = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    guest = relationship("Guest")
    hotel = relationship("Hotel")
    room_type = relationship("RoomType")
    assigned_room = relationship("Room")
    booking_guests = relationship("BookingGuest", back_populates="booking")