from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose.exceptions import JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM
from app.crud.user import get_user, is_active, is_manager_or_admin, is_superuser
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenPayload

# Token URL (ruta donde se obtiene el token)
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """
    Valida el token JWT y obtiene el usuario actual.
    
    Args:
        db: Sesión de base de datos
        token: Token JWT
        
    Returns:
        Usuario autenticado
        
    Raises:
        HTTPException: Si el token es inválido o el usuario no existe
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = await get_user(db, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Usuario no encontrado"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verifica que el usuario esté activo.
    
    Args:
        current_user: Usuario actual
        
    Returns:
        Usuario activo
        
    Raises:
        HTTPException: Si el usuario no está activo
    """
    if not await is_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Usuario inactivo"
        )
    
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Verifica que el usuario tenga permisos de superusuario.
    
    Args:
        current_user: Usuario actual
        
    Returns:
        Usuario con permisos de superusuario
        
    Raises:
        HTTPException: Si el usuario no es superusuario
    """
    if not await is_superuser(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="No tienes permisos suficientes"
        )
    
    return current_user


async def get_current_manager_or_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Verifica que el usuario sea manager o admin.
    
    Args:
        current_user: Usuario actual
        
    Returns:
        Usuario con permisos de manager o admin
        
    Raises:
        HTTPException: Si el usuario no es manager ni admin
    """
    if not await is_manager_or_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Se requieren permisos de administrador o manager"
        )
    
    return current_user 