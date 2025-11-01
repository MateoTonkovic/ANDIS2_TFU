
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pybreaker import CircuitBreakerError
from db import Base, engine, session_scope, init_schema
from models import Project
from schemas import ProjectCreate, ProjectOut
from patterns import CacheAside, RateLimiter, check_redis_health, call_external_service
from messaging import AsyncTaskProcessor, check_rabbitmq_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Projects API")

init_schema()
Base.metadata.create_all(bind=engine)

# Inicializar patrones
cache = CacheAside(prefix="projects", ttl=300)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
task_processor = AsyncTaskProcessor("project_tasks")

USERS_API_URL = os.getenv("USERS_API_URL", "http://users-api:8000")

# Registrar handlers de tareas asíncronas
def handle_project_notification(data: dict):
    """Ejemplo de handler async para notificaciones de proyecto"""
    logger.info(f"Procesando notificación de proyecto: {data}")

task_processor.register_handler("project_notification", handle_project_notification)

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando Projects API con patrones arquitectónicos")
    logger.info("Queue-based load leveling listo ")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Deteniendo Projects API")
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
        "service": "projects-api",
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
    
    # Verificar Users API con circuit breaker
    try:
        users_health = await call_external_service(f"{USERS_API_URL}/healthz")
        health_status["dependencies"]["users-api"] = {"status": "healthy"}
    except CircuitBreakerError:
        health_status["dependencies"]["users-api"] = {"status": "circuit_open"}
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["users-api"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(payload: ProjectCreate):
    logger.info(f"Creando proyecto '{payload.name}' para user_id={payload.owner_user_id}")
    
    # Validar que usuario existe usando patrones Circuit Breaker + Retry
    try:
        user_url = f"{USERS_API_URL}/users/{payload.owner_user_id}"
        logger.info(f"Validando que usuario existe en: {user_url}")
        user_data = await call_external_service(user_url)
        logger.info(f"Validación de usuario exitosa: {user_data.get('id')}")
    except CircuitBreakerError as e:
        logger.error(f"Circuit breaker está abierto para validación de usuario: {e}")
        raise HTTPException(
            status_code=503,
            detail="Servicio de usuarios temporalmente no disponible. Circuit breaker está abierto."
        )
    except Exception as e:
        logger.error(f"Falló al validar usuario {payload.owner_user_id}: {type(e).__name__} - {e}")
        raise HTTPException(status_code=400, detail=f"user_id inválido: {payload.owner_user_id}")
    
    # Crear proyecto
    with session_scope() as s:
        p = Project(name=payload.name, owner_user_id=payload.owner_user_id)
        s.add(p)
        s.flush()
        
        # Invalidar cache
        cache.invalidate_pattern("project:*")
        cache.invalidate_pattern("projects:list")
        
        # Encolar notificación async
        try:
            task_processor.enqueue_task("project_notification", {
                "project_id": p.id,
                "owner_user_id": p.owner_user_id,
                "type": "created"
            })
        except Exception as e:
            logger.warning(f"Falló al encolar notificación: {e}")
        
        return p

@app.get("/projects", response_model=list[ProjectOut])
def list_projects():
    """Listar proyectos con patrón Cache-Aside"""
    cache_key = "projects:list"
    cached_projects = cache.get(cache_key)
    
    if cached_projects is not None:
        return cached_projects
    
    with session_scope() as s:
        projects = s.query(Project).order_by(Project.id).all()
        project_list = [ProjectOut.model_validate(p) for p in projects]
        cache.set(cache_key, [p.model_dump() for p in project_list])
        return project_list

@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int):
    """Obtener proyecto por ID con patrón Cache-Aside"""
    cache_key = f"project:{project_id}"
    cached_project = cache.get(cache_key)
    
    if cached_project is not None:
        return ProjectOut(**cached_project)
    
    with session_scope() as s:
        p = s.get(Project, project_id)
        if not p:
            raise HTTPException(status_code=404, detail="not found")
        project_out = ProjectOut.model_validate(p)
        cache.set(cache_key, project_out.model_dump())
        return project_out
