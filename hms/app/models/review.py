import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Review(db_class):
    __tablename__ = "reviews"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    guest_id = Column(Uuid, ForeignKey("guests.id"), nullable=False)
    booking_id = Column(Uuid, ForeignKey("bookings.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    guest = relationship("Guest")
    booking = relationship("Booking", back_populates="reviews")

    @property
    def hotel_id(self):
        return self.booking.hotel_id if self.booking else None

    @property
    def guest_name(self):
        return self.guest.name if self.guest else None

    @property
    def hotel_name(self):
        return self.booking.hotel.name if self.booking and self.booking.hotel else None