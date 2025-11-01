
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pybreaker import CircuitBreakerError
from db import Base, engine, session_scope, init_schema
from models import Task, TaskActivity
from schemas import TaskCreate, TaskOut
from patterns import CacheAside, RateLimiter, check_redis_health, call_external_service
from messaging import AsyncTaskProcessor, check_rabbitmq_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tasks API")

init_schema()
Base.metadata.create_all(bind=engine)

# Inicializar patrones
cache = CacheAside(prefix="tasks", ttl=300)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
task_processor = AsyncTaskProcessor("task_tasks")

USERS_API_URL = os.getenv("USERS_API_URL", "http://users-api:8000")
PROJECTS_API_URL = os.getenv("PROJECTS_API_URL", "http://projects-api:8000")

# Registrar handlers de tareas asíncronas
def handle_task_notification(data: dict):
    """Ejemplo de handler async para notificaciones de tarea"""
    logger.info(f"Procesando notificación de tarea: {data}")

task_processor.register_handler("task_notification", handle_task_notification)

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando Tasks API con patrones arquitectónicos")
    logger.info("Queue-based load leveling listo ")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Deteniendo Tasks API")
    task_processor.stop_worker()

# Middleware de rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    identifier = request.client.host
    if request.url.path in ["/healthz", "/health"]:
        return await call_next(request)
    if not rate_limiter.is_allowed(identifier):
        return JSONResponse(
            status_code=429,
            content={"detail": "Límite de rate excedido. Intente nuevamente más tarde."}
        )
    return await call_next(request)

@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Servicio temporalmente no disponible. Circuit breaker está abierto."}
    )

@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Patrón Enhanced Health Endpoint Monitoring"""
    health_status = {
        "service": "tasks-api",
        "status": "healthy",
        "dependencies": {}
    }
    
    # Verificar base de datos
    try:
        with session_scope() as s:
            s.execute(text("SELECT 1"))
        health_status["dependencies"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["dependencies"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Verificar Redis
    redis_health = check_redis_health()
    health_status["dependencies"]["redis"] = redis_health
    if redis_health["status"] != "healthy":
        health_status["status"] = "degraded"
    
    # Verificar RabbitMQ
    rabbitmq_health = check_rabbitmq_health()
    health_status["dependencies"]["rabbitmq"] = rabbitmq_health
    if rabbitmq_health["status"] != "healthy":
        health_status["status"] = "degraded"
    
    # Verificar servicios dependientes con circuit breaker
    try:
        users_health = await call_external_service(f"{USERS_API_URL}/healthz")
        health_status["dependencies"]["users-api"] = {"status": "healthy"}
    except CircuitBreakerError:
        health_status["dependencies"]["users-api"] = {"status": "circuit_open"}
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["users-api"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    try:
        projects_health = await call_external_service(f"{PROJECTS_API_URL}/healthz")
        health_status["dependencies"]["projects-api"] = {"status": "healthy"}
    except CircuitBreakerError:
        health_status["dependencies"]["projects-api"] = {"status": "circuit_open"}
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["projects-api"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(payload: TaskCreate):
    """
    Crear tarea con validación via patrón Circuit Breaker
    """
    # Validar que usuario existe usando patrones Circuit Breaker + Retry
    try:
        user_url = f"{USERS_API_URL}/users/{payload.assignee_user_id}"
        await call_external_service(user_url)
    except CircuitBreakerError:
        raise HTTPException(
            status_code=503,
            detail="Servicio de usuarios temporalmente no disponible. Circuit breaker está abierto."
        )
    except Exception as e:
        logger.error(f"Falló al validar usuario: {e}")
        raise HTTPException(status_code=400, detail=f"assignee_user_id inválido: {payload.assignee_user_id}")
    
    # Validar que proyecto existe
    try:
        project_url = f"{PROJECTS_API_URL}/projects/{payload.project_id}"
        await call_external_service(project_url)
    except CircuitBreakerError:
        raise HTTPException(
            status_code=503,
            detail="Servicio de proyectos temporalmente no disponible. Circuit breaker está abierto."
        )
    except Exception as e:
        logger.error(f"Falló al validar proyecto: {e}")
        raise HTTPException(status_code=400, detail=f"project_id inválido: {payload.project_id}")
    
    # Ejemplo ACID: crear Task + TaskActivity inicial atómicamente
    with session_scope() as s:
        t = Task(title=payload.title, project_id=payload.project_id, assignee_user_id=payload.assignee_user_id)
        s.add(t)
        s.flush()
        a = TaskActivity(task_id=t.id, action="CREATED", note="Task created")
        s.add(a)
        
        # Invalidar cache
        cache.invalidate_pattern("task:*")
        cache.invalidate_pattern("tasks:list")
        
        # Encolar notificación async
        try:
            task_processor.enqueue_task("task_notification", {
                "task_id": t.id,
                "assignee_user_id": t.assignee_user_id,
                "project_id": t.project_id,
                "type": "assigned"
            })
        except Exception as e:
            logger.warning(f"Falló al encolar notificación: {e}")
        
        return t

@app.get("/tasks", response_model=list[TaskOut])
def list_tasks():
    """Listar tareas con patrón Cache-Aside"""
    cache_key = "tasks:list"
    cached_tasks = cache.get(cache_key)
    
    if cached_tasks is not None:
        return cached_tasks
    
    with session_scope() as s:
        tasks = s.query(Task).order_by(Task.id).all()
        task_list = [TaskOut.model_validate(t) for t in tasks]
        cache.set(cache_key, [t.model_dump() for t in task_list])
        return task_list

@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    """Obtener tarea por ID con patrón Cache-Aside"""
    cache_key = f"task:{task_id}"
    cached_task = cache.get(cache_key)
    
    if cached_task is not None:
        return TaskOut(**cached_task)
    
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t:
            raise HTTPException(status_code=404, detail="not found")
        task_out = TaskOut.model_validate(t)
        cache.set(cache_key, task_out.model_dump())
        return task_out
