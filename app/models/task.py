import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Uuid
from app.core.database import db_class

class Task(db_class):
    __tablename__ = "tasks"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    status = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    deadline = Column(String, nullable=True)