import asyncio
import json
from typing import Dict, List, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from jose import jwt, JWTError
from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import ALGORITHM
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging import get_logger

router = APIRouter()

# Logger para los WebSockets
logger = get_logger("app.websockets")

# Almacena conexiones activas de WebSockets
active_connections: Dict[str, List[WebSocket]] = {}


class WebSocketManager:
    """
    Gestiona las conexiones WebSocket y la entrega de mensajes.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.redis_clients: Dict[str, Redis] = {}
        self.redis_tasks: Dict[str, asyncio.Task] = {}
        self.logger = get_logger("app.websockets.manager")
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Establece la conexión WebSocket y guarda la referencia.
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        self.logger.info(f"Nueva conexión WebSocket para usuario {user_id}")
        
        # Iniciar tarea de suscripción a Redis si no existe para este usuario
        if user_id not in self.redis_tasks:
            self.logger.debug(f"Iniciando suscripción Redis para usuario {user_id}")
            self.redis_clients[user_id] = Redis.from_url(settings.REDIS_URL)
            self.redis_tasks[user_id] = asyncio.create_task(
                self.subscribe_to_redis(user_id)
            )
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Desconecta el WebSocket y elimina la referencia.
        """
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                self.logger.info(f"Conexión WebSocket cerrada para usuario {user_id}")
            
            # Si no hay más conexiones para este usuario, cancelar la tarea de Redis
            if not self.active_connections[user_id]:
                self.logger.debug(f"No quedan conexiones para usuario {user_id}, limpiando recursos")
                if user_id in self.redis_tasks:
                    self.redis_tasks[user_id].cancel()
                    del self.redis_tasks[user_id]
                
                if user_id in self.redis_clients:
                    asyncio.create_task(self.redis_clients[user_id].close())
                    del self.redis_clients[user_id]
                
                del self.active_connections[user_id]
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Envía un mensaje a todas las conexiones de un usuario específico.
        """
        if user_id in self.active_connections:
            disconnected_websockets = []
            
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                    self.logger.debug(f"Mensaje enviado a usuario {user_id}")
                except Exception as e:
                    self.logger.warning(f"Error al enviar mensaje a usuario {user_id}: {str(e)}")
                    disconnected_websockets.append(websocket)
            
            # Limpiar conexiones cerradas
            for websocket in disconnected_websockets:
                self.disconnect(websocket, user_id)
    
    async def subscribe_to_redis(self, user_id: str):
        """
        Suscribe a un canal de Redis y reenvía mensajes a los WebSockets.
        """
        try:
            self.logger.info(f"Iniciando suscripción a canal Redis para usuario {user_id}")
            redis_client = self.redis_clients[user_id]
            pubsub = redis_client.pubsub()
            
            channel = f"user:{user_id}:notifications"
            await pubsub.subscribe(channel)
            
            # Esperar mensajes indefinidamente
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        self.logger.debug(
                            f"Mensaje recibido de Redis para usuario {user_id}",
                            extra={"data": {"type": payload.get("type")}}
                        )
                        await self.broadcast_to_user(user_id, payload)
                    except Exception as e:
                        self.logger.error(
                            f"Error al procesar mensaje: {str(e)}",
                            exc_info=True,
                            extra={"data": {"user_id": user_id}}
                        )
                
                # Si el usuario ya no tiene conexiones activas, salir
                if user_id not in self.active_connections:
                    self.logger.info(f"Terminando suscripción Redis para usuario {user_id} (no hay conexiones)")
                    break
        except asyncio.CancelledError:
            # Tarea cancelada, limpiar recursos
            self.logger.info(f"Suscripción Redis cancelada para usuario {user_id}")
            if user_id in self.redis_clients:
                pubsub = self.redis_clients[user_id].pubsub()
                await pubsub.unsubscribe()
        except Exception as e:
            self.logger.error(
                f"Error en suscripción Redis: {str(e)}",
                exc_info=True,
                extra={"data": {"user_id": user_id}}
            )


# Singleton del gestor de WebSockets
manager = WebSocketManager()


async def get_user_from_token(token: str) -> User:
    """
    Valida un token JWT y obtiene el usuario.
    
    Args:
        token: Token JWT
        
    Returns:
        Usuario autenticado
        
    Raises:
        HTTPException: Si el token es inválido
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.db.session import get_db
        from app.crud.user import get_user
        
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id = payload.get("sub")
        
        if user_id is None:
            logger.warning("Token JWT sin subject (sub)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        # Obtener la sesión de DB
        db = await get_db().__anext__()
        
        # Obtener el usuario
        user = await get_user(db, user_id)
        
        if user is None:
            logger.warning(f"Usuario no encontrado para token JWT: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        logger.debug(f"Usuario autenticado: {user.email} (ID: {user.id})")
        return user
    
    except JWTError as e:
        logger.error(f"Error de validación JWT: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar el token"
        )


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket
):
    """
    Endpoint WebSocket para recibir notificaciones en tiempo real.
    
    El cliente debe enviar un primer mensaje con el token JWT para autenticar.
    """
    client_ip = websocket.client.host
    logger.info(f"Nueva conexión WebSocket desde {client_ip}")
    
    await websocket.accept()
    user_id = None
    
    try:
        # Esperar mensaje de autenticación
        logger.debug("Esperando mensaje de autenticación")
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        # Verificar token
        token = auth_data.get("token")
        if not token:
            logger.warning(f"Intento de conexión sin token desde {client_ip}")
            await websocket.send_text(json.dumps({"error": "Token no proporcionado"}))
            await websocket.close()
            return
        
        # Autenticar usuario
        try:
            user = await get_user_from_token(token)
            user_id = str(user.id)
            
            logger.info(f"Usuario {user.email} (ID: {user_id}) autenticado para WebSocket")
            
            # Enviar confirmación de conexión exitosa
            await websocket.send_text(json.dumps({
                "status": "connected",
                "user_id": user_id
            }))
            
            # Conectar al gestor de WebSockets
            await manager.connect(websocket, user_id)
            
            # Mantener la conexión abierta
            while True:
                # Esperar mensajes del cliente para mantener la conexión activa
                await websocket.receive_text()
                
        except HTTPException as e:
            logger.warning(f"Error de autenticación WebSocket: {e.detail}")
            await websocket.send_text(json.dumps({"error": e.detail}))
            await websocket.close()
            return
        
    except WebSocketDisconnect:
        # El cliente se desconectó
        logger.info(f"Cliente WebSocket desconectado: {client_ip} (user_id: {user_id})")
        if user_id:
            manager.disconnect(websocket, user_id)
    except Exception as e:
        # Error inesperado
        logger.error(
            f"Error inesperado en WebSocket: {str(e)}",
            exc_info=True,
            extra={"data": {"client_ip": client_ip, "user_id": user_id}}
        )
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
            await websocket.close()
        except:
            pass 