import uuid
from fastapi import APIRouter, Depends, status, Form
from sqlalchemy.orm import Session
from typing import Annotated, List, Annotated
from app.api.deps import get_db
from app.schemas import role as role_schema
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("", response_model=role_schema.RoleListResponse, status_code=status.HTTP_201_CREATED)
def create_role(role: Annotated[role_schema.RoleCreate, Form()], db: Session = Depends(get_db)):
    return {"roles": [role_service.create_role(db=db, role=role)]}

@router.get("", response_model=role_schema.RoleListResponse)
def read_roles(db: Session = Depends(get_db)):
    return {"roles": role_service.get_roles(db=db)}
@router.get("/{id}", response_model=role_schema.RoleListResponse)
def role_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"roles": [role_service.get_role_by_id(db, id)]}

@router.put("/{id}", response_model=role_schema.RoleListResponse)
def update_role(id: uuid.UUID, update_data: Annotated[role_schema.RoleUpdate, Form()], db: Session = Depends(get_db)):
    return {"roles": [role_service.update_role(db, id, update_data)]}

@router.delete("/{id}", response_model=role_schema.RoleListResponse)
def delete_role(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"roles": [role_service.delete_role(db, id)]}
