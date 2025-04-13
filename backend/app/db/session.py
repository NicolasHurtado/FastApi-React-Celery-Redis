from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import settings

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

# Base declarativa para modelos ORM
Base = declarative_base()

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