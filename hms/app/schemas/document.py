import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DocumentCreateText(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Document title")
    content: str = Field(..., min_length=10, description="Raw text, FAQ, or policy content")
    category: str = Field(default="general", max_length=50, description="policies, catalog, menu, faq, events, general")
    access_level: str = Field(default="public", description="public, staff_only, resident_only")


class DocumentResponse(BaseModel):
    id: uuid.UUID
    hotel_id: uuid.UUID
    title: str
    category: str
    file_type: str
    file_name: Optional[str] = None
    access_level: str
    chunk_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSyncResponse(BaseModel):
    hotel_id: uuid.UUID
    hotel_name: str
    synced_policies: int
    synced_amenities: int
    synced_room_types: int
    total_chunks_created: int


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search or question")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to return")


class DocumentChunkResult(BaseModel):
    chunk_id: uuid.UUID
    hotel_id: uuid.UUID
    hotel_name: str
    document_id: Optional[uuid.UUID] = None
    source_type: str
    source_id: Optional[uuid.UUID] = None
    content: str
    metadata: Dict[str, Any] = {}
    similarity_score: float
