"""app/api/v1/admin/users.py  —  CORREGIDO

 1. BUG: /users/{id}/disable siempre ponia is_active=False, y el front usa ese mismo
    endpoint para reactivar -> era imposible reactivar a alguien desde la UI.
    Ahora acepta {"is_active": true|false} en el body (y sin body = desactivar).
 2. BUG: al editar un usuario el front manda "password"; el setattr ciego lo asignaba
    a un atributo inexistente y la contrasena NUNCA cambiaba, sin error visible.
    Ahora se hashea correctamente y se revocan las sesiones abiertas.
 3. setattr() ciego permitia escribir password_hash, failed_login_attempts, etc.
    -> lista blanca de campos.
 4. Un admin podia desactivarse a si mismo o desactivar al ultimo admin y dejar el
    sistema sin acceso. Ahora se bloquea.
 5. UUID invalido devolvia 500; ahora 422. Se agrega paginacion y busqueda.
"""
import math
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.models.technician import Technician

from app.api.deps import get_current_admin_user
from app.core.security import get_password_hash
from app.services.passwords import replace_password
from app.models.account_setup import PasswordReset
from app.core.timezone import now_utc
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserStatusUpdate
from app.services.users import sync_technician_profile
from app.services.audit import AuditAction, audit_event

router = APIRouter()

EDITABLE_FIELDS = {"full_name", "username", "email", "role", "is_active", "password"}


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="El id de usuario no es valido")


async def _count_active_admins(db: AsyncSession, excluding: Optional[uuid.UUID] = None) -> int:
    stmt = select(func.count(User.id)).where(
        User.role == UserRole.ADMIN, User.is_active == True  # noqa: E712
    )
    if excluding:
        stmt = stmt.where(User.id != excluding)
    return await db.scalar(stmt) or 0



async def _commit(db):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="El usuario, correo o número de empleado ya está en uso")


async def _update_profile(db, profile, values):
    values = {key: value.strip() or None if isinstance(value, str) else value for key, value in values.items()}
    if profile is None:
        if any(values.values()):
            raise HTTPException(status_code=422, detail="Los datos de empleado requieren un perfil técnico")
        return
    number = values.get("employee_number")
    if number:
        duplicate = await db.scalar(select(Technician.id).where(Technician.employee_number == number, Technician.user_id != profile.user_id))
        if duplicate:
            raise HTTPException(status_code=409, detail="El número de empleado ya está en uso")
    phone = values.get("phone", profile.phone)
    enabled = values.get("reminders_enabled", profile.reminders_enabled)
    if enabled:
        import re
        if not phone or not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
            raise HTTPException(status_code=422, detail="Para WhatsApp indica el teléfono con código de país, por ejemplo +528112345678")
        duplicate_phone = await db.scalar(select(Technician.id).where(Technician.phone == phone, Technician.reminders_enabled.is_(True), Technician.id != profile.id))
        if duplicate_phone:
            raise HTTPException(status_code=409, detail="Ese WhatsApp ya recibe recordatorios de otro técnico")
    for key, value in values.items():
        setattr(profile, key, value)


@router.get("")
async def list_users(
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(User.full_name.ilike(like), User.username.ilike(like), User.email.ilike(like))
        )

    total = await db.scalar(select(func.count(User.id)).where(*filters)) or 0
    users = (
        await db.execute(
            select(User).options(selectinload(User.technician))
            .where(*filters)
            .order_by(User.full_name, User.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return {
        "items": [UserResponse.model_validate(u).model_dump() for u in users],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 0,
    }


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exists = (
        await db.execute(
            select(User).where((User.username == body.username) | (User.email == body.email))
        )
    ).scalars().first()
    if exists:
        raise HTTPException(status_code=409, detail="El usuario o el email ya existen")

    user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        password_hash=get_password_hash(body.password),
    )
    db.add(user)
    profile = await sync_technician_profile(db, user)
    await _update_profile(db, profile, {"phone": body.phone, "employee_number": body.employee_number, "reminders_enabled": body.reminders_enabled})
    await _commit(db)
    await db.refresh(user, ["technician"])

    await audit_event(
        db, AuditAction.USER_CREATED, user_id=current_user.id, entity_type="users", entity_id=user.id
    )
    return user


@router.get("/{id}", response_model=UserResponse)
async def get_user(
    id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == _parse_uuid(id)).options(selectinload(User.technician)).with_for_update().execution_options(populate_existing=True))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.patch("/{id}", response_model=UserResponse)
async def update_user(
    id: str,
    body: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == _parse_uuid(id)).options(selectinload(User.technician)).with_for_update().execution_options(populate_existing=True))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    data = body.model_dump(exclude_unset=True)
    profile_data = {key: data.pop(key) for key in ("phone", "employee_number", "reminders_enabled") if key in data}
    if any(value is None for value in data.values()):
        raise HTTPException(status_code=422, detail="Los campos de usuario no pueden ser nulos")
    if user.id == current_user.id and (data.get("is_active") is False or data.get("role", user.role) != user.role):
        raise HTTPException(status_code=409, detail="No puedes desactivar tu cuenta ni cambiar tu propio rol")
    unknown = set(data) - EDITABLE_FIELDS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Campos no editables: {', '.join(sorted(unknown))}")

    password = data.pop("password", None)

    # No permitir dejar el sistema sin administradores activos.
    losing_admin = (data.get("role") and data["role"] != UserRole.ADMIN) or data.get("is_active") is False
    if user.role == UserRole.ADMIN and losing_admin and await _count_active_admins(db, excluding=user.id) == 0:
        raise HTTPException(status_code=409, detail="Debe existir al menos un administrador activo")

    if "username" in data or "email" in data:
        dup = (
            await db.execute(
                select(User).where(
                    User.id != user.id,
                    or_(
                        User.username == data.get("username", user.username),
                        User.email == data.get("email", user.email),
                    ),
                )
            )
        ).scalars().first()
        if dup:
            raise HTTPException(status_code=409, detail="El usuario o el email ya existen")

    if 'email' in data and data['email'] != user.email:
        await db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=now_utc()))
    for key, value in data.items():
        setattr(user, key, value)

    profile = await sync_technician_profile(db, user)
    await _update_profile(db, profile, profile_data)
    if data.get("is_active") is False or "role" in data:
        await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True))

    if password:
        if len(password) < 8:
            raise HTTPException(status_code=422, detail="La contrasena debe tener al menos 8 caracteres")
        await replace_password(db, user, password, temporary=True, actor_id=current_user.id)

    await _commit(db)
    await db.refresh(user, ["technician"])
    return user


@router.patch("/{id}/disable", response_model=UserResponse)
async def set_user_status(
    id: str,
    payload: UserStatusUpdate = Body(default=UserStatusUpdate()),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva. Sin body (o sin is_active) equivale a desactivar."""
    user = await db.scalar(select(User).where(User.id == _parse_uuid(id)).options(selectinload(User.technician)).with_for_update().execution_options(populate_existing=True))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    is_active = payload.is_active

    if not is_active:
        if user.id == current_user.id:
            raise HTTPException(status_code=409, detail="No puedes desactivar tu propia cuenta")
        if user.role == UserRole.ADMIN and await _count_active_admins(db, excluding=user.id) == 0:
            raise HTTPException(status_code=409, detail="Debe existir al menos un administrador activo")

    user.is_active = is_active
    await sync_technician_profile(db, user)
    if not is_active:
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True)
        )
    else:
        user.failed_login_attempts = 0
        user.locked_until = None

    await _commit(db)
    await db.refresh(user, ["technician"])

    await audit_event(
        db,
        AuditAction.USER_DISABLED if not is_active else AuditAction.USER_CREATED,
        user_id=current_user.id,
        entity_type="users",
        entity_id=user.id,
        metadata_json={"is_active": is_active},
    )
    return user
