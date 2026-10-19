import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Room(db_class):
    __tablename__ = "rooms"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    room_type_id = Column(Uuid, ForeignKey("room_types.id"), nullable=False)
    room_number = Column(String, nullable=False)
    floor = Column(Integer, nullable=True)
    status = Column(String, default="available")
    deleted_at = Column(DateTime, nullable=True)

    room_type = relationship("RoomType")