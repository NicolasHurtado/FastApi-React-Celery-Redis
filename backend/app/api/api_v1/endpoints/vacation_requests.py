import logging
import sys
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.deps import (
    get_current_active_user,
    get_current_manager_or_admin,
    get_current_superuser
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.vacation_request import RequestStatus
from app.crud import vacation_request as crud
from app.schemas.vacation_request import (
    VacationRequest,
    VacationRequestCreate,
    VacationRequestUpdate
)
from app.services import notification_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=VacationRequest)
async def create_vacation_request(
    *,
    db: AsyncSession = Depends(get_db),
    request_in: VacationRequestCreate,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Create a new vacation request.
    
    Args:
        db: Database session
        request_in: Request data
        current_user: Authenticated user
        
    Returns:
        The created request
    """
    # Calculate requested days
    delta = (request_in.end_date - request_in.start_date).days + 1
    
    # Verify that the user has enough days available
    if delta > current_user.total_vacation_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You don't have enough days available. Requested: {delta}, Available: {current_user.total_vacation_days}"
        )
    
    # Create the request
    vacation_request = await crud.create_vacation_request(
        db=db, obj_in=request_in, requester_id=current_user.id
    )
    
    # Get the IDs of all managers and admins to notify them
    query = select(User.id).where(
        and_(
            User.role.in_([UserRole.MANAGER, UserRole.ADMIN]),
            User.is_active == True
        )
    )
    result = await db.execute(query)
    manager_ids = result.scalars().all()
    
    logger.info(f"Notifying managers: {manager_ids}")
    
    if manager_ids:
        try:          
            await notification_service.notify_new_request(db, vacation_request, manager_ids)
            logger.info("Notifications sent correctly to managers")
        except Exception as e:
            logger.error(f"Error sending notifications: {str(e)}", exc_info=True)
    else:
        logger.warning("No managers/admins to notify")
    
    return vacation_request


@router.get("/", response_model=List[VacationRequest])
async def read_vacation_requests(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get my vacation requests.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        status: Filter by status
        current_user: Authenticated user
        
    Returns:
        List of vacation requests for the user
    """
    requests = await crud.get_vacation_requests(
        db=db, skip=skip, limit=limit, requester_id=current_user.id, status=status
    )
    return requests


@router.get("/for-review", response_model=List[VacationRequest])
async def read_vacation_requests_for_review(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None,
    current_user: User = Depends(get_current_manager_or_admin)
) -> Any:
    """
    Get vacation requests to review (only managers and admins).
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        status: Filter by status
        current_user: Authenticated user (manager or admin)
        
    Returns:
        List of requests to review
    """
    requests = await crud.get_vacation_requests_for_review(
        db=db, reviewer_id=current_user.id, skip=skip, limit=limit, status=status
    )
    return requests


@router.get("/{request_id}", response_model=VacationRequest)
async def read_vacation_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get a specific vacation request.
    
    Normal users can only see their own requests.
    Managers and admins can see all requests.
    
    Args:
        request_id: ID of the request
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Vacation request
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )
    
    # Verify permissions
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN] and request.requester_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this request"
        )
    
    return request


@router.put("/{request_id}", response_model=VacationRequest)
async def update_vacation_request(
    *,
    request_id: int,
    request_in: VacationRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Update a vacation request.
    
    Normal users can only update their own pending requests.
    Managers and admins can update any request.
    
    Args:
        request_id: ID de la solicitud
        request_in: Update data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated request
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )
    
    # Verify permissions
    is_manager_or_admin = current_user.role in [UserRole.MANAGER, UserRole.ADMIN]
    is_owner = request.requester_id == current_user.id
    
    # If not owner or manager/admin, cannot update
    if not is_owner and not is_manager_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this request"
        )
    
    # If owner but not manager/admin, can only update pending requests
    if is_owner and not is_manager_or_admin and request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify pending requests"
        )
    
    # If owner, cannot change status (only managers/admins can)
    if is_owner and not is_manager_or_admin and request_in.status is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change the status of the request"
        )
    
    # If there is a change in the dates, verify available days
    if (request_in.start_date is not None or request_in.end_date is not None) and is_owner:
        start_date = request_in.start_date or request.start_date
        end_date = request_in.end_date or request.end_date
        
        delta = (end_date - start_date).days + 1
        
        if delta > current_user.total_vacation_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You don't have enough days available. Requested: {delta}, Available: {current_user.total_vacation_days}"
            )
    
    # Save previous status for notifications
    old_status = request.status
    
    # Update the request
    request = await crud.update_vacation_request(
        db=db, 
        db_obj=request, 
        obj_in=request_in,
        reviewer_id=current_user.id if is_manager_or_admin else None
    )
    
    # Generate notifications if the status changed
    if old_status != request.status:
        await notification_service.notify_status_change(db, request, old_status)
    
    return request


@router.put("/{request_id}/review", response_model=VacationRequest)
async def review_vacation_request(
    *,
    request_id: int,
    request_in: VacationRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
) -> Any:
    """
    Review a vacation request (only managers and admins).
    
    Args:
        request_id: ID of the request
        request_in: Update data with status and reviewer_comment
        db: Database session
        current_user: Authenticated user (manager or admin)
        
    Returns:
        Updated vacation request with status and comment
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )
    
    # Save previous status for notifications
    old_status = request.status
    
    # Update the request
    request = await crud.update_vacation_request(
        db=db, 
        db_obj=request, 
        obj_in=request_in,
        reviewer_id=current_user.id
    )
    
    # Generate notifications if the status changed
    if old_status != request.status:
        await notification_service.notify_status_change(db, request, old_status)
    
    return request


@router.delete("/{request_id}", response_model=VacationRequest)
async def delete_vacation_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Delete a vacation request.
    
    Normal users can only delete their own pending requests.
    Admins can delete any request.
    
    Args:
        request_id: ID of the request
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Deleted vacation request with status code 204
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )
    
    # Verify permissions
    is_admin = current_user.role == UserRole.ADMIN
    is_owner = request.requester_id == current_user.id
    
    # If not owner or admin, cannot delete
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this request"
        )
    
    # If owner but not admin, can only delete pending requests
    if is_owner and not is_admin and request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete pending requests"
        )
    
    # Eliminar la solicitud
    request = await crud.delete_vacation_request(db=db, id=request_id)
    
    return Response(status_code=status.HTTP_204_NO_CONTENT) 