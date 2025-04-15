import uuid
from sqlalchemy import Column, String, Boolean, Integer, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
import enum

class UserRole(str, enum.Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    total_vacation_days = Column(Integer, default=20)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)

    # Relaciones con solicitudes de vacaciones
    vacation_requests = relationship("VacationRequest", foreign_keys="VacationRequest.requester_id", back_populates="requester")
    reviewed_requests = relationship("VacationRequest", foreign_keys="VacationRequest.reviewer_id", back_populates="reviewer")
    
    # Relación con notificaciones
    notifications = relationship("Notification", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>" 