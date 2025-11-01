
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pybreaker import CircuitBreakerError
from db import Base, engine, session_scope, init_schema
from models import User, AuditLog
from schemas import UserCreate, UserOut
from patterns import CacheAside, RateLimiter, check_redis_health
from messaging import AsyncTaskProcessor, check_rabbitmq_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Users API")

# Inicializar schema y tablas
init_schema()
Base.metadata.create_all(bind=engine)

# Inicializar patrones
cache = CacheAside(prefix="users", ttl=300)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
task_processor = AsyncTaskProcessor("user_tasks")

# Registrar handlers de tareas asíncronas
def handle_user_notification(data: dict):
    """Ejemplo de handler async para notificaciones de usuario"""
    logger.info(f"Procesando notificación de usuario: {data}")

task_processor.register_handler("user_notification", handle_user_notification)

# Iniciar worker en background para procesamiento de cola
@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando Users API con patrones arquitectónicos")
    logger.info("Queue-based load leveling listo ")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Deteniendo Users API")
    task_processor.stop_worker()


# Middleware de rate limiting a nivel de aplicación
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting - complementa el rate limiting del gateway"""
    # Extraer identificador (usando IP como ejemplo, podría usar user_id de token)
    identifier = request.client.host
    
    # Saltar rate limiting para health checks
    if request.url.path in ["/healthz", "/health"]:
        return await call_next(request)
    
    if not rate_limiter.is_allowed(identifier):
        return JSONResponse(
            status_code=429,
            content={"detail": "Límite de rate excedido. Intente nuevamente más tarde."}
        )
    
    return await call_next(request)


# Handler de errores de circuit breaker
@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Servicio temporalmente no disponible. Circuit breaker está abierto."}
    )


@app.get("/health")
@app.get("/healthz")
async def health_check():
    """
    Patrón Enhanced Health Endpoint Monitoring
    """
    health_status = {
        "service": "users-api",
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
    
    # Verificar tamaño de cola
    try:
        queue_size = task_processor.queue.get_queue_size()
        health_status["queue_size"] = queue_size
        if queue_size > 5000:  # Umbral de advertencia
            health_status["status"] = "degraded"
            health_status["warning"] = "Tamaño de cola es alto"
    except Exception as e:
        logger.warning(f"No se pudo verificar tamaño de cola: {e}")
    
    # Retornar código de status apropiado
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate):
    """
    Crear usuario con transacción ACID + Queue-Based Load Leveling
    
    La creación de usuario es síncrona, pero las notificaciones se encolan para procesamiento async.
    """
    # Ejemplo ACID: crear user + audit log atómicamente
    with session_scope() as s:
        if s.query(User).filter_by(email=payload.email).first():
            raise HTTPException(status_code=409, detail="email already exists")
        u = User(name=payload.name, email=payload.email)
        s.add(u)
        s.flush()  # obtener u.id
        log = AuditLog(action="CREATE_USER", detail=f"User {u.id} created with email {u.email}")
        s.add(log)
        
        # Invalidar cache
        cache.invalidate_pattern("user:*")
        cache.invalidate_pattern("users:list")
        
        # Encolar notificación async (patrón Queue-Based Load Leveling)
        try:
            task_processor.enqueue_task("user_notification", {
                "user_id": u.id,
                "email": u.email,
                "type": "welcome"
            })
        except Exception as e:
            logger.warning(f"Falló al encolar notificación: {e}")
            # No fallar el request si falla el encolamiento
        
        return u


@app.get("/users", response_model=list[UserOut])
def list_users():
    """
    Listar usuarios con patrón Cache-Aside
    
    Los resultados se cachean por 5 minutos para mejorar rendimiento.
    """
    # Intentar cache primero (patrón Cache-Aside)
    cache_key = "users:list"
    cached_users = cache.get(cache_key)
    
    if cached_users is not None:
        return cached_users
    
    # Cache miss - consultar base de datos
    with session_scope() as s:
        users = s.query(User).order_by(User.id).all()
        user_list = [UserOut.model_validate(u) for u in users]
        
        # Almacenar en cache
        cache.set(cache_key, [u.model_dump() for u in user_list])
        
        return user_list


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    """
    Obtener usuario por ID con patrón Cache-Aside
    """
    # Intentar cache primero
    cache_key = f"user:{user_id}"
    cached_user = cache.get(cache_key)
    
    if cached_user is not None:
        return UserOut(**cached_user)
    
    # Cache miss - consultar base de datos
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="not found")
        
        user_out = UserOut.model_validate(u)
        
        # Almacenar en cache
        cache.set(cache_key, user_out.model_dump())
        
        return user_out
