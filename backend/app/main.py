from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from app.db.session import engine, Base # Ya no se necesita importar Base aquí
# from app.db.session import engine # Tampoco engine por ahora
from app.core.config import settings # Importar settings
from app.core.logging import setup_logging, get_logger # Importar configuración de logging
from app.api.api_v1.api import api_router # Importar el router de la API
# Importar modelos ORM (cuando existan)
# from app.models.user import User # Ejemplo, descomentar cuando exista User

# Configurar el sistema de logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)

# --- La función create_db_and_tables y el evento on_startup se eliminan ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version=settings.VERSION
)

# Configuración de CORS
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