
from fastapi import FastAPI, HTTPException
from db import Base, engine, session_scope, init_schema
from models import Project
from schemas import ProjectCreate, ProjectOut

app = FastAPI(title="Projects API")

init_schema()
Base.metadata.create_all(bind=engine)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate):
    with session_scope() as s:
        p = Project(name=payload.name, owner_user_id=payload.owner_user_id)
        s.add(p)
        s.flush()
        return p

@app.get("/projects", response_model=list[ProjectOut])
def list_projects():
    with session_scope() as s:
        return s.query(Project).order_by(Project.id).all()

@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int):
    with session_scope() as s:
        p = s.get(Project, project_id)
        if not p:
            raise HTTPException(status_code=404, detail="not found")
        return p
