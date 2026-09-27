import secrets
from datetime import timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func
from app.api.deps import get_current_user
from app.api.v1.auth import _aware
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import hash_token, verify_password
from app.core.timezone import now_utc
from app.db.session import get_db
from app.models.user import User
from app.models.account_setup import PasswordReset
from app.services.passwords import replace_password, send_recovery_email

router = APIRouter()


class NewPassword(BaseModel):
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator('new_password')
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('La contraseña supera el límite de 72 bytes; usa menos caracteres.')
        if value.isspace():
            raise ValueError('La contraseña no puede contener solo espacios.')
        return value


class ChangePassword(NewPassword):
    current_password: str = Field(max_length=200)


class ResetPassword(NewPassword):
    token: str = Field(min_length=32, max_length=128)


class ForgotPassword(BaseModel):
    email: EmailStr


@router.post('/change-password')
@limiter.limit('5/15minutes')
async def change_password(request: Request, response: Response, body: ChangePassword, actor=Depends(get_current_user), db=Depends(get_db)):
    version = actor.credential_version
    user = await db.scalar(select(User).where(User.id == actor.id).with_for_update().execution_options(populate_existing=True))
    if user.credential_version != version:
        raise HTTPException(401, 'La sesión cambió. Inicia sesión nuevamente.')
    if user.locked_until and _aware(user.locked_until) > now_utc():
        raise HTTPException(423, 'Cuenta bloqueada temporalmente. Intenta más tarde.')
    if not verify_password(body.current_password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now_utc() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        await db.commit()
        raise HTTPException(400, 'La contraseña actual no es correcta.')
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(422, 'Elige una contraseña distinta de la actual o temporal.')
    await replace_password(db, user, body.new_password)
    await db.commit()
    return {'message': 'Contraseña guardada. Inicia sesión con tu nueva contraseña.'}


@router.post('/forgot-password')
@limiter.limit('3/15minutes')
async def forgot_password(request: Request, response: Response, body: ForgotPassword, background: BackgroundTasks, db=Depends(get_db)):
    result = {'message': 'Si el correo corresponde a una cuenta activa, recibirás un enlace. Revisa también correo no deseado. Si no llega, contacta al administrador.'}
    users = (await db.scalars(select(User).where(func.lower(User.email) == str(body.email).lower(), User.is_active.is_(True)).with_for_update())).all()
    # Legacy records differing only in case must be corrected by an administrator.
    if len(users) != 1:
        return result
    user = users[0]
    last = await db.scalar(select(PasswordReset.created_at).where(PasswordReset.user_id == user.id).order_by(PasswordReset.created_at.desc()).limit(1))
    if last and _aware(last) > now_utc() - timedelta(minutes=2):
        return result
    token = secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user.id, token_hash=hash_token(token), credential_version=user.credential_version, expires_at=now_utc()+timedelta(minutes=30)))
    await db.commit()
    background.add_task(send_recovery_email, user.email, token)
    return result


@router.post('/reset-password')
@limiter.limit('10/15minutes')
async def reset_password(request: Request, response: Response, body: ResetPassword, db=Depends(get_db)):
    invalid = HTTPException(400, 'El enlace no es válido o ya venció. Solicita uno nuevo.')
    reset = await db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(body.token)))
    if not reset:
        raise invalid
    user = await db.scalar(select(User).where(User.id == reset.user_id).with_for_update().execution_options(populate_existing=True))
    await db.refresh(reset)
    if not user or not user.is_active or reset.used_at or _aware(reset.expires_at) <= now_utc() or reset.credential_version != user.credential_version:
        raise invalid
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(422, 'Elige una contraseña distinta de la anterior.')
    reset.used_at = now_utc()
    await replace_password(db, user, body.new_password)
    await db.commit()
    return {'message': 'Contraseña guardada. Inicia sesión con tu nueva contraseña.'}
