"""Historical reports shared by JSON and CSV, using local work-date offsets."""
import csv
import io
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user, get_current_panel_user
from app.core.timezone import to_local
from app.db.session import get_db
from app.models.task import CreatedByType, Task, TaskStatus
from app.models.technician import Technician
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus

router = APIRouter()

EMPTY = "—"


def _avg_local_time(workdays, field: str) -> str | None:
    # Measure from each work date, so a 00:30 checkout is later than 23:30.
    minutes = []
    for workday in workdays:
        value = getattr(workday, field)
        if value is not None:
            local = to_local(value)
            minutes.append((local.date() - workday.work_date).days * 1440 + local.hour * 60 + local.minute)
    if not minutes:
        return None
    avg = (sum(minutes) // len(minutes)) % 1440
    h, m = divmod(avg, 60)
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


async def _build_rows(
    db: AsyncSession,
    date_from: Optional[date],
    date_to: Optional[date],
    technician_id: Optional[str],
) -> list[dict]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="La fecha inicial no puede ser mayor que la final")
    techs_stmt = (
        select(Technician)
        .options(selectinload(Technician.user))
    )
    if technician_id:
        try:
            techs_stmt = techs_stmt.where(Technician.id == uuid.UUID(technician_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="El id del tecnico no es valido")

    technicians = (await db.execute(techs_stmt)).scalars().all()
    rows = []

    for tech in technicians:
        w_stmt = select(Workday).where(Workday.is_void.is_(False), Workday.technician_id == tech.id)
        t_stmt = select(Task).where(Task.technician_id == tech.id)
        if date_from:
            w_stmt = w_stmt.where(Workday.work_date >= date_from)
            t_stmt = t_stmt.where(Task.assigned_date >= date_from)
        if date_to:
            w_stmt = w_stmt.where(Workday.work_date <= date_to)
            t_stmt = t_stmt.where(Task.assigned_date <= date_to)

        workdays = (await db.execute(w_stmt)).scalars().all()
        tasks = (await db.execute(t_stmt)).scalars().all()

        closed = [w for w in workdays if w.status == WorkdayStatus.CLOSED]
        total_minutes = sum(w.duration_minutes or 0 for w in closed)

        rows.append(
            {
                "technician_id": str(tech.id),
                "technician_name": tech.user.full_name,
                "days_worked": len({w.work_date for w in closed}),
                "total_minutes": total_minutes,
                "total_hours": round(total_minutes / 60, 1),
                "avg_check_in": _avg_local_time(closed, "check_in_at"),
                "avg_check_out": _avg_local_time(closed, "check_out_at"),
                "tasks_assigned": len([t for t in tasks if t.status != TaskStatus.CANCELLED]),
                "tasks_completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                "tasks_unplanned": len([t for t in tasks if t.created_by_type == CreatedByType.TECHNICIAN]),
                "tasks_pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
                "tasks_cancelled": len([t for t in tasks if t.status == TaskStatus.CANCELLED]),
            }
        )

    rows.sort(key=lambda r: r["technician_name"])
    return rows


@router.get("")
async def get_reports(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    technician_id: Optional[str] = None,
    current_user: User = Depends(get_current_panel_user),
    db: AsyncSession = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="La fecha inicial no puede ser mayor que la final")
    return await _build_rows(db, date_from, date_to, technician_id)


@router.get("/export/csv")
async def export_reports_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    technician_id: Optional[str] = None,
    current_user: User = Depends(get_current_panel_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await _build_rows(db, date_from, date_to, technician_id)

    output = io.StringIO()
    writer = csv.writer(output)  # separador coma + BOM utf-8 (Excel)
    writer.writerow(
        [
            "Tecnico", "Dias Trabajados", "Total Horas", "Prom. Entrada", "Prom. Salida",
            "Tareas Asignadas", "Tareas Realizadas", "Actividades No Programadas",
            "Tareas Pendientes", "Tareas Canceladas",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                ("'" + r["technician_name"] if r["technician_name"].lstrip().startswith(("=", "+", "-", "@")) else r["technician_name"]), r["days_worked"], r["total_hours"],
                r["avg_check_in"], r["avg_check_out"], r["tasks_assigned"], r["tasks_completed"],
                r["tasks_unplanned"], r["tasks_pending"], r["tasks_cancelled"],
            ]
        )

    filename = f"reporte_{date_from or 'inicio'}_{date_to or 'hoy'}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
