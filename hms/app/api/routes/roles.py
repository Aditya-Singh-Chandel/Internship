from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import role as role_schema
from app.services import role_service
from enum import Enum

class RoleSortBy(str, Enum):
    name = "name"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class FilterOperator(str, Enum):
    eq = "eq"
    like = "like"

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("", response_model=role_schema.RoleListResponse, status_code=status.HTTP_201_CREATED)
def create_role(role: Annotated[role_schema.RoleCreate, Form()], db: Session = Depends(get_db)):
    return {"roles": [role_service.create_role(db=db, role=role)]}

@router.get("", response_model=role_schema.RoleListResponse)
def read_roles(
    name: str | None = Query(default=None),
    name_op: FilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: RoleSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default=SortOrder.asc),
    db: Session = Depends(get_db)
):
    """
    List roles with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return role_service.get_roles(db=db, query_params=query_params)

@router.get("/{id}", response_model=role_schema.RoleListResponse)
def role_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"roles": [role_service.get_role_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=role_schema.RoleListResponse)
def update_role(id: uuid.UUID, update_data: Annotated[role_schema.RoleUpdate, Form()], db: Session = Depends(get_db)):
    return {"roles": [role_service.update_role(db, id, update_data)]}

@router.delete("/{id}", response_model=role_schema.RoleListResponse)
def delete_role(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"roles": [role_service.delete_role(db, id)]}

@router.post("/{id}/restore", response_model=role_schema.RoleListResponse)
def restore_role(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted role.
    """
    return {"roles": [role_service.restore_role(db, id)]}
