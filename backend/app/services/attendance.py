from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.config import settings
from app.core.timezone import now_utc, to_local
from app.models.attendance import LeaveRequest, AttendanceIncident, AttendanceEvent
from app.models.workday import Workday


def schedule(day: date):
    if day.weekday() == 6:
        return None
    tz = ZoneInfo(settings.TIMEZONE)
    return (datetime.combine(day, time(9), tz), datetime.combine(day, time(13 if day.weekday() == 5 else 18), tz))


def working_days(start, end):
    return sum((start + timedelta(days=i)).weekday() != 6 for i in range((end - start).days + 1))


async def approved_leave(db, technician_id, day):
    return await db.scalar(select(LeaveRequest).where(
        LeaveRequest.technician_id == technician_id, LeaveRequest.status == 'APPROVED',
        LeaveRequest.start_date <= day, LeaveRequest.end_date >= day))


def event(db, actor_id, entity_id, action, **details):
    db.add(AttendanceEvent(actor_id=actor_id, entity_id=entity_id, action=action, details=details))


async def reconcile_missing(db, technician_id, day):
    incident = await db.scalar(select(AttendanceIncident).where(
        AttendanceIncident.technician_id == technician_id, AttendanceIncident.work_date == day,
        AttendanceIncident.kind == 'MISSING_ENTRY', AttendanceIncident.status == 'PENDING'))
    if incident:
        incident.status = 'JUSTIFIED'
        incident.review_note = 'Reconciliada por registro de entrada o ausencia aprobada.'
        incident.reviewed_at = now_utc()
        event(db, None, incident.id, 'INCIDENT_RECONCILED', note=incident.review_note)


async def generate_missing(db, tech, day):
    from app.models.night_plan import NightPlan
    plans = (await db.scalars(select(NightPlan).where(NightPlan.technician_id == tech.id, NightPlan.work_date == day, NightPlan.status.in_(['PENDING', 'APPROVED'])))).all()
    if plans:
        night = await db.scalar(select(Workday.id).where(Workday.technician_id == tech.id, Workday.work_date == day, Workday.shift_kind == 'NIGHT', Workday.is_void.is_(False)))
        incident = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == tech.id, AttendanceIncident.work_date == day, AttendanceIncident.kind == 'MISSING_NIGHT'))
        if not night and not incident:
            db.add(AttendanceIncident(technician_id=tech.id, work_date=day, kind='MISSING_NIGHT', reason='Noche programada sin registro de entrada. Requiere revisión.'))
    if not schedule(day) or to_local(tech.created_at).date() > day:
        return
    from app.services.night_shift import day_exception
    exists = await db.scalar(select(Workday.id).where(Workday.is_void.is_(False), Workday.technician_id == tech.id, Workday.work_date == day, Workday.shift_kind == "DAY"))
    if exists or await approved_leave(db, tech.id, day) or await day_exception(db, tech.id, day):
        await reconcile_missing(db, tech.id, day)
        return
    incident = await db.scalar(select(AttendanceIncident.id).where(
        AttendanceIncident.technician_id == tech.id, AttendanceIncident.work_date == day,
        AttendanceIncident.kind == 'MISSING_ENTRY'))
    if not incident:
        db.add(AttendanceIncident(technician_id=tech.id, work_date=day, kind='MISSING_ENTRY',
                                 reason='Sin registro de entrada ni ausencia autorizada. Requiere revisión.'))
