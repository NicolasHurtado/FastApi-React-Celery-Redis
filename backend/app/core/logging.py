import logging
import logging.handlers
import os
import sys
import json
from pathlib import Path

from app.core.config import settings

# Configuración básica de niveles de logging
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# Directorio para los logs
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(exist_ok=True, parents=True)

# Formatos de log
CONSOLE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

# Caché de loggers ya configurados
_loggers = {}

# Determinar el nivel de log global a partir de la configuración
LOG_LEVEL = LOG_LEVELS.get(settings.LOG_LEVEL.lower() if hasattr(settings, "LOG_LEVEL") else "info", logging.INFO)

def get_console_handler():
    """Crea un handler para logs en consola"""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    return console_handler

def get_file_handler(log_file):
    """Crea un handler para logs en archivo con rotación"""
    file_path = LOG_DIR / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        filename=file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf8"
    )
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    return file_handler

def get_json_file_handler(log_file="app.json.log"):
    """Crea un handler para logs en formato JSON con rotación"""
    json_path = LOG_DIR / log_file
    json_handler = logging.handlers.RotatingFileHandler(
        filename=json_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf8"
    )
    
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S,%03d"),
                "name": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
                "path": f"{record.pathname}:{record.lineno}"
            }
            
            # Añadir los campos extra si existen
            if hasattr(record, "extra"):
                log_data.update(record.extra)
            
            # Añadir información de excepción si existe
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
                
            return json.dumps(log_data)
    
    json_handler.setFormatter(JsonFormatter())
    return json_handler

class JsonAdapter(logging.LoggerAdapter):
    """Adaptador para añadir campos extra a los logs en formato JSON"""
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        if extra:
            kwargs["extra"] = extra
        return msg, kwargs

def get_logger(name):
    """
    Obtiene o crea un logger con el nombre especificado.
    
    Args:
        name: Nombre del módulo o componente para el logger
        
    Returns:
        Un logger configurado
    """
    # Si ya tenemos este logger configurado, lo devolvemos
    if name in _loggers:
        return _loggers[name]
        
    # Obtener el nivel de log de la variable de entorno o usar INFO por defecto
    log_level_name = os.getenv("LOG_LEVEL", "info").lower()
    log_level = LOG_LEVELS.get(log_level_name, logging.INFO)
    
    # Configurar el logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Limpiar handlers existentes
    if logger.handlers:
        logger.handlers.clear()
    
    # Añadir handlers
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler(f"{name.split('.')[-1]}.log"))
    logger.addHandler(get_json_file_handler(f"{name.split('.')[-1]}.json.log"))
    
    # Evitar propagación para prevenir logs duplicados
    logger.propagate = False
    
    # Adaptar el logger para facilitar el uso de campos extra
    adapter = JsonAdapter(logger, {})
    
    # Guardar en cache y retornar
    _loggers[name] = adapter
    return adapter

def setup_fastapi_logging():
    """Configura el logging para FastAPI"""
    fastapi_logger = logging.getLogger("fastapi")
    fastapi_logger.setLevel(LOG_LEVEL)
    for handler in [get_console_handler(), get_file_handler("fastapi.log")]:
        fastapi_logger.addHandler(handler)
    fastapi_logger.propagate = False

def setup_uvicorn_logging():
    """Configura el logging para Uvicorn"""
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(LOG_LEVEL)
    for handler in [get_console_handler(), get_file_handler("uvicorn.log")]:
        uvicorn_logger.addHandler(handler)
    uvicorn_logger.propagate = False

def setup_sqlalchemy_logging():
    """Configura el logging para SQLAlchemy"""
    sqlalchemy_logger = logging.getLogger("sqlalchemy")
    sqlalchemy_logger.setLevel(LOG_LEVEL)
    for handler in [get_console_handler(), get_file_handler("sqlalchemy.log")]:
        sqlalchemy_logger.addHandler(handler)
    sqlalchemy_logger.propagate = False

def setup_celery_logging():
    """Configura el logging para Celery"""
    celery_logger = logging.getLogger("celery")
    celery_logger.setLevel(LOG_LEVEL)
    for handler in [get_console_handler(), get_file_handler("celery.log")]:
        celery_logger.addHandler(handler)
    celery_logger.propagate = False

def setup_logging(log_level=None):
    """
    Configura todos los loggers principales del sistema
    
    Args:
        log_level: Nivel de logging opcional (debug, info, warning, error, critical)
    """
    global LOG_LEVEL
    
    # Configurar nivel de log si se proporciona
    if log_level:
        os.environ["LOG_LEVEL"] = log_level
        LOG_LEVEL = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    
    # Asegurar que el directorio de logs existe
    LOG_DIR.mkdir(exist_ok=True, parents=True)
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Limpiar handlers existentes
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Añadir handlers al logger raíz
    root_logger.addHandler(get_console_handler())
    root_logger.addHandler(get_file_handler("app.log"))
    
    # Configurar loggers específicos
    setup_fastapi_logging()
    setup_uvicorn_logging()
    setup_sqlalchemy_logging()
    setup_celery_logging()
    
    # Logger principal de la aplicación
    app_logger = get_logger("app")
    app_logger.info(f"Logging configurado con nivel: {logging.getLevelName(LOG_LEVEL)}")
    
    return app_logger

# Configurar logging al importar el módulo
logger = setup_logging() 