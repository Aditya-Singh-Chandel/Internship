import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Uuid, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.database import db_class

class ChatSession(db_class):
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    hotel_id = Column(Uuid, ForeignKey("hotels.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), default="New Conversation", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")
    hotel = relationship("Hotel")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at.asc()")


class ChatMessage(db_class):
    __tablename__ = "chat_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id = Column(Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)  # discovery, policy, booking_inquiry, general
    citations_json = Column(JSON, default=list, nullable=False)
    tool_calls_json = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("ChatSession", back_populates="messages")
    