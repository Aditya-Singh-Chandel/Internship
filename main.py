from fastapi import FastAPI, Form, Query
from pydantic import BaseModel, Field
from typing import Annotated, Literal
import uuid
import re
from datetime import datetime

db = {}

app = FastAPI()

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
    """Base helper to convert dd/mm/yyyy hh:mm:ss into a standard ISO timestamp without future restrictions."""
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
        return {"error": "Date must be in dd/mm/yyyy format."}
    
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
        return {"error": "Invalid date or time numbers."}
    
    if month_int in [4, 6, 9, 11] and day_int > 30:
        return {"error": "Invalid date: This month only has 30 days."}
        
    if month_int == 2:
        is_leap_year = (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0)
        if is_leap_year and day_int > 29:
            return {"error": "Invalid date: February has only 29 days in a leap year."}
        elif not is_leap_year and day_int > 28:
            return {"error": "Invalid date: February has only 28 days in a non-leap year."}
            
    return f"{year_int:04d}-{month_int:02d}-{day_int:02d}T{hour_int:02d}:{minute_int:02d}:{second_int:02d}"

def format_deadline_string(deadline_str: str | None):
    """Parses date and adds the restriction that it MUST be in the future."""
    parsed = parse_datetime_input(deadline_str)
    
    if isinstance(parsed, dict) or parsed is None:
        return parsed
        
    dt = datetime.fromisoformat(parsed)
    if dt <= datetime.now():
        return {"error": "Deadline must be a date and time in the future."}
            
    return parsed

@app.get("/")
def home():
    return {"message": "this is todo list"}

@app.get("/list")
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
        return {"error": "To filter by creation date, both 'created_at_date' and 'created_at_op' must be provided."}
    if bool(deadline_date) != bool(deadline_op):
        return {"error": "To filter by deadline, both 'deadline_date' and 'deadline_op' must be provided."}
        
    parsed_created_at = None
    if created_at_date:
        parsed_created_at = parse_datetime_input(created_at_date)
        if isinstance(parsed_created_at, dict):
            return {"error": f"Invalid format for created_at_date: {parsed_created_at['error']}"}

    parsed_deadline = None
    if deadline_date:
        parsed_deadline = parse_datetime_input(deadline_date)
        if isinstance(parsed_deadline, dict):
            return {"error": f"Invalid format for deadline_date: {parsed_deadline['error']}"}

    matched = {}
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
            matched[key] = value
            
    if sort_by:
        reverse_order = order == "desc"
        if sort_by == "deadline":
            matched = dict(sorted(matched.items(), key=lambda item: item[1]["deadline"] or ("0000-01-01T00:00:00" if reverse_order else "9999-12-31T23:59:59"), reverse=reverse_order))
        else:
            matched = dict(sorted(matched.items(), key=lambda item: item[1][sort_by], reverse=reverse_order))

    return matched

@app.get("/list/{id}")
def task_by_id(id: uuid.UUID):
    if id not in db:
        return {"error": "this task is not present"}
    return db[id]

@app.post("/list")
def add_task(addition: Annotated[task_post, Form()]):
    is_completed = addition.status == "true"
    
    new_title = " ".join(addition.title.split())
    
    if not new_title:
        return {"error": "Title cannot be empty."}
        
    if re.fullmatch(r'[\d\s]+', new_title):
        return {"error": "Title cannot consist solely of numbers."}
        
    if not re.search(r'[a-zA-Z0-9\U00010000-\U0010ffff\u2600-\u27BF]', new_title):
        return {"error": "Title cannot consist solely of special characters."}
        
    if len(new_title) > 100:
        return {"error": "Title cannot exceed 100 characters."}
        
    task_id = uuid.uuid4()
    
    parsed_deadline = format_deadline_string(addition.deadline)
    if isinstance(parsed_deadline, dict) and "error" in parsed_deadline:
        return parsed_deadline
    
    task = {
        "title": new_title, 
        "status": is_completed,
        "created_at": datetime.now().isoformat(),
        "deadline": parsed_deadline 
    }
    db[task_id] = task

    return {
        "task_id": task_id, 
        "title": task["title"], 
        "status": task["status"],
        "created_at": task["created_at"],
        "deadline": task["deadline"]
    }

@app.put("/list/{id}")
def update_task(id: uuid.UUID, update_data: Annotated[updater, Form()]):
    if id not in db:
        return {"error": "this task is not present"}

    current_task = db[id]

    if update_data.title is not None:
        req_title = " ".join(update_data.title.split())
        
        if not req_title:
            return {"error": "Title cannot be empty."}
            
        if re.fullmatch(r'[\d\s]+', req_title):
            return {"error": "Title cannot consist solely of numbers."}
            
        if not re.search(r'[a-zA-Z0-9\U00010000-\U0010ffff\u2600-\u27BF]', req_title):
            return {"error": "Title cannot consist solely of special characters."}
            
        if len(req_title) > 100:
            return {"error": "Title cannot exceed 100 characters."}
    else:
        req_title = current_task["title"]
        
    req_status = (update_data.status == "true") if update_data.status is not None else current_task["status"]
    
    if update_data.deadline is not None:
        parsed_deadline = format_deadline_string(update_data.deadline)
        if isinstance(parsed_deadline, dict) and "error" in parsed_deadline:
            return parsed_deadline
        db[id]["deadline"] = parsed_deadline

    db[id]["title"] = req_title
    db[id]["status"] = req_status

    return {
        "task_id": id, 
        "title": db[id]["title"], 
        "status": db[id]["status"], 
        "created_at": db[id]["created_at"],
        "deadline": db[id]["deadline"],
        "message": "Task updated successfully."
    }

@app.delete("/list/{id}")
def delete_task(id: uuid.UUID):
    if id not in db:
        return {"error": "this task is not present"}
    deleted = db[id]
    del db[id]
    return {
        "task_id": id,
        "title": deleted["title"], 
        "status": deleted["status"],
        "created_at": deleted["created_at"],
        "deadline": deleted["deadline"]
    }