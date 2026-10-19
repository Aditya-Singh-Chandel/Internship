from app.utils.validation_utils import (
    validate_string, validate_future_date, validate_media_linkage
)
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.media import Media
from app.schemas.media import MediaCreate, BulkMediaCreate


def create_media(db: Session, media: MediaCreate):
    _data_dict = media.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Validate foreign keys: either one is set, or if both are set, they must link to the same hotel
    validate_media_linkage(db, _data_dict.get("hotel_id"), _data_dict.get("room_type_id"))

    # If marking as primary, ensure only one primary media exists in that entity scope
    if _data_dict.get("is_primary"):
        if _data_dict.get("room_type_id"):
            db.query(Media).filter(
                Media.room_type_id == _data_dict["room_type_id"],
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})
        elif _data_dict.get("hotel_id"):
            db.query(Media).filter(
                Media.hotel_id == _data_dict["hotel_id"],
                Media.room_type_id == None,
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})

    db_media = Media(**_data_dict)
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media

def create_media_bulk(db: Session, bulk_data: BulkMediaCreate):
    # Validate foreign keys: either hotel_id or room_type_id must be provided, mutually exclusive
    validate_media_linkage(db, bulk_data.hotel_id, bulk_data.room_type_id)

    # Check primary flag logic across the incoming batch
    primary_items = [item for item in bulk_data.media if item.is_primary]
    if len(primary_items) > 1:
        raise HTTPException(status_code=400, detail="Only one media item can be marked as primary in a single batch.")

    has_primary = len(primary_items) == 1

    # If any item in the batch is marked as primary, unset existing primary media in that scope
    if has_primary:
        if bulk_data.room_type_id:
            db.query(Media).filter(
                Media.room_type_id == bulk_data.room_type_id,
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})
        elif bulk_data.hotel_id:
            db.query(Media).filter(
                Media.hotel_id == bulk_data.hotel_id,
                Media.room_type_id == None,
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})

    db_media_list = [
        Media(
            hotel_id=bulk_data.hotel_id,
            room_type_id=bulk_data.room_type_id,
            image_url=item.image_url.strip(),
            is_primary=bool(item.is_primary)
        )
        for item in bulk_data.media
    ]
    db.add_all(db_media_list)
    db.commit()
    for m in db_media_list:
        db.refresh(m)
    return db_media_list

def get_media(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Media)
    query = filter_active(query, Media, query_params)
    query = apply_filters(query, Media, parsed["filters"])
    query = apply_sorting(query, Media, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "media", query_params)

def get_media_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Media).filter(Media.id == item_id)
    if not include_deleted:
        query = query.filter(Media.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")
    return item

def update_media(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Media).filter(Media.id == item_id, Media.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    # Validate foreign keys linkage on effective values
    effective_hotel_id = update_data_dict.get("hotel_id", item.hotel_id)
    effective_room_type_id = update_data_dict.get("room_type_id", item.room_type_id)
    validate_media_linkage(db, effective_hotel_id, effective_room_type_id)

    # If updating is_primary to True, un-set existing primary in that scope
    if update_data_dict.get("is_primary"):
        if effective_room_type_id:
            db.query(Media).filter(
                Media.room_type_id == effective_room_type_id,
                Media.id != item.id,
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})
        elif effective_hotel_id:
            db.query(Media).filter(
                Media.hotel_id == effective_hotel_id,
                Media.room_type_id == None,
                Media.id != item.id,
                Media.deleted_at.is_(None)
            ).update({"is_primary": False})

    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_media(db: Session, item_id: uuid.UUID):
    item = db.query(Media).filter(Media.id == item_id, Media.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_media(db: Session, item_id: uuid.UUID):
    item = db.query(Media).filter(Media.id == item_id, Media.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present or not deleted.")

    if item.hotel_id:
        from app.models.hotel import Hotel
        hotel = db.query(Hotel).filter(Hotel.id == item.hotel_id, Hotel.deleted_at.is_(None)).first()
        if not hotel:
            raise HTTPException(status_code=400, detail="Cannot restore media: associated hotel is deleted.")
    if item.room_type_id:
        from app.models.room_type import RoomType
        rt = db.query(RoomType).filter(RoomType.id == item.room_type_id, RoomType.deleted_at.is_(None)).first()
        if not rt:
            raise HTTPException(status_code=400, detail="Cannot restore media: associated room type is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
