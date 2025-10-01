
from fastapi import FastAPI, HTTPException
from db import Base, engine, session_scope, init_schema
from models import Task, TaskActivity
from schemas import TaskCreate, TaskOut

app = FastAPI(title="Tasks API")

init_schema()
Base.metadata.create_all(bind=engine)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate):
    # ACID example: create Task + initial TaskActivity atomically
    with session_scope() as s:
        t = Task(title=payload.title, project_id=payload.project_id, assignee_user_id=payload.assignee_user_id)
        s.add(t)
        s.flush()
        a = TaskActivity(task_id=t.id, action="CREATED", note="Task created")
        s.add(a)
        return t

@app.get("/tasks", response_model=list[TaskOut])
def list_tasks():
    with session_scope() as s:
        return s.query(Task).order_by(Task.id).all()

@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t:
            raise HTTPException(status_code=404, detail="not found")
        return t
