import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacation_request import VacationRequest, RequestStatus
from app.models.notification import NotificationType
from app.schemas.notification import NotificationCreate
from app.crud import notification as notification_crud
from app.worker import send_notification_task


async def notify_status_change(
    db: AsyncSession,
    vacation_request: VacationRequest,
    old_status: RequestStatus
) -> None:
    """
    Genera notificaciones cuando cambia el estado de una solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        vacation_request: Solicitud de vacaciones actualizada
        old_status: Estado anterior de la solicitud
    """
    # Si el estado no ha cambiado, no hacer nada
    if old_status == vacation_request.status:
        return
    
    # Datos comunes para todas las notificaciones
    request_dates = f"({vacation_request.start_date.strftime('%d/%m/%Y')} - {vacation_request.end_date.strftime('%d/%m/%Y')})"
    related_request_id = str(vacation_request.id)
    
    # Notificación para el solicitante
    if vacation_request.status == RequestStatus.APPROVED:
        # Solicitud aprobada
        message = f"Tu solicitud de vacaciones {request_dates} ha sido APROBADA."
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_APPROVED,
            message
        )
        
        # Enviar notificación en tiempo real
        send_notification_task.delay(
            user_id=str(vacation_request.requester_id),
            notification_type=NotificationType.REQUEST_APPROVED.value,
            message=message,
            related_request_id=related_request_id
        )
        
    elif vacation_request.status == RequestStatus.REJECTED:
        # Solicitud rechazada
        message = f"Tu solicitud de vacaciones {request_dates} ha sido RECHAZADA."
        if vacation_request.reviewer_comment:
            message += f" Comentario: {vacation_request.reviewer_comment}"
            
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_REJECTED,
            message
        )
        
        # Enviar notificación en tiempo real
        send_notification_task.delay(
            user_id=str(vacation_request.requester_id),
            notification_type=NotificationType.REQUEST_REJECTED.value,
            message=message,
            related_request_id=related_request_id
        )
        
    elif vacation_request.status == RequestStatus.CANCELLED:
        # Solicitud cancelada
        message = f"Tu solicitud de vacaciones {request_dates} ha sido CANCELADA."
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_CANCELLED,
            message
        )
        
        # Enviar notificación en tiempo real
        send_notification_task.delay(
            user_id=str(vacation_request.requester_id),
            notification_type=NotificationType.REQUEST_CANCELLED.value,
            message=message,
            related_request_id=related_request_id
        )
    
    # Si hay un revisor asignado, notificar al manager/admin para solicitudes nuevas
    if old_status == RequestStatus.PENDING and vacation_request.reviewer_id:
        employee_name = vacation_request.requester.full_name or vacation_request.requester.email
        message = f"Has revisado la solicitud de vacaciones de {employee_name} {request_dates}."
        
        await create_manager_notification(
            db,
            vacation_request.id,
            vacation_request.reviewer_id,
            NotificationType.REQUEST_CREATED,
            message
        )
        
        # Enviar notificación en tiempo real
        send_notification_task.delay(
            user_id=str(vacation_request.reviewer_id),
            notification_type=NotificationType.REQUEST_CREATED.value,
            message=message,
            related_request_id=related_request_id
        )


async def notify_new_request(
    db: AsyncSession,
    vacation_request: VacationRequest,
    manager_ids: list[uuid.UUID]
) -> None:
    """
    Genera notificaciones cuando se crea una nueva solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        vacation_request: Solicitud de vacaciones creada
        manager_ids: Lista de IDs de managers a notificar
    """
    # Datos comunes
    employee_name = vacation_request.requester.full_name or vacation_request.requester.email
    request_dates = f"({vacation_request.start_date.strftime('%d/%m/%Y')} - {vacation_request.end_date.strftime('%d/%m/%Y')})"
    message = f"Nueva solicitud de vacaciones de {employee_name} {request_dates}."
    related_request_id = str(vacation_request.id)
    
    # Notificar a todos los managers
    for manager_id in manager_ids:
        await create_manager_notification(
            db,
            vacation_request.id,
            manager_id,
            NotificationType.REQUEST_CREATED,
            message
        )
        
        # Enviar notificación en tiempo real
        send_notification_task.delay(
            user_id=str(manager_id),
            notification_type=NotificationType.REQUEST_CREATED.value,
            message=message,
            related_request_id=related_request_id
        )


async def create_requester_notification(
    db: AsyncSession,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    message: str
) -> None:
    """
    Crea una notificación para el solicitante.
    """
    notification_data = NotificationCreate(
        user_id=user_id,
        type=notification_type,
        message=message,
        related_request_id=request_id
    )
    await notification_crud.create_notification(db, notification_data)


async def create_manager_notification(
    db: AsyncSession,
    request_id: uuid.UUID,
    manager_id: uuid.UUID,
    notification_type: NotificationType,
    message: str
) -> None:
    """
    Crea una notificación para un manager.
    """
    notification_data = NotificationCreate(
        user_id=manager_id,
        type=notification_type,
        message=message,
        related_request_id=request_id
    )
    await notification_crud.create_notification(db, notification_data) 