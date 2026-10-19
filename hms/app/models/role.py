import uuid
from sqlalchemy import Column, String, Uuid, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Role(db_class):
    __tablename__ = "roles"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    users = relationship("User", back_populates="role")