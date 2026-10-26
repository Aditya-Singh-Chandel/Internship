from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_staff
from app.schemas import booking_item as bi_schema
from app.services import booking_item_service

router = APIRouter(prefix="/booking-items", tags=["Booking Items"], dependencies=[Depends(require_staff)])

@router.get("", response_model=bi_schema.BookingItemPaginatedResponse)
def read_booking_items(
    booking_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    quantity: int | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    db: Session = Depends(get_db)
):
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return booking_item_service.get_booking_items(db, query_params)

@router.get("/{id}", response_model=bi_schema.BookingItemItemResponse)
def get_booking_item_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = booking_item_service.get_booking_item_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Booking item retrieved successfully", "data": item}
