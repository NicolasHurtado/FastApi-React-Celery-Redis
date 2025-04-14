import uuid
from typing import Any, Dict, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Obtiene un usuario por su email.
    
    Args:
        db: Sesión de base de datos
        email: Email del usuario a buscar
        
    Returns:
        Usuario encontrado o None
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()



async def get_user(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """
    Obtiene un usuario por su ID.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a buscar
        
    Returns:
        Usuario encontrado o None
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()



async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[User]:
    """
    Obtiene una lista paginada de usuarios.
    
    Args:
        db: Sesión de base de datos
        skip: Número de usuarios a saltar (para paginación)
        limit: Número máximo de usuarios a devolver
        
    Returns:
        Lista de usuarios
    """
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()



async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Crea un nuevo usuario.
    
    Args:
        db: Sesión de base de datos
        user_in: Datos del usuario a crear
        
    Returns:
        Usuario creado
    """
    # Verificar si el email ya existe
    existing_user = await get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise ValueError(f"El email {user_in.email} ya está registrado")
        
    # Crear objeto de usuario con los datos recibidos
    user = User(
        email=user_in.email,
        password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
        total_vacation_days=user_in.total_vacation_days or 20,  # Valor predeterminado
    )
    
    # Añadir a la sesión y confirmar
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user



async def update_user(
    db: AsyncSession, 
    user: User, 
    user_in: Union[UserUpdate, Dict[str, Any]]
) -> User:
    """
    Actualiza un usuario existente.
    
    Args:
        db: Sesión de base de datos
        user: Usuario a actualizar
        user_in: Datos de actualización
        
    Returns:
        Usuario actualizado
    """
    # Convertir dict a UserUpdate si es necesario
    update_data = user_in if isinstance(user_in, dict) else user_in.dict(exclude_unset=True)
    
    # Manejar la contraseña si se proporciona
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["password"] = hashed_password
        
    # Actualizar los atributos del usuario
    for field, value in update_data.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)
    
    # Guardar cambios
    await db.commit()
    await db.refresh(user)
    return user



async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """
    Elimina un usuario por su ID.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a eliminar
        
    Returns:
        Usuario eliminado o None si no existe
    """
    user = await get_user(db, user_id)
    if not user:
        return None
        
    await db.delete(user)
    await db.commit()
    return user



async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Autentica un usuario por email y contraseña.
    
    Args:
        db: Sesión de base de datos
        email: Email del usuario
        password: Contraseña en texto plano
        
    Returns:
        Usuario autenticado o None si la autenticación falla
    """
    user = await get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


async def is_active(user: User) -> bool:
    """
    Verifica si un usuario está activo.
    
    Args:
        user: Usuario a verificar
        
    Returns:
        True si el usuario está activo, False en caso contrario
    """
    return user.is_active


async def is_superuser(user: User) -> bool:
    """
    Verifica si un usuario es superusuario.
    
    Args:
        user: Usuario a verificar
        
    Returns:
        True si el usuario es superusuario, False en caso contrario
    """
    return user.is_superuser


async def is_manager_or_admin(user: User) -> bool:
    """
    Verifica si un usuario es manager o admin.
    
    Args:
        user: Usuario a verificar
        
    Returns:
        True si el usuario es manager o admin, False en caso contrario
    """
    return user.role in [UserRole.MANAGER, UserRole.ADMIN] 