import secrets
from typing import Any, Dict, Optional, List
from pydantic import PostgresDsn, validator, AnyHttpUrl

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Información del proyecto
    PROJECT_NAME: str = "Vacation Manager"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"
    
    # Entorno (development/staging/production)
    ENVIRONMENT: str = "production"
    
    # Configuración de seguridad
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # Generación por defecto de clave segura en caso de que no se proporcione
    @validator("SECRET_KEY", pre=True, always=True)
    def set_secret_key(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if not v or len(v) < 32:
            # Warning: Secret key not defined or very weak
            if values.get("ENVIRONMENT") == "production":
                raise ValueError("SECRET_KEY should be configured in production with at least 32 characters")
            # For development/staging, generate a default key (not recommended for production)
            return secrets.token_urlsafe(32)
        return v
    
    # Configuración JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 60 minutos * 24 horas * 8 días = 8 días
    ALGORITHM: str = "HS256"
    
    # Base de datos
    DATABASE_URL: PostgresDsn
    
    # Validación de la URL de la base de datos
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if not v:
            raise ValueError("DATABASE_URL is required")
        # Ensure it is asyncpg for the asynchronous ORM
        if values.get("ENVIRONMENT") == "production" and "+asyncpg" not in v:
            raise ValueError("It is recommended to use postgresql+asyncpg in production")
        return v

    # Redis
    REDIS_URL: str
    
    # Usuario inicial (superusuario)
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"
    
    # Opciones de CORS (Cross-Origin Resource Sharing)
    # Lista de orígenes permitidos para conectarse a la API
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Configuración de logging
    LOG_LEVEL: str = "info"
    LOG_DIR: str = "logs"
    SQL_DEBUG: bool = False
    
    class Config:
        case_sensitive = True
        env_file = ".env"  # Habilitar carga desde archivo .env
        env_file_encoding = "utf-8"

settings = Settings() 