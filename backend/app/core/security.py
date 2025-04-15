from datetime import datetime, timedelta
from typing import Any, Optional, Union

from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext

from app.core.config import settings

# Contexto para el hashing de contraseñas (usando bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Genera un token JWT.

    Args:
        subject: El identificador del usuario (e.g., email o ID).
        expires_delta: Tiempo de vida del token.

    Returns:
        El token JWT codificado.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_subject_from_token(token: str) -> str:
    """Extrae el subject (sub) de un token JWT.
    
    Args:
        token: Token JWT codificado.
        
    Returns:
        El subject del token, generalmente el ID del usuario, como string.
        
    Raises:
        JWTError: Si el token es inválido o ha expirado.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    subject = payload.get("sub")
    if subject is None:
        raise JWTError("Token no contiene un subject válido")
    
    # Asegurarnos de que siempre devolvemos un string
    return str(subject)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con su hash.

    Args:
        plain_password: Contraseña en texto plano.
        hashed_password: Hash de la contraseña.

    Returns:
        True si la contraseña coincide con el hash, False en caso contrario.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera un hash para una contraseña.

    Args:
        password: Contraseña en texto plano.

    Returns:
        Hash de la contraseña.
    """
    return pwd_context.hash(password) 