import json
import sys
import traceback
from typing import Any, Dict, Optional
import datetime
import logging

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, after_setup_logger

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Configure logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger("celery.worker")

# Configure Celery with Redis as broker and backend
celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    broker_connection_retry_on_startup=True
)

# Configure Celery
celery_app.conf.task_routes = {
    "app.worker.send_notification_task": "notifications-queue",
}
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,
    task_track_started=True,
    task_send_sent_event=True,
    task_always_eager=True,  # Set to True to run tasks synchronously for debugging
)


@celery_app.task
def send_notification_task(
    user_id: str,
    notification_type: str,
    message: str,
    related_request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async task to send real-time notifications through Redis.
    
    Args:
        user_id: ID of the recipient user
        notification_type: Notification type
        message: Notification message
        related_request_id: Optional ID of the related request
        
    Returns:
        Dictionary with the result
    """
    print("\n" + "="*80)
    
    task_logger = get_logger("celery.task.notification")
    task_logger.info(
        f"Sending notification type={notification_type} to user={user_id}",
        extra={"data": {"type": notification_type, "user_id": user_id}}
    )
    
    try:
        from redis import Redis
        
        # Connect to Redis
        redis_client = Redis.from_url(settings.REDIS_URL)
        
        # Create the notification payload
        payload = {
            "user_id": user_id,
            "type": notification_type,
            "message": message,
            "related_request_id": related_request_id
        }
        
        # Publish on the user's specific channel
        channel = f"user:{user_id}:notifications"
        redis_client.publish(channel, json.dumps(payload))
        
        task_logger.debug(f"✅ Notification sent successfully to channel {channel}")
        return {"status": "delivered", "channel": channel}
    
    except Exception as e:        
        task_logger.error(
            f"❌ Error sending notification: {str(e)}",
            exc_info=True,
            extra={"data": {"user_id": user_id, "type": notification_type}}
        )
        raise