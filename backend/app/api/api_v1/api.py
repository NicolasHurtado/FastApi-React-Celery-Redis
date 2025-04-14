from fastapi import APIRouter

from app.api.api_v1.endpoints import auth, users, vacation_requests, notifications, websockets

api_router = APIRouter()

# Incluir los diferentes routers específicos
api_router.include_router(auth.router, prefix="/auth", tags=["autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["usuarios"])
api_router.include_router(vacation_requests.router, prefix="/vacation-requests", tags=["solicitudes de vacaciones"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notificaciones"])
api_router.include_router(websockets.router, prefix="/ws", tags=["websockets"])

# Futuros routers para la lógica principal del proyecto
# api_router.include_router(calendar.router, prefix="/calendar", tags=["calendario"]) 