import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Auth API - Gatekeeper")
security = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mi-clave-secreta-super-segura-cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenValidationResponse(BaseModel):
    valid: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    roles: Optional[list[str]] = None
    error: Optional[str] = None

def create_access_token(user_id: int, username: str, roles: list[str] = None) -> str:
    """
    Crear JWT access token.
    """
    if roles is None:
        roles = ["user"]
    
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Token creado para usuario: {username} (ID: {user_id})")
    
    return encoded_jwt


def validate_token(token: str) -> dict:
    """
    Validar JWT token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Token validado exitosamente para usuario: {payload.get('username')}")
        return {
            "valid": True,
            "user_id": int(payload.get("sub")),
            "username": payload.get("username"),
            "roles": payload.get("roles", [])
        }
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        return {"valid": False, "error": "Token expirado"}
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token inválido: {e}")
        return {"valid": False, "error": "Token inválido"}


def check_permission(token_data: dict, required_role: str = None) -> bool:
    """
    Verificar permisos basados en roles.
    """
    if not token_data.get("valid"):
        return False
    
    if required_role:
        roles = token_data.get("roles", [])
        if required_role not in roles and "admin" not in roles:
            logger.warning(f"Usuario {token_data.get('username')} no tiene rol requerido: {required_role}")
            return False
    
    return True

@app.get("/health")
@app.get("/healthz")
def health_check():
    """Health check del servicio Gatekeeper"""
    return {
        "service": "auth-api-gatekeeper",
        "status": "healthy"
    }


@app.post("/auth/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    """
    Endpoint de login - Gatekeeper emite tokens de acceso
    """
    # Demo: Usuarios hardcodeados
    valid_users = {
        "admin": {"password": "admin123", "user_id": 1, "roles": ["admin", "user"]},
        "user": {"password": "user123", "user_id": 2, "roles": ["user"]},
        "developer": {"password": "dev123", "user_id": 3, "roles": ["user", "developer"]}
    }
    
    user_data = valid_users.get(credentials.username)
    
    if not user_data or user_data["password"] != credentials.password:
        logger.warning(f"Intento de login fallido para: {credentials.username}")
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas"
        )
    
    access_token = create_access_token(
        user_id=user_data["user_id"],
        username=credentials.username,
        roles=user_data["roles"]
    )
    
    logger.info(f"Login exitoso para usuario: {credentials.username}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@app.post("/auth/validate", response_model=TokenValidationResponse)
def validate(authorization: Optional[str] = Header(None)):
    """
    Endpoint de validación - Gatekeeper valida tokens
    """
    if not authorization:
        return TokenValidationResponse(
            valid=False,
            error="No se proveyó token de autorización"
        )
    
    # Extraer token del header "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return TokenValidationResponse(
                valid=False,
                error="Esquema de autorización debe ser Bearer"
            )
    except ValueError:
        return TokenValidationResponse(
            valid=False,
            error="Formato de autorización inválido"
        )
    
    # Validar token
    validation_result = validate_token(token)
    
    if validation_result.get("valid"):
        return TokenValidationResponse(
            valid=True,
            user_id=validation_result.get("user_id"),
            username=validation_result.get("username"),
            roles=validation_result.get("roles")
        )
    else:
        return TokenValidationResponse(
            valid=False,
            error=validation_result.get("error")
        )


@app.get("/auth/verify/{token}")
def verify_token(token: str):
    """
    Verificación rápida de token (para debugging)
    """
    result = validate_token(token)
    return result


@app.get("/auth/whoami")
def whoami(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Obtener información del usuario actual desde el token
    """
    validation = validate_token(credentials.credentials)
    
    if not validation.get("valid"):
        raise HTTPException(
            status_code=401,
            detail=validation.get("error", "Token inválido")
        )
    
    return {
        "user_id": validation.get("user_id"),
        "username": validation.get("username"),
        "roles": validation.get("roles")
    }

@app.post("/auth/refresh")
def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Renovar token de acceso
    """
    validation = validate_token(credentials.credentials)
    
    if not validation.get("valid"):
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado"
        )
    
    # Emitir nuevo token
    new_token = create_access_token(
        user_id=validation.get("user_id"),
        username=validation.get("username"),
        roles=validation.get("roles")
    )
    
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

