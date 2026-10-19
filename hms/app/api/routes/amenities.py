from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import amenity as amenity_schema
from app.services import amenity_service


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


class AmenitySortBy(str, Enum):
    name = "name"
router = APIRouter(prefix="/amenities", tags=["Amenities"])

@router.post("", response_model=amenity_schema.AmenityListResponse, status_code=status.HTTP_201_CREATED)
def create_amenity(amenity: Annotated[amenity_schema.AmenityCreate, Form()], db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.create_amenity(db=db, amenity=amenity)]}

@router.post("/bulk", response_model=amenity_schema.AmenityListResponse, status_code=status.HTTP_201_CREATED)
def create_amenities_bulk(bulk_data: amenity_schema.BulkAmenityCreate, db: Session = Depends(get_db)):
    """
    Bulk create multiple amenities under a hotel or room type using JSON.
    """
    return {"amenities": amenity_service.create_amenities_bulk(db=db, bulk_data=bulk_data)}

@router.get("", response_model=amenity_schema.AmenityListResponse)
def read_amenities(
    hotel_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: AmenitySortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List amenities with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return amenity_service.get_amenities(db=db, query_params=query_params)

@router.get("/{id}", response_model=amenity_schema.AmenityListResponse)
def amenity_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"amenities": [amenity_service.get_amenity_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=amenity_schema.AmenityListResponse)
def update_amenity(id: uuid.UUID, update_data: Annotated[amenity_schema.AmenityUpdate, Form()], db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.update_amenity(db, id, update_data)]}

@router.delete("/{id}", response_model=amenity_schema.AmenityListResponse)
def delete_amenity(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"amenities": [amenity_service.delete_amenity(db, id)]}

@router.post("/{id}/restore", response_model=amenity_schema.AmenityListResponse)
def restore_amenity(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted amenity.
    """
    return {"amenities": [amenity_service.restore_amenity(db, id)]}
