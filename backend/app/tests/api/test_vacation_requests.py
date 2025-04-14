import pytest
import uuid
from datetime import date, timedelta
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.models.vacation_request import RequestStatus
from app.schemas.vacation_request import VacationRequestCreate


@pytest.mark.asyncio
async def test_create_vacation_request(client: AsyncClient, normal_user_token_headers):
    """Prueba la creación de una solicitud de vacaciones."""
    # Crear datos para la solicitud
    start_date = date.today() + timedelta(days=10)
    end_date = start_date + timedelta(days=5)
    
    data = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "reason": "Vacaciones de verano"
    }
    
    response = await client.post(
        f"{settings.API_V1_STR}/vacation-requests/",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    content = response.json()
    assert content["start_date"] == start_date.isoformat()
    assert content["end_date"] == end_date.isoformat()
    assert content["status"] == RequestStatus.PENDING.value
    assert "id" in content
    
    # Guardar el ID para pruebas posteriores
    return content["id"]


@pytest.mark.asyncio
async def test_read_vacation_requests(client: AsyncClient, normal_user_token_headers):
    """Prueba obtener las solicitudes de vacaciones del usuario actual."""
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)


@pytest.mark.asyncio
async def test_read_vacation_requests_for_review(client: AsyncClient, hr_user_token_headers):
    """Prueba obtener las solicitudes de vacaciones pendientes para revisión."""
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/for-review",
        headers=hr_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)


@pytest.mark.asyncio
async def test_read_vacation_request(client: AsyncClient, normal_user_token_headers):
    """Prueba obtener una solicitud de vacaciones específica."""
    # Primero creamos una solicitud
    request_id = await test_create_vacation_request(client, normal_user_token_headers)
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["id"] == request_id


@pytest.mark.asyncio
async def test_update_vacation_request(client: AsyncClient, normal_user_token_headers):
    """Prueba actualizar una solicitud de vacaciones."""
    # Primero creamos una solicitud
    request_id = await test_create_vacation_request(client, normal_user_token_headers)
    
    # Actualizamos la solicitud
    data = {
        "reason": "Vacaciones de invierno actualizadas"
    }
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request_id}",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["reason"] == data["reason"]
    assert content["id"] == request_id


@pytest.mark.asyncio
async def test_delete_vacation_request(client: AsyncClient, normal_user_token_headers):
    """Prueba eliminar una solicitud de vacaciones."""
    # Primero creamos una solicitud
    request_id = await test_create_vacation_request(client, normal_user_token_headers)
    
    # Eliminamos la solicitud
    response = await client.delete(
        f"{settings.API_V1_STR}/vacation-requests/{request_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verificamos que la solicitud ya no existe
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request_id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_approve_vacation_request(client: AsyncClient, normal_user_token_headers, hr_user_token_headers):
    """Prueba aprobar una solicitud de vacaciones."""
    # Primero creamos una solicitud
    request_id = await test_create_vacation_request(client, normal_user_token_headers)
    
    # Aprobamos la solicitud (rol HR)
    data = {"status": RequestStatus.APPROVED.value}
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request_id}",
        headers=hr_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["status"] == RequestStatus.APPROVED.value 