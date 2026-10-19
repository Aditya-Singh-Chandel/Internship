from app.utils.validation_utils import (
    validate_room_belongs_to_room_type,
    validate_room_type_availability,
    validate_assigned_rooms_not_overlapping,
    validate_string
)
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, OPERATOR_MAP, paginate_and_format
from datetime import date, datetime, timezone
from decimal import Decimal
import math
from fastapi import HTTPException
import uuid
from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.guest import Guest
from app.models.booking_guest import BookingGuest
from app.models.booking_room import BookingRoom
from app.schemas.booking import BookingCreate, BookingUpdate

def create_booking(db: Session, booking: BookingCreate):
    _data_dict = booking.model_dump()
    items_data = _data_dict.pop("items", [])

    if not items_data:
        raise HTTPException(status_code=400, detail="At least one room type item must be selected for the booking.")

    if _data_dict["checkin_date"] >= _data_dict["checkout_date"]:
        raise HTTPException(status_code=400, detail="checkout_date must be after checkin_date.")
    if _data_dict["checkin_date"] < date.today():
        raise HTTPException(status_code=400, detail="checkin_date must be today or in the future.")

    # Validate hotel exists and is active
    hotel = db.query(Hotel).filter(Hotel.id == _data_dict["hotel_id"], Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="The specified hotel does not exist.")

    # Validate primary booker exists and is active
    guest = db.query(Guest).filter(Guest.id == _data_dict["guest_id"], Guest.deleted_at.is_(None)).first()
    if not guest:
        raise HTTPException(status_code=404, detail="The specified guest does not exist.")

    nights = max(1, (_data_dict["checkout_date"] - _data_dict["checkin_date"]).days)

    # Validate and calculate price dynamically
    total_amount = Decimal("0.00")
    prepared_items = []

    for line in items_data:
        if line["quantity"] < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1.")

        rt = db.query(RoomType).filter(RoomType.id == line["room_type_id"], RoomType.deleted_at.is_(None)).first()
        if not rt:
            raise HTTPException(status_code=404, detail=f"Room type {line['room_type_id']} not found.")
        if str(rt.hotel_id) != str(_data_dict["hotel_id"]):
            raise HTTPException(status_code=400, detail=f"Room type {rt.name} does not belong to the selected hotel.")

        validate_room_type_availability(
            db=db,
            room_type_id=rt.id,
            checkin_date=_data_dict["checkin_date"],
            checkout_date=_data_dict["checkout_date"],
            requested_rooms=line["quantity"]
        )

        line_price = Decimal(rt.price)
        total_amount += line_price * line["quantity"] * Decimal(nights)

        prepared_items.append({
            "room_type_id": rt.id,
            "quantity": line["quantity"],
            "unit_price": line_price
        })

    _data_dict["total_amount"] = total_amount

    db_booking = Booking(**_data_dict)
    db.add(db_booking)
    db.flush()

    for p_item in prepared_items:
        bi = BookingItem(
            booking_id=db_booking.id,
            room_type_id=p_item["room_type_id"],
            quantity=p_item["quantity"],
            unit_price=p_item["unit_price"]
        )
        db.add(bi)
        db.flush()

        for _ in range(p_item["quantity"]):
            br = BookingRoom(
                booking_item_id=bi.id,
                room_id=None,
                guest_id=db_booking.guest_id,
                checkin_date=db_booking.checkin_date,
                checkout_date=db_booking.checkout_date,
                status="assigned"
            )
            db.add(br)

    db.commit()
    db.refresh(db_booking)
    return db_booking

def get_bookings(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    month = query_params.get("month")
    year = query_params.get("year")
    month_op = query_params.get("month_op")
    year_op = query_params.get("year_op")

    if hasattr(month_op, "value"): month_op = month_op.value
    if hasattr(year_op, "value"): year_op = year_op.value
    month_op = month_op or "eq"
    year_op = year_op or "eq"

    if month and not year:
        raise HTTPException(status_code=400, detail="year is required when month is provided")
    if year and not month:
        raise HTTPException(status_code=400, detail="month is required when year is provided")

    rooms_count = query_params.get("rooms_count")
    rooms_count_op = query_params.get("rooms_count_op")
    if hasattr(rooms_count_op, "value"): rooms_count_op = rooms_count_op.value
    rooms_count_op = rooms_count_op or "eq"

    parsed = extract_filters(query_params, extra_reserved={"month", "year", "month_op", "year_op", "rooms_count", "rooms_count_op"})

    query = db.query(Booking).options(
        joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms)
    )
    query = filter_active(query, Booking, query_params)

    # Apply month/year filter on checkin_date
    if month and year:
        op_func_month = OPERATOR_MAP[month_op]
        op_func_year = OPERATOR_MAP[year_op]
        query = query.filter(
            op_func_month(extract("month", Booking.checkin_date), month),
            op_func_year(extract("year", Booking.checkin_date), year),
        )

    query = apply_filters(query, Booking, parsed["filters"])
    query = apply_sorting(query, Booking, parsed["sort_by"], parsed["sort_order"])

    if rooms_count is not None:
        items = query.all()
        op_func = OPERATOR_MAP.get(rooms_count_op, OPERATOR_MAP["eq"])
        items = [b for b in items if op_func(sum(bi.quantity for bi in b.booking_items if bi.deleted_at is None), rooms_count)]
        page = max(1, int(query_params.get("page") or 1))
        limit = max(1, int(query_params.get("limit") or 10))
        total = len(items)
        total_pages = math.ceil(total / limit) if total > 0 else 0
        paged_items = items[(page - 1) * limit : page * limit]
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "bookings": paged_items,
        }

    return paginate_and_format(query, "bookings", query_params)

def get_booking_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Booking).options(
        joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms)
    ).filter(Booking.id == item_id)
    if not include_deleted:
        query = query.filter(Booking.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")
    return item

def update_booking(db: Session, item_id: uuid.UUID, update_data: BookingUpdate):
    item = db.query(Booking).filter(Booking.id == item_id, Booking.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    if "hotel_id" in update_data_dict and update_data_dict["hotel_id"] != item.hotel_id:
        active_rooms = [r for bi in item.booking_items if bi.deleted_at is None for r in bi.booking_rooms if r.deleted_at is None]
        if active_rooms:
            raise HTTPException(
                status_code=400,
                detail="Cannot change hotel_id for a booking that already has allocated rooms."
            )
        hotel = db.query(Hotel).filter(Hotel.id == update_data_dict["hotel_id"], Hotel.deleted_at.is_(None)).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="The specified hotel does not exist.")

    if "guest_id" in update_data_dict:
        guest = db.query(Guest).filter(Guest.id == update_data_dict["guest_id"], Guest.deleted_at.is_(None)).first()
        if not guest:
            raise HTTPException(status_code=404, detail="The specified guest does not exist.")

    dates_changed = (
        ("checkin_date" in update_data_dict and update_data_dict["checkin_date"] != item.checkin_date) or
        ("checkout_date" in update_data_dict and update_data_dict["checkout_date"] != item.checkout_date)
    )

    if dates_changed and item.status == "in_house" and "checkin_date" in update_data_dict and update_data_dict["checkin_date"] != item.checkin_date:
        raise HTTPException(status_code=400, detail="Cannot change check-in date for a booking that is already in-house.")

    for key, value in update_data_dict.items():
        setattr(item, key, value)

    if item.checkin_date >= item.checkout_date:
        raise HTTPException(status_code=400, detail="checkout_date must be after checkin_date.")

    # Revalidate availability and physical room assignments if dates changed on an active reservation
    if dates_changed and item.status not in ["cancelled", "completed"] and item.booking_items:
        # 1. Validate room types aggregate capacity for the new dates
        for b_item in item.booking_items:
            if b_item.deleted_at is None:
                validate_room_type_availability(
                    db,
                    b_item.room_type_id,
                    item.checkin_date,
                    item.checkout_date,
                    exclude_booking_id=item.id,
                    requested_rooms=b_item.quantity
                )

        # 2. Explicitly revalidate all already-assigned physical rooms against overlapping stays
        assigned_rooms = [
            r for bi in item.booking_items if bi.deleted_at is None
            for r in bi.booking_rooms if r.deleted_at is None and r.room_id is not None and r.status not in ["cancelled", "checked_out"]
        ]
        if assigned_rooms:
            assigned_room_ids = [r.room_id for r in assigned_rooms]
            validate_assigned_rooms_not_overlapping(
                db=db,
                room_ids=assigned_room_ids,
                checkin_date=item.checkin_date,
                checkout_date=item.checkout_date,
                exclude_booking_id=item.id
            )

        # 3. Synchronize dates on all active physical booking rooms
        for bi in item.booking_items:
            if bi.deleted_at is None:
                for r in bi.booking_rooms:
                    if r.deleted_at is None and r.status not in ["cancelled", "checked_out"]:
                        r.checkin_date = item.checkin_date
                        r.checkout_date = item.checkout_date

        # 4. Auto-update total_amount based on new duration if not explicitly provided
        if "total_amount" not in update_data_dict:
            nights = max(1, (item.checkout_date - item.checkin_date).days)
            item.total_amount = sum(
                Decimal(bi.unit_price) * Decimal(bi.quantity) * Decimal(nights)
                for bi in item.booking_items if bi.deleted_at is None
            )

    # If status cancelled, cancel all active allocated rooms
    if update_data_dict.get("status") == "cancelled":
        for bi in item.booking_items:
            if bi.deleted_at is None:
                for r in bi.booking_rooms:
                    if r.deleted_at is None and r.status not in ["cancelled", "checked_out"]:
                        r.status = "cancelled"

    db.commit()
    db.refresh(item)
    return item

def delete_booking(db: Session, item_id: uuid.UUID):
    item = db.query(Booking).filter(Booking.id == item_id, Booking.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Cascade soft-delete to booking_rooms
    for b_item in item.booking_items:
        db.query(BookingRoom).filter(BookingRoom.booking_item_id == b_item.id, BookingRoom.deleted_at.is_(None)).update({
            BookingRoom.deleted_at: now
        })

    # Cascade soft-delete to booking_items
    db.query(BookingItem).filter(BookingItem.booking_id == item.id, BookingItem.deleted_at.is_(None)).update({
        BookingItem.deleted_at: now
    })

    # Cascade soft-delete to booking_guests
    db.query(BookingGuest).filter(BookingGuest.booking_id == item.id, BookingGuest.deleted_at.is_(None)).update({
        BookingGuest.deleted_at: now
    })

    # Cascade soft-delete to reviews
    from app.models.review import Review
    db.query(Review).filter(Review.booking_id == item.id, Review.deleted_at.is_(None)).update({
        Review.deleted_at: now
    })

    db.commit()
    db.refresh(item)
    return item

def restore_booking(db: Session, item_id: uuid.UUID):
    item = db.query(Booking).filter(Booking.id == item_id, Booking.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present or not deleted.")

    from app.models.hotel import Hotel
    from app.models.guest import Guest
    hotel = db.query(Hotel).filter(Hotel.id == item.hotel_id, Hotel.deleted_at.is_(None)).first()
    guest = db.query(Guest).filter(Guest.id == item.guest_id, Guest.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(status_code=400, detail="Cannot restore booking: associated hotel is deleted.")
    if not guest:
        raise HTTPException(status_code=400, detail="Cannot restore booking: associated guest is deleted.")

    item.deleted_at = None

    db.query(BookingItem).filter(BookingItem.booking_id == item.id, BookingItem.deleted_at.isnot(None)).update({
        BookingItem.deleted_at: None
    })

    for b_item in item.booking_items:
        db.query(BookingRoom).filter(BookingRoom.booking_item_id == b_item.id, BookingRoom.deleted_at.isnot(None)).update({
            BookingRoom.deleted_at: None
        })

    db.query(BookingGuest).filter(BookingGuest.booking_id == item.id, BookingGuest.deleted_at.isnot(None)).update({
        BookingGuest.deleted_at: None
    })

    from app.models.review import Review
    db.query(Review).filter(Review.booking_id == item.id, Review.deleted_at.isnot(None)).update({
        Review.deleted_at: None
    })

    db.commit()
    db.refresh(item)
    return item