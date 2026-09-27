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

from app.api.deps import get_current_admin_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate
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


@router.get("")
async def list_users(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(User.full_name.ilike(like), User.username.ilike(like), User.email.ilike(like))
        )

    total = await db.scalar(select(func.count(User.id)).where(*filters)) or 0
    users = (
        await db.execute(
            select(User)
            .where(*filters)
            .order_by(User.full_name)
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
        password_hash=get_password_hash(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

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
    user = await db.get(User, _parse_uuid(id))
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
    user = await db.get(User, _parse_uuid(id))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    data = body.model_dump(exclude_unset=True)
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

    for key, value in data.items():
        setattr(user, key, value)

    if password:
        if len(password) < 8:
            raise HTTPException(status_code=422, detail="La contrasena debe tener al menos 8 caracteres")
        user.password_hash = get_password_hash(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        # Al cambiar la contrasena se cierran las sesiones abiertas.
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True)
        )

    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{id}/disable", response_model=UserResponse)
async def set_user_status(
    id: str,
    payload: dict = Body(default=None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva. Sin body (o sin is_active) equivale a desactivar."""
    user = await db.get(User, _parse_uuid(id))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    is_active = bool(payload.get("is_active")) if isinstance(payload, dict) and "is_active" in payload else False

    if not is_active:
        if user.id == current_user.id:
            raise HTTPException(status_code=409, detail="No puedes desactivar tu propia cuenta")
        if user.role == UserRole.ADMIN and await _count_active_admins(db, excluding=user.id) == 0:
            raise HTTPException(status_code=409, detail="Debe existir al menos un administrador activo")

    user.is_active = is_active
    if not is_active:
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True)
        )
    else:
        user.failed_login_attempts = 0
        user.locked_until = None

    await db.commit()
    await db.refresh(user)

    await audit_event(
        db,
        AuditAction.USER_DISABLED if not is_active else AuditAction.USER_CREATED,
        user_id=current_user.id,
        entity_type="users",
        entity_id=user.id,
        metadata_json={"is_active": is_active},
    )
    return user
