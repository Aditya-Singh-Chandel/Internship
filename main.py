from fastapi import FastAPI, Form, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Annotated, Literal
import uuid, os, re
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.dialects.postgresql import UUID
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_CONNECTION_LOCAL")

db_class = declarative_base()
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, bind=engine)

class Task(db_class):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False)
    description = Column(String, nullable=True) 
    status = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    deadline = Column(String, nullable=True)

db_class.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

class HTTPError(BaseModel):
    detail: str
    
responses_400 = {400: {"model": HTTPError, "description": "Bad Request - Validation Error"}}
responses_404 = {404: {"model": HTTPError, "description": "Not Found - Task ID does not exist"}}
responses_400_and_404 = {**responses_400, **responses_404}

class TaskItem(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None 
    status: bool
    created_at: str
    deadline: str | None

class TaskListResponse(BaseModel):
    tasks: list[TaskItem]

class task_post(BaseModel):
    title: str = Field(
        description="Letters, numbers, emojis, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 100 chars after trimming.",
        examples=[""]
    )
    description: str | None = Field(
        default=None, 
        description="Detailed notes or description for the task. Leading and trailing whitespaces will be stripped.",
        examples=[""]
    )
    status: Literal["true", "false"] = "false"
    
    deadline: str | None = Field(
        default=None, 
        pattern=r"^\s*(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/(19\d{2}|20\d{2}|2100)(?: ([01][0-9]|2[0-3])(?:[:]([0-5][0-9])(?:[:]([0-5][0-9]))?)?)?\s*$",
        description="Format: dd/mm/yyyy OR dd/mm/yyyy hh:mm:ss. Extra spaces are allowed.",
        examples=[""]
    )

class updater(BaseModel):
    title: str | None = Field(
        default=None, 
        description="Letters, numbers, emojis, special characters, and spaces. Cannot be exclusively numbers or special characters. Max 100 chars after trimming.",
        examples=[""]
    )
    description: str | None = Field(
        default=None, 
        description="Detailed notes or description for the task. Leading and trailing whitespaces will be stripped.",
        examples=[""]
    )
    status: Literal["true", "false"] | None = None
    
    deadline: str | None = Field(
        default=None, 
        pattern=r"^\s*(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/(19\d{2}|20\d{2}|2100)(?: ([01][0-9]|2[0-3])(?:[:]([0-5][0-9])(?:[:]([0-5][0-9]))?)?)?\s*$",
        description="Format: dd/mm/yyyy OR dd/mm/yyyy hh:mm:ss. Extra spaces are allowed.",
        examples=[""]
    )

def parse_datetime_input(dt_str: str | None):
    if not dt_str:
        return None
        
    dt_str = dt_str.strip()
    parts = dt_str.split()
    
    if len(parts) > 1:
        date_part = parts[0]
        time_part = parts[1]
    else:
        date_part = parts[0]
        time_part = "00:00:00"
        
    try:
        day, month, year = date_part.split("/")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in dd/mm/yyyy format.")
    
    time_components = time_part.split(":")
    while len(time_components) < 3:
        time_components.append("00")
        
    try:
        hour, minute, second = time_components
        day_int = int(day)
        month_int = int(month)
        year_int = int(year)
        hour_int = int(hour)
        minute_int = int(minute)
        second_int = int(second)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time numbers.")
    
    if month_int in [4, 6, 9, 11] and day_int > 30:
        raise HTTPException(status_code=400, detail="Invalid date: This month only has 30 days.")
        
    if month_int == 2:
        is_leap_year = (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0)
        if is_leap_year and day_int > 29:
            raise HTTPException(status_code=400, detail="Invalid date: February has only 29 days in a leap year.")
        elif not is_leap_year and day_int > 28:
            raise HTTPException(status_code=400, detail="Invalid date: February has only 28 days in a non-leap year.")
            
    return f"{year_int:04d}-{month_int:02d}-{day_int:02d}T{hour_int:02d}:{minute_int:02d}:{second_int:02d}"

def format_deadline_string(deadline_str: str | None):
    parsed = parse_datetime_input(deadline_str)
    
    if parsed is None:
        return None
        
    dt = datetime.fromisoformat(parsed)
    if dt <= datetime.now():
        raise HTTPException(status_code=400, detail="Deadline must be a date and time in the future.")
            
    return parsed

@app.get("/")
def home():
    return {"message": "this is todo list"}

@app.get("/list", response_model=TaskListResponse, responses=responses_400)
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
        sort_column = getattr(Task, sort_by)
        if order == "desc":
            query = query.order_by(sort_column.desc().nulls_last())
        else:
            query = query.order_by(sort_column.asc().nulls_last())

    tasks = query.all()
    return {"tasks": tasks}

@app.get("/list/{id}", response_model=TaskListResponse, responses=responses_404)
def task_by_id(id: uuid.UUID, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="This task is not present.")
    
    return {"tasks": [task]}

@app.post("/list", status_code=201, response_model=TaskListResponse, responses=responses_400)
def add_task(addition: Annotated[task_post, Form()], db: Session = Depends(get_db)):
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

    return {"tasks": [new_task]}

@app.put("/list/{id}", response_model=TaskListResponse, responses=responses_400_and_404)
def update_task(id: uuid.UUID, update_data: Annotated[updater, Form()], db: Session = Depends(get_db)):
    current_task = db.query(Task).filter(Task.id == id).first()
    
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

    return {"tasks": [current_task]}

@app.delete("/list/{id}", response_model=TaskListResponse, responses=responses_404)
def delete_task(id: uuid.UUID, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="This task is not present.")
    
    db.delete(task)
    db.commit()
    
    return {"tasks": [task]}