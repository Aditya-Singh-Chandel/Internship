import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Uuid, Boolean
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
    booking = relationship("Booking")