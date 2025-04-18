# Importar Base primero
from app.db.base import Base

# Luego importar todos los modelos que usan Base
# No elimines estas importaciones, son necesarias para que Alembic encuentre los modelos
from app.models.user import User
from app.models.vacation_request import VacationRequest
from app.models.notification import Notification 