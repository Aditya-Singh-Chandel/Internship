from fastapi import FastAPI, Form, Query
from pydantic import BaseModel, Field
from typing import Annotated, Literal
import uuid

db = {}

app = FastAPI()

class task_post(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^(?:[a-zA-Z][a-zA-Z0-9\s]*|[0-9][a-zA-Z0-9\s]*[a-zA-Z][a-zA-Z0-9\s]*)$"
    )
    status: Literal["true", "false"] = "false"
    count: int = Field(gt=0, lt=101, default=1)

class updater(BaseModel):
    title: str | None = Field(
        min_length=1,
        max_length=20,
        default=None, 
        pattern=r"^(?:[a-zA-Z][a-zA-Z0-9\s]*|[0-9][a-zA-Z0-9\s]*[a-zA-Z][a-zA-Z0-9\s]*)$"
    )
    status: Literal["true", "false"] | None = None
    count: int | None = Field(ge=0, lt=101, default=None)
    count_action: Literal["increase", "decrease", "set"] | None = None

@app.get("/")
def home():
    return {"message": "this is todo list"}

@app.get("/list")
def full_list(
    q: str | None = None, 
    completed: bool | None = None, 
    sort_on_title: Literal["asc", "desc"] | None = None,
    sort_on_status: Literal["asc", "desc"] | None = None,
    count: int | None = None,
    count_op: Literal["gt", "lt", "eq"] | None = None
):
    if count is not None and count_op is None:
        return {
            "error": "Missing count_op",
            "message": "Please provide a 'count_op' (gt, lt, or eq) if you are providing a 'count', or set 'count' to null."
        }
        
    if count_op is not None and count is None:
        return {
            "error": "Missing count",
            "message": "Please provide a 'count' value if you are providing a 'count_op', or set 'count_op' to null."
        }

    matched = {}
    q_stripped = q.strip() if q else None
    
    for key, value in db.items():
        title_matches = True
        status_matches = True
        count_matches = True
        
        if q_stripped is not None:
            title_matches = q_stripped in value["title"]
            
        if completed is not None:
            status_matches = value["status"] == completed
            
        if count is not None:
            if count_op == "gt":
                count_matches = value["count"] > count
            elif count_op == "lt":
                count_matches = value["count"] < count
            elif count_op == "eq":
                count_matches = value["count"] == count

        if title_matches and status_matches and count_matches:
            matched[key] = value

    if sort_on_title == "asc":
        matched = dict(sorted(matched.items(), key=lambda item: item[1]["title"]))
    elif sort_on_title == "desc":
        matched = dict(sorted(matched.items(), key=lambda item: item[1]["title"], reverse=True))

    if sort_on_status == "asc":
        matched = dict(sorted(matched.items(), key=lambda item: item[1]["status"]))
    elif sort_on_status == "desc":
        matched = dict(sorted(matched.items(), key=lambda item: item[1]["status"], reverse=True))

    return matched

@app.get("/list/{id}")
def task_by_id(id: uuid.UUID):
    if id not in db:
        return {"error": "this task is not present"}
    else:
        return db[id]

@app.post("/list")
def add_task(addition: Annotated[task_post, Form()]):
    is_completed = addition.status == "true"
    new_title = addition.title.rstrip()
    
    for t_id, task in db.items():
        if task["title"] == new_title and task["status"] == is_completed:
            if db[t_id]["count"] + addition.count > 100:
                return {
                    "error": "Count Limit Exceeded",
                    "message": f"Cannot add {addition.count} to this task. It already has {db[t_id]['count']} and the maximum allowed is 100."
                }
                
            db[t_id]["count"] += addition.count
            return {
                "task_id": t_id, 
                "title": db[t_id]["title"], 
                "status": db[t_id]["status"], 
                "count": db[t_id]["count"],
                "message": "Task already exists with this status, count increased"
            }
    
    task_id = uuid.uuid4()
    task = {"title": new_title, "status": is_completed, "count": addition.count}
    db[task_id] = task
    
    return {"task_id": task_id, "title": task["title"], "status": task["status"], "count": task["count"]}

@app.put("/list/{id}")
def update_task(id: uuid.UUID, updater: Annotated[updater, Form()]):
    if id not in db:
        return {"error": "this task is not present"}

    if updater.count is not None and updater.count_action is None:
        return {"error": "Missing count_action", "message": "Please provide a 'count_action' (increase, decrease, or set)."}
    if updater.count_action is not None and updater.count is None:
        return {"error": "Missing count", "message": "Please provide a 'count' value if you are using 'count_action'."}

    current_task = db[id]
    
    # 1. Determine Target Identity
    req_title = updater.title.rstrip() if updater.title is not None else current_task["title"]
    req_status = (updater.status == "true") if updater.status is not None else current_task["status"]
        
    # --- NEW BLOCK: PREVENT EXPLICIT IDENTITY COLLISIONS ---
    
    # If the user is explicitly trying to rename this task to a name that already exists
    if updater.title is not None and req_title != current_task["title"]:
        for t_id, task in db.items():
            if task["title"] == req_title and t_id != id:
                return {
                    "error": "Task Name Already Present",
                    "message": f"The task name '{req_title}' is already present in another record. Please update the existing task directly if you want to make changes.",
                    "existing_task_id": t_id
                }

    # If the user explicitly changes the status to match an exact counterpart that already exists
    if updater.status is not None and req_status != current_task["status"]:
        for t_id, task in db.items():
            if task["title"] == req_title and task["status"] == req_status and t_id != id:
                return {
                    "error": "Task Counterpart Already Present",
                    "message": f"A task named '{req_title}' with status '{str(req_status).lower()}' already exists. Please modify its count directly instead of changing this task's status.",
                    "existing_task_id": t_id
                }
                
    # -------------------------------------------------------

    # 2. Determine Requested Count 
    if updater.count is not None:
        if updater.count_action == "increase":
            req_count = current_task["count"] + updater.count
        elif updater.count_action == "decrease":
            req_count = current_task["count"] - updater.count
        else: # "set"
            req_count = updater.count 
    else:
        req_count = current_task["count"]
        
    if req_count < 0:
        return {"error": "Invalid Operation", "message": "Cannot decrease the count below 0."}
        
    # 3. Determine Shed Count (Items shifting to Opposite Status)
    shed_count = max(0, current_task["count"] - req_count)
    
    if req_count > 100:
        return {"error": "Count Limit Exceeded", "message": f"Requested count of {req_count} exceeds maximum of 100."}
    
    # 4. Find Existing Counterpart Tasks
    existing_1 = None # Direct match (should be None due to collision blockers above, left as safeguard)
    existing_2 = None # Opposite status match (e.g. false if we are true)
    
    for t_id, task in db.items():
        if t_id == id:
            continue
        if task["title"] == req_title:
            if task["status"] == req_status:
                existing_1 = t_id
            else:
                existing_2 = t_id

    # 5. Check Limits Before Modifying Anything
    if existing_1 and req_count > 0:
        if db[existing_1]["count"] + req_count > 100:
            return {"error": "Limit Exceeded", "message": "Merging these items would exceed the 100 limit in the target task."}
    if existing_2 and shed_count > 0:
        if db[existing_2]["count"] + shed_count > 100:
            return {"error": "Limit Exceeded", "message": "Transferring decreased items would exceed the 100 limit in the opposite task."}

    # 6. Apply Changes (Bucket 2 - Shed Items transfer to opposite status)
    bucket_2_id = None
    if shed_count > 0:
        if existing_2:
            db[existing_2]["count"] += shed_count
            bucket_2_id = existing_2
        else:
            new_id = uuid.uuid4()
            db[new_id] = {"title": req_title, "status": not req_status, "count": shed_count}
            bucket_2_id = new_id

    # 7. Apply Changes (Bucket 1 - Requested Items stay here)
    bucket_1_id = None
    if req_count > 0:
        if existing_1:
            db[existing_1]["count"] += req_count
            bucket_1_id = existing_1
            del db[id] 
        else:
            db[id]["title"] = req_title
            db[id]["status"] = req_status
            db[id]["count"] = req_count
            bucket_1_id = id
    else:
        # User reduced the count to exactly 0, meaning all items transferred to opposite status
        del db[id]

    # 8. Prepare Dynamic Success Message
    if req_count == 0:
        msg = "Task count reached 0. Items transferred to opposite status and original task removed."
    elif shed_count > 0:
        msg = "Task updated and decreased items were seamlessly transferred to the opposite status."
    elif existing_1 and bucket_1_id == existing_1:
        msg = "Task updated and merged with an identical existing task."
    else:
        msg = "Task updated successfully."

    final_id = bucket_1_id if bucket_1_id else bucket_2_id

    return {
        "task_id": final_id, 
        "title": db[final_id]["title"], 
        "status": db[final_id]["status"], 
        "count": db[final_id]["count"],
        "message": msg
    }
    
@app.delete("/list/{id}")
def delete_task(id: uuid.UUID):
    if id not in db:
        return {"error": "this task is not present"}
    else:
        deleted = db[id]
        del db[id]
        return {
            "task_id": id,
            "title": deleted["title"], 
            "status": deleted["status"],
            "count": deleted["count"]
        }