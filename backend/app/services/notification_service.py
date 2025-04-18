import logging
import sys
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacation_request import VacationRequest, RequestStatus
from app.models.notification import NotificationType
from app.schemas.notification import NotificationCreate
from app.crud import notification as notification_crud
from app.worker import send_notification_task


logger = logging.getLogger(__name__)


async def notify_status_change(
    db: AsyncSession,
    vacation_request: VacationRequest,
    old_status: RequestStatus
) -> None:
    """
    Generate notifications when the status of a vacation request changes.
    
    Args:
        db: Database session
        vacation_request: Updated vacation request
        old_status: Previous status of the request
    """
    # If the status hasn't changed, do nothing
    if old_status == vacation_request.status:
        return
    
    logger.info(f"Notifying status change for request {vacation_request.id}")
    
    # Common data for all notifications
    request_dates = f"({vacation_request.start_date.strftime('%d/%m/%Y')} - {vacation_request.end_date.strftime('%d/%m/%Y')})"
    related_request_id = str(vacation_request.id)
    
    # Notification for the requester
    if vacation_request.status == RequestStatus.APPROVED:
        # Request approved
        message = f"Your vacation request {request_dates} has been APPROVED."
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_APPROVED,
            message
        )
        
        # Send real-time notification
        try:
                        
            # Llamada async normal
            async_result = send_notification_task.delay(
                user_id=str(vacation_request.requester_id),
                notification_type=NotificationType.REQUEST_APPROVED.value,
                message=message,
                related_request_id=related_request_id
            )
            
            logger.info(f"Tarea asíncrona enviada: ID={async_result.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación: {str(e)}", exc_info=True)
        
    elif vacation_request.status == RequestStatus.REJECTED:
        # Request rejected
        message = f"Your vacation request {request_dates} has been REJECTED."
        if vacation_request.reviewer_comment:
            message += f" Comment: {vacation_request.reviewer_comment}"
            
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_REJECTED,
            message
        )
        
        # Send real-time notification
        try:
            async_result = send_notification_task.delay(
                user_id=str(vacation_request.requester_id),
                notification_type=NotificationType.REQUEST_REJECTED.value,
                message=message,
                related_request_id=related_request_id
            )
            logger.info(f"Tarea de notificación de rechazo enviada: ID={async_result.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación de rechazo: {str(e)}", exc_info=True)
        
    elif vacation_request.status == RequestStatus.CANCELLED:
        # Request cancelled
        message = f"Your vacation request {request_dates} has been CANCELLED."
        await create_requester_notification(
            db, 
            vacation_request.id,
            vacation_request.requester_id,
            NotificationType.REQUEST_CANCELLED,
            message
        )
        
        # Send real-time notification
        try:
            async_result = send_notification_task.delay(
                user_id=str(vacation_request.requester_id),
                notification_type=NotificationType.REQUEST_CANCELLED.value,
                message=message,
                related_request_id=related_request_id
            )
            logger.info(f"Tarea de notificación de cancelación enviada: ID={async_result.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación de cancelación: {str(e)}", exc_info=True)
    
    # If there is a reviewer assigned, notify the manager/admin for new requests
    if old_status == RequestStatus.PENDING and vacation_request.reviewer_id:
        employee_name = vacation_request.requester.full_name or vacation_request.requester.email
        message = f"You have reviewed the vacation request of {employee_name} {request_dates}."
        
        await create_manager_notification(
            db,
            vacation_request.id,
            vacation_request.reviewer_id,
            NotificationType.REQUEST_REVIEWED,
            message
        )
        
        # Send real-time notification
        try:
            async_result = send_notification_task.delay(
                user_id=str(vacation_request.reviewer_id),
                notification_type=NotificationType.REQUEST_REVIEWED.value,
                message=message,
                related_request_id=related_request_id
            )
            logger.info(f"Tarea de notificación para revisor enviada: ID={async_result.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación al revisor: {str(e)}", exc_info=True)


async def notify_new_request(
    db: AsyncSession,
    vacation_request: VacationRequest,
    manager_ids: list[int]
) -> None:
    """
    Generate notifications when a new vacation request is created.
    
    Args:
        db: Database session
        vacation_request: Created vacation request
        manager_ids: List of IDs of managers to notify
    """
    # Common data
    employee_name = vacation_request.requester.full_name or vacation_request.requester.email
    request_dates = f"({vacation_request.start_date.strftime('%d/%m/%Y')} - {vacation_request.end_date.strftime('%d/%m/%Y')})"
    message = f"New vacation request from {employee_name} {request_dates}."
    related_request_id = str(vacation_request.id)
    
    logger.info(f"Creating notifications for {len(manager_ids)} managers: {manager_ids}")
    
    # Notify all managers
    for index, manager_id in enumerate(manager_ids):
        await create_manager_notification(
            db,
            vacation_request.id,
            manager_id,
            NotificationType.REQUEST_CREATED,
            message
        )
        
        # Send real-time notification with delay
        try:            
            # Llamada async con seguimiento
            task_id = f"manager_notify_{vacation_request.id}_{manager_id}"
            logger.info(f"Enviando notificación #{index+1} a manager {manager_id}")
            
            async_result = send_notification_task.delay(
                user_id=str(manager_id),
                notification_type=NotificationType.REQUEST_CREATED.value,
                message=message,
                related_request_id=related_request_id
            )
            
            logger.info(f"Notificación enviada a manager {manager_id}, ID de tarea: {async_result.id}")
        except Exception as e:
            logger.error(f"Error al enviar notificación a manager {manager_id}: {str(e)}", exc_info=True)


async def create_requester_notification(
    db: AsyncSession,
    request_id: int,
    user_id: int,
    notification_type: NotificationType,
    message: str
) -> None:
    """
    Create a notification for the requester.
    """
    notification_data = NotificationCreate(
        user_id=user_id,
        type=notification_type,
        message=message,
        related_request_id=request_id
    )
    notification = await notification_crud.create_notification(db, notification_data)
    logger.info(f"Requester notification created: ID={notification.id}, User={user_id}")


async def create_manager_notification(
    db: AsyncSession,
    request_id: int,
    manager_id: int,
    notification_type: NotificationType,
    message: str
) -> None:
    """
    Create a notification for a manager.
    """
    notification_data = NotificationCreate(
        user_id=manager_id,
        type=notification_type,
        message=message,
        related_request_id=request_id
    )
    notification = await notification_crud.create_notification(db, notification_data)
    logger.info(f"Manager notification created: ID={notification.id}, Manager={manager_id}") 