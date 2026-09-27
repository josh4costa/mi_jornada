from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_active_user, get_current_operator_user
from app.api.v1.attendance import tech_filter
from app.core.config import settings
from app.core.timezone import today_local, to_local
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.night_plan import NightPlan
from app.models.workday import Workday
from app.services.attendance import event, reconcile_missing, approved_leave

router = APIRouter()


class PlanInput(BaseModel):
    technician_id: UUID | None = None
    work_date: date
    reminder_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    replaces_day: bool = False
    rest_next_day: bool = False
    reason: str = Field(min_length=3, max_length=1000)


class Decision(BaseModel):
    status: Literal['APPROVED', 'REJECTED', 'CANCELLED']
    note: str = Field(min_length=3, max_length=1000)


@router.get('')
async def plans(date_from: date, date_to: date, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(422, 'Consulta un rango de hasta un año')
    stmt = select(NightPlan, User.full_name).join(Technician, Technician.id == NightPlan.technician_id).join(User, User.id == Technician.user_id).where(NightPlan.work_date >= date_from, NightPlan.work_date <= date_to)
    own_id = tech_filter(user)
    if own_id:
        stmt = stmt.where(NightPlan.technician_id == own_id)
    rows = (await db.execute(stmt.order_by(NightPlan.work_date.desc(), NightPlan.created_at.desc()))).all()
    return [{**{c.name: getattr(row, c.name) for c in row.__table__.columns}, 'technician_name': name} for row, name in rows]


@router.post('', status_code=201)
async def create(body: PlanInput, user: User = Depends(get_current_operator_user), db: AsyncSession = Depends(get_db)):
    own_id = tech_filter(user)
    tech_id = own_id or body.technician_id
    if not tech_id or (own_id and body.technician_id and body.technician_id != own_id):
        raise HTTPException(403, 'Selecciona un técnico autorizado')
    if not today_local() <= body.work_date <= today_local() + timedelta(days=366) or len(body.reason.strip()) < 3:
        raise HTTPException(422, 'Indica un motivo y una fecha desde hoy hasta un año')
    if own_id and body.rest_next_day:
        raise HTTPException(403, 'Solo el administrador puede autorizar descanso al día siguiente')
    tech = await db.scalar(select(Technician).where(Technician.id == tech_id).with_for_update())
    target_user = await db.get(User, tech.user_id) if tech else None
    if not tech or not tech.is_active or not target_user.is_active or target_user.role != UserRole.TECHNICIAN:
        raise HTTPException(404, 'Técnico activo no encontrado')
    existing = await db.scalar(select(NightPlan.id).where(NightPlan.technician_id == tech_id, NightPlan.work_date == body.work_date, NightPlan.status.in_(['APPROVED', 'PENDING'])))
    night = await db.scalar(select(Workday.id).where(Workday.technician_id == tech_id, Workday.work_date == body.work_date, Workday.shift_kind == 'NIGHT', Workday.is_void.is_(False)))
    if existing or night:
        raise HTTPException(409, 'Ya existe una programación o jornada nocturna para esa fecha')
    if await approved_leave(db, tech_id, body.work_date):
        raise HTTPException(409, 'Hay una ausencia aprobada para esa fecha; el administrador debe revisarla primero')
    row = NightPlan(technician_id=tech_id, work_date=body.work_date,
        reminder_at=datetime.combine(body.work_date, datetime.strptime(body.reminder_time, '%H:%M').time(), ZoneInfo(settings.TIMEZONE)).astimezone(timezone.utc),
        replaces_day=body.replaces_day, rest_next_day=body.rest_next_day, reason=body.reason.strip(),
        status='PENDING' if own_id else 'APPROVED', requested_by=user.id, reviewed_by=None if own_id else user.id)
    db.add(row)
    await db.flush()
    event(db, user.id, row.id, 'NIGHT_PLANNED', status=row.status, date=str(row.work_date), replaces_day=row.replaces_day, rest_next_day=row.rest_next_day, reminder_at=row.reminder_at.isoformat(), note=row.reason)
    await db.commit()
    return {'id': row.id, 'status': row.status}


@router.patch('/{id}')
async def decide(id: UUID, body: Decision, user: User = Depends(get_current_operator_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(NightPlan, id)
    if not row:
        raise HTTPException(404, 'Programación no encontrada')
    own_id = tech_filter(user)
    if own_id and (row.technician_id != own_id or body.status != 'CANCELLED'):
        raise HTTPException(403, 'Solo el administrador puede validar la programación')
    if len(body.note.strip()) < 3:
        raise HTTPException(422, 'Indica el motivo')
    await db.execute(select(Technician).where(Technician.id == row.technician_id).with_for_update())
    await db.refresh(row)
    if row.status not in ['PENDING', 'APPROVED'] or (row.status == 'APPROVED' and body.status != 'CANCELLED'):
        raise HTTPException(409, 'La programación ya fue revisada; actualiza la página')
    if body.status == 'CANCELLED':
        used = await db.scalar(select(Workday.id).where(Workday.night_plan_id == id, Workday.is_void.is_(False)))
        if used or row.work_date < today_local():
            raise HTTPException(409, 'La noche ya comenzó o su fecha pasó; revisa la incidencia conservando el historial')
    previous = row.status
    row.status, row.reviewed_by = body.status, user.id
    if row.status == 'APPROVED':
        if row.replaces_day:
            await reconcile_missing(db, row.technician_id, row.work_date)
        if row.rest_next_day:
            await reconcile_missing(db, row.technician_id, row.work_date + timedelta(days=1))
    event(db, user.id, row.id, 'NIGHT_REVIEWED', previous=previous, status=row.status, note=body.note.strip())
    await db.commit()
    return {'status': row.status}
