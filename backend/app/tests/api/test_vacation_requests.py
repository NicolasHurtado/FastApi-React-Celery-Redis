"""Tests for the vacation requests API."""
import logging
from typing import Optional
from datetime import date, timedelta
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
from unittest.mock import patch
import io

from app.core.config import settings
from app.models.vacation_request import VacationRequest, RequestStatus
from app.schemas.vacation_request import VacationRequestCreate
from app.crud.vacation_request import create_vacation_request
from app.tests.api.test_users import create_test_user
from app.worker import celery_app
from app.services import notification_service
from app.models.user import UserRole

# Configure logging system
logger = logging.getLogger(__name__)


async def create_test_vacation_request(
    db: AsyncSession,
    requester_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    reason: str = "Test vacation",
    status: RequestStatus = RequestStatus.PENDING,
    reviewer_id: Optional[int] = None
) -> VacationRequest:
    """Create a test vacation request."""
    # Set default dates if not provided
    if not start_date:
        start_date = date.today() + timedelta(days=10)
    if not end_date:
        end_date = start_date + timedelta(days=5)
    
    # Create vacation request object
    request_in = VacationRequestCreate(
        start_date=start_date,
        end_date=end_date,
        reason=reason
    )
    
    # Create vacation request in the database
    request = await create_vacation_request(db=db, obj_in=request_in, requester_id=requester_id)
    
    # Set additional attributes if needed
    if status != RequestStatus.PENDING or reviewer_id:
        request.status = status
        if reviewer_id:
            request.reviewer_id = reviewer_id
        await db.commit()
        await db.refresh(request)
    
    logger.info(f"Vacation request created: id={request.id}, requester_id={request.requester_id}, status={request.status}")
    return request


async def test_create_vacation_request(client: AsyncClient, db_session, superuser, normal_user_token_headers):
    """Test the creation of a vacation request."""
    # Create data for the request
    start_date = date.today() + timedelta(days=10)
    end_date = start_date + timedelta(days=5)
    
    data = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "reason": "Summer vacation"
    }
    
    response = await client.post(
        f"{settings.API_V1_STR}/vacation-requests/",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
    content = response.json()
    assert content["start_date"] == start_date.isoformat()
    assert content["end_date"] == end_date.isoformat()
    assert content["status"] == RequestStatus.PENDING.value
    assert "id" in content


async def test_read_vacation_requests(client: AsyncClient, db_session, normal_user_token_headers, normal_user):
    """Test getting the vacation requests of the current user."""
    # Create several requests for this user
    for _ in range(3):
        await create_test_vacation_request(
            db=db_session,
            requester_id=normal_user.id
        )
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 3  # Should have at least the requests we created


async def test_read_vacation_requests_for_review(client: AsyncClient, db_session, hr_user_token_headers, hr_user):
    """Test getting pending vacation requests for review."""
    # Create several employees with pending requests
    for _ in range(3):
        employee = await create_test_user(db=db_session)
        await create_test_vacation_request(
            db=db_session,
            requester_id=employee.id,
            status=RequestStatus.PENDING
        )
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/for-review",
        headers=hr_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 3  # Should have at least the requests we created


async def test_read_vacation_request(client: AsyncClient, db_session, normal_user_token_headers, normal_user):
    """Test getting a specific vacation request."""
    # Create a request for this user
    request = await create_test_vacation_request(
        db=db_session,
        requester_id=normal_user.id
    )
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["id"] == request.id


async def test_update_vacation_request(client: AsyncClient, db_session, normal_user_token_headers, normal_user):
    """Test updating a vacation request."""
    # Create a request for this user
    request = await create_test_vacation_request(
        db=db_session,
        requester_id=normal_user.id
    )
    
    # Update the request
    data = {
        "reason": "Updated winter vacation"
    }
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["reason"] == data["reason"]
    assert content["id"] == request.id


async def test_delete_vacation_request(client: AsyncClient, db_session, normal_user_token_headers, normal_user):
    """Test deleting a vacation request."""
    # Create a request for this user
    request = await create_test_vacation_request(
        db=db_session,
        requester_id=normal_user.id
    )
    
    # Delete the request
    response = await client.delete(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify that the request no longer exists
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_approve_vacation_request(client: AsyncClient, db_session, normal_user_token_headers, hr_user_token_headers, normal_user, hr_user):
    """Test approving a vacation request."""
    # Create a request for the normal user
    request = await create_test_vacation_request(
        db=db_session,
        requester_id=normal_user.id,
        status=RequestStatus.PENDING
    )
    
    # Approve the request (HR role)
    data = {
        "status": RequestStatus.APPROVED.value,
        "reviewer_comment": "Approved vacation request"
    }
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}/review",
        headers=hr_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["status"] == RequestStatus.APPROVED.value
    assert content["reviewer_comment"] == "Approved vacation request"
    assert content["reviewer_id"] == hr_user.id


@pytest.mark.asyncio
async def test_notification_task_execution_on_request_creation(client, db_session, normal_user, normal_user_token_headers, monkeypatch):
    """Test that notification tasks execute completely when creating a vacation request."""
    
    # 1. Configure Celery para ejecutar tareas inmediatamente (eager mode)
    monkeypatch.setattr(celery_app.conf, 'task_always_eager', True)
    monkeypatch.setattr(celery_app.conf, 'task_eager_propagates', True)
    
    # 2. Crear un manager para recibir notificaciones
    manager = await create_test_user(
        db=db_session,
        role=UserRole.MANAGER,
        email="test_manager@example.com"
    )
    
    # 3. Configurar captura de logs
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    task_logger = logging.getLogger("celery.task.notification")
    original_level = task_logger.level
    task_logger.setLevel(logging.DEBUG)
    task_logger.addHandler(handler)
    
    try:
        # 4. Crear solicitud de vacaciones que debe desencadenar notificaciones
        data = {
            "start_date": (date.today() + timedelta(days=10)).isoformat(),
            "end_date": (date.today() + timedelta(days=15)).isoformat(),
            "reason": "Test notification chain"
        }
        
        # Mock para Redis.publish para evitar errores de conexión a Redis
        with patch('redis.Redis.publish') as mock_publish:
            mock_publish.return_value = 1  # Simular éxito en publicación
            
            response = await client.post(
                f"{settings.API_V1_STR}/vacation-requests/",
                headers=normal_user_token_headers,
                json=data
            )
            
            # 5. Verificar respuesta HTTP
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
            
            # 6. Verificar que mock_publish fue llamado (la notificación se envió)
            assert mock_publish.called
            
            # 7. Verificar contenido de los logs
            log_content = log_capture.getvalue()
            assert "Sending notification" in log_content
            assert "Notification sent successfully" in log_content
            
    finally:
        # Restaurar configuración de logging
        task_logger.removeHandler(handler)
        task_logger.setLevel(original_level) 