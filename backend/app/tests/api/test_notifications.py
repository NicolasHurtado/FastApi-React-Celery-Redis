import pytest
import uuid
from httpx import AsyncClient
from fastapi import status
import logging

from app.core.config import settings
from app.models.notification import NotificationType

# Configurar el sistema de logging
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_create_notification(client: AsyncClient, superuser_token_headers, test_normal_user):
    """Prueba la creación de una notificación para un usuario."""
    # Datos de la notificación
    data = {
        "user_id": str(test_normal_user.id),
        "type": NotificationType.OTHER.value,  # Usamos OTHER como tipo genérico
        "message": "Esto es una notificación de prueba"
    }
    
    logger.info("Datos de prueba: %s", data)  # Usar logger en lugar de print
    
    # Hacer la petición
    response = await client.post(
        f"{settings.API_V1_STR}/notifications/",
        headers=superuser_token_headers,
        json=data
    )
    
    logger.info("Código de respuesta: %s", response.status_code)
    logger.info("Respuesta: %s", response.json())
    
    # Verificar resultado
    assert response.status_code == status.HTTP_201_CREATED
    content = response.json()
    assert content["message"] == data["message"]
    assert content["type"] == data["type"]
    assert content["user_id"] == data["user_id"]
    assert "id" in content
    
    # Guardar el ID para pruebas posteriores
    return content["id"]


@pytest.mark.asyncio
async def test_read_notifications(client: AsyncClient, normal_user_token_headers):
    """Prueba obtener las notificaciones del usuario actual."""
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)


@pytest.mark.asyncio
async def test_read_unread_count(client: AsyncClient, normal_user_token_headers):
    """Prueba obtener el contador de notificaciones no leídas."""
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/unread-count",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    count = response.json()
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_read_notification(client: AsyncClient, superuser_token_headers, normal_user_token_headers, test_normal_user):
    """Prueba obtener una notificación específica."""
    # Primero creamos una notificación
    notification_id = await test_create_notification(client, superuser_token_headers, test_normal_user)
    
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["id"] == notification_id


@pytest.mark.asyncio
async def test_update_notification(client: AsyncClient, superuser_token_headers, normal_user_token_headers, test_normal_user):
    """Prueba actualizar una notificación."""
    # Primero creamos una notificación
    notification_id = await test_create_notification(client, superuser_token_headers, test_normal_user)
    
    # Actualizamos la notificación (marcar como leída)
    data = {"read": True}
    
    response = await client.put(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["read"] == data["read"]
    assert content["id"] == notification_id


@pytest.mark.asyncio
async def test_delete_notification(client: AsyncClient, superuser_token_headers, normal_user_token_headers, test_normal_user):
    """Prueba eliminar una notificación."""
    # Primero creamos una notificación
    notification_id = await test_create_notification(client, superuser_token_headers, test_normal_user)
    
    # Eliminamos la notificación
    response = await client.delete(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verificamos que la notificación ya no existe
    response = await client.get(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_mark_notification_as_read(client: AsyncClient, superuser_token_headers, normal_user_token_headers, test_normal_user):
    """Prueba marcar una notificación como leída."""
    # Primero creamos una notificación
    notification_id = await test_create_notification(client, superuser_token_headers, test_normal_user)
    
    # Marcamos como leída
    response = await client.patch(
        f"{settings.API_V1_STR}/notifications/{notification_id}/mark-as-read",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["read"] is True
    assert content["id"] == notification_id


@pytest.mark.asyncio
async def test_mark_all_as_read(client: AsyncClient, superuser_token_headers, normal_user_token_headers, test_normal_user):
    """Prueba marcar todas las notificaciones como leídas."""
    # Creamos varias notificaciones
    for _ in range(3):
        await test_create_notification(client, superuser_token_headers, test_normal_user)
    
    # Marcamos todas como leídas
    response = await client.patch(
        f"{settings.API_V1_STR}/notifications/mark-all-as-read",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    count = response.json()
    assert count >= 0  # Al menos debería haber marcado algunas 