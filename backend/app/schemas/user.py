import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole # Importar el Enum

# Propiedades compartidas
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.EMPLOYEE
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    total_vacation_days: Optional[int] = None

# Propiedades para recibir en la creación
class UserCreate(UserBase):
    email: EmailStr
    password: str
    role: UserRole = UserRole.EMPLOYEE # Rol por defecto al crear
    is_superuser: bool = False

# Propiedades para recibir en la actualización
class UserUpdate(UserBase):
    password: Optional[str] = None # Permitir cambiar la contraseña

# Propiedades compartidas almacenadas en DB
class UserInDBBase(UserBase):
    id: int
    # Nota: No incluimos password aquí por seguridad

    class Config:
        from_attributes = True  # Actualizado de orm_mode para Pydantic v2

# Propiedades adicionales para devolver al cliente
class User(UserInDBBase):
    pass

# Propiedades adicionales almacenadas en DB
class UserInDB(UserInDBBase):
    password: str 