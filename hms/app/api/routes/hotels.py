from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import hotel as hotel_schema
from app.services import hotel_service


from enum import Enum

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class StringFilterOperator(str, Enum):
    eq = "eq"
    like = "like"

class NumericFilterOperator(str, Enum):
    eq = "eq"
    lt = "lt"
    gt = "gt"
    lte = "lte"
    gte = "gte"


class HotelSortBy(str, Enum):
    name = "name"
    city = "city"
    state = "state"
    country = "country"
    rating = "rating"
router = APIRouter(prefix="/hotels", tags=["Hotels"])

@router.post("", response_model=hotel_schema.HotelListResponse, status_code=status.HTTP_201_CREATED)
def create_hotel(hotel: Annotated[hotel_schema.HotelCreate, Form()], db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.create_hotel(db=db, hotel=hotel)]}

@router.get("", response_model=hotel_schema.HotelListResponse)
def read_hotels(
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    city: str | None = Query(default=None),
    city_op: StringFilterOperator | None = Query(default=None),
    state: str | None = Query(default=None),
    state_op: StringFilterOperator | None = Query(default=None),
    country: str | None = Query(default=None),
    country_op: StringFilterOperator | None = Query(default=None),
    postal_code: str | None = Query(default=None),
    email: str | None = Query(default=None),
    email_op: StringFilterOperator | None = Query(default=None),
    phone: str | None = Query(default=None),
    latitude: Decimal | None = Query(default=None),
    latitude_op: NumericFilterOperator | None = Query(default=None),
    longitude: Decimal | None = Query(default=None),
    longitude_op: NumericFilterOperator | None = Query(default=None),
    amenity: str | None = Query(default=None, description="Filter hotels offering this amenity name (case-insensitive substring search, e.g. 'Pool', 'WiFi')"),
    amenity_id: UUID | None = Query(default=None, description="Filter hotels offering this specific amenity ID"),
    policy_type: str | None = Query(default=None, description="Filter hotels having this policy type (case-insensitive substring search, e.g. 'cancellation')"),
    policy: str | None = Query(default=None, description="Filter hotels having a policy with this keyword in description"),
    min_rating: Decimal | None = Query(default=None, ge=1.0, le=5.0, description="Filter hotels with average review rating >= min_rating (1.0 to 5.0)"),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: HotelSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List hotels with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return hotel_service.get_hotels(db=db, query_params=query_params)

@router.get("/{id}", response_model=hotel_schema.HotelListResponse)
def hotel_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"hotels": [hotel_service.get_hotel_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=hotel_schema.HotelListResponse)
def update_hotel(id: uuid.UUID, update_data: Annotated[hotel_schema.HotelUpdate, Form()], db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.update_hotel(db, id, update_data)]}

@router.delete("/{id}", response_model=hotel_schema.HotelListResponse)
def delete_hotel(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"hotels": [hotel_service.delete_hotel(db, id)]}

@router.post("/{id}/restore", response_model=hotel_schema.HotelListResponse)
def restore_hotel(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted hotel and its cascadingly deleted room types, rooms, amenities, policies, and media.
    """
    return {"hotels": [hotel_service.restore_hotel(db, id)]}
