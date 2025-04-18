""" Main file for the backend application """
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings 
from app.core.logging import setup_logging, get_logger 
from app.api.api_v1.api import api_router 

# Configure the logging system
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs"
)

# Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

logger.info(f"Iniciando aplicación: {settings.PROJECT_NAME} v{settings.VERSION}")

# Incluir router de la API
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/ping", summary="Check if API is running")
def pong():
    """Sanity check endpoint."""
    logger.debug("Petición de ping recibida")
    return {"ping": "pong!"}

# Aquí incluiremos los routers de la API más adelante
# from app.api.api_v1 import api_router
# app.include_router(api_router, prefix="/api/v1") 