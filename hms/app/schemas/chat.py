import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question or statement")
    session_id: Optional[uuid.UUID] = Field(default=None, description="Existing chat session ID to maintain conversation history")
    hotel_id: Optional[uuid.UUID] = Field(default=None, description="Optional hotel scope for policy or amenity queries")


class ChatCitation(BaseModel):
    source_type: str = Field(description="document, policy, amenity, hotel, room_type")
    title: str = Field(description="Source title or document name")
    relevance_score: float = Field(description="Confidence or similarity score")
    snippet: str = Field(description="Quoted passage or text excerpt")


class ChatMessageResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID
    role: str = "assistant"
    intent: str
    response: str
    citations: List[ChatCitation] = []
    context_data: Dict[str, Any] = {}


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    hotel_id: Optional[uuid.UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageHistoryItem(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    intent: Optional[str] = None
    citations_json: List[Dict[str, Any]] = []
    tool_calls_json: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True
