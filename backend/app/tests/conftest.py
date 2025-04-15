import uuid
import asyncio
import pytest
from typing import AsyncGenerator, Dict, Generator
import os

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi import Depends
from fastapi.exceptions import HTTPException
from fastapi import status

from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.main import app
from app.api.deps import get_current_user, reusable_oauth2
from app.core.logging import setup_logging


# Configurar engine para tests (SQLite en memoria)
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Sobreescribir las dependencias para los tests
async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Crear un event loop para las pruebas asíncronas."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture para crear tablas y proporcionar una sesión de BD para tests."""
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Proporcionar sesión
    async with TestingSessionLocal() as session:
        yield session
    
    # Limpiar después
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Fixture para proporcionar un cliente HTTP con dependencias sobreescritas."""
    # Sobreescribir la dependencia de la base de datos
    app.dependency_overrides[get_db] = lambda: db_session
    
    # Usar un cliente AsyncClient sin TestClient
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Fixture para crear un superuser de prueba."""
    from app.crud.user import get_user_by_email, create_user
    from app.schemas.user import UserCreate
    
    # Primero verificar si ya existe
    superuser = await get_user_by_email(db_session, email=settings.FIRST_SUPERUSER)
    
    if not superuser:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            full_name="Super Admin",
            role=UserRole.ADMIN,
            is_superuser=True
        )
        superuser = await create_user(db_session, user_in=user_in)
    
    return superuser


@pytest.fixture
async def test_normal_user(db_session: AsyncSession) -> User:
    """Fixture para crear un usuario normal de prueba."""
    from app.crud.user import get_user_by_email, create_user
    from app.schemas.user import UserCreate
    
    email = "normal-user@example.com"
    user = await get_user_by_email(db_session, email=email)
    
    if not user:
        user_in = UserCreate(
            email=email,
            password="testpassword",
            full_name="Normal User",
            role=UserRole.EMPLOYEE,
            is_superuser=False
        )
        user = await create_user(db_session, user_in=user_in)
    
    return user


@pytest.fixture
async def test_hr_user(db_session: AsyncSession) -> User:
    """Fixture para crear un usuario HR de prueba."""
    from app.crud.user import get_user_by_email, create_user
    from app.schemas.user import UserCreate
    
    email = "hr-user@example.com"
    user = await get_user_by_email(db_session, email=email)
    
    if not user:
        user_in = UserCreate(
            email=email,
            password="testpassword",
            full_name="HR User",
            role=UserRole.MANAGER,
            is_superuser=False
        )
        user = await create_user(db_session, user_in=user_in)
    
    return user


@pytest.fixture
async def superuser_token_headers(client: AsyncClient, test_superuser: User) -> Dict[str, str]:
    """Fixture para obtener un token de autenticación para el superuser."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(
        subject=str(test_superuser.id)
    )
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def normal_user_token_headers(client: AsyncClient, test_normal_user: User) -> Dict[str, str]:
    """Fixture para obtener un token de autenticación para el usuario normal."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(
        subject=str(test_normal_user.id)
    )
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def hr_user_token_headers(client: AsyncClient, test_hr_user: User) -> Dict[str, str]:
    """Fixture para obtener un token de autenticación para el usuario HR."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(
        subject=str(test_hr_user.id)
    )
    
    return {"Authorization": f"Bearer {access_token}"}


# Sobreescribir la dependencia de usuario autenticado para los tests
async def override_get_current_user_for_tests(
    db: AsyncSession = Depends(get_db), 
    token: str = Depends(reusable_oauth2)
) -> User:
    """Sobreescribe la dependencia para usar el usuario real del token en tests.
    
    A diferencia de la sobreescritura anterior, esta función extrae el usuario del token
    en lugar de devolver siempre el mismo usuario, lo que permite que las pruebas que
    utilizan diferentes tokens (superuser_token_headers, normal_user_token_headers) 
    funcionen correctamente.
    """
    from app.core.security import get_subject_from_token
    from app.crud.user import get_user
    
    # Extraer el ID del usuario del token
    user_id = get_subject_from_token(token)
    
    # Convertir a entero si es necesario
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    
    # Obtener el usuario de la base de datos
    user = await get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    
    return user

app.dependency_overrides[get_current_user] = override_get_current_user_for_tests 


@pytest.fixture(autouse=True)
def configure_logging():
    """Configura el nivel de logging para todos los tests"""
    # Obtener el nivel de log de la variable de entorno o usar 'error' por defecto
    log_level = os.getenv("TEST_LOG_LEVEL", "error")
    setup_logging(log_level)
    return None 


@pytest.fixture
async def superuser(client: AsyncClient, test_superuser: User) -> User:
    """Fixture que proporciona directamente el objeto de usuario superusuario.
    
    A diferencia de otros métodos que extraen el usuario del token, este fixture
    proporciona directamente el objeto User, evitando llamadas API adicionales.
    """
    return test_superuser


@pytest.fixture
async def normal_user(client: AsyncClient, test_normal_user: User) -> User:
    """Fixture que proporciona directamente el objeto de usuario normal.
    
    A diferencia de otros métodos que extraen el usuario del token, este fixture
    proporciona directamente el objeto User, evitando llamadas API adicionales.
    """
    return test_normal_user


@pytest.fixture
async def hr_user(client: AsyncClient, test_hr_user: User) -> User:
    """Fixture que proporciona directamente el objeto de usuario HR.
    
    A diferencia de otros métodos que extraen el usuario del token, este fixture
    proporciona directamente el objeto User, evitando llamadas API adicionales.
    """
    return test_hr_user 