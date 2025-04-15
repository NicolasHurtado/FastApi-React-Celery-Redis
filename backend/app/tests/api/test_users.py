import uuid
import pytest
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string
from app.models.user import UserRole
from app.tests.factories.models import UserFactory


@pytest.mark.asyncio
async def test_get_users_me(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba que un usuario autenticado puede obtener su propia información."""
    response = await client.get(
        f"{settings.API_V1_STR}/users/me", 
        headers=normal_user_token_headers
    )
    assert response.status_code == status.HTTP_200_OK
    user = response.json()
    assert user["email"] is not None
    assert "id" in user
    assert "password" not in user


@pytest.mark.asyncio
async def test_update_user_me(client: AsyncClient, db_session, normal_user_token_headers):
    """Prueba que un usuario puede actualizar su propia información."""
    # Primero obtenemos el usuario actual para tener el ID
    response = await client.get(
        f"{settings.API_V1_STR}/users/me", 
        headers=normal_user_token_headers
    )
    current_user = response.json()
    
    # Actualizamos con un nombre nuevo
    new_name = random_lower_string()
    data = {"full_name": new_name}
    
    response = await client.put(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    updated_user = response.json()
    assert updated_user["full_name"] == new_name


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient, db_session, superuser_token_headers):
    """Prueba que un superuser puede obtener información de otro usuario por ID."""
    # Crear un usuario con factory
    user = await UserFactory.create_async(db=db_session)
    
    # Obtener información del usuario a través de la API
    response = await client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["email"] == user.email
    assert content["id"] == str(user.id)


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, db_session, superuser_token_headers):
    """Prueba que un superuser puede actualizar otro usuario."""
    # Crear un usuario con factory
    user = await UserFactory.create_async(db=db_session)
    
    # Actualizar el usuario
    new_name = random_lower_string()
    data = {"full_name": new_name}
    
    response = await client.put(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data
    )
    
    assert response.status_code == status.HTTP_200_OK
    updated_user = response.json()
    assert updated_user["full_name"] == new_name
    assert updated_user["id"] == str(user.id)


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, db_session, superuser_token_headers):
    """Prueba que un superuser puede eliminar un usuario."""
    # Crear un usuario con factory
    user = await UserFactory.create_async(db=db_session)
    
    # Eliminar el usuario
    response = await client.delete(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verificar que el usuario ya no existe
    response = await client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND 