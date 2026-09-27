"""app/api/v1/admin/dashboard.py  —  CORREGIDO

Bug visible en pantalla: el backend devolvia la hora ya formateada ("7:58 AM") y
Dashboard.tsx hace new Date(iso) -> "Invalid Date" en la columna Entrada/Salida.
Ahora se devuelve ISO-8601 (el front ya la formatea a America/Monterrey).

Ademas:
 - Se agregan user_id y coordenadas de entrada que adminApi.ts ya declaraba y nunca llegaban.
 - Solo tecnicos activos (antes aparecian los dados de baja).
 - Los conteos de tareas se hacen en SQL (GROUP BY) en vez de en Python.
 - Las tareas CANCELADAS ya no cuentan como "pendientes".
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user, get_current_panel_user
from app.core.timezone import today_local
from app.db.session import get_db
from app.models.task import Task, TaskStatus
from app.models.technician import Technician
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus

router = APIRouter()


def _iso(dt):
    return dt.isoformat() if dt else None


@router.get("")
async def get_dashboard(
    current_user: User = Depends(get_current_panel_user),
    db: AsyncSession = Depends(get_db),
):
    today = today_local()

    techs = (
        await db.execute(
            select(Technician)
            .options(selectinload(Technician.user))
            .where(Technician.is_active == True)  # noqa: E712
        )
    ).scalars().all()

    workdays = {
        w.technician_id: w
        for w in (
            await db.execute(select(Workday).where(Workday.is_void.is_(False), or_(Workday.work_date == today, Workday.status == WorkdayStatus.OPEN)).order_by((Workday.status == WorkdayStatus.OPEN).asc(), Workday.check_in_at.asc()))
        ).scalars().all()
    }

    counts_rows = (
        await db.execute(
            select(Task.technician_id, Task.status, func.count(Task.id))
            .where(Task.assigned_date == today)
            .group_by(Task.technician_id, Task.status)
        )
    ).all()
    counts: dict = {}
    for tech_id, status_value, total in counts_rows:
        counts.setdefault(tech_id, {})[status_value] = total

    working_now = not_started = finished = 0
    total_completed = total_pending = 0
    rows = []

    for tech in techs:
        by_status = counts.get(tech.id, {})
        completed = by_status.get(TaskStatus.COMPLETED, 0)
        pending = by_status.get(TaskStatus.PENDING, 0)
        total_completed += completed
        total_pending += pending

        w = workdays.get(tech.id)
        if not w:
            status = "NOT_STARTED"
            not_started += 1
        elif w.status == WorkdayStatus.OPEN:
            status = "WORKING"
            working_now += 1
        else:
            status = "FINISHED"
            finished += 1

        from app.services.night_shift import day_exception
        exception = await day_exception(db, tech.id, today, include_pending=True)
        rows.append(
            {
                "id": str(tech.id),
                "user_id": str(tech.user_id),
                "full_name": tech.user.full_name,
                "status": status, "shift_kind": w.shift_kind if w else None,
                "day_note": ("Cambio nocturno pendiente de validación" if exception.status == "PENDING" else "Descanso diurno por noche autorizada") if exception else None,
                "check_in_time": _iso(w.check_in_at) if w else None,
                "check_out_time": _iso(w.check_out_at) if w else None,
                "check_in_latitude": float(w.check_in_latitude) if w and w.check_in_latitude is not None else None,
                "check_in_longitude": float(w.check_in_longitude) if w and w.check_in_longitude is not None else None,
                "duration_minutes": w.duration_minutes if w else None,
                "tasks_completed": completed,
                "tasks_pending": pending,
            }
        )

    rows.sort(key=lambda r: r["full_name"])

    return {
        "working_now": working_now,
        "not_started": not_started,
        "finished": finished,
        "tasks_completed": total_completed,
        "tasks_pending": total_pending,
        "technicians": rows,
    }
