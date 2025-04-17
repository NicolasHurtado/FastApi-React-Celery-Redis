"""Manage users CRUD operations"""
from typing import Any, Dict, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get a user by their email.
    
    Args:
        db: Database session
        email: User email to search
        
    Returns:
        User found or None
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()



async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Get a user by their ID.
    
    Args:
        db: Database session
        user_id: User ID to search
        
    Returns:
        User found or None
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()



async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[User]:
    """
    Get a paginated list of users.
    
    Args:
        db: Database session
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        
    Returns:
        List of users
    """
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()



async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_in: User data to create
        
    Returns:
        Created user
    """
    # Verify if the email already exists
    existing_user = await get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise ValueError(f"The email {user_in.email} already exists")
        
    # Create user object with the received data
    user = User(
        email=user_in.email,
        password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
        total_vacation_days=user_in.total_vacation_days or 20,  # Default value
    )
    
    # Add to the session and confirm
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user



async def update_user(
    db: AsyncSession, 
    user: User, 
    user_in: Union[UserUpdate, Dict[str, Any]]
) -> User:
    """
    Update an existing user.
    
    Args:
        db: Database session
        user: User to update
        user_in: Update data
        
    Returns:
        Updated user
    """
    # Convert dict to UserUpdate if necessary
    update_data = user_in if isinstance(user_in, dict) else user_in.dict(exclude_unset=True)
    
    # Handle password if provided
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["password"] = hashed_password
        
    # Update user attributes
    for field, value in update_data.items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)
    
    # Save changes
    await db.commit()
    await db.refresh(user)
    return user



async def delete_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Delete a user by their ID.
    
    Args:
        db: Database session
        user_id: ID of the user to delete
        
    Returns:
        Deleted user or None if it does not exist
    """
    user = await get_user(db, user_id)
    if not user:
        return None
        
    await db.delete(user)
    await db.commit()
    return user



async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        Authenticated user or None if authentication fails
    """
    user = await get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


async def is_active(user: User) -> bool:
    """
    Verify if a user is active.
    
    Args:
        user: User to verify
        
    Returns:
        True if the user is active, False otherwise
    """
    return user.is_active


async def is_superuser(user: User) -> bool:
    """
    Verify if a user is a superuser.
    
    Args:
        user: User to verify
        
    Returns:
        True if the user is a superuser, False otherwise
    """
    return user.is_superuser


async def is_manager_or_admin(user: User) -> bool:
    """
    Verify if a user is a manager or admin.
    
    Args:
        user: User to verify
        
    Returns:
        True if the user is a manager or admin, False otherwise
    """
    return user.role in [UserRole.MANAGER, UserRole.ADMIN] 