from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.schemas.document import (
    DocumentCreateText,
    DocumentResponse,
    DocumentSyncResponse,
    DocumentSearchRequest,
    DocumentChunkResult
)
from app.schemas.common import ItemResponse, ActionResponse
from app.services import document_service
from app.utils.scoping_utils import resolve_and_verify_hotel_id

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/hotels/{hotel_id}/documents", tags=["Hotel Knowledge & Documents"])


@router.post("/upload", response_model=ItemResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_document(
    hotel_id: UUID,
    file: UploadFile = File(..., description="Upload .pdf, .docx, .xlsx, or .txt file"),
    title: Optional[str] = Form(None, description="Optional custom title for the document"),
    category: str = Form("general", description="policies, catalog, menu, faq, events, general"),
    access_level: str = Form("public", description="public, staff_only, resident_only"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Upload a document (PDF, DOCX, XLSX, TXT) for a hotel.
    The document is automatically parsed, structure-aware chunked, embedded via FastEmbed,
    and indexed for RAG retrieval.
    """
    resolve_and_verify_hotel_id(db, current_user, hotel_id)
    if access_level not in ("public", "staff_only", "resident_only"):
        raise HTTPException(status_code=422, detail="access_level must be one of: public, staff_only, resident_only.")
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. The maximum size is 10 MB.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    doc = document_service.ingest_file(
        db=db,
        hotel_id=hotel_id,
        file_name=file.filename or "uploaded_document",
        file_bytes=file_bytes,
        category=category,
        access_level=access_level,
        title=title
    )
    return {
        "success": True,
        "message": f"Document '{doc.title}' uploaded and indexed successfully into {len(doc.chunks)} chunks.",
        "data": doc
    }


@router.post("/text", response_model=ItemResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
def create_text_document(
    hotel_id: UUID,
    payload: DocumentCreateText,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Directly ingest written policies, FAQs, or catalog descriptions as text.
    """
    resolve_and_verify_hotel_id(db, current_user, hotel_id)
    doc = document_service.ingest_text(
        db=db,
        hotel_id=hotel_id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        access_level=payload.access_level
    )
    return {
        "success": True,
        "message": f"Text document '{doc.title}' ingested and indexed successfully.",
        "data": doc
    }


@router.post("/sync", response_model=ItemResponse[DocumentSyncResponse], status_code=status.HTTP_200_OK)
def sync_hotel_knowledge(
    hotel_id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Synchronizes existing database entities (Hotel profile, Policies, Amenities, Room Types)
    into vector chunks so the chatbot has real-time knowledge of all database updates.
    """
    resolve_and_verify_hotel_id(db, current_user, hotel_id)
    sync_result = document_service.sync_hotel_database_knowledge(db=db, hotel_id=hotel_id)
    return {
        "success": True,
        "message": f"Successfully synchronized database records for {sync_result['hotel_name']}.",
        "data": sync_result
    }


@router.get("", response_model=ItemResponse[List[DocumentResponse]])
def list_hotel_documents(
    hotel_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    List all uploaded documents for a hotel (staff of that hotel only; includes staff_only documents).
    """
    resolve_and_verify_hotel_id(db, current_user, hotel_id)
    docs = document_service.list_documents(db=db, hotel_id=hotel_id, limit=limit, offset=offset)
    return {
        "success": True,
        "message": "Hotel documents retrieved successfully.",
        "data": docs
    }


@router.delete("/{document_id}", response_model=ActionResponse)
def delete_hotel_document(
    hotel_id: UUID,
    document_id: UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Soft-deletes a hotel document and its indexed vector chunks.
    """
    resolve_and_verify_hotel_id(db, current_user, hotel_id)
    document_service.delete_document(db=db, hotel_id=hotel_id, document_id=document_id)
    return {
        "success": True,
        "message": "Document and associated knowledge chunks deleted successfully.",
        "data": {"document_id": str(document_id)}
    }


@router.post("/search", response_model=ItemResponse[List[DocumentChunkResult]])
def test_search_hotel_chunks(
    hotel_id: UUID,
    req: DocumentSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Test vector and hybrid search directly against this hotel's knowledge base.
    """
    hits = document_service.search_chunks(
        db=db,
        query=req.query,
        hotel_id=hotel_id,
        top_k=req.top_k,
        access_level="public"
    )
    return {
        "success": True,
        "message": f"Found {len(hits)} matching knowledge chunks.",
        "data": hits
    }
