from app.utils.validation_utils import validate_string, validate_future_date, validate_amenity_linkage
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.amenity import Amenity
from app.schemas.amenity import AmenityCreate, BulkAmenityCreate


def create_amenity(db: Session, amenity: AmenityCreate):
    _data_dict = amenity.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Validate cross-reference linkage between hotel and room_type
    validate_amenity_linkage(db, _data_dict.get("hotel_id"), _data_dict.get("room_type_id"))

    db_amenity = Amenity(**_data_dict)
    db.add(db_amenity)
    db.commit()
    db.refresh(db_amenity)
    return db_amenity

def create_amenities_bulk(db: Session, bulk_data: BulkAmenityCreate):
    if not bulk_data.hotel_id and not bulk_data.room_type_id:
        raise HTTPException(status_code=400, detail="Must provide at least hotel_id or room_type_id for amenities.")

    # Validate cross-reference linkage between hotel and room_type
    validate_amenity_linkage(db, bulk_data.hotel_id, bulk_data.room_type_id)

    # Check for intra-batch duplicate names
    cleaned_names = [validate_string("name", item.name) for item in bulk_data.amenities]
    seen = set()
    intra_dups = []
    for name in cleaned_names:
        low = name.lower()
        if low in seen:
            intra_dups.append(name)
        seen.add(low)
    if intra_dups:
        raise HTTPException(status_code=400, detail=f"Duplicate amenity names provided in request batch: {', '.join(set(intra_dups))}.")

    # Check for existing amenities with the same name in the same scope
    query = db.query(Amenity.name).filter(Amenity.deleted_at.is_(None))
    if bulk_data.room_type_id:
        query = query.filter(Amenity.room_type_id == bulk_data.room_type_id)
    elif bulk_data.hotel_id:
        query = query.filter(Amenity.hotel_id == bulk_data.hotel_id, Amenity.room_type_id == None)

    existing_names = {row[0].lower() for row in query.all()}
    conflicts = [name for name in cleaned_names if name.lower() in existing_names]
    if conflicts:
        raise HTTPException(status_code=400, detail=f"Amenity already exists in this scope: {', '.join(conflicts)}.")

    db_amenities = [
        Amenity(
            hotel_id=bulk_data.hotel_id,
            room_type_id=bulk_data.room_type_id,
            name=name
        )
        for name in cleaned_names
    ]
    db.add_all(db_amenities)
    db.commit()
    for a in db_amenities:
        db.refresh(a)
    return db_amenities

def get_amenities(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Amenity)
    query = filter_active(query, Amenity, query_params)
    query = apply_filters(query, Amenity, parsed["filters"])
    query = apply_sorting(query, Amenity, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "amenities", query_params)

def get_amenity_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Amenity).filter(Amenity.id == item_id)
    if not include_deleted:
        query = query.filter(Amenity.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")
    return item

def update_amenity(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Amenity).filter(Amenity.id == item_id, Amenity.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    effective_hotel_id = update_data_dict.get("hotel_id", item.hotel_id)
    effective_room_type_id = update_data_dict.get("room_type_id", item.room_type_id)
    validate_amenity_linkage(db, effective_hotel_id, effective_room_type_id)

    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_amenity(db: Session, item_id: uuid.UUID):
    item = db.query(Amenity).filter(Amenity.id == item_id, Amenity.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_amenity(db: Session, item_id: uuid.UUID):
    item = db.query(Amenity).filter(Amenity.id == item_id, Amenity.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present or not deleted.")

    if item.hotel_id:
        from app.models.hotel import Hotel
        hotel = db.query(Hotel).filter(Hotel.id == item.hotel_id, Hotel.deleted_at.is_(None)).first()
        if not hotel:
            raise HTTPException(status_code=400, detail="Cannot restore amenity: associated hotel is deleted.")
    if item.room_type_id:
        from app.models.room_type import RoomType
        rt = db.query(RoomType).filter(RoomType.id == item.room_type_id, RoomType.deleted_at.is_(None)).first()
        if not rt:
            raise HTTPException(status_code=400, detail="Cannot restore amenity: associated room type is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
