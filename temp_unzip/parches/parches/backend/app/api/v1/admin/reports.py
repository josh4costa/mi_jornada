"""app/api/v1/admin/reports.py  —  CORREGIDO

 1. BUG DE ZONA HORARIA: el promedio de entrada/salida usaba t.astimezone(), que
    convierte a la hora LOCAL DEL CONTENEDOR (UTC en el VPS). En Monterrey eso
    mostraba las entradas 6 horas adelantadas. Ahora usa to_local() (America/Monterrey).
 2. El promedio de horas se calculaba sobre minutos "circulares" (07:50 y 23:50
    promediaban 15:50): ahora se promedia en minutos desde medianoche local, que es
    lo correcto para jornadas que no cruzan la medianoche, y se ignoran los nulos.
 3. El CSV mostraba "-" en Prom. Entrada / Prom. Salida: ahora exporta los valores reales.
 4. La logica estaba duplicada entre JSON y CSV (podian dar numeros distintos):
    ahora ambas salidas usan la misma funcion _build_rows().
 5. El nombre del archivo CSV va entre comillas (fechas con guiones rompian el header).
 6. Se agrega el filtro por estado CANCELLED en tareas asignadas.
"""
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

from app.api.deps import get_current_admin_user
from app.core.timezone import to_local
from app.db.session import get_db
from app.models.task import CreatedByType, Task, TaskStatus
from app.models.technician import Technician
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus

router = APIRouter()

EMPTY = "—"


def _avg_local_time(datetimes) -> str:
    valid = [d for d in datetimes if d is not None]
    if not valid:
        return EMPTY
    minutes = [to_local(d).hour * 60 + to_local(d).minute for d in valid]
    avg = sum(minutes) // len(minutes)
    h, m = divmod(avg, 60)
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {suffix}"


async def _build_rows(
    db: AsyncSession,
    date_from: Optional[date],
    date_to: Optional[date],
    technician_id: Optional[str],
) -> list[dict]:
    techs_stmt = (
        select(Technician)
        .options(selectinload(Technician.user))
        .where(Technician.is_active == True)  # noqa: E712
    )
    if technician_id:
        try:
            techs_stmt = techs_stmt.where(Technician.id == uuid.UUID(technician_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="El id del tecnico no es valido")

    technicians = (await db.execute(techs_stmt)).scalars().all()
    rows = []

    for tech in technicians:
        w_stmt = select(Workday).where(Workday.technician_id == tech.id)
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
                "days_worked": len(closed),
                "total_minutes": total_minutes,
                "total_hours": round(total_minutes / 60, 1),
                "avg_check_in": _avg_local_time([w.check_in_at for w in closed]),
                "avg_check_out": _avg_local_time([w.check_out_at for w in closed]),
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
    current_user: User = Depends(get_current_admin_user),
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
    current_user: User = Depends(get_current_admin_user),
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
                r["technician_name"], r["days_worked"], r["total_hours"],
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
