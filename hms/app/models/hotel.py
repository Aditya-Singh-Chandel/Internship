import uuid
from sqlalchemy import Column, String, Text, Numeric, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Hotel(db_class):
    __tablename__ = "hotels"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    address_line1 = Column(String, nullable=False)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    country = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    description = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    room_types = relationship("RoomType", back_populates="hotel")