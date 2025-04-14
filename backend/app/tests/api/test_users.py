import uuid
import pytest
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string


@pytest.mark.asyncio
async def test_get_users_me(client: AsyncClient, normal_user_token_headers):
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
async def test_update_user_me(client: AsyncClient, normal_user_token_headers):
    """Prueba que un usuario puede actualizar su propia información."""
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
async def test_get_user_by_id(client: AsyncClient, superuser_token_headers, test_normal_user):
    """Prueba que un superuser puede obtener información de otro usuario por ID."""
    response = await client.get(
        f"{settings.API_V1_STR}/users/{test_normal_user.id}",
        headers=superuser_token_headers
    )
    assert response.status_code == status.HTTP_200_OK
    user = response.json()
    assert user["email"] == test_normal_user.email
    assert user["id"] == str(test_normal_user.id)


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, superuser_token_headers, test_normal_user):
    """Prueba que un superuser puede actualizar otro usuario."""
    new_name = random_lower_string()
    data = {"full_name": new_name}
    response = await client.put(
        f"{settings.API_V1_STR}/users/{test_normal_user.id}",
        headers=superuser_token_headers,
        json=data
    )
    assert response.status_code == status.HTTP_200_OK
    updated_user = response.json()
    assert updated_user["full_name"] == new_name
    assert updated_user["id"] == str(test_normal_user.id)


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, superuser_token_headers, db_session):
    """Prueba que un superuser puede eliminar un usuario."""
    # Crear un usuario temporal para eliminar
    from app.crud.user import create_user
    from app.schemas.user import UserCreate
    
    user_in = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        full_name=random_lower_string()
    )
    user = await create_user(db_session, user_in=user_in)
    
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