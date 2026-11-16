import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.booking_item import BookingItem
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from app.utils.scoping_utils import bookings_in_scope

def get_booking_items(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    hotel_ids = query_params.pop("_hotel_ids", None)
    parsed = extract_filters(query_params)
    query = db.query(BookingItem)
    query = filter_active(query, BookingItem, query_params)
    if hotel_ids is not None:
        query = query.filter(BookingItem.booking_id.in_(bookings_in_scope(hotel_ids)))
    query = apply_filters(query, BookingItem, parsed["filters"])
    query = apply_sorting(query, BookingItem, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "booking_items", query_params)

def get_booking_item_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(BookingItem).filter(BookingItem.id == item_id)
    if not include_deleted:
        query = query.filter(BookingItem.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingItem is not present.")
    return item
