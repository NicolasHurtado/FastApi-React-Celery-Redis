import uuid
import enum
from datetime import date
from sqlalchemy import Column, String, Boolean, Integer, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class VacationRequest(Base):
    __tablename__ = "vacation_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    created_at = Column(Date, nullable=False, default=date.today)
    updated_at = Column(Date, nullable=True)
    
    # Razón o comentario para la solicitud
    reason = Column(String, nullable=True)
    
    # Comentario del aprobador (manager/admin)
    reviewer_comment = Column(String, nullable=True)
    
    # Relaciones con usuarios
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relaciones bidireccionales con usuarios
    requester = relationship("User", foreign_keys=[requester_id], back_populates="vacation_requests")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviewed_requests")
    
    # Relación con notificaciones
    notifications = relationship("Notification", back_populates="related_request")

    def __repr__(self):
        return f"<VacationRequest(id={self.id}, requester={self.requester_id}, status={self.status})>"

    @property
    def days_requested(self):
        """Calcula el número de días solicitados."""
        if not self.start_date or not self.end_date:
            return 0
        delta = self.end_date - self.start_date
        return delta.days + 1  # Inclusive de ambos días 