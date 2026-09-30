import uuid
from sqlalchemy import Column, String, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Amenity(db_class):
    __tablename__ = "amenities"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=True)
    room_type_id = Column(Uuid, ForeignKey("room_types.id"), nullable=True)
    name = Column(String, nullable=False)

    hotel = relationship("Hotel")
    room_type = relationship("RoomType")