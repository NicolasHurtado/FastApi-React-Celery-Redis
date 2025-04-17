"""Tests for the users API."""
import logging

from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.crud.user import create_user
from app.schemas.user import UserCreate

# Configure logging system
logger = logging.getLogger(__name__)


async def create_test_user(
    db: AsyncSession,
    email: str = None,
    password: str = "testpassword",
    full_name: str = "Test User",
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
    is_superuser: bool = False,
    total_vacation_days: int = 20
) -> User:
    """Create a test user in the database."""
    # Generate random email if not provided
    if not email:
        email = random_email()
    
    # Create user object
    user_in = UserCreate(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
        is_active=is_active,
        is_superuser=is_superuser,
        total_vacation_days=total_vacation_days
    )
    
    # Create user in the database
    try:
        user = await create_user(db=db, user_in=user_in)
        logger.info(f"User created: id={user.id}, email={user.email}, role={user.role}")
        return user
    except ValueError as e:
        logger.error(f"Error creating user: {str(e)}")
        raise


async def test_get_users(client: AsyncClient, db_session, superuser_token_headers):
    """Test that an authenticated user can get their own information."""
    response = await client.get(
        f"{settings.API_V1_STR}/users/", 
        headers=superuser_token_headers
    )
    logger.info(f"Response: {response.json()}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["email"] == settings.FIRST_SUPERUSER


async def test_get_users_me(client: AsyncClient, db_session, normal_user_token_headers):
    """Test that an authenticated user can get their own information."""
    response = await client.get(
        f"{settings.API_V1_STR}/users/me", 
        headers=normal_user_token_headers
    )
    assert response.status_code == status.HTTP_200_OK
    user = response.json()
    assert user["email"] is not None
    assert "id" in user
    assert "password" not in user


async def test_update_user_me(client: AsyncClient, db_session, normal_user_token_headers):
    """Test that a user can update their own information."""
    # First get the current user to have the ID
    response = await client.get(
        f"{settings.API_V1_STR}/users/me", 
        headers=normal_user_token_headers
    )
    current_user = response.json()
    
    # Update with a new name
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


async def test_get_user_by_id(client: AsyncClient, db_session, superuser_token_headers, superuser):
    """Test that a superuser can get information from another user by ID."""
    # Create a test user
    user = await create_test_user(db=db_session)
    
    logger.info(f"User created: id={user.id}, email={user.email}, role={user.role}")
    # Get user information through the API
    response = await client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    content = response.json()
    assert content["email"] == user.email
    assert content["id"] == user.id


async def test_update_user(client: AsyncClient, db_session, superuser_token_headers, superuser):
    """Test that a superuser can update another user."""
    # Create a test user
    user = await create_test_user(db=db_session)
    
    # Update the user
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
    assert updated_user["id"] == user.id


async def test_delete_user(client: AsyncClient, db_session, superuser_token_headers, superuser):
    """Test that a superuser can delete a user."""
    # Create a test user
    user = await create_test_user(db=db_session)
    
    # Delete the user
    response = await client.delete(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify that the user no longer exists
    response = await client.get(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND 