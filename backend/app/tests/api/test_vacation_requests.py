import pytest
import uuid
from datetime import date, timedelta
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.models.vacation_request import RequestStatus
from app.schemas.vacation_request import VacationRequestCreate
from app.tests.factories.models import UserFactory, VacationRequestFactory


@pytest.mark.asyncio
async def test_create_vacation_request(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba la creación de una solicitud de vacaciones."""
    # Obtener información del usuario actual
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    user_id = get_subject_from_token(token)
    
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
async def test_read_vacation_requests(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba obtener las solicitudes de vacaciones del usuario actual."""
    # Obtener información del usuario actual
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    user_id = get_subject_from_token(token)
    
    # Crear varias solicitudes para este usuario
    for _ in range(3):
        await VacationRequestFactory.create_async(
            db=db_session,
            requester_id=user_id
        )
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 3  # Al menos deberían estar las solicitudes que creamos


@pytest.mark.asyncio
async def test_read_vacation_requests_for_review(client: AsyncClient, db_session, hr_user_token_headers):
    """Prueba obtener las solicitudes de vacaciones pendientes para revisión."""
    # Crear varios empleados con solicitudes pendientes
    for _ in range(3):
        employee = await UserFactory.create_async(db=db_session)
        await VacationRequestFactory.create_async(
            db=db_session,
            requester=employee,
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
    assert len(content) >= 3  # Al menos deberían estar las solicitudes que creamos


@pytest.mark.asyncio
async def test_read_vacation_request(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba obtener una solicitud de vacaciones específica."""
    # Obtener información del usuario actual
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    user_id = get_subject_from_token(token)
    
    # Crear una solicitud para este usuario
    request = await VacationRequestFactory.create_async(
        db=db_session,
        requester_id=user_id
    )
    
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["id"] == str(request.id)


@pytest.mark.asyncio
async def test_update_vacation_request(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba actualizar una solicitud de vacaciones."""
    # Obtener información del usuario actual
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    user_id = get_subject_from_token(token)
    
    # Crear una solicitud para este usuario
    request = await VacationRequestFactory.create_async(
        db=db_session,
        requester_id=user_id
    )
    
    # Actualizamos la solicitud
    data = {
        "reason": "Vacaciones de invierno actualizadas"
    }
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["reason"] == data["reason"]
    assert content["id"] == str(request.id)


@pytest.mark.asyncio
async def test_delete_vacation_request(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba eliminar una solicitud de vacaciones."""
    # Obtener información del usuario actual
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    user_id = get_subject_from_token(token)
    
    # Crear una solicitud para este usuario
    request = await VacationRequestFactory.create_async(
        db=db_session,
        requester_id=user_id
    )
    
    # Eliminamos la solicitud
    response = await client.delete(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verificamos que la solicitud ya no existe
    response = await client.get(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=normal_user_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_approve_vacation_request(client: AsyncClient, db_session, normal_user_token_headers, hr_user_token_headers):
    """Prueba aprobar una solicitud de vacaciones."""
    # Obtener información del usuario normal
    from app.core.security import get_subject_from_token
    
    token = normal_user_token_headers["Authorization"].split()[1]
    employee_id = get_subject_from_token(token)
    
    # Crear una solicitud para este usuario
    request = await VacationRequestFactory.create_async(
        db=db_session,
        requester_id=employee_id,
        status=RequestStatus.PENDING
    )
    
    # Aprobamos la solicitud (rol HR)
    data = {"status": RequestStatus.APPROVED.value}
    
    response = await client.put(
        f"{settings.API_V1_STR}/vacation-requests/{request.id}",
        headers=hr_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["status"] == RequestStatus.APPROVED.value 