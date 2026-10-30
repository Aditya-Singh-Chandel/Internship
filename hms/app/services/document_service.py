import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, or_, text
from fastapi import HTTPException, status

from app.models.document import HotelDocument, HotelDocumentChunk, HAS_PGVECTOR
from app.models.hotel import Hotel
from app.models.policy import Policy
from app.models.amenity import Amenity
from app.models.room_type import RoomType
from app.models.review import Review
from app.models.booking import Booking
from app.utils.document_parsers import (
    parse_pdf, parse_docx, parse_xlsx, parse_text_file, chunk_text
)
from app.services import embedding_service


def ingest_file(
    db: Session,
    hotel_id: uuid.UUID,
    file_name: str,
    file_bytes: bytes,
    category: str = "general",
    access_level: str = "public",
    title: Optional[str] = None
) -> HotelDocument:
    """
    Parses an uploaded file (.pdf, .docx, .xlsx, .txt), chunks its content,
    generates dense embeddings, and saves both the document record and its chunks.
    """
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with id {hotel_id} not found."
        )

    _, ext = os.path.splitext(file_name.lower())
    clean_title = title.strip() if title and title.strip() else os.path.splitext(file_name)[0]

    all_chunks_raw: List[Dict[str, Any]] = []

    try:
        if ext == ".pdf":
            file_type = "pdf"
            parsed_pages = parse_pdf(file_bytes)
            for page in parsed_pages:
                page_meta = {"page": page["page"], "source_file": file_name}
                chunks = chunk_text(page["text"], metadata=page_meta, chunk_size=500, chunk_overlap=60)
                all_chunks_raw.extend(chunks)

        elif ext in (".docx", ".doc"):
            file_type = "docx"
            parsed_sections = parse_docx(file_bytes)
            for sec in parsed_sections:
                sec_meta = {"section": sec["section"], "source_file": file_name}
                chunks = chunk_text(sec["text"], metadata=sec_meta, chunk_size=500, chunk_overlap=60)
                all_chunks_raw.extend(chunks)

        elif ext in (".xlsx", ".xls"):
            file_type = "xlsx"
            parsed_sheets = parse_xlsx(file_bytes)
            for sheet in parsed_sheets:
                sheet_meta = {"sheet": sheet["sheet"], "source_file": file_name}
                chunks = chunk_text(sheet["text"], metadata=sheet_meta, chunk_size=500, chunk_overlap=60)
                all_chunks_raw.extend(chunks)

        elif ext in (".txt", ".md", ".json", ".csv"):
            file_type = "text"
            text_content = parse_text_file(file_bytes)
            text_meta = {"source_file": file_name}
            all_chunks_raw = chunk_text(text_content, metadata=text_meta, chunk_size=500, chunk_overlap=60)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported formats: .pdf, .docx, .xlsx, .txt, .md"
            )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse document: {str(ve)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error parsing document: {str(e)}"
        )

    if not all_chunks_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The document produced no readable text chunks."
        )

    # Create HotelDocument
    doc = HotelDocument(
        hotel_id=hotel_id,
        title=clean_title,
        category=category,
        file_type=file_type,
        file_name=file_name,
        access_level=access_level
    )
    db.add(doc)
    db.flush()

    # Generate Embeddings in batch
    texts = [c["content"] for c in all_chunks_raw]
    embeddings = embedding_service.get_embeddings(texts)

    for idx, (chunk_data, emb) in enumerate(zip(all_chunks_raw, embeddings)):
        meta = chunk_data.get("metadata", {})
        meta.update({
            "title": clean_title,
            "category": category,
            "file_name": file_name
        })
        chunk_obj = HotelDocumentChunk(
            document_id=doc.id,
            hotel_id=hotel_id,
            chunk_index=idx,
            content=chunk_data["content"],
            embedding=emb,
            metadata_json=meta,
            source_type="document",
            source_id=doc.id,
            access_level=access_level
        )
        db.add(chunk_obj)

    db.commit()
    db.refresh(doc)
    return doc


def ingest_text(
    db: Session,
    hotel_id: uuid.UUID,
    title: str,
    content: str,
    category: str = "general",
    access_level: str = "public"
) -> HotelDocument:
    """
    Ingests raw text, FAQs, or written policies directly into the knowledge base.
    """
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with id {hotel_id} not found."
        )

    if not content or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document content cannot be empty."
        )

    clean_title = title.strip()
    doc = HotelDocument(
        hotel_id=hotel_id,
        title=clean_title,
        category=category,
        file_type="text",
        file_name=None,
        access_level=access_level
    )
    db.add(doc)
    db.flush()

    meta = {"title": clean_title, "category": category, "source_type": "text"}
    raw_chunks = chunk_text(content, metadata=meta, chunk_size=500, chunk_overlap=60)
    texts = [c["content"] for c in raw_chunks]
    embeddings = embedding_service.get_embeddings(texts)

    for idx, (chunk_data, emb) in enumerate(zip(raw_chunks, embeddings)):
        chunk_obj = HotelDocumentChunk(
            document_id=doc.id,
            hotel_id=hotel_id,
            chunk_index=idx,
            content=chunk_data["content"],
            embedding=emb,
            metadata_json=chunk_data["metadata"],
            source_type="document",
            source_id=doc.id,
            access_level=access_level
        )
        db.add(chunk_obj)

    db.commit()
    db.refresh(doc)
    return doc


def sync_hotel_database_knowledge(db: Session, hotel_id: uuid.UUID) -> Dict[str, Any]:
    """
    Synchronizes structured database records (Hotel profile, Policies, Amenities, RoomTypes)
    into the knowledge base. Deletes previously synchronized system chunks for this hotel
    and regenerates them so changes in hotel tables are immediately searchable by the chatbot.
    """
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with id {hotel_id} not found."
        )

    # 1. Clean up existing system chunks for this hotel (source_type != 'document')
    db.query(HotelDocumentChunk).filter(
        HotelDocumentChunk.hotel_id == hotel_id,
        HotelDocumentChunk.source_type.in_(["hotel", "policy", "amenity", "room_type", "review"])
    ).delete(synchronize_session=False)

    synced_items: List[Dict[str, Any]] = []

    # 2. Hotel Profile
    hotel_info = (
        f"Hotel Profile: {hotel.name}\n"
        f"Location: {hotel.address_line1}, {hotel.city}, {hotel.state}, {hotel.country} (Postal: {hotel.postal_code})\n"
        f"Contact: Phone {hotel.phone or 'N/A'}, Email {hotel.email or 'N/A'}\n"
        f"Overview: {hotel.description or 'No description provided.'}"
    )
    synced_items.append({
        "content": hotel_info,
        "source_type": "hotel",
        "source_id": hotel.id,
        "meta": {"title": f"{hotel.name} - Profile", "category": "profile"}
    })

    # 3. Policies
    policies = db.query(Policy).filter(Policy.hotel_id == hotel_id, Policy.deleted_at.is_(None)).all()
    for pol in policies:
        pol_content = (
            f"Hotel Policy for {hotel.name}:\n"
            f"Policy Type: {pol.policy_type}\n"
            f"Details: {pol.description}"
        )
        synced_items.append({
            "content": pol_content,
            "source_type": "policy",
            "source_id": pol.id,
            "meta": {"title": f"Policy: {pol.policy_type}", "category": "policies", "policy_type": pol.policy_type}
        })

    # 4. Amenities
    amenities = db.query(Amenity).filter(Amenity.hotel_id == hotel_id, Amenity.deleted_at.is_(None)).all()
    if amenities:
        amenity_names = [a.name for a in amenities]
        amenity_content = (
            f"Hotel Amenities for {hotel.name}:\n"
            f"Available amenities: {', '.join(amenity_names)}.\n"
            f"Guests can enjoy these services and facilities during their stay."
        )
        synced_items.append({
            "content": amenity_content,
            "source_type": "amenity",
            "source_id": hotel.id,
            "meta": {"title": "Hotel Amenities", "category": "amenities", "count": len(amenity_names)}
        })

    # 5. Room Types
    room_types = db.query(RoomType).filter(RoomType.hotel_id == hotel_id, RoomType.deleted_at.is_(None)).all()
    for rt in room_types:
        # Check if room type has specific amenities
        rt_amenities = db.query(Amenity).filter(Amenity.room_type_id == rt.id, Amenity.deleted_at.is_(None)).all()
        rt_amenity_str = f"Room Amenities: {', '.join([a.name for a in rt_amenities])}" if rt_amenities else ""
        rt_content = (
            f"Room Type at {hotel.name}: {rt.name}\n"
            f"Base Price: ${float(rt.base_price):.2f} per night\n"
            f"Guests Allowed: {rt.guests_allowed} guests\n"
            f"Description: {rt.description or 'Comfortable and fully equipped room.'}\n"
            f"{rt_amenity_str}"
        ).strip()
        synced_items.append({
            "content": rt_content,
            "source_type": "room_type",
            "source_id": rt.id,
            "meta": {"title": f"Room: {rt.name}", "category": "catalog", "price": float(rt.base_price)}
        })

        # 6. Reviews & Guest Reputation
    hotel_reviews = (
        db.query(Review)
        .join(Booking, Booking.id == Review.booking_id)
        .filter(Booking.hotel_id == hotel_id, Review.deleted_at.is_(None))
        .order_by(Review.created_at.desc())
        .all()
    )
    if hotel_reviews:
        avg_rating = sum(r.rating for r in hotel_reviews) / len(hotel_reviews)
        review_lines = [
            f"Verified Guest Reviews & Ratings for {hotel.name}:",
            f"Overall Guest Rating: {avg_rating:.1f} out of 5 stars based on {len(hotel_reviews)} verified guest reviews.",
            "Guest Feedback & Sentiment:"
        ]
        for rev in hotel_reviews:
            review_lines.append(f"- Rating: {rev.rating}/5 stars - \"{rev.comment}\"")

        review_content = "\n".join(review_lines)
        synced_items.append({
            "content": review_content,
            "source_type": "review",
            "source_id": hotel.id,
            "meta": {
                "title": f"{hotel.name} - Guest Reviews & Ratings",
                "category": "reviews",
                "average_rating": round(avg_rating, 2),
                "total_reviews": len(hotel_reviews)
            }
        })

    # Generate Embeddings
    texts = [item["content"] for item in synced_items]
    embeddings = embedding_service.get_embeddings(texts)

    for idx, (item, emb) in enumerate(zip(synced_items, embeddings)):
        chunk_obj = HotelDocumentChunk(
            document_id=None,
            hotel_id=hotel_id,
            chunk_index=idx,
            content=item["content"],
            embedding=emb,
            metadata_json=item["meta"],
            source_type=item["source_type"],
            source_id=item["source_id"],
            access_level="public"
        )
        db.add(chunk_obj)

    db.commit()

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.name,
        "synced_policies": len(policies),
        "synced_amenities": len(amenities),
        "synced_room_types": len(room_types),
        "total_chunks_created": len(synced_items)
    }


def search_chunks(
    db: Session,
    query: str,
    hotel_id: Optional[uuid.UUID] = None,
    top_k: int = 5,
    access_level: str = "public"
) -> List[Dict[str, Any]]:
    """
    Searches the knowledge base using semantic vector similarity and hybrid keyword matching.
    If hotel_id is provided, restricts search to that hotel's documents and data.
    If hotel_id is None, searches across all hotels for general discovery.
    """
    if not query or not query.strip():
        return []

    q_vec = embedding_service.get_embedding(query)
    q_tokens = set(query.lower().split())

    # Build DB filter
    filters = [HotelDocumentChunk.deleted_at.is_(None)]
    if hotel_id:
        filters.append(HotelDocumentChunk.hotel_id == hotel_id)
    if access_level == "public":
        filters.append(HotelDocumentChunk.access_level == "public")

    # If native pgvector is available, perform cosine distance directly
    if HAS_PGVECTOR:
        try:
            results = (
                db.query(
                    HotelDocumentChunk,
                    Hotel.name.label("hotel_name"),
                    HotelDocumentChunk.embedding.cosine_distance(q_vec).label("distance")
                )
                .join(Hotel, Hotel.id == HotelDocumentChunk.hotel_id)
                .filter(*filters)
                .order_by("distance")
                .limit(top_k)
                .all()
            )
            hits = []
            for chunk, h_name, dist in results:
                similarity = 1.0 - float(dist)
                hits.append({
                    "chunk_id": chunk.id,
                    "hotel_id": chunk.hotel_id,
                    "hotel_name": h_name,
                    "document_id": chunk.document_id,
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "content": chunk.content,
                    "metadata": chunk.metadata_json,
                    "similarity_score": round(similarity, 4)
                })
            return hits
        except Exception:
            # Fall back to Python similarity if pgvector operator raises an issue
            pass

    # Universal / Fallback search (computes cosine similarity & keyword score)
    query_chunks = (
        db.query(HotelDocumentChunk, Hotel.name.label("hotel_name"))
        .join(Hotel, Hotel.id == HotelDocumentChunk.hotel_id)
        .filter(*filters)
        .all()
    )

    scored_candidates = []
    for chunk, h_name in query_chunks:
        if not chunk.embedding:
            continue
        vec_sim = embedding_service.compute_cosine_similarity(q_vec, chunk.embedding)

        # Keyword overlap bonus
        chunk_words = chunk.content.lower()
        matched_tokens = sum(1 for tok in q_tokens if tok in chunk_words)
        kw_score = matched_tokens / max(len(q_tokens), 1)

        # Hybrid score (70% semantic, 30% lexical)
        hybrid_score = (0.7 * vec_sim) + (0.3 * kw_score)

        if hybrid_score > 0.15:  # Relevance threshold
            scored_candidates.append({
                "chunk_id": chunk.id,
                "hotel_id": chunk.hotel_id,
                "hotel_name": h_name,
                "document_id": chunk.document_id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "content": chunk.content,
                "metadata": chunk.metadata_json,
                "similarity_score": round(float(hybrid_score), 4)
            })

    # Sort descending by hybrid score
    scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_candidates[:top_k]


def list_documents(
    db: Session,
    hotel_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0
) -> List[HotelDocument]:
    """
    Lists uploaded documents for a specific hotel.
    """
    return (
        db.query(HotelDocument)
        .options(joinedload(HotelDocument.chunks))
        .filter(HotelDocument.hotel_id == hotel_id, HotelDocument.deleted_at.is_(None))
        .order_by(HotelDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_document(db: Session, document_id: uuid.UUID) -> bool:
    """
    Soft-deletes a document and all its corresponding chunks.
    """
    doc = db.query(HotelDocument).filter(
        HotelDocument.id == document_id,
        HotelDocument.deleted_at.is_(None)
    ).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id {document_id} not found."
        )

    now = datetime.now(timezone.utc)
    doc.deleted_at = now
    db.query(HotelDocumentChunk).filter(
        HotelDocumentChunk.document_id == document_id,
        HotelDocumentChunk.deleted_at.is_(None)
    ).update({"deleted_at": now})

    db.commit()
    return True
