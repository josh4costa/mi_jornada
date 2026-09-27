from datetime import timezone, date
from zoneinfo import ZoneInfo
from app.core.config import settings
from fastapi import HTTPException
from sqlalchemy import select, or_
from app.core.timezone import now_utc, to_local, today_local
from app.models.workday import Workday, WorkdayStatus
from app.models.technician import Technician
from app.models.attendance import AttendanceIncident
from app.services.attendance import event, schedule, reconcile_missing, generate_missing


def aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


def snapshot(row):
    return {'check_in_at': aware(row.check_in_at).isoformat(), 'check_out_at': aware(row.check_out_at).isoformat() if row.check_out_at else None,
            'duration_minutes': row.duration_minutes, 'status': row.status.value, 'is_void': row.is_void, 'revision': row.revision}


async def change(db, id, body, actor, action):
    row = await db.get(Workday, id)
    if not row:
        raise HTTPException(404, 'Jornada no encontrada')
    await db.execute(select(Technician).where(Technician.id == row.technician_id).with_for_update())
    await db.refresh(row)
    if row.revision != body.revision:
        raise HTTPException(409, 'La jornada cambió. Actualiza la lista antes de modificarla.')
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(422, 'Escribe un motivo de al menos 3 caracteres')
    before = snapshot(row)
    if action == 'EDIT':
        if row.is_void:
            raise HTTPException(409, 'Restaura la jornada antes de editarla')
        def local_to_utc(value):
            if value is None: return None
            if value.tzinfo is None: value = value.replace(tzinfo=ZoneInfo(settings.TIMEZONE))
            return value.astimezone(timezone.utc)
        start, end = local_to_utc(body.check_in_at), local_to_utc(body.check_out_at)
        if to_local(start).date() != row.work_date:
            raise HTTPException(422, 'La entrada debe conservar la fecha de la jornada; las tareas permanecen vinculadas a ese día')
        if start > now_utc() or (end and (end > now_utc() or end < start)):
            raise HTTPException(422, 'Las horas no pueden ser futuras y la salida debe ser posterior o igual a la entrada')
        row.check_in_at, row.check_out_at = start, end
        row.duration_minutes = int((end - start).total_seconds() // 60) if end else None
        row.status = WorkdayStatus.CLOSED if end else WorkdayStatus.OPEN
    elif action == 'VOID':
        if row.is_void:
            raise HTTPException(409, 'La jornada ya está anulada')
        row.is_void = True
    elif action == 'RESTORE':
        if not row.is_void:
            raise HTTPException(409, 'La jornada ya está activa')
        row.is_void = False
    if not row.is_void:
        # Avoid flushing a reopened row before checking the partial unique index.
        with db.no_autoflush:
            others = (await db.scalars(select(Workday).where(Workday.technician_id == row.technician_id, Workday.id != row.id, Workday.is_void.is_(False)))).all()
        for other in others:
            if (other.work_date == row.work_date and other.shift_kind == row.shift_kind) or (row.status == WorkdayStatus.OPEN and other.status == WorkdayStatus.OPEN):
                raise HTTPException(409, 'Ya existe otra jornada de ese día o una jornada abierta. Corrige esa jornada primero.')
            if aware(other.check_in_at) < (aware(row.check_out_at) or now_utc()) and (aware(other.check_out_at) or now_utc()) > aware(row.check_in_at):
                raise HTTPException(409, 'Las horas se superponen con otra jornada del técnico')
    row.revision += 1
    hours = schedule(row.work_date) if row.shift_kind == "DAY" else None
    early = not row.is_void and row.check_out_at and hours and aware(row.check_out_at) < hours[1]
    incident = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == row.technician_id, AttendanceIncident.work_date == row.work_date, AttendanceIncident.kind == 'EARLY_EXIT'))
    if early:
        if not incident:
            incident = AttendanceIncident(technician_id=row.technician_id, work_date=row.work_date, kind='EARLY_EXIT', workday_id=row.id, reason=reason)
            db.add(incident)
        else:
            incident.status, incident.reviewed_by, incident.review_note, incident.reviewed_at = 'PENDING', None, None, None
            incident.workday_id = row.id
    elif incident and incident.workday_id == row.id:
        event(db, actor.id, incident.id, 'INCIDENT_RECONCILED', previous=incident.status, note='Jornada corregida o anulada: ' + reason)
        incident.status, incident.reviewed_by, incident.review_note, incident.reviewed_at = 'JUSTIFIED', actor.id, 'Jornada corregida o anulada: ' + reason, now_utc()
    if not row.is_void and row.shift_kind == "DAY":
        await reconcile_missing(db, row.technician_id, row.work_date)
    if row.is_void and settings.ATTENDANCE_START_DATE and date.fromisoformat(settings.ATTENDANCE_START_DATE) <= row.work_date < today_local():
        await generate_missing(db, await db.get(Technician, row.technician_id), row.work_date)
    event(db, actor.id, row.id, 'WORKDAY_' + action, note=reason, before=before, after=snapshot(row))
    await db.commit()
    return {'id': row.id, **snapshot(row)}
