import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import sys
import os

# Configurar el sistema para importar desde el directorio raíz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.core.config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_superuser(
    email: str = "admin@example.com",
    password: str = "admin",
    full_name: str = "Admin User",
    role: UserRole = UserRole.ADMIN,
    is_active: bool = True,
    is_superuser: bool = True,
    total_vacation_days: int = 30
):
    """
    Create a superuser in the database using secure hashing for the password.
    
    Args:
        email: User email (must be unique)
        password: Plain text password (will be hashed)
        full_name: Full name
        role: User role (ADMIN by default)
        is_active: If the user is active
        is_superuser: If the user has superuser permissions
        total_vacation_days: Annual vacation days
    """
    logger.info(f"Creating superuser with email: {email}")
    
    # Configurar la conexión a la base de datos usando settings
    # Asegurarse de convertir la URL a string para SQLAlchemy
    db_url = str(settings.DATABASE_URL)
    logger.info(f"Using database URL: {db_url}")

    # Crear el engine para la base de datos
    engine = create_async_engine(db_url)
    async_session = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    # Crear la sesión y el usuario
    async with async_session() as session:
        # Verificar si el usuario ya existe
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalars().first()
        
        if existing_user:
            logger.info(f"The user {email} already exists with ID {existing_user.id}")
            return
        
        try:
            # Crear el hash seguro de la contraseña
            hashed_password = get_password_hash(password)
            logger.info("Password hashed correctly")
            
            # Crear el usuario
            new_user = User(
                email=email,
                password=hashed_password,
                full_name=full_name,
                role=role,
                is_active=is_active,
                is_superuser=is_superuser,
                total_vacation_days=total_vacation_days
            )
            
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            logger.info(f"Superuser created with ID {new_user.id}")
            return new_user
        except Exception as e:
            logger.error(f"Error creating superuser: {e}")
            raise

if __name__ == "__main__":
    try:
        asyncio.run(create_superuser())
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1) 