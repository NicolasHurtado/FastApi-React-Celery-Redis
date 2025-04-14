from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user import authenticate_user, get_user_by_email
from app.db.session import get_db
from app.schemas.token import Token

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    Iniciar sesión para obtener un token de acceso.
    
    Este endpoint es utilizado por la interfaz OAuth2PasswordBearer,
    que espera un formulario con los campos username (en este caso, email) y password.
    
    Args:
        db: Sesión de la base de datos
        form_data: Formulario con username (email) y password
        
    Returns:
        Token de acceso JWT
        
    Raises:
        HTTPException: Si las credenciales son incorrectas
    """
    user = await authenticate_user(
        db, email=form_data.username, password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Crear token con ID de usuario
    return {
        "access_token": create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/test-token", response_model=Token)
async def test_token(token: Token) -> Any:
    """
    Endpoint de prueba para verificar la estructura del token.
    """
    return token 