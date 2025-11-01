"""
Implementación de Patrones Arquitectónicos:
- Circuit Breaker
- Retry con Exponential Backoff
- Cache-Aside
- Rate Limiting
"""

import os
import time
import json
import logging
from functools import wraps
from typing import Optional, Any, Callable
import redis
import httpx
from pybreaker import CircuitBreaker, CircuitBreakerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexión a Redis para caching
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Configuración del Circuit Breaker
circuit_breaker = CircuitBreaker(
    fail_max=5,  # Abre el circuito después de 5 fallos
    reset_timeout=30,  # Mantiene el circuito abierto por 30 segundos
    name="inter_service_breaker"
)

def retry_with_backoff(max_attempts=3):
    """
    Patrón Retry con exponential backoff.
    Reintenta operaciones fallidas con delays incrementales.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"Intento de retry {retry_state.attempt_number} después de {retry_state.outcome.exception()}"
        )
    )

@circuit_breaker
@retry_with_backoff(max_attempts=3)
async def call_external_service(url: str, method: str = "GET", **kwargs) -> dict:
    """
    Realiza llamadas HTTP con patrones Circuit Breaker y Retry.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            logger.info(f"Llamando {method} {url} con circuit breaker")
            response = await getattr(client, method.lower())(url, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP {e.response.status_code} llamando {url}: {e}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Error de request llamando {url}: {e}")
        raise


class CacheAside:
    """
    Implementación del patrón Cache-Aside.
    """
    
    def __init__(self, prefix: str = "cache", ttl: int = 300):
        self.prefix = prefix
        self.ttl = ttl  # Tiempo de vida en segundos (default 5 minutos)
    
    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor desde cache"""
        try:
            cached = redis_client.get(self._make_key(key))
            if cached:
                logger.info(f"Cache HIT: {key}")
                return json.loads(cached)
            logger.info(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Error al obtener de cache: {e}")
            return None
    
    def set(self, key: str, value: Any) -> bool:
        """Establecer valor en cache con TTL"""
        try:
            redis_client.setex(
                self._make_key(key),
                self.ttl,
                json.dumps(value, default=str)
            )
            logger.info(f"Cache SET: {key} (TTL: {self.ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error al establecer en cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Eliminar valor del cache"""
        try:
            redis_client.delete(self._make_key(key))
            logger.info(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Error al eliminar de cache: {e}")
            return False
    
    def invalidate_pattern(self, pattern: str):
        """Invalidar todas las keys que coincidan con el patrón"""
        try:
            keys = redis_client.keys(f"{self.prefix}:{pattern}")
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cache INVALIDATE: {len(keys)} keys que coinciden con {pattern}")
        except Exception as e:
            logger.error(f"Error al invalidar cache: {e}")


def cached(cache_key_func: Callable, ttl: int = 300):
    """
    Decorador para implementar patrón Cache-Aside en funciones.
    """
    def decorator(func):
        cache = CacheAside(prefix=func.__name__, ttl=ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar cache key
            cache_key = cache_key_func(*args, **kwargs)
            
            # Intentar obtener desde cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Cache miss - ejecutar función
            result = func(*args, **kwargs)
            
            # Almacenar en cache
            if result is not None:
                cache.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator

class RateLimiter:
    """
    Rate limiting a nivel de aplicación usando Redis.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Verifica si el request está permitido para el identificador dado (ej: user_id, IP)
        Usando algoritmo de sliding window.
        """
        key = f"rate_limit:{identifier}"
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        try:
            pipe = redis_client.pipeline()
            # Remover entradas viejas fuera de la ventana
            pipe.zremrangebyscore(key, 0, window_start)
            # Contar requests en ventana actual
            pipe.zcard(key)
            # Agregar request actual
            pipe.zadd(key, {current_time: current_time})
            # Establecer expiración
            pipe.expire(key, self.window_seconds)
            results = pipe.execute()
            
            request_count = results[1]
            
            if request_count >= self.max_requests:
                logger.warning(f"Límite de rate excedido para {identifier}: {request_count}/{self.max_requests}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error en rate limiter: {e}")
            return True


def check_redis_health() -> dict:
    """Verificar conectividad a Redis"""
    try:
        redis_client.ping()
        return {"status": "healthy", "service": "redis"}
    except Exception as e:
        return {"status": "unhealthy", "service": "redis", "error": str(e)}
