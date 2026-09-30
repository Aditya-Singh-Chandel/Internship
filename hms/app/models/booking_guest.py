import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class BookingGuest(db_class):
    __tablename__ = "booking_guests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    guest_name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)

    booking = relationship("Booking", back_populates="booking_guests")