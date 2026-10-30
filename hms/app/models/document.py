import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Uuid, DateTime, Integer, JSON
from sqlalchemy.orm import relationship
from app.core.database import db_class, engine
from sqlalchemy import text, ARRAY, Float

# Auto-detect if native pgvector extension exists in the running PostgreSQL instance
def _detect_vector_support():
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
            if not res:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                    res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
                except Exception:
                    pass
            return bool(res)
    except Exception:
        return False

HAS_PGVECTOR = _detect_vector_support()

if HAS_PGVECTOR:
    try:
        from pgvector.sqlalchemy import Vector
        EmbeddingType = Vector(384)
    except Exception:
        EmbeddingType = ARRAY(Float)
else:
    EmbeddingType = ARRAY(Float)


class HotelDocument(db_class):
    __tablename__ = "hotel_documents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(50), default="general", nullable=False)  # policies, catalog, menu, faq, events, general
    file_type = Column(String(20), default="text", nullable=False)    # pdf, docx, xlsx, text
    file_name = Column(String(255), nullable=True)
    access_level = Column(String(20), default="public", nullable=False)  # public, staff_only, resident_only
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    hotel = relationship("Hotel")
    chunks = relationship("HotelDocumentChunk", back_populates="document", cascade="all, delete-orphan")

    @property
    def chunk_count(self) -> int:
        return len(self.chunks) if self.chunks else 0



class HotelDocumentChunk(db_class):
    __tablename__ = "hotel_document_chunks"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid, ForeignKey("hotel_documents.id", ondelete="CASCADE"), nullable=True, index=True)
    hotel_id = Column(Uuid, ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(EmbeddingType, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    source_type = Column(String(50), default="document", nullable=False)  # document, policy, amenity, hotel, room_type
    source_id = Column(Uuid, nullable=True, index=True)
    access_level = Column(String(20), default="public", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    document = relationship("HotelDocument", back_populates="chunks")
    hotel = relationship("Hotel")
