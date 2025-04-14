import json
from typing import Any, Dict, Optional

from celery import Celery

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Configurar logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger("celery.worker")

# Configurar Celery con Redis como broker y backend
celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    broker_connection_retry_on_startup=True
)

# Configurar Celery
celery_app.conf.task_routes = {
    "app.worker.send_notification_task": "notifications-queue",
}
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=4,
)

logger.info("Worker de Celery inicializado")


@celery_app.task
def send_notification_task(
    user_id: str,
    notification_type: str,
    message: str,
    related_request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tarea asíncrona para enviar notificaciones en tiempo real a través de Redis.
    
    Args:
        user_id: ID del usuario destinatario
        notification_type: Tipo de notificación
        message: Mensaje de la notificación
        related_request_id: ID opcional de la solicitud relacionada
        
    Returns:
        Diccionario con el resultado
    """
    task_logger = get_logger("celery.task.notification")
    task_logger.info(
        f"Enviando notificación tipo={notification_type} a usuario={user_id}",
        extra={"data": {"type": notification_type, "user_id": user_id}}
    )
    
    try:
        from redis import Redis
        
        # Conectar a Redis
        redis_client = Redis.from_url(settings.REDIS_URL)
        
        # Crear el payload de la notificación
        payload = {
            "user_id": user_id,
            "type": notification_type,
            "message": message,
            "related_request_id": related_request_id
        }
        
        # Publicar en el canal específico del usuario
        channel = f"user:{user_id}:notifications"
        redis_client.publish(channel, json.dumps(payload))
        
        task_logger.debug(f"Notificación enviada exitosamente al canal {channel}")
        return {"status": "delivered", "channel": channel}
    
    except Exception as e:
        task_logger.error(
            f"Error al enviar notificación: {str(e)}",
            exc_info=True,
            extra={"data": {"user_id": user_id, "type": notification_type}}
        )
        raise 