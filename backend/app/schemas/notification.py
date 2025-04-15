import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from app.models.notification import NotificationType


# Propiedades compartidas
class NotificationBase(BaseModel):
    type: NotificationType
    message: str
    related_request_id: Optional[int] = None


# Propiedades para recibir en la creación
class NotificationCreate(NotificationBase):
    user_id: int
    read: Optional[bool] = None


# Propiedades para recibir en la actualización
class NotificationUpdate(BaseModel):
    read: Optional[bool] = None


# Propiedades compartidas en respuestas
class NotificationInDBBase(NotificationBase):
    id: int
    user_id: int
    created_at: datetime
    read: bool

    class Config:
        from_attributes = True


# Propiedades para responder al cliente
class Notification(NotificationInDBBase):
    pass


# Propiedades adicionales almacenadas en DB
class NotificationInDB(NotificationInDBBase):
    pass


# Esquema para envío de notificaciones en tiempo real
class NotificationSend(BaseModel):
    id: int
    type: NotificationType
    message: str
    created_at: datetime 