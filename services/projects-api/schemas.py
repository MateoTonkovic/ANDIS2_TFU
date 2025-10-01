
from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    owner_user_id: int

class ProjectOut(BaseModel):
    id: int
    name: str
    owner_user_id: int

    class Config:
        from_attributes = True
