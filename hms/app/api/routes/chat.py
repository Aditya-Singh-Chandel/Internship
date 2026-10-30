import os
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
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

    if current_user and session.user_id and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation.")

    messages = chat_service.get_session_history(db=db, session_id=session_id)
    return {
        "success": True,
        "message": "Conversation history retrieved successfully.",
        "data": messages
    }


class GeminiConfigPayload(BaseModel):
    api_key: str
    model: Optional[str] = "gemini-1.5-flash"


@router.get("/llm-status")
def get_llm_status():
    """
    Checks if Google Gemini Cloud API is configured.
    """
    from app.services import llm_service
    configured = llm_service.is_gemini_configured()
    key = llm_service.get_gemini_api_key()
    masked = (key[:6] + "..." + key[-4:]) if (key and len(key) > 10) else None
    return {
        "success": True,
        "data": {
            "is_configured": configured,
            "provider": "Google Gemini Cloud API (REST)",
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            "masked_key": masked
        }
    }


@router.post("/llm-config")
def update_llm_config(payload: GeminiConfigPayload):
    """
    Dynamically configures or updates the Google Gemini Cloud API key.
    """
    import os
    clean_key = payload.api_key.strip()
    os.environ["GEMINI_API_KEY"] = clean_key
    if payload.model:
        os.environ["GEMINI_MODEL"] = payload.model.strip()

    # Persist into .env
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env_file = os.path.join(base_dir, ".env")
    try:
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
            if "GEMINI_API_KEY=" in content:
                import re
                content = re.sub(r"GEMINI_API_KEY=.*", f"GEMINI_API_KEY={clean_key}", content)
            else:
                content += f"\nGEMINI_API_KEY={clean_key}\n"
            with open(env_file, "w") as f:
                f.write(content)
    except Exception:
        pass

    return {
        "success": True,
        "message": "Gemini Cloud API configured successfully! Chatbot is now powered by Gemini Cloud.",
        "data": {
            "is_configured": True,
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        }
    }
