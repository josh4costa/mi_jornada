from datetime import date, timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_active_user, get_current_admin_user, get_current_panel_user, get_current_operator_user
from app.db.session import get_db
from app.core.config import settings
from app.core.timezone import today_local, now_utc
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.attendance import LeaveRequest, AttendanceIncident, ReminderDelivery, AttendanceEvent
from app.services.attendance import working_days, event, reconcile_missing, generate_missing

router = APIRouter()


class LeaveInput(BaseModel):
    technician_id: UUID | None = None
    kind: Literal['VACATION', 'PERMISSION']
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode='after')
    def validate_range(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 365:
            raise ValueError('Selecciona un rango de fechas válido de hasta un año')
        if not working_days(self.start_date, self.end_date) or len(self.reason.strip()) < 3:
            raise ValueError('Indica un motivo y al menos un día laboral')
        return self


class ReviewInput(BaseModel):
    status: Literal['APPROVED', 'REJECTED', 'CANCELLED', 'JUSTIFIED', 'UNJUSTIFIED']
    note: str = Field(min_length=3, max_length=1000)


def tech_filter(user):
    if user.role in (UserRole.ADMIN, UserRole.READ_ONLY):
        return None
    if not user.technician or not user.technician.is_active:
        raise HTTPException(403, 'Perfil técnico no disponible')
    return user.technician.id


def serialize(row, name):
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    data['technician_name'] = name
    if isinstance(row, LeaveRequest):
        data['working_days'] = working_days(row.start_date, row.end_date)
    return data


@router.get('/schedule')
async def get_schedule(user: User = Depends(get_current_active_user)):
    return {'timezone': settings.TIMEZONE, 'weekdays': '09:00–18:00', 'saturday': '09:00–13:00',
            'sunday': 'Descanso', 'reminder_delay_minutes': 10}


@router.get('/leaves')
async def list_leaves(date_from: date, date_to: date, include_pending: bool = False, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(422, 'Consulta un rango de hasta un año')
    stmt = select(LeaveRequest, User.full_name).join(Technician, Technician.id == LeaveRequest.technician_id).join(User, User.id == Technician.user_id).where(or_((LeaveRequest.start_date <= date_to) & (LeaveRequest.end_date >= date_from), (LeaveRequest.status == "PENDING") if include_pending else False))
    tech_id = tech_filter(user)
    if tech_id:
        stmt = stmt.where(LeaveRequest.technician_id == tech_id)
    rows = (await db.execute(stmt.order_by(LeaveRequest.start_date, LeaveRequest.created_at))).all()
    return [serialize(row, name) for row, name in rows]


@router.post('/leaves', status_code=201)
async def create_leave(body: LeaveInput, user: User = Depends(get_current_operator_user), db: AsyncSession = Depends(get_db)):
    own_id = tech_filter(user)
    tech_id = own_id or body.technician_id
    if not tech_id or (own_id and body.technician_id and body.technician_id != own_id):
        raise HTTPException(403, 'Selecciona un técnico autorizado')
    if own_id and body.start_date < today_local():
        raise HTTPException(422, 'Las ausencias pasadas deben ser registradas por el administrador')
    tech = await db.scalar(select(Technician).where(Technician.id == tech_id).with_for_update())
    if not tech or not tech.is_active:
        raise HTTPException(404, 'Técnico activo no encontrado')
    overlap = await db.scalar(select(LeaveRequest.id).where(LeaveRequest.technician_id == tech_id, LeaveRequest.status.in_(['PENDING', 'APPROVED']), LeaveRequest.start_date <= body.end_date, LeaveRequest.end_date >= body.start_date))
    if overlap:
        raise HTTPException(409, 'Ya existe una solicitud pendiente o aprobada que coincide con esas fechas')
    row = LeaveRequest(technician_id=tech_id, kind=body.kind, start_date=body.start_date, end_date=body.end_date, reason=body.reason.strip(), requested_by=user.id)
    db.add(row)
    await db.flush()
    event(db, user.id, row.id, 'LEAVE_REQUESTED', start=str(body.start_date), end=str(body.end_date), kind=body.kind)
    await db.commit()
    return {'id': row.id, 'status': row.status, 'working_days': working_days(row.start_date, row.end_date)}


@router.patch('/leaves/{id}')
async def review_leave(id: UUID, body: ReviewInput, user: User = Depends(get_current_operator_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(LeaveRequest, id)
    if not row:
        raise HTTPException(404, 'Solicitud no encontrada')
    own_id = tech_filter(user)
    if own_id and (row.technician_id != own_id or body.status != 'CANCELLED'):
        raise HTTPException(403, 'Solo el administrador puede revisar solicitudes')
    await db.execute(select(Technician).where(Technician.id == row.technician_id).with_for_update())
    await db.refresh(row)
    if body.status not in ['APPROVED', 'REJECTED', 'CANCELLED'] or len(body.note.strip()) < 3:
        raise HTTPException(422, 'Selecciona una decisión y escribe el motivo')
    if row.status != 'PENDING' and not (not own_id and row.status == 'APPROVED' and body.status == 'CANCELLED'):
        raise HTTPException(409, 'La solicitud ya fue revisada; actualiza la página')
    previous = row.status
    row.status, row.review_note, row.reviewed_by, row.reviewed_at = body.status, body.note.strip(), user.id, now_utc()
    if row.status == 'APPROVED':
        for offset in range((row.end_date - row.start_date).days + 1):
            await reconcile_missing(db, row.technician_id, row.start_date + timedelta(days=offset))
    if previous == 'APPROVED' and row.status == 'CANCELLED':
        tech = await db.get(Technician, row.technician_id)
        for offset in range((row.end_date - row.start_date).days + 1):
            day = row.start_date + timedelta(days=offset)
            if day >= today_local() or not settings.ATTENDANCE_START_DATE or day < date.fromisoformat(settings.ATTENDANCE_START_DATE):
                continue
            old = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == tech.id, AttendanceIncident.work_date == day, AttendanceIncident.kind == 'MISSING_ENTRY', AttendanceIncident.status == 'JUSTIFIED', AttendanceIncident.reviewed_by.is_(None)))
            if old:
                old.status, old.review_note, old.reviewed_at = 'PENDING', None, None
                event(db, user.id, old.id, 'INCIDENT_REOPENED', note='Ausencia autorizada cancelada')
            await generate_missing(db, tech, day)
    event(db, user.id, row.id, 'LEAVE_REVIEWED' , previous=previous, status=row.status, note=row.review_note)
    await db.commit()
    return {'status': row.status}


@router.get('/incidents')
async def incidents(status: Literal['PENDING', 'JUSTIFIED', 'UNJUSTIFIED'] | None = None, page: int = Query(1, ge=1), user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    filters = []
    own_id = tech_filter(user)
    if own_id:
        filters.append(AttendanceIncident.technician_id == own_id)
    if status:
        filters.append(AttendanceIncident.status == status)
    total = await db.scalar(select(func.count(AttendanceIncident.id)).where(*filters))
    rows = (await db.execute(select(AttendanceIncident, User.full_name).join(Technician, Technician.id == AttendanceIncident.technician_id).join(User, User.id == Technician.user_id).where(*filters).order_by(AttendanceIncident.work_date.desc(), AttendanceIncident.id).offset((page - 1) * 30).limit(30))).all()
    return {'items': [serialize(row, name) for row, name in rows], 'total': total}


@router.patch('/incidents/{id}')
async def review_incident(id: UUID, body: ReviewInput, user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(AttendanceIncident, id)
    if not row:
        raise HTTPException(404, 'Incidencia no encontrada')
    await db.execute(select(Technician).where(Technician.id == row.technician_id).with_for_update())
    await db.refresh(row)
    if body.status not in ['JUSTIFIED', 'UNJUSTIFIED'] or len(body.note.strip()) < 3:
        raise HTTPException(422, 'Selecciona una resolución e indica el motivo')
    event(db, user.id, row.id, 'INCIDENT_REVIEWED', previous=row.status, status=body.status, note=body.note.strip())
    row.status, row.review_note, row.reviewed_by, row.reviewed_at = body.status, body.note.strip(), user.id, now_utc()
    await db.commit()
    return {'status': row.status}


@router.get('/summary')
async def summary(user: User = Depends(get_current_panel_user), db: AsyncSession = Depends(get_db)):
    pending = await db.scalar(select(func.count(AttendanceIncident.id)).where(AttendanceIncident.status == 'PENDING'))
    leaves = await db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == 'PENDING'))
    from app.models.night_plan import NightPlan
    nights = await db.scalar(select(func.count(NightPlan.id)).where(NightPlan.status == 'PENDING'))
    return {'incidents': pending, 'leaves': leaves, 'nights': nights}


@router.get('/events/{id}')
async def events(id: UUID, user: User = Depends(get_current_panel_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AttendanceEvent, User.full_name).outerjoin(User, User.id == AttendanceEvent.actor_id).where(AttendanceEvent.entity_id == id).order_by(AttendanceEvent.created_at))).all()
    return [{**{c.name: getattr(row, c.name) for c in row.__table__.columns}, 'actor_name': name} for row, name in rows]


@router.get('/reminders')
async def reminders(user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ReminderDelivery, User.full_name).join(Technician, Technician.id == ReminderDelivery.technician_id).join(User, User.id == Technician.user_id).order_by(ReminderDelivery.created_at.desc()).limit(50))).all()
    return {'enabled': settings.REMINDERS_ENABLED, 'configured': bool(settings.ULTRAMSG_INSTANCE and settings.ULTRAMSG_TOKEN), 'items': [serialize(row, name) for row, name in rows]}
