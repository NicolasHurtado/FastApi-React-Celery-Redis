import uuid
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.crud import notification as crud
from app.schemas.notification import Notification, NotificationUpdate, NotificationCreate, NotificationSend
from app.worker import send_notification_task
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("app.api.notifications")


@router.post("/", response_model=Notification, status_code=status.HTTP_201_CREATED)
async def create_user_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification_in: NotificationCreate,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks
) -> Any:
    """
    Crea una nueva notificación para un usuario.
    """
    logger.info(
        f"Creando notificación para usuario ID {notification_in.user_id}",
        extra={"data": {"user_id": str(notification_in.user_id), "type": notification_in.type}}
    )
    
    try:
        # Crear la notificación en la base de datos
        notification = await crud.create_notification(db=db, obj_in=notification_in)
        
        # Enviar la notificación en tiempo real
        notification_send = NotificationSend(
            id=notification.id,
            type=notification.type,
            message=notification.message,
            created_at=notification.created_at
        )
        logger.info(f"Notificación creada: {notification_send}")
        
        # Usar Celery para manejar el envío de la notificación en segundo plano
        background_tasks.add_task(
            send_notification_task.delay,
            user_id=str(notification.user_id),
            notification_type=str(notification.type),
            message=notification.message,
            related_request_id=str(notification.related_request_id) if notification.related_request_id else None
        )
        
        logger.debug(
            f"Notificación creada y programada para envío",
            extra={"data": {"notification_id": str(notification.id)}}
        )
        
        return notification
    except Exception as e:
        import traceback
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )


@router.get("/", response_model=List[Notification])
async def read_notifications(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    unread_only: bool = False
) -> Any:
    """
    Recupera las notificaciones del usuario actual.
    """
    logger.info(
        f"Obteniendo notificaciones para usuario ID {current_user.id}",
        extra={"data": {"unread_only": unread_only, "skip": skip, "limit": limit}}
    )
    
    try:
        notifications = await crud.get_user_notifications(
            db=db, 
            user_id=current_user.id, 
            skip=skip, 
            limit=limit, 
            unread_only=unread_only
        )
        logger.debug(f"Retornando {len(notifications)} notificaciones para usuario {current_user.id}")
        return notifications
    except Exception as e:
        logger.error(
            f"Error al obtener notificaciones: {str(e)}",
            exc_info=True,
            extra={"data": {"user_id": str(current_user.id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las notificaciones: {str(e)}"
        )


@router.put("/{notification_id}", response_model=Notification)
async def update_user_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification_id: UUID,
    notification_in: NotificationUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Actualiza una notificación.
    """
    logger.info(
        f"Actualizando notificación ID {notification_id}",
        extra={"data": {"notification_id": str(notification_id)}}
    )
    
    try:
        # Obtener notificaciones del usuario
        notifications = await crud.get_user_notifications(db=db, user_id=current_user.id)
        
        # Verificar si la notificación pertenece al usuario
        notification = next((n for n in notifications if n.id == notification_id), None)
        
        if not notification:
            logger.warning(
                f"Intento de actualizar notificación no encontrada: {notification_id}",
                extra={"data": {"user_id": str(current_user.id)}}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada"
            )
        
        # Actualizar la notificación
        notification = await crud.update_notification(
            db=db, 
            db_obj=notification, 
            obj_in=notification_in
        )
        
        logger.debug(
            f"Notificación actualizada: {notification_id}",
            extra={"data": {"read": notification.read}}
        )
        
        return notification
    except HTTPException:
        # Rethrow HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Error al actualizar notificación: {str(e)}",
            exc_info=True,
            extra={"data": {"notification_id": str(notification_id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la notificación: {str(e)}"
        )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification_id: UUID,
    current_user: User = Depends(get_current_user)
) -> Response:
    """
    Elimina una notificación.
    """
    logger.info(
        f"Eliminando notificación ID {notification_id}",
        extra={"data": {"notification_id": str(notification_id)}}
    )
    
    try:
        # Obtener notificaciones del usuario
        notifications = await crud.get_user_notifications(db=db, user_id=current_user.id)
        
        # Verificar si la notificación pertenece al usuario
        notification = next((n for n in notifications if n.id == notification_id), None)
        
        if not notification:
            logger.warning(
                f"Intento de eliminar notificación no encontrada: {notification_id}",
                extra={"data": {"user_id": str(current_user.id)}}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada"
            )
        
        # Eliminar la notificación
        await crud.delete_notification(db=db, id=notification_id)
        
        logger.info(f"Notificación eliminada: {notification_id}")
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        # Rethrow HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Error al eliminar notificación: {str(e)}",
            exc_info=True,
            extra={"data": {"notification_id": str(notification_id)}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar la notificación: {str(e)}"
        )


@router.get("/unread-count", response_model=int)
async def read_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Obtener el número de notificaciones no leídas.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Número de notificaciones no leídas
    """
    count = await crud.get_unread_count(db=db, user_id=current_user.id)
    return count


@router.get("/{notification_id}", response_model=Notification)
async def read_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Obtener una notificación específica.
    
    Args:
        notification_id: ID de la notificación
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Notificación
    """
    notification = await crud.get_notification(db=db, id=notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )
    
    # Verificar que la notificación pertenece al usuario
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a esta notificación"
        )
    
    return notification


@router.patch("/{notification_id}/mark-as-read", response_model=Notification)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Marcar una notificación como leída.
    
    Args:
        notification_id: ID de la notificación
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Notificación actualizada
    """
    notification = await crud.get_notification(db=db, id=notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )
    
    # Verificar que la notificación pertenece al usuario
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a esta notificación"
        )
    
    notification = await crud.mark_as_read(db=db, notification_id=notification_id)
    return notification


@router.patch("/mark-all-as-read", response_model=int)
async def mark_all_notifications_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Marcar todas las notificaciones del usuario como leídas.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Número de notificaciones actualizadas
    """
    count = await crud.mark_all_as_read(db=db, user_id=current_user.id)
    return count 