import uuid
from sqlalchemy import Column, Boolean, Text, ForeignKey, Uuid, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Media(db_class):
    __tablename__ = "media"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=True)
    room_type_id = Column(Uuid, ForeignKey("room_types.id"), nullable=True)
    image_url = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    hotel = relationship("Hotel")
    room_type = relationship("RoomType")