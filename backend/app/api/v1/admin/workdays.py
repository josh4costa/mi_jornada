"""app/api/v1/admin/workdays.py  —  CORREGIDO

 - La tabla del front muestra technician_name, tasks_assigned y tasks_completed;
   el backend no los enviaba (columna de nombre vacia en /admin/jornadas).
 - technician_id llegaba como string y se comparaba contra una columna UUID:
   con un valor mal formado el endpoint respondia 500. Ahora 422.
 - Orden estable (fecha DESC, luego hora de entrada DESC) para que la paginacion
   no repita ni salte registros.
 - Conteo de tareas en una sola consulta agrupada (antes ni existia).
"""
import math
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user, get_current_panel_user
from app.db.session import get_db
from app.models.task import Task, TaskStatus
from app.models.technician import Technician
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus

router = APIRouter()


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"El {label} no es valido")


@router.get("")
async def list_workdays(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    technician_id: Optional[str] = None,
    status: Optional[WorkdayStatus] = None,
    include_void: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_panel_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [] if include_void else [Workday.is_void.is_(False)]
    if date_from:
        filters.append(Workday.work_date >= date_from)
    if date_to:
        filters.append(Workday.work_date <= date_to)
    if technician_id:
        filters.append(Workday.technician_id == _parse_uuid(technician_id, "id del tecnico"))
    if status:
        filters.append(Workday.status == status)

    total = await db.scalar(select(func.count(Workday.id)).where(*filters)) or 0

    stmt = (
        select(Workday)
        .options(selectinload(Workday.technician).selectinload(Technician.user))
        .where(*filters)
        .order_by(Workday.work_date.desc(), Workday.check_in_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = (await db.execute(stmt)).scalars().all()

    # Conteo de tareas de todas las jornadas de la pagina, en una sola consulta.
    pairs = {(w.technician_id, w.work_date) for w in items}
    counts: dict = {}
    if pairs:
        tech_ids = {p[0] for p in pairs}
        dates = {p[1] for p in pairs}
        rows = (
            await db.execute(
                select(Task.technician_id, Task.assigned_date, Task.status, func.count(Task.id))
                .where(Task.technician_id.in_(tech_ids), Task.assigned_date.in_(dates))
                .group_by(Task.technician_id, Task.assigned_date, Task.status)
            )
        ).all()
        for tech_id, day, status_value, total_count in rows:
            bucket = counts.setdefault((tech_id, day), {"assigned": 0, "completed": 0})
            if status_value != TaskStatus.CANCELLED:
                bucket["assigned"] += total_count
            if status_value == TaskStatus.COMPLETED:
                bucket["completed"] += total_count

    result = []
    for w in items:
        bucket = counts.get((w.technician_id, w.work_date), {"assigned": 0, "completed": 0})
        result.append(
            {
                "id": str(w.id),
                "is_void": w.is_void,
                "revision": w.revision,
                "technician_id": str(w.technician_id),
                "technician_name": w.technician.user.full_name if w.technician else "",
                "shift_kind": w.shift_kind, "work_date": w.work_date.isoformat(),
                "check_in_at": w.check_in_at.isoformat(),
                "check_out_at": w.check_out_at.isoformat() if w.check_out_at else None,
                "duration_minutes": w.duration_minutes,
                "status": w.status,
                "check_in_latitude": float(w.check_in_latitude) if w.check_in_latitude is not None else None,
                "check_in_longitude": float(w.check_in_longitude) if w.check_in_longitude is not None else None,
                "check_out_latitude": float(w.check_out_latitude) if w.check_out_latitude is not None else None,
                "check_out_longitude": float(w.check_out_longitude) if w.check_out_longitude is not None else None,
                "tasks_assigned": bucket["assigned"],
                "tasks_completed": bucket["completed"],
            }
        )

    return {
        "items": result,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 0,
    }


@router.get("/{id}")
async def get_workday_detail(
    id: str,
    current_user: User = Depends(get_current_panel_user),
    db: AsyncSession = Depends(get_db),
):
    workday_id = _parse_uuid(id, "id de la jornada")
    workday = (
        await db.execute(
            select(Workday)
            .options(selectinload(Workday.technician).selectinload(Technician.user))
            .where(Workday.id == workday_id)
        )
    ).scalars().first()
    if not workday:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")

    tasks = (
        await db.execute(
            select(Task).where(
                Task.technician_id == workday.technician_id,
                Task.assigned_date == workday.work_date,
            )
        )
    ).scalars().all()

    from app.schemas.task import TaskResponse

    return {
        "id": str(workday.id),
        "is_void": workday.is_void,
        "revision": workday.revision,
        "technician_id": str(workday.technician_id),
        "technician_name": workday.technician.user.full_name if workday.technician else "",
        "shift_kind": workday.shift_kind, "work_date": workday.work_date.isoformat(),
        "check_in_at": workday.check_in_at.isoformat(),
        "check_out_at": workday.check_out_at.isoformat() if workday.check_out_at else None,
        "duration_minutes": workday.duration_minutes,
        "status": workday.status,
        "check_in_latitude": float(workday.check_in_latitude) if workday.check_in_latitude is not None else None,
        "check_in_longitude": float(workday.check_in_longitude) if workday.check_in_longitude is not None else None,
        "tasks": [TaskResponse.model_validate(t).model_dump() for t in tasks],
    }


from pydantic import BaseModel, Field
from app.services.workday_admin import change

class WorkdayAction(BaseModel):
    revision: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=1000)

class WorkdayEdit(WorkdayAction):
    check_in_at: datetime
    check_out_at: datetime | None = None

@router.patch('/{id}')
async def edit_workday(id: uuid.UUID, body: WorkdayEdit, current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    return await change(db, id, body, current_user, 'EDIT')

@router.patch('/{id}/void')
async def void_workday(id: uuid.UUID, body: WorkdayAction, current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    return await change(db, id, body, current_user, 'VOID')

@router.patch('/{id}/restore')
async def restore_workday(id: uuid.UUID, body: WorkdayAction, current_user: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)):
    return await change(db, id, body, current_user, 'RESTORE')
