"""
Factories para la creación de modelos de prueba.
"""
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

import factory
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.notification import Notification, NotificationType
from app.models.vacation_request import VacationRequest, RequestStatus
from app.core.security import get_password_hash

# Inicializar faker con locale español
faker = Faker('es_ES')


class UserFactory(factory.Factory):
    """Factory para la creación de usuarios de prueba."""
    
    class Meta:
        model = User
    
    # No definimos id porque se generará automáticamente por la base de datos
    email = factory.LazyFunction(lambda: faker.email())
    password = factory.LazyFunction(lambda: get_password_hash("testpassword"))
    full_name = factory.LazyFunction(lambda: faker.name())
    role = UserRole.EMPLOYEE
    is_active = True
    is_superuser = False
    total_vacation_days = 30
    
    @classmethod
    async def create_async(cls, db: AsyncSession, **kwargs) -> User:
        """Crear y guardar un usuario en la base de datos de forma asíncrona."""
        obj = cls.build(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj
    
    @classmethod
    def build_superuser(cls, **kwargs) -> User:
        """Crea un superusuario."""
        return cls.build(
            role=UserRole.ADMIN,
            is_superuser=True,
            **kwargs
        )
    
    @classmethod
    def build_manager(cls, **kwargs) -> User:
        """Crea un usuario con rol de manager."""
        return cls.build(
            role=UserRole.MANAGER,
            **kwargs
        )


class NotificationFactory(factory.Factory):
    """Factory para la creación de notificaciones de prueba."""
    
    class Meta:
        model = Notification
    
    # No definimos id porque se generará automáticamente por la base de datos
    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute('user.id')
    type = NotificationType.OTHER
    message = factory.LazyFunction(lambda: faker.sentence())
    read = False
    created_at = factory.LazyFunction(datetime.utcnow)
    
    @classmethod
    async def create_async(cls, db: AsyncSession, **kwargs) -> Notification:
        """Crear y guardar una notificación en la base de datos de forma asíncrona."""
        # Si se proporciona explícitamente un user_id, eliminamos la dependencia del user
        if 'user_id' in kwargs and 'user' not in kwargs:
            kwargs.pop('user', None)  # Eliminar user si existe
        
        obj = cls.build(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj


class VacationRequestFactory(factory.Factory):
    """Factory para la creación de solicitudes de vacaciones de prueba."""
    
    class Meta:
        model = VacationRequest
    
    # No definimos id porque se generará automáticamente por la base de datos
    requester_id = factory.SelfAttribute('requester.id')
    requester = factory.SubFactory(UserFactory)
    start_date = factory.LazyFunction(lambda: date.today() + timedelta(days=10))
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=15))
    status = RequestStatus.PENDING
    reason = factory.LazyFunction(lambda: faker.paragraph())
    created_at = factory.LazyFunction(date.today)
    
    @classmethod
    async def create_async(cls, db: AsyncSession, **kwargs) -> VacationRequest:
        """Crear y guardar una solicitud de vacaciones en la base de datos de forma asíncrona."""
        obj = cls.build(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj
    
    @classmethod
    def build_approved(cls, reviewer=None, **kwargs) -> VacationRequest:
        """Crea una solicitud de vacaciones aprobada."""
        if reviewer is None:
            reviewer = UserFactory.build_manager()
        
        return cls.build(
            status=RequestStatus.APPROVED,
            reviewer=reviewer,
            reviewer_id=reviewer.id,
            **kwargs
        )
    
    @classmethod
    def build_rejected(cls, reviewer=None, **kwargs) -> VacationRequest:
        """Crea una solicitud de vacaciones rechazada."""
        if reviewer is None:
            reviewer = UserFactory.build_manager()
        
        return cls.build(
            status=RequestStatus.REJECTED,
            reviewer=reviewer,
            reviewer_id=reviewer.id,
            **kwargs
        ) 