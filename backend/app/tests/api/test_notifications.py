"""Tests for the notifications API."""
import logging
from typing import Any

from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import NotificationType
from app.crud.notification import create_notification
from app.schemas.notification import NotificationCreate
from app.models.user import User

# Configurar el sistema de logging
logger = logging.getLogger(__name__)


async def create_test_notification(
    db: AsyncSession, 
    user_id: int, 
    message: str = "Test notification", 
    notification_type: NotificationType = NotificationType.OTHER,
    read: bool = False,
    related_request_id: int = None
) -> Any:
    """Create a test notification for a specific user."""
    # Ensure user_id is an integer
    if isinstance(user_id, str):
        user_id = int(user_id)
    
    # Create notification object
    notif_data = NotificationCreate(
        user_id=user_id,
        type=notification_type,
        message=message,
        read=read,
        related_request_id=related_request_id
    )
    # Create notification in the database
    notification = await create_notification(db=db, obj_in=notif_data)
    logger.info(
        f"Notification created: id={notification.id}, user_id={notification.user_id}, message={notification.message}, read={notification.read}"
    )
    return notification


async def create_multiple_notifications(
    db: AsyncSession, 
    user_id: int, 
    count: int = 3, 
    prefix: str = "Test notification",
    related_request_id: int = None
) -> list:
    """Create multiple notifications for a specific user."""
    # Ensure user_id is an integer
    if isinstance(user_id, str):
        user_id = int(user_id)
    
    notifications = []
    logger.info(f"Creating {count} notifications for user {user_id}")
    
    # Create the notifications
    for i in range(count):
        notification = await create_test_notification(
            db=db, 
            user_id=user_id, 
            message=f"{prefix} {i+1}",
            related_request_id=related_request_id
        )
        notifications.append(notification)
    
    return notifications


async def test_create_notification(client: AsyncClient, db_session, normal_user_token_headers, normal_user: User):
    """Test the creation of a notification for a user."""
    
    
    # Notification data
    data = {
        "user_id": normal_user.id,
        "type": NotificationType.OTHER.value,
        "message": "This is a test notification"
    }

    logger.info(f"Notification data: {data}")
    
    # Make the request
    response = await client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers,
        json=data
    )

    # Verify the result
    assert response.status_code == status.HTTP_201_CREATED
    content = response.json()
    assert content["message"] == data["message"]
    assert content["type"] == data["type"]
    assert content["user_id"] == data["user_id"]
    


async def test_read_notifications(client: AsyncClient, db_session, normal_user_token_headers, normal_user: User):
    """Test the reading of the current user's notifications."""    
    # Create multiple notifications for this user
    await create_multiple_notifications(db=db_session, user_id=normal_user.id, count=3)
    
    # Make the request through the API
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers
    )
        
    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)
    
    # Check that there are at least 3 notifications more than before
    assert len(content) >= 3
    assert content[0]["user_id"] == normal_user.id



async def test_read_unread_count(client: AsyncClient, db_session, normal_user_token_headers, normal_user: User):
    """Test the reading of the unread notification count."""
        
    
    # Create multiple unread notifications for this user
    await create_multiple_notifications(db=db_session, user_id=normal_user.id, count=2)
    await create_test_notification(db=db_session, user_id=normal_user.id, read=True)
    
    # Query the unread notification count
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/unread-count",
        headers=normal_user_token_headers
    )
    
    
    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    count = response.json()
    assert isinstance(count, int)
    # Check that there are at least the correct number of unread notifications
    assert count == 2


async def test_read_notification(client: AsyncClient, db_session, superuser_token_headers, superuser: User):
    """Test the reading of a specific notification."""
    
    # Create a notification for the superuser
    notification = await create_test_notification(
        db=db_session,
        user_id=superuser.id,  # Use the user object ID
        message="Test single notification"
    )
    logger.info(f"Notification created with ID {notification.id} for user {notification.user_id}")
    
    # Get the notification through the API
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/{notification.id}",
        headers=superuser_token_headers
    )

    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["id"] == notification.id
    # Verify that the notification belongs to the current user
    assert content["user_id"] == superuser.id


async def test_update_notification(client: AsyncClient, db_session, superuser_token_headers, superuser: User):
    """Test the updating of a notification."""
    
    # Create a notification for the superuser
    notification = await create_test_notification(
        db=db_session,
        user_id=superuser.id,  # Use the user object ID
        message="Test update notification"
    )
    logger.info(f"Notification created with ID {notification.id} for user {notification.user_id}")
    
    # Update the notification
    data = {"read": True}
    response = await client.put(
        f"{settings.API_V1_STR}/notifications/{notification.id}",
        headers=superuser_token_headers,
        json=data
    )
    
    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["read"] == data["read"]
    assert content["id"] == notification.id
    # Verify that the notification belongs to the current user
    assert content["user_id"] == superuser.id


async def test_delete_notification(client: AsyncClient, db_session, superuser_token_headers, superuser: User):
    """Test the deletion of a notification."""
    
    # Create a notification for the superuser
    notification = await create_test_notification(
        db=db_session,
        user_id=superuser.id,  # Use the user object ID
        message="Test delete notification"
    )
    
    # Delete the notification
    response = await client.delete(
        f"{settings.API_V1_STR}/notifications/{notification.id}",
        headers=superuser_token_headers
    )
    
    # Verify the deletion
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_mark_notification_as_read(client: AsyncClient, db_session, superuser_token_headers, superuser: User):
    """Test the marking of a notification as read."""
    
    # Create a notification for the superuser
    notification = await create_test_notification(
        db=db_session,
        user_id=superuser.id,  # Use the user object ID
        message="Test mark-as-read notification"
    )
    
    # Mark as read
    response = await client.patch(
        f"{settings.API_V1_STR}/notifications/{notification.id}/mark-as-read",
        headers=superuser_token_headers
    )
    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["read"] is True
    # Verify that the notification belongs to the current user
    assert content["user_id"] == superuser.id


async def test_mark_all_as_read(client: AsyncClient, db_session, superuser_token_headers, superuser: User):
    """Test the marking of all notifications as read."""
    await create_multiple_notifications(db=db_session, user_id=superuser.id, count=3)
    
    # Mark all as read
    response = await client.patch(
        f"{settings.API_V1_STR}/notifications/mark-all-as-read",
        headers=superuser_token_headers
    )
    
    # Verify the result
    assert response.status_code == status.HTTP_200_OK
    count = response.json()
    assert count == 3  # At least should have marked the ones we created