import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.workday import Workday, WorkdayStatus
from app.core.timezone import today_local, now_utc
from app.services.webhook import enqueue_webhook
from app.services.audit import audit_event, AuditAction

async def check_in(db: AsyncSession, technician_id: uuid.UUID, lat: float=None, lon: float=None, acc: float=None, user_id: uuid.UUID=None, night_plan_id=None, commit=True, at=None):
    # Serialize check-in/out for this technician, including the first workday.
    await db.execute(select(Technician).where(Technician.id == technician_id).with_for_update())
    today = today_local()
    from app.models.night_plan import NightPlan
    from app.services.night_shift import day_exception
    shift = 'NIGHT' if night_plan_id else 'DAY'
    if night_plan_id:
        plan = await db.get(NightPlan, night_plan_id)
        if not plan or plan.technician_id != technician_id or plan.status not in ['PENDING', 'APPROVED'] or plan.work_date != today:
            raise HTTPException(409, 'La programación nocturna no está disponible para hoy. Actualiza la página.')
    elif await day_exception(db, technician_id, today):
        raise HTTPException(409, 'Hoy tienes descanso diurno autorizado por programación nocturna. Consulta al administrador si cambió el plan.')
    # Check for an existing shift of this type today
    stmt = select(Workday).where(Workday.is_void.is_(False), 
        Workday.technician_id == technician_id,
        Workday.work_date == today, Workday.shift_kind == shift
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya tienes una jornada de este tipo iniciada hoy.")
    
    # Check for any OPEN workday that wasn't closed
    stmt_open = select(Workday).where(Workday.is_void.is_(False), 
        Workday.technician_id == technician_id,
        Workday.status == WorkdayStatus.OPEN
    )
    res_open = await db.execute(stmt_open)
    existing_open = res_open.scalars().first()
    if existing_open:
        raise HTTPException(status_code=409, detail="Cierra tu jornada anterior antes de iniciar otra.")

    workday = Workday(
        technician_id=technician_id,
        work_date=today, shift_kind=shift, night_plan_id=night_plan_id,
        check_in_at=at or now_utc(),
        check_in_latitude=lat,
        check_in_longitude=lon,
        check_in_accuracy=acc,
        status=WorkdayStatus.OPEN
    )
    db.add(workday)
    await db.flush()
    if shift == 'NIGHT':
        from app.models.attendance import AttendanceIncident
        from app.services.attendance import event
        missing = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == technician_id, AttendanceIncident.work_date == today, AttendanceIncident.kind == 'MISSING_NIGHT', AttendanceIncident.status == 'PENDING'))
        if missing:
            missing.status, missing.review_note, missing.reviewed_at = 'JUSTIFIED', 'Reconciliada por entrada nocturna registrada.', now_utc()
            event(db, user_id, missing.id, 'INCIDENT_RECONCILED', note=missing.review_note)

    enqueue_webhook(db, "CHECK_IN", {"workday_id": str(workday.id), "technician_id": str(technician_id), "at": workday.check_in_at.isoformat()})
    if not commit:
        await db.flush()
        return workday
    await db.commit()
    await db.refresh(workday)
    
    await audit_event(db, AuditAction.CHECK_IN, user_id=user_id, entity_type="workdays", entity_id=workday.id)
    return workday

async def check_out(db: AsyncSession, technician_id: uuid.UUID, lat: float=None, lon: float=None, acc: float=None, user_id: uuid.UUID=None, early_exit_reason: str=None, commit=True, at=None):
    await db.execute(select(Technician).where(Technician.id == technician_id).with_for_update())
    stmt = select(Workday).where(Workday.is_void.is_(False), 
        Workday.technician_id == technician_id,
        Workday.status == WorkdayStatus.OPEN
    )
    res = await db.execute(stmt)
    workday = res.scalars().first()
    
    if not workday:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay jornada abierta.")
        
    out_time = at or now_utc()
    from app.services.attendance import schedule
    from app.models.attendance import AttendanceIncident
    hours = schedule(workday.work_date) if workday.shift_kind == "DAY" else None
    if hours and out_time < hours[1]:
        reason = (early_exit_reason or '').strip()
        if len(reason) < 3:
            raise HTTPException(422, detail="Salida anticipada: indica un motivo de al menos 3 caracteres. Quedará pendiente de revisión.")
        incident = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == technician_id, AttendanceIncident.work_date == workday.work_date, AttendanceIncident.kind == 'EARLY_EXIT'))
        if incident:
            incident.workday_id, incident.reason, incident.status = workday.id, reason, 'PENDING'
            incident.reviewed_by, incident.review_note, incident.reviewed_at = None, None, None
        else:
            db.add(AttendanceIncident(technician_id=technician_id, workday_id=workday.id, work_date=workday.work_date, kind='EARLY_EXIT', reason=reason))
    workday.check_out_at = out_time
    workday.check_out_latitude = lat
    workday.check_out_longitude = lon
    workday.check_out_accuracy = acc
    workday.status = WorkdayStatus.CLOSED
    workday.revision += 1

    # Ensure check_in_at is timezone-aware (SQLite may return naive datetimes)
    check_in = workday.check_in_at
    if check_in.tzinfo is None:
        from datetime import timezone as tz
        check_in = check_in.replace(tzinfo=tz.utc)
    duration = out_time - check_in
    workday.duration_minutes = int(duration.total_seconds() / 60)
    enqueue_webhook(db, "CHECK_OUT", {"workday_id": str(workday.id), "technician_id": str(technician_id), "at": out_time.isoformat(), "duration_minutes": workday.duration_minutes})
    
    if not commit:
        await db.flush()
        return workday
    await db.commit()
    await db.refresh(workday)
    
    await audit_event(db, AuditAction.CHECK_OUT, user_id=user_id, entity_type="workdays", entity_id=workday.id)
    return workday
