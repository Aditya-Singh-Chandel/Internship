import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class BookingGuest(db_class):
    __tablename__ = "booking_guests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    guest_id = Column(Uuid, ForeignKey("guests.id"), nullable=False)
    booking_room_id = Column(Uuid, ForeignKey("booking_rooms.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    booking = relationship("Booking", back_populates="booking_guests")
    booking_room = relationship("BookingRoom")
    guest = relationship("Guest")