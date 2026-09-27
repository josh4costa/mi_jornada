"""app/api/v1/auth.py  —  CORREGIDO

Problemas que resuelve:
 1. El limiter no estaba en app.state -> al pasar el limite respondia 500 (ahora importa
    el limiter compartido de app.core.limiter y main.py lo registra).
 2. /refresh NO validaba la firma ni la expiracion del JWT: bastaba conocer el hash
    guardado. Ahora se valida firma + tipo + expiracion + usuario activo.
 3. Sin rotacion de refresh tokens: un token robado servia 30 dias. Ahora rota en cada
    uso y detecta reuso (si llega un token ya revocado se revoca toda la familia).
 4. Comparacion datetime naive vs aware -> TypeError con SQLite/columnas sin tz.
 5. Enumeracion de usuarios: se respondia distinto si el usuario no existia.
 6. El contador de intentos fallidos no se reiniciaba al expirar el bloqueo.
 7. Logout dejaba viva la sesion en otros dispositivos: se agrega /logout-all.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.core.timezone import now_utc
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenResponse,
    TokenResponse,
)
from app.services.audit import AuditAction, audit_event

router = APIRouter()

# Hash "quemado" para igualar el tiempo de respuesta cuando el usuario no existe.
_DUMMY_HASH = get_password_hash("mi-jornada-dummy-password")


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite (y columnas sin tz) devuelven datetimes naive: los normalizamos a UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _user_info(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


async def _issue_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    token = create_refresh_token(subject=user_id)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return token


@router.post("/login", response_model=TokenResponse)
@limiter.limit(f"{settings.LOGIN_MAX_ATTEMPTS}/{settings.LOGIN_LOCKOUT_MINUTES}minutes")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(
        (User.username == body.username_or_email) | (User.email == body.username_or_email)
    )
    user = (await db.execute(stmt)).scalars().first()

    generic_401 = HTTPException(status_code=401, detail="Usuario o contrasena incorrectos")

    if not user:
        verify_password(body.password, _DUMMY_HASH)  # tiempo constante
        raise generic_401

    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > now_utc():
        raise HTTPException(
            status_code=423,
            detail="Cuenta bloqueada temporalmente por multiples intentos fallidos",
        )

    if not verify_password(body.password, user.password_hash):
        # Si el bloqueo ya vencio, el contador arranca de cero.
        if locked_until and locked_until <= now_utc():
            user.failed_login_attempts = 0
            user.locked_until = None
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now_utc() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        await db.commit()
        raise generic_401

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inactivo. Contacta al administrador.")

    user.failed_login_attempts = 0
    user.locked_until = None

    access_token = create_access_token(subject=user.id)
    refresh_token = await _issue_refresh_token(db, user.id)
    await db.commit()

    await audit_event(
        db,
        AuditAction.LOGIN,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _user_info(user),
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    invalid = HTTPException(status_code=401, detail="Token de refresco invalido o expirado")

    payload = decode_token(body.refresh_token, REFRESH_TOKEN_TYPE)
    if payload is None:
        raise invalid

    token_hash = hash_token(body.refresh_token)
    db_token = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalars().first()

    if db_token is None:
        raise invalid

    # Deteccion de reuso: el token ya se habia rotado -> se revocan todas las sesiones.
    if db_token.is_revoked:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == db_token.user_id)
            .values(is_revoked=True)
        )
        await db.commit()
        raise invalid

    if _aware(db_token.expires_at) < now_utc():
        raise invalid

    user = await db.get(User, db_token.user_id)
    if user is None or not user.is_active:
        raise invalid

    # Rotacion
    db_token.is_revoked = True
    new_refresh = await _issue_refresh_token(db, user.id)
    await db.commit()

    return {
        "access_token": create_access_token(subject=user.id),
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(body.refresh_token)
    db_token = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalars().first()
    if db_token and not db_token.is_revoked:
        db_token.is_revoked = True
        await db.commit()
    return {"message": "Sesion cerrada correctamente"}


@router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.is_revoked == False)  # noqa: E712
        .values(is_revoked=True)
    )
    await db.commit()
    return {"message": "Todas las sesiones fueron cerradas"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    data = _user_info(current_user)
    data["is_active"] = current_user.is_active
    if current_user.technician:
        data["technician_id"] = str(current_user.technician.id)
        data["employee_number"] = current_user.technician.employee_number
        data["phone"] = current_user.technician.phone
    return data
