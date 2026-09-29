from fastapi import APIRouter, Form, Query, Depends
from typing import Annotated, Literal
import uuid
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.task import TaskListResponse, TaskCreate, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/list", tags=["tasks"])

@router.get("", response_model=TaskListResponse)
def full_list(
    q: str | None = Query(default=None, examples=[""]), 
    completed: bool | None = None,
    sort_by : Literal["title", "status", "created_at", "deadline"] | None = "created_at",
    order : Literal["asc", "desc"] | None = "asc",
    created_at_date: str | None = Query(default=None, examples=[""]),
    created_at_op: Literal["eq", "lt", "gt"] | None = None,
    deadline_date: str | None = Query(default=None, examples=[""]),
    deadline_op: Literal["eq", "lt", "gt"] | None = None,
    db: Session = Depends(get_db)
):
    tasks = task_service.get_all_tasks(
        db=db, q=q, completed=completed, sort_by=sort_by, order=order,
        created_at_date=created_at_date, created_at_op=created_at_op,
        deadline_date=deadline_date, deadline_op=deadline_op
    )
    return {"tasks": tasks}

@router.get("/{id}", response_model=TaskListResponse)
def task_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    task = task_service.get_task_by_id(db, id)
    return {"tasks": [task]}

@router.post("", status_code=201, response_model=TaskListResponse)
def add_task(addition: Annotated[TaskCreate, Form()], db: Session = Depends(get_db)):
    task = task_service.create_task(db, addition)
    return {"tasks": [task]}

@router.put("/{id}", response_model=TaskListResponse)
def update_task(id: uuid.UUID, update_data: Annotated[TaskUpdate, Form()], db: Session = Depends(get_db)):
    task = task_service.update_task(db, id, update_data)
    return {"tasks": [task]}

@router.delete("/{id}", response_model=TaskListResponse)
def delete_task(id: uuid.UUID, db: Session = Depends(get_db)):
    task = task_service.delete_task(db, id)
    return {"tasks": [task]}