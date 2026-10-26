from typing import Annotated
from uuid import UUID
from enum import Enum
from fastapi import APIRouter, Depends, status, Form, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_admin
from app.schemas import role as role_schema
from app.schemas.common import ActionResponse, SortOrder, FilterOperator
from app.services import role_service

class RoleSortBy(str, Enum):
    name = "name"

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("", response_model=role_schema.RoleItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_role(role: Annotated[role_schema.RoleCreate, Form()], db: Session = Depends(get_db)):
    """Only Admins can create new system roles."""
    item = role_service.create_role(db=db, role=role)
    return {"success": True, "message": "Role created successfully", "data": item}

@router.get("", response_model=role_schema.RolePaginatedResponse)
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
    List roles with advanced filtering and sorting. Accessible to view available roles.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return role_service.get_roles(db=db, query_params=query_params)

@router.get("/{id}", response_model=role_schema.RoleItemResponse)
def role_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    """View role details by ID."""
    item = role_service.get_role_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Role retrieved successfully", "data": item}

@router.put("/{id}", response_model=role_schema.RoleItemResponse, dependencies=[Depends(require_admin)])
def update_role(id: UUID, update_data: Annotated[role_schema.RoleUpdate, Form()], db: Session = Depends(get_db)):
    """Only Admins can update roles."""
    item = role_service.update_role(db, id, update_data)
    return {"success": True, "message": "Role updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse, dependencies=[Depends(require_admin)])
def delete_role(id: UUID, db: Session = Depends(get_db)):
    """Only Admins can delete roles."""
    item = role_service.delete_role(db, id)
    return {"success": True, "message": "Role deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=role_schema.RoleItemResponse, dependencies=[Depends(require_admin)])
def restore_role(id: UUID, db: Session = Depends(get_db)):
    """Only Admins can restore soft-deleted roles."""
    item = role_service.restore_role(db, id)
    return {"success": True, "message": "Role restored successfully", "data": item}
