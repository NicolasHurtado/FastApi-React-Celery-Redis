"""Manage users endpoints"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (get_current_active_user, get_current_superuser,
                       get_current_manager_or_admin)
from app.crud.user import (create_user, delete_user, get_user, get_users,
                        update_user)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (User as UserSchema, UserCreate, UserUpdate)

router = APIRouter()


@router.get("/", response_model=List[UserSchema])
async def read_users(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_manager_or_admin),
) -> Any:
    """
    Get a paginated list of users.
    
    Only accessible to administrators and managers.
    
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        current_user: Current authenticated user
        
    Returns:
        List of users
    """
    users = await get_users(db, skip=skip, limit=limit)
    return users


@router.post("/", response_model=UserSchema)
async def create_new_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Create a new user.
    
    Only accessible to superusers.
    
    Args:
        db: Database session
        user_in: User data to create
        current_user: Current authenticated user
        
    Returns:
        Created user
        
    Raises:
        HTTPException: If the email already exists
    """
    try:
        user = await create_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserSchema)
async def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get information about the currently authenticated user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Information about the current user
    """
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update information about the currently authenticated user.
    
    Args:
        db: Database session
        user_in: Data to update
        current_user: Current authenticated user
        
    Returns:
        Updated user information
    """
    # Restrict the fields that a user can update themselves
    # (do not allow changing role, permissions, etc.)
    allowed_fields = {"full_name", "password"}
    user_data = user_in.dict(exclude_unset=True)
    restricted_data = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    user = await update_user(db, current_user, UserUpdate(**restricted_data))
    return user


@router.get("/{user_id}", response_model=UserSchema)
async def read_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get information from a specific user by their ID.
    
    Only superusers and managers can access information from any user.
    Normal users can only access their own information.
    
    Args:
        user_id: ID of the user to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Information of the requested user
        
    Raises:
        HTTPException: If the user does not exist or you do not have permission
    """
    user = await get_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    # If not superuser or manager, only can access their own information
    if str(user.id) != str(current_user.id) and not await get_current_manager_or_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have enough permissions",
        )
        
    return user


@router.put("/{user_id}", response_model=UserSchema)
async def update_specific_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_manager_or_admin),
) -> Any:
    """
    Update information from a specific user.
    
    Only accessible to administrators and managers.
    
    Args:
        db: Database session
        user_id: ID of the user to update
        user_in: Data to update
        current_user: Current authenticated user
        
    Returns:
        Information of the updated user
        
    Raises:
        HTTPException: If the user does not exist
    """
    user = await get_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    user = await update_user(db, user, user_in)
    return user


@router.delete("/{user_id}")
async def delete_specific_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a specific user.
    
    Only accessible to superusers.
    
    Args:
        db: Database session
        user_id: ID of the user to delete
        current_user: Current authenticated user
        
    Returns:
        Information of the deleted user
        
    Raises:
        HTTPException: If the user does not exist or if you try to delete your own user
    """
    # Avoid that a user deletes themselves
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own user",
        )
        
    user = await delete_user(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    return Response(status_code=status.HTTP_204_NO_CONTENT) 