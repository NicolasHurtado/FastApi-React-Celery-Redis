import uuid
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """
    Respuesta del endpoint de login con el token de acceso.
    """
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """
    Contenido (payload) del token JWT.
    
    El campo `sub` (subject) contiene el ID del usuario.
    """
    sub: Optional[str] = None
    exp: Optional[int] = None  # Unix timestamp de expiración 