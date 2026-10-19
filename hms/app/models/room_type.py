import uuid
from sqlalchemy import Column, String, Text, Numeric, Integer, ForeignKey, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class RoomType(db_class):
    __tablename__ = "room_types"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    base_price = Column(Numeric(10, 2), nullable=False)
    guests_allowed = Column(Integer, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    hotel = relationship("Hotel", back_populates="room_types")