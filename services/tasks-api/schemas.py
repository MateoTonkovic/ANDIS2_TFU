
from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    project_id: int
    assignee_user_id: int | None = None

class TaskOut(BaseModel):
    id: int
    title: str
    project_id: int
    assignee_user_id: int | None = None

    class Config:
        from_attributes = True
