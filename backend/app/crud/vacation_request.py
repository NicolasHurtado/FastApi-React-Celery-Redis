import uuid
from datetime import date
from typing import List, Optional, Union, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from app.models.vacation_request import VacationRequest, RequestStatus
from app.models.user import User, UserRole
from app.schemas.vacation_request import VacationRequestCreate, VacationRequestUpdate


async def create_vacation_request(
    db: AsyncSession, 
    obj_in: VacationRequestCreate, 
    requester_id: int
) -> VacationRequest:
    """
    Create a new vacation request.
    
    Args:
        db: Database session
        obj_in: Request data
        requester_id: ID of the user who is making the request
        
    Returns:
        Created vacation request
    """
    db_obj = VacationRequest(
        start_date=obj_in.start_date,
        end_date=obj_in.end_date,
        reason=obj_in.reason,
        requester_id=requester_id,
        status=RequestStatus.PENDING,
        created_at=date.today()
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_vacation_request(
    db: AsyncSession, 
    id: int
) -> Optional[VacationRequest]:
    """
    Get a vacation request by its ID.
    
    Args:
        db: Database session
        id: ID of the request (can be int or UUID)
        
    Returns:
        Found vacation request or None
    """
    result = await db.execute(select(VacationRequest).where(VacationRequest.id == id))
    return result.scalars().first()


async def get_vacation_requests(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    requester_id: Optional[int] = None,
    status: Optional[RequestStatus] = None
) -> List[VacationRequest]:
    """
    Get a list of vacation requests with optional filters.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        requester_id: Filter by requester
        status: Filter by status
        
    Returns:
        List of vacation requests
    """
    query = select(VacationRequest)
    conditions = []
    
    if requester_id:
        conditions.append(VacationRequest.requester_id == requester_id)
    
    if status:
        conditions.append(VacationRequest.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_vacation_requests_for_review(
    db: AsyncSession,
    reviewer_id: int,
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None
) -> List[VacationRequest]:
    """
    Get vacation requests for review by a manager or admin.
    
    Args:
        db: Database session
        reviewer_id: ID of the reviewer (manager or admin)
        skip: Number of records to skip
        limit: Maximum number of records to return
        status: Filter by status
        
    Returns:
        List of requests for review
    """
    # First get the reviewer's role
    reviewer_result = await db.execute(select(User).where(User.id == reviewer_id))
    reviewer = reviewer_result.scalars().first()
    
    if not reviewer:
        return []
    
    # If it's an admin, can see all requests
    if reviewer.role == UserRole.ADMIN:
        query = select(VacationRequest)
    # If it's a manager, only see requests of their employees (for now all)
    elif reviewer.role == UserRole.MANAGER:
        query = select(VacationRequest)
    else:
        # It's neither admin nor manager, shouldn't see requests of others
        return []
    
    if status:
        query = query.where(VacationRequest.status == status)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_vacation_request(
    db: AsyncSession,
    db_obj: VacationRequest,
    obj_in: Union[VacationRequestUpdate, Dict[str, Any]],
    reviewer_id: Optional[int] = None
) -> VacationRequest:
    """
    Update a vacation request.
    
    Args:
        db: Database session
        db_obj: Existing request object
        obj_in: Update data
        reviewer_id: ID of the reviewer, if applicable
        
    Returns:
        Updated request
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    # If changing the status, record who did it and when
    if "status" in update_data and update_data["status"] != db_obj.status:
        db_obj.updated_at = date.today()
        if reviewer_id:
            db_obj.reviewer_id = reviewer_id
    
    for field in update_data:
        if hasattr(db_obj, field) and update_data[field] is not None:
            setattr(db_obj, field, update_data[field])
    
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_vacation_request(
    db: AsyncSession, 
    id: int
) -> Optional[VacationRequest]:
    """
    Delete a vacation request.
    
    Args:
        db: Database session
        id: ID of the request
        
    Returns:
        Deleted request or None
    """
    obj = await get_vacation_request(db, id)
    if not obj:
        return None
    
    await db.delete(obj)
    await db.commit()
    return obj 