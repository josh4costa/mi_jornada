"""app/api/deps.py  —  CORREGIDO

 - Valida el tipo de token: antes un refresh token (30 dias) servia como bearer.
 - UUID invalido devolvia 500 (ValueError sin capturar); ahora 401.
 - Mensajes de error sin filtrar si el usuario existe o no.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales invalidas",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    if payload is None:
        raise CREDENTIALS_EXCEPTION

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError, KeyError):
        raise CREDENTIALS_EXCEPTION

    stmt = select(User).options(selectinload(User.technician)).where(User.id == user_id)
    user = (await db.execute(stmt)).scalars().first()

    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


async def get_current_technician_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.TECHNICIAN:
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere rol de TECNICO")
    if not current_user.technician or not current_user.technician.is_active:
        raise HTTPException(status_code=403, detail="Acceso denegado: perfil de tecnico inactivo o no encontrado")
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere rol de ADMINISTRADOR")
    return current_user
