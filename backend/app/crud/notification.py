import uuid
from typing import List, Optional, Union, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from app.models.notification import Notification, NotificationType
from app.models.vacation_request import VacationRequest, RequestStatus
from app.schemas.notification import NotificationCreate, NotificationUpdate


async def create_notification(
    db: AsyncSession, 
    obj_in: NotificationCreate
) -> Notification:
    """
    Crea una nueva notificación.
    
    Args:
        db: Sesión de base de datos
        obj_in: Datos de la notificación a crear
        
    Returns:
        Notificación creada
    """
    db_obj = Notification(
        user_id=obj_in.user_id,
        type=obj_in.type,
        message=obj_in.message,
        related_request_id=obj_in.related_request_id,
        read=obj_in.read
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_notification(
    db: AsyncSession, 
    id: int
) -> Optional[Notification]:
    """
    Obtiene una notificación por su ID.
    
    Args:
        db: Sesión de base de datos
        id: ID de la notificación
        
    Returns:
        Notificación encontrada o None
    """
    result = await db.execute(select(Notification).where(Notification.id == id))
    return result.scalars().first()


async def get_user_notifications(
    db: AsyncSession, 
    user_id: Union[int, uuid.UUID],
    skip: int = 0, 
    limit: int = 100,
    unread_only: bool = False
) -> List[Notification]:
    """
    Obtiene las notificaciones de un usuario.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario (puede ser int o UUID)
        skip: Número de registros a saltar
        limit: Número máximo de registros a devolver
        unread_only: Si es True, solo devuelve notificaciones no leídas
        
    Returns:
        Lista de notificaciones
    """
    query = select(Notification).where(Notification.user_id == user_id)
    
    if unread_only:
        query = query.where(Notification.read == False)
    
    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_unread_count(
    db: AsyncSession, 
    user_id: int
) -> int:
    """
    Obtiene el número de notificaciones no leídas de un usuario.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario (puede ser int o UUID)
        
    Returns:
        Número de notificaciones no leídas
    """
    print(f"user_id: {user_id}")
    query = select(Notification).where(
        and_(
            Notification.user_id == user_id,
            Notification.read == False
        )
    )
    result = await db.execute(query)
    return len(result.scalars().all())


async def update_notification(
    db: AsyncSession,
    db_obj: Notification,
    obj_in: Union[NotificationUpdate, Dict[str, Any]]
) -> Notification:
    """
    Actualiza una notificación.
    
    Args:
        db: Sesión de base de datos
        db_obj: Objeto de notificación existente
        obj_in: Datos de actualización
        
    Returns:
        Notificación actualizada
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    for field in update_data:
        if hasattr(db_obj, field) and update_data[field] is not None:
            setattr(db_obj, field, update_data[field])
    
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def mark_as_read(
    db: AsyncSession,
    notification_id: int
) -> Optional[Notification]:
    """
    Marca una notificación como leída.
    
    Args:
        db: Sesión de base de datos
        notification_id: ID de la notificación
        
    Returns:
        Notificación actualizada o None
    """
    notification = await get_notification(db, notification_id)
    if not notification:
        return None
    
    notification.read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(
    db: AsyncSession,
    user_id: Union[int, uuid.UUID]
) -> int:
    """
    Marca todas las notificaciones de un usuario como leídas.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario (puede ser int o UUID)
        
    Returns:
        Número de notificaciones actualizadas
    """
    notifications = await get_user_notifications(db, user_id, unread_only=True, limit=1000)
    for notification in notifications:
        notification.read = True
    
    await db.commit()
    return len(notifications)


async def delete_notification(
    db: AsyncSession, 
    id: int
) -> Optional[Notification]:
    """
    Elimina una notificación.
    
    Args:
        db: Sesión de base de datos
        id: ID de la notificación
        
    Returns:
        Notificación eliminada o None
    """
    notification = await get_notification(db, id)
    if not notification:
        return None
    
    await db.delete(notification)
    await db.commit()
    return notification 