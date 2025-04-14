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
    requester_id: uuid.UUID
) -> VacationRequest:
    """
    Crea una nueva solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        obj_in: Datos de la solicitud
        requester_id: ID del usuario que realiza la solicitud
        
    Returns:
        Solicitud de vacaciones creada
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
    id: uuid.UUID
) -> Optional[VacationRequest]:
    """
    Obtiene una solicitud de vacaciones por su ID.
    
    Args:
        db: Sesión de base de datos
        id: ID de la solicitud
        
    Returns:
        Solicitud de vacaciones encontrada o None
    """
    result = await db.execute(select(VacationRequest).where(VacationRequest.id == id))
    return result.scalars().first()


async def get_vacation_requests(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    requester_id: Optional[uuid.UUID] = None,
    status: Optional[RequestStatus] = None
) -> List[VacationRequest]:
    """
    Obtiene una lista de solicitudes de vacaciones con filtros opcionales.
    
    Args:
        db: Sesión de base de datos
        skip: Número de registros a saltar
        limit: Número máximo de registros a devolver
        requester_id: Filtrar por solicitante
        status: Filtrar por estado
        
    Returns:
        Lista de solicitudes de vacaciones
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
    reviewer_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None
) -> List[VacationRequest]:
    """
    Obtiene solicitudes de vacaciones para revisión por un manager o admin.
    
    Args:
        db: Sesión de base de datos
        reviewer_id: ID del revisor (manager o admin)
        skip: Número de registros a saltar
        limit: Número máximo de registros a devolver
        status: Filtrar por estado
        
    Returns:
        Lista de solicitudes para revisión
    """
    # Primero obtenemos el rol del revisor
    reviewer_result = await db.execute(select(User).where(User.id == reviewer_id))
    reviewer = reviewer_result.scalars().first()
    
    if not reviewer:
        return []
    
    # Si es admin, puede ver todas las solicitudes
    if reviewer.role == UserRole.ADMIN:
        query = select(VacationRequest)
    # Si es manager, solo ve las solicitudes de sus empleados (por ahora todas)
    elif reviewer.role == UserRole.MANAGER:
        query = select(VacationRequest)
    else:
        # No es ni admin ni manager, no debería ver solicitudes de otros
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
    reviewer_id: Optional[uuid.UUID] = None
) -> VacationRequest:
    """
    Actualiza una solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        db_obj: Objeto de solicitud existente
        obj_in: Datos de actualización
        reviewer_id: ID del revisor, si aplica
        
    Returns:
        Solicitud actualizada
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    # Si se está cambiando el estado, registramos quién lo hizo y cuándo
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
    id: uuid.UUID
) -> Optional[VacationRequest]:
    """
    Elimina una solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        id: ID de la solicitud
        
    Returns:
        Solicitud eliminada o None
    """
    obj = await get_vacation_request(db, id)
    if not obj:
        return None
    
    await db.delete(obj)
    await db.commit()
    return obj 