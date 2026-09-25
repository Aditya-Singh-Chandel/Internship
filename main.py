from fastapi import FastAPI, Form, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Annotated, Literal
import uuid
import re
from datetime import datetime

db = {}

app = FastAPI()

class HTTPError(BaseModel):
    detail: str
    
responses_400 = {400: {"model": HTTPError, "description": "Bad Request - Validation Error"}}
responses_404 = {404: {"model": HTTPError, "description": "Not Found - Task ID does not exist"}}
responses_400_and_404 = {**responses_400, **responses_404}

class TaskItem(BaseModel):
    id: uuid.UUID
    title: str
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
    deadline_op: Literal["eq", "lt", "gt"] | None = None
):
    if bool(created_at_date) != bool(created_at_op):
        raise HTTPException(status_code=400, detail="To filter by creation date, both 'created_at_date' and 'created_at_op' must be provided.")
    if bool(deadline_date) != bool(deadline_op):
        raise HTTPException(status_code=400, detail="To filter by deadline, both 'deadline_date' and 'deadline_op' must be provided.")
        
    parsed_created_at = None
    if created_at_date:
        parsed_created_at = parse_datetime_input(created_at_date)

    parsed_deadline = None
    if deadline_date:
        parsed_deadline = parse_datetime_input(deadline_date)

    matched = []
    q_cleaned = " ".join(q.split()).lower() if q is not None else None

    for key, value in db.items():
        title_matches = True
        status_matches = True
        created_matches = True
        deadline_matches = True
        
        if q_cleaned is not None:
            title_matches = q_cleaned in value["title"].lower()
            
        if completed is not None:
            status_matches = value["status"] == completed

        if parsed_created_at:
            task_created = value["created_at"][:19]
            if created_at_op == "eq" and task_created != parsed_created_at:
                created_matches = False
            elif created_at_op == "lt" and task_created >= parsed_created_at:
                created_matches = False
            elif created_at_op == "gt" and task_created <= parsed_created_at:
                created_matches = False

        if parsed_deadline:
            task_deadline = value["deadline"]
            if task_deadline:
                task_deadline = task_deadline[:19]
                if deadline_op == "eq" and task_deadline != parsed_deadline:
                    deadline_matches = False
                elif deadline_op == "lt" and task_deadline >= parsed_deadline:
                    deadline_matches = False
                elif deadline_op == "gt" and task_deadline <= parsed_deadline:
                    deadline_matches = False
            else:
                deadline_matches = False

        if title_matches and status_matches and created_matches and deadline_matches:
            matched.append({
                "id": key,
                "title": value["title"],
                "status": value["status"],
                "created_at": value["created_at"],
                "deadline": value["deadline"]
            })
            
    if sort_by:
        reverse_order = order == "desc"
        if sort_by == "deadline":
            matched.sort(
                key=lambda item: item["deadline"] or ("0000-01-01T00:00:00" if reverse_order else "9999-12-31T23:59:59"), 
                reverse=reverse_order
            )
        else:
            matched.sort(key=lambda item: item[sort_by], reverse=reverse_order)

    return {"tasks": matched}


@app.get("/list/{id}", response_model=TaskListResponse, responses=responses_404)
def task_by_id(id: uuid.UUID):
    if id not in db:
        raise HTTPException(status_code=404, detail="This task is not present.")
    
    task = db[id]
    return {"tasks": [{
        "id": id,
        "title": task["title"],
        "status": task["status"],
        "created_at": task["created_at"],
        "deadline": task["deadline"]
    }]}

@app.post("/list", status_code=201, response_model=TaskListResponse, responses=responses_400)
def add_task(addition: Annotated[task_post, Form()]):
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
        
    task_id = uuid.uuid4()
    
    parsed_deadline = format_deadline_string(addition.deadline)
    
    task = {
        "title": new_title, 
        "status": is_completed,
        "created_at": datetime.now().isoformat(),
        "deadline": parsed_deadline 
    }
    db[task_id] = task

    return {"tasks": [{
        "id": task_id, 
        "title": task["title"], 
        "status": task["status"],
        "created_at": task["created_at"],
        "deadline": task["deadline"]
    }]}


@app.put("/list/{id}", response_model=TaskListResponse, responses=responses_400_and_404)
def update_task(id: uuid.UUID, update_data: Annotated[updater, Form()]):
    if id not in db:
        raise HTTPException(status_code=404, detail="This task is not present.")

    current_task = db[id]

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
    else:
        req_title = current_task["title"]
        
    req_status = (update_data.status == "true") if update_data.status is not None else current_task["status"]
    
    if update_data.deadline is not None:
        parsed_deadline = format_deadline_string(update_data.deadline)
        db[id]["deadline"] = parsed_deadline

    db[id]["title"] = req_title
    db[id]["status"] = req_status

    return {"tasks": [{
        "id": id, 
        "title": db[id]["title"], 
        "status": db[id]["status"], 
        "created_at": db[id]["created_at"],
        "deadline": db[id]["deadline"]
    }]}


@app.delete("/list/{id}", response_model=TaskListResponse, responses=responses_404)
def delete_task(id: uuid.UUID):
    if id not in db:
        raise HTTPException(status_code=404, detail="This task is not present.")
    deleted = db[id]
    del db[id]
    
    return {"tasks": [{
        "id": id,
        "title": deleted["title"], 
        "status": deleted["status"],
        "created_at": deleted["created_at"],
        "deadline": deleted["deadline"]
    }]}