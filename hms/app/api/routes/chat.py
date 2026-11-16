from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_optional_current_user
from app.models.user import User
from app.models.chat import ChatSession
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatMessageHistoryItem
)
from app.schemas.common import ItemResponse
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["AI Hotel Concierge Chatbot"])


@router.post("", response_model=ItemResponse[ChatMessageResponse], status_code=status.HTTP_200_OK)
def chat_with_concierge(
    payload: ChatMessageRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Primary endpoint for the RAG-powered Hotel Assistant.
    Supports:
    - **Cross-hotel discovery**: e.g., *"Hotels where pets are allowed"*, *"Hotels with swimming pool"*.
    - **Hotel-specific policy & rules**: e.g., *"What is check-in time at this hotel?"*, *"Is smoking permitted?"*.
    - **Personalized booking & refund calculation**: e.g., *"What refund will I get as per my booking?"*, dynamically checking cancellation policies and scheduled arrival times.
    """
    result = chat_service.send_chat_message(
        db=db,
        message=payload.message,
        user=current_user,
        session_id=payload.session_id,
        hotel_id=payload.hotel_id
    )
    return {
        "success": True,
        "message": "Assistant responded successfully.",
        "data": result
    }


@router.get("/sessions", response_model=ItemResponse[List[ChatSessionResponse]])
def get_user_chat_sessions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve previous chat conversations for the authenticated user.
    """
    sessions = chat_service.list_user_sessions(db=db, user_id=current_user.id, limit=limit)
    return {
        "success": True,
        "message": "Chat sessions retrieved successfully.",
        "data": sessions
    }


@router.get("/sessions/{session_id}/messages", response_model=ItemResponse[List[ChatMessageHistoryItem]])
def get_session_message_history(
    session_id: UUID,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve the full conversation transcript for a specific chat session.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    if session.user_id and (not current_user or session.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation.")

    messages = chat_service.get_session_history(db=db, session_id=session_id)
    return {
        "success": True,
        "message": "Conversation history retrieved successfully.",
        "data": messages
    }
