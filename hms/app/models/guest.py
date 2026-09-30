import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Uuid
from app.core.database import db_class

class Guest(db_class):
    __tablename__ = "guests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    id_document_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))