import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


@router.post("/", response_model=VacationRequest)
async def create_vacation_request(
    *,
    db: AsyncSession = Depends(get_db),
    request_in: VacationRequestCreate,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Crear una nueva solicitud de vacaciones.
    
    Args:
        db: Sesión de base de datos
        request_in: Datos de la solicitud
        current_user: Usuario autenticado
        
    Returns:
        La solicitud creada
    """
    # Calcular días solicitados
    delta = (request_in.end_date - request_in.start_date).days + 1
    
    # Verificar que el usuario tiene suficientes días disponibles
    if delta > current_user.total_vacation_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No tienes suficientes días disponibles. Solicitados: {delta}, Disponibles: {current_user.total_vacation_days}"
        )
    
    # Crear la solicitud
    vacation_request = await crud.create_vacation_request(
        db=db, obj_in=request_in, requester_id=current_user.id
    )
    
    # Obtener los IDs de todos los managers y admins para notificarles
    query = select(User).where(
        and_(
            User.role.in_([UserRole.MANAGER, UserRole.ADMIN]),
            User.is_active == True
        )
    )
    result = await db.execute(query)
    managers = result.scalars().all()
    manager_ids = [manager.id for manager in managers]
    
    # Notificar a los managers sobre la nueva solicitud
    if manager_ids:
        await notification_service.notify_new_request(db, vacation_request, manager_ids)
    
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
    Obtener mis solicitudes de vacaciones.
    
    Args:
        db: Sesión de base de datos
        skip: Número de registros a saltar
        limit: Número máximo de registros a devolver
        status: Filtrar por estado
        current_user: Usuario autenticado
        
    Returns:
        Lista de solicitudes de vacaciones del usuario
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
    Obtener solicitudes para revisar (solo managers y admins).
    
    Args:
        db: Sesión de base de datos
        skip: Número de registros a saltar
        limit: Número máximo de registros a devolver
        status: Filtrar por estado
        current_user: Usuario autenticado (manager o admin)
        
    Returns:
        Lista de solicitudes para revisar
    """
    requests = await crud.get_vacation_requests_for_review(
        db=db, reviewer_id=current_user.id, skip=skip, limit=limit, status=status
    )
    return requests


@router.get("/{request_id}", response_model=VacationRequest)
async def read_vacation_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Obtener una solicitud de vacaciones específica.
    
    Los usuarios normales solo pueden ver sus propias solicitudes.
    Managers y admins pueden ver todas las solicitudes.
    
    Args:
        request_id: ID de la solicitud
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Solicitud de vacaciones
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )
    
    # Verificar permisos
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN] and request.requester_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a esta solicitud"
        )
    
    return request


@router.put("/{request_id}", response_model=VacationRequest)
async def update_vacation_request(
    *,
    request_id: uuid.UUID,
    request_in: VacationRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Actualizar una solicitud de vacaciones.
    
    Los usuarios normales solo pueden actualizar sus propias solicitudes pendientes.
    Managers y admins pueden actualizar cualquier solicitud.
    
    Args:
        request_id: ID de la solicitud
        request_in: Datos de actualización
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Solicitud actualizada
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )
    
    # Verificar permisos
    is_manager_or_admin = current_user.role in [UserRole.MANAGER, UserRole.ADMIN]
    is_owner = request.requester_id == current_user.id
    
    # Si no es dueño ni manager/admin, no puede actualizar
    if not is_owner and not is_manager_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta solicitud"
        )
    
    # Si es dueño pero no es manager/admin, solo puede actualizar solicitudes pendientes
    if is_owner and not is_manager_or_admin and request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes modificar solicitudes en estado pendiente"
        )
    
    # Si es dueño, no puede cambiar el estado (solo managers/admins pueden)
    if is_owner and not is_manager_or_admin and request_in.status is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes cambiar el estado de la solicitud"
        )
    
    # Si hay cambio en las fechas, verificar días disponibles
    if (request_in.start_date is not None or request_in.end_date is not None) and is_owner:
        start_date = request_in.start_date or request.start_date
        end_date = request_in.end_date or request.end_date
        
        delta = (end_date - start_date).days + 1
        
        if delta > current_user.total_vacation_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No tienes suficientes días disponibles. Solicitados: {delta}, Disponibles: {current_user.total_vacation_days}"
            )
    
    # Guardar el estado anterior para las notificaciones
    old_status = request.status
    
    # Actualizar la solicitud
    request = await crud.update_vacation_request(
        db=db, 
        db_obj=request, 
        obj_in=request_in,
        reviewer_id=current_user.id if is_manager_or_admin else None
    )
    
    # Generar notificaciones si cambió el estado
    if old_status != request.status:
        await notification_service.notify_status_change(db, request, old_status)
    
    return request


@router.delete("/{request_id}", response_model=VacationRequest)
async def delete_vacation_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Eliminar una solicitud de vacaciones.
    
    Los usuarios normales solo pueden eliminar sus propias solicitudes pendientes.
    Admins pueden eliminar cualquier solicitud.
    
    Args:
        request_id: ID de la solicitud
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Solicitud eliminada
    """
    request = await crud.get_vacation_request(db=db, id=request_id)
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )
    
    # Verificar permisos
    is_admin = current_user.role == UserRole.ADMIN
    is_owner = request.requester_id == current_user.id
    
    # Si no es dueño ni admin, no puede eliminar
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta solicitud"
        )
    
    # Si es dueño pero no admin, solo puede eliminar solicitudes pendientes
    if is_owner and not is_admin and request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes eliminar solicitudes en estado pendiente"
        )
    
    # Eliminar la solicitud
    request = await crud.delete_vacation_request(db=db, id=request_id)
    
    return request 