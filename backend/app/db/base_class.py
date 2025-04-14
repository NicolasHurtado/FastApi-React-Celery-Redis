from app.db.base import Base

# Importar todos los modelos para que Alembic los detecte
from app.models.user import User
from app.models.vacation_request import VacationRequest
from app.models.notification import Notification 