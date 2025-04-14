from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
# from sqlalchemy.ext.declarative import declarative_base # Ya no se define aquí

from app.core.config import settings
# Importar Base si algún módulo futuro en este archivo la necesitara
# from app.db.base import Base

# Crear el motor asíncrono de SQLAlchemy
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.ENVIRONMENT != "production",
    future=True,   # Usar funcionalidades futuras de SQLAlchemy
    pool_pre_ping=True,  # Verificar conexiones antes de usarlas
)

# Sesiones asíncronas
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependencia para FastAPI
async def get_db() -> AsyncSession:
    """Dependencia para obtener una sesión de base de datos.
    
    Yields:
        AsyncSession: Sesión de base de datos asíncrona
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 