import uuid
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, validator

from app.models.vacation_request import RequestStatus


# Propiedades compartidas
class VacationRequestBase(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = None

    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date debe ser posterior a start_date')
        return v


# Propiedades para recibir en la creación
class VacationRequestCreate(VacationRequestBase):
    pass


# Propiedades para recibir en la actualización
class VacationRequestUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[RequestStatus] = None
    reason: Optional[str] = None
    reviewer_comment: Optional[str] = None

    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if v and 'start_date' in values and values['start_date'] and v < values['start_date']:
            raise ValueError('end_date debe ser posterior a start_date')
        return v


# Propiedades compartidas en respuestas
class VacationRequestInDBBase(VacationRequestBase):
    id: uuid.UUID
    requester_id: uuid.UUID
    status: RequestStatus
    created_at: date
    updated_at: Optional[date] = None
    reviewer_id: Optional[uuid.UUID] = None
    reviewer_comment: Optional[str] = None

    class Config:
        from_attributes = True


# Propiedades para responder al cliente
class VacationRequest(VacationRequestInDBBase):
    days_requested: int


# Propiedades adicionales almacenadas en DB
class VacationRequestInDB(VacationRequestInDBBase):
    pass 