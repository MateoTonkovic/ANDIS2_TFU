
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from db import Base, engine, session_scope, init_schema
from models import User, AuditLog
from schemas import UserCreate, UserOut

app = FastAPI(title="Users API")

# Init schema and tables
init_schema()
Base.metadata.create_all(bind=engine)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate):
    # ACID example: create user + audit log atomically
    with session_scope() as s:
        if s.query(User).filter_by(email=payload.email).first():
            raise HTTPException(status_code=409, detail="email already exists")
        u = User(name=payload.name, email=payload.email)
        s.add(u)
        s.flush()  # get u.id
        log = AuditLog(action="CREATE_USER", detail=f"User {u.id} created with email {u.email}")
        s.add(log)
        return u

@app.get("/users", response_model=list[UserOut])
def list_users():
    with session_scope() as s:
        return s.query(User).order_by(User.id).all()

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="not found")
        return u
