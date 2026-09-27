from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.api.deps import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.account_setup import TaskLocation
from app.models.user import UserRole
from app.services.attendance import event

router = APIRouter()


class LocationCreate(BaseModel):
    group_name: Literal['EL POLLO LOCO', 'TACO PALENQUE', 'Otras ubicaciones']
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = ' '.join(value.split())
        if not value:
            raise ValueError('Escribe el nombre de la ubicación.')
        return value


class LocationStatus(BaseModel):
    is_active: bool
    revision: int = Field(ge=0)


@router.get('')
async def list_locations(include_inactive: bool = False, user=Depends(get_current_active_user), db=Depends(get_db)):
    if include_inactive and user.role != UserRole.ADMIN:
        raise HTTPException(403, 'Solo administradores pueden consultar ubicaciones inactivas.')
    query = select(TaskLocation).order_by(TaskLocation.group_name, TaskLocation.name)
    if not include_inactive:
        query = query.where(TaskLocation.is_active.is_(True))
    return (await db.scalars(query)).all()


@router.post('', status_code=201)
async def create_location(body: LocationCreate, user=Depends(get_current_admin_user), db=Depends(get_db)):
    # Serialize catalog writes, including case-insensitive duplicate checks.
    await db.execute(select(TaskLocation.id).order_by(TaskLocation.id).with_for_update())
    exists = await db.scalar(select(TaskLocation.id).where(TaskLocation.group_name == body.group_name, func.lower(TaskLocation.name) == body.name.lower()))
    if exists:
        raise HTTPException(409, 'La ubicación ya existe, incluso si está desactivada.')
    location = TaskLocation(**body.model_dump())
    db.add(location)
    await db.flush()
    event(db, user.id, location.id, 'LOCATION_CREATED', group=body.group_name, name=body.name)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'La ubicación ya existe.')
    return location


@router.patch('/{id}')
async def toggle_location(id: UUID, body: LocationStatus, user=Depends(get_current_admin_user), db=Depends(get_db)):
    location = await db.scalar(select(TaskLocation).where(TaskLocation.id == id).with_for_update())
    if not location:
        raise HTTPException(404, 'Ubicación no encontrada.')
    if location.revision != body.revision:
        raise HTTPException(409, 'La ubicación cambió. Recarga el catálogo.')
    location.is_active = body.is_active
    location.revision += 1
    event(db, user.id, location.id, 'LOCATION_STATUS_CHANGED', is_active=body.is_active)
    await db.commit()
    return location


async def selected_location(db, id):
    if not id:
        raise HTTPException(422, 'Selecciona la sucursal relacionada con la tarea.')
    location = await db.scalar(select(TaskLocation).where(TaskLocation.id == id).with_for_update())
    if not location or not location.is_active:
        raise HTTPException(422, 'La ubicación no está disponible. Elige una ubicación activa.')
    return location.id, (location.name if location.group_name == 'Otras ubicaciones' else f'{location.group_name} · {location.name}')
