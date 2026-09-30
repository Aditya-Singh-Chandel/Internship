from pydantic import BaseModel, Field
from typing import Literal
import uuid

class TaskItem(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None 
    status: bool
    created_at: str
    deadline: str | None

class TaskListResponse(BaseModel):
    tasks: list[TaskItem]

class TaskCreate(BaseModel):
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

class TaskUpdate(BaseModel):
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