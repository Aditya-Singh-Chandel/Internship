import uuid
from sqlalchemy import Column, String, Text, ForeignKey, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Policy(db_class):
    __tablename__ = "policies"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    policy_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    hotel = relationship("Hotel")