from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.db.session import get_db
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus
from app.api.deps import get_current_technician_user
from app.schemas.workday import WorkdayLocation, WorkdayResponse, WorkdayCheckout, WorkdayCheckin
from app.services.workday import check_in as svc_check_in, check_out as svc_check_out
from app.core.timezone import today_local

router = APIRouter()

@router.post("/check-in", response_model=WorkdayResponse)
async def check_in_endpoint(
    body: WorkdayCheckin,
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    return await svc_check_in(
        db=db,
        technician_id=current_user.technician.id,
        lat=body.latitude,
        lon=body.longitude,
        acc=body.accuracy,
        user_id=current_user.id, night_plan_id=body.night_plan_id
    )

@router.post("/check-out", response_model=WorkdayResponse)
async def check_out_endpoint(
    body: WorkdayCheckout,
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    return await svc_check_out(
        db=db,
        early_exit_reason=body.early_exit_reason,
        technician_id=current_user.technician.id,
        lat=body.latitude,
        lon=body.longitude,
        acc=body.accuracy,
        user_id=current_user.id
    )

@router.get("/today")
async def get_today_workday(
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    today = today_local()
    stmt = select(Workday).where(Workday.is_void.is_(False), 
        Workday.technician_id == current_user.technician.id,
        or_(Workday.status == WorkdayStatus.OPEN, Workday.work_date == today)
    ).order_by((Workday.status == WorkdayStatus.OPEN).desc(), Workday.check_in_at.desc())
    result = await db.execute(stmt)
    workday = result.scalars().first()
    
    from app.services.attendance import schedule, approved_leave
    from app.core.timezone import now_utc
    hours = schedule(workday.work_date if workday else today) if not workday or workday.shift_kind == "DAY" else None
    leave = await approved_leave(db, current_user.technician.id, today)
    from app.models.night_plan import NightPlan
    from app.services.night_shift import day_exception
    todays = (await db.scalars(select(Workday).where(Workday.technician_id == current_user.technician.id, Workday.work_date == today, Workday.is_void.is_(False)))).all()
    plans = (await db.scalars(select(NightPlan).where(NightPlan.technician_id == current_user.technician.id, NightPlan.work_date == today, NightPlan.status.in_(['PENDING', 'APPROVED'])))).all()
    exemption = await day_exception(db, current_user.technician.id, today)
    info = {"can_start_day": not exemption and not any(w.shift_kind == 'DAY' for w in todays),
            "day_rest": bool(exemption),
            "night_options": [{"id": p.id, "status": p.status, "reminder_at": p.reminder_at} for p in plans if not any(w.shift_kind == 'NIGHT' for w in todays)],"scheduled_exit": hours[1].isoformat() if hours else None,
            "early_exit": bool(workday and workday.status == WorkdayStatus.OPEN and hours and now_utc() < hours[1]),
            "approved_absence": {"kind": leave.kind, "end_date": str(leave.end_date)} if leave else None}
    if not workday:
        return {"status": "NOT_STARTED", "workday": None, **info}
    
    if workday.status == WorkdayStatus.OPEN:
        return {"status": "WORKING", "workday": WorkdayResponse.model_validate(workday), **info}
    
    return {"status": "FINISHED", "workday": WorkdayResponse.model_validate(workday), **info}


@router.post('/continue-day', response_model=WorkdayResponse)
async def continue_day(body: WorkdayLocation, current_user: User = Depends(get_current_technician_user), db: AsyncSession = Depends(get_db)):
    from app.models.technician import Technician
    from app.core.timezone import now_utc
    from app.services.attendance import event
    tech_id = current_user.technician.id
    await db.execute(select(Technician).where(Technician.id == tech_id).with_for_update())
    night = await db.scalar(select(Workday).where(Workday.technician_id == tech_id, Workday.is_void.is_(False), Workday.status == WorkdayStatus.OPEN))
    if not night or night.shift_kind != 'NIGHT':
        raise HTTPException(409, 'Necesitas una jornada nocturna abierta para continuar con turno diurno')
    at = now_utc()
    # One transaction: a failed new entry rolls back the night checkout as well.
    await svc_check_out(db, tech_id, body.latitude, body.longitude, body.accuracy, current_user.id, commit=False, at=at)
    day = await svc_check_in(db, tech_id, body.latitude, body.longitude, body.accuracy, current_user.id, commit=False, at=at)
    event(db, current_user.id, night.id, 'NIGHT_CONTINUED_DAY', day_workday_id=str(day.id), at=at.isoformat())
    await db.commit()
    await db.refresh(day)
    return day
