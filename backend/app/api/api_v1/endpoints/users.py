import uuid
from typing import Any, List

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (get_current_active_user, get_current_superuser,
                       get_current_manager_or_admin)
from app.crud.user import (create_user, delete_user, get_user, get_users,
                        update_user)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (User as UserSchema, UserCreate, UserUpdate)

router = APIRouter()


@router.get("/", response_model=List[UserSchema])
async def read_users(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_manager_or_admin),
) -> Any:
    """
    Obtiene una lista paginada de usuarios.
    
    Solo accesible para administradores y managers.
    
    Args:
        db: Sesión de base de datos
        skip: Número de registros a saltar (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario autenticado actual
        
    Returns:
        Lista de usuarios
    """
    users = await get_users(db, skip=skip, limit=limit)
    return users


@router.post("/", response_model=UserSchema)
async def create_new_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Crea un nuevo usuario.
    
    Solo accesible para superusuarios.
    
    Args:
        db: Sesión de base de datos
        user_in: Datos del usuario a crear
        current_user: Usuario autenticado actual
        
    Returns:
        Usuario creado
        
    Raises:
        HTTPException: Si el email ya está registrado
    """
    try:
        user = await create_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserSchema)
async def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Obtiene información del usuario autenticado actual.
    
    Args:
        current_user: Usuario autenticado actual
        
    Returns:
        Información del usuario actual
    """
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Actualiza información del propio usuario autenticado.
    
    Args:
        db: Sesión de base de datos
        user_in: Datos a actualizar
        current_user: Usuario autenticado actual
        
    Returns:
        Información del usuario actualizada
    """
    # Restringir los campos que un usuario puede actualizar de sí mismo
    # (no permitir cambiar rol, permisos, etc.)
    allowed_fields = {"full_name", "password"}
    user_data = user_in.dict(exclude_unset=True)
    restricted_data = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    user = await update_user(db, current_user, UserUpdate(**restricted_data))
    return user


@router.get("/{user_id}", response_model=UserSchema)
async def read_user_by_id(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Obtiene información de un usuario específico por su ID.
    
    Solo superusuarios y managers pueden acceder a información de cualquier usuario.
    Los usuarios normales solo pueden acceder a su propia información.
    
    Args:
        user_id: ID del usuario a obtener
        db: Sesión de base de datos
        current_user: Usuario autenticado actual
        
    Returns:
        Información del usuario solicitado
        
    Raises:
        HTTPException: Si el usuario no existe o no se tienen permisos
    """
    user = await get_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
        
    # Si no es superuser o manager, solo puede acceder a su propia información
    if str(user.id) != str(current_user.id) and not await get_current_manager_or_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos suficientes",
        )
        
    return user


@router.put("/{user_id}", response_model=UserSchema)
async def update_specific_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_manager_or_admin),
) -> Any:
    """
    Actualiza información de un usuario específico.
    
    Solo accesible para administradores y managers.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a actualizar
        user_in: Datos a actualizar
        current_user: Usuario autenticado actual
        
    Returns:
        Información del usuario actualizada
        
    Raises:
        HTTPException: Si el usuario no existe
    """
    user = await get_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
        
    user = await update_user(db, user, user_in)
    return user


@router.delete("/{user_id}", response_model=UserSchema)
async def delete_specific_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Elimina un usuario específico.
    
    Solo accesible para superusuarios.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a eliminar
        current_user: Usuario autenticado actual
        
    Returns:
        Información del usuario eliminado
        
    Raises:
        HTTPException: Si el usuario no existe o si se intenta eliminar el propio usuario
    """
    # Evitar que un usuario se elimine a sí mismo
    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propio usuario",
        )
        
    user = await delete_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
        
    return user 