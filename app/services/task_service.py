import re
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.datetime_utils import parse_datetime_input, format_deadline_string

def get_all_tasks(
    db: Session,
    q: str | None,
    completed: bool | None,
    sort_by: str | None,
    order: str | None,
    created_at_date: str | None,
    created_at_op: str | None,
    deadline_date: str | None,
    deadline_op: str | None,
):
    if bool(created_at_date) != bool(created_at_op):
        raise HTTPException(status_code=400, detail="To filter by creation date, both 'created_at_date' and 'created_at_op' must be provided.")
    if bool(deadline_date) != bool(deadline_op):
        raise HTTPException(status_code=400, detail="To filter by deadline, both 'deadline_date' and 'deadline_op' must be provided.")
        
    query = db.query(Task)
    
    if q is not None:
        q_cleaned = " ".join(q.split()).lower()
        query = query.filter((Task.title.ilike(f"%{q_cleaned}%")) | (Task.description.ilike(f"%{q_cleaned}%")))
        
    if completed is not None:
        query = query.filter(Task.status == completed)

    if created_at_date:
        parsed_created_at = parse_datetime_input(created_at_date)
        if created_at_op == "eq":
            query = query.filter(Task.created_at.startswith(parsed_created_at))
        elif created_at_op == "lt":
            query = query.filter(Task.created_at < parsed_created_at)
        elif created_at_op == "gt":
            query = query.filter(Task.created_at > parsed_created_at)

    if deadline_date:
        parsed_deadline = parse_datetime_input(deadline_date)
        query = query.filter(Task.deadline.isnot(None))
        if deadline_op == "eq":
            query = query.filter(Task.deadline.startswith(parsed_deadline))
        elif deadline_op == "lt":
            query = query.filter(Task.deadline < parsed_deadline)
        elif deadline_op == "gt":
            query = query.filter(Task.deadline > parsed_deadline)
            
    if sort_by:
        sort_column = getattr(Task, sort_by, None)
        if sort_column:
            if order == "desc":
                query = query.order_by(sort_column.desc().nulls_last())
            else:
                query = query.order_by(sort_column.asc().nulls_last())

    return query.all()

def get_task_by_id(db: Session, task_id: uuid.UUID):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="This task is not present.")
    return task

def create_task(db: Session, addition: TaskCreate):
    is_completed = addition.status == "true"
    new_title = " ".join(addition.title.split())
    
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if re.fullmatch(r'[\d\s]+', new_title):
        raise HTTPException(status_code=400, detail="Title cannot consist solely of numbers.")
    if not re.search(r'[a-zA-Z0-9\U00010000-\U0010ffff\u2600-\u27BF]', new_title):
        raise HTTPException(status_code=400, detail="Title cannot consist solely of special characters.")
    if len(new_title) > 100:
        raise HTTPException(status_code=400, detail="Title cannot exceed 100 characters.")
        
    parsed_deadline = format_deadline_string(addition.deadline)
    parsed_description = addition.description.strip() if addition.description is not None else None
    
    new_task = Task(
        title=new_title, 
        description=parsed_description,
        status=is_completed,
        deadline=parsed_deadline 
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

def update_task(db: Session, task_id: uuid.UUID, update_data: TaskUpdate):
    current_task = db.query(Task).filter(Task.id == task_id).first()
    
    if not current_task:
        raise HTTPException(status_code=404, detail="This task is not present.")

    if update_data.title is not None:
        req_title = " ".join(update_data.title.split())
        
        if not req_title:
            raise HTTPException(status_code=400, detail="Title cannot be empty.")
        if re.fullmatch(r'[\d\s]+', req_title):
            raise HTTPException(status_code=400, detail="Title cannot consist solely of numbers.")
        if not re.search(r'[a-zA-Z0-9\U00010000-\U0010ffff\u2600-\u27BF]', req_title):
            raise HTTPException(status_code=400, detail="Title cannot consist solely of special characters.")
        if len(req_title) > 100:
            raise HTTPException(status_code=400, detail="Title cannot exceed 100 characters.")
            
        current_task.title = req_title

    if update_data.description is not None:
        current_task.description = update_data.description.strip()
        
    if update_data.status is not None:
        current_task.status = (update_data.status == "true")
    
    if update_data.deadline is not None:
        parsed_deadline = format_deadline_string(update_data.deadline)
        current_task.deadline = parsed_deadline

    db.commit()
    db.refresh(current_task)
    return current_task

def delete_task(db: Session, task_id: uuid.UUID):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="This task is not present.")
    
    db.delete(task)
    db.commit()
    return task