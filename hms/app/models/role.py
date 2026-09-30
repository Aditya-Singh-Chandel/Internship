import uuid
from sqlalchemy import Column, String, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class Role(db_class):
    __tablename__ = "roles"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    users = relationship("User", back_populates="role")