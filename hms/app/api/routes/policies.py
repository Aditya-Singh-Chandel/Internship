from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import policy as policy_schema
from app.services import policy_service


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


class PolicySortBy(str, Enum):
    policy_type = "policy_type"
router = APIRouter(prefix="/policies", tags=["Policies"])

@router.post("", response_model=policy_schema.PolicyListResponse, status_code=status.HTTP_201_CREATED)
def create_policy(policy: Annotated[policy_schema.PolicyCreate, Form()], db: Session = Depends(get_db)):
    return {"policies": [policy_service.create_policy(db=db, policy=policy)]}

@router.get("", response_model=policy_schema.PolicyListResponse)
def read_policies(
    hotel_id: UUID | None = Query(default=None),
    policy_type: str | None = Query(default=None),
    policy_type_op: StringFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: PolicySortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List policies with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return policy_service.get_policies(db=db, query_params=query_params)

@router.get("/{id}", response_model=policy_schema.PolicyListResponse)
def policy_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"policies": [policy_service.get_policy_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=policy_schema.PolicyListResponse)
def update_policy(id: uuid.UUID, update_data: Annotated[policy_schema.PolicyUpdate, Form()], db: Session = Depends(get_db)):
    return {"policies": [policy_service.update_policy(db, id, update_data)]}

@router.delete("/{id}", response_model=policy_schema.PolicyListResponse)
def delete_policy(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"policies": [policy_service.delete_policy(db, id)]}

@router.post("/{id}/restore", response_model=policy_schema.PolicyListResponse)
def restore_policy(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted policy.
    """
    return {"policies": [policy_service.restore_policy(db, id)]}
