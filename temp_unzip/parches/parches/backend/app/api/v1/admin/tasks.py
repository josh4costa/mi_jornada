"""app/api/v1/admin/tasks.py  —  CORREGIDO

 1. BUG FUNCIONAL GRANDE: el POST ignoraba body.assigned_date y forzaba today_local(),
    asi que el admin NO podia programar tareas para dias futuros (el formulario del
    front si manda la fecha). Ahora se respeta.
    -> Requiere que TaskCreate incluya assigned_date: date (ver nota en el informe).
 2. El front filtra con ?date= y el backend leia ?task_date=: el filtro se ignoraba
    en silencio. Ahora se acepta el alias "date".
 3. PATCH hacia setattr() ciego: se podia escribir cualquier atributo (incluido
    created_by o campos inexistentes como "notes", que se perdian sin avisar).
    Ahora hay lista blanca y error claro.
 4. No se podia cancelar dos veces ni reasignar una tarea completada sin control.
 5. Se valida que el tecnico exista y este activo antes de asignarle trabajo.
"""
import uuid
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user
from app.core.timezone import today_local
from app.db.session import get_db
from app.models.task import CreatedByType, Task, TaskStatus
from app.models.technician import Technician
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.audit import AuditAction, audit_event

router = APIRouter()

EDITABLE_FIELDS = {
    "technician_id",
    "assigned_date",
    "title",
    "description",
    "location_name",
    "scheduled_time",
    "priority",
    "external_service_order_url",
}


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"El {label} no es valido")


async def _get_active_technician(db: AsyncSession, technician_id) -> Technician:
    tech = await db.get(Technician, _parse_uuid(technician_id, "id del tecnico"))
    if not tech or not tech.is_active:
        raise HTTPException(status_code=404, detail="Tecnico no encontrado o inactivo")
    return tech


async def _get_task(db: AsyncSession, task_id: str) -> Task:
    task = await db.get(Task, _parse_uuid(task_id, "id de la tarea"))
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task


@router.post("", response_model=TaskResponse, status_code=201)
async def assign_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    tech = await _get_active_technician(db, body.technician_id)
    assigned_date = getattr(body, "assigned_date", None) or today_local()

    task = Task(
        technician_id=tech.id,
        assigned_date=assigned_date,
        title=body.title,
        description=body.description,
        location_name=body.location_name,
        scheduled_time=body.scheduled_time,
        priority=body.priority,
        created_by=current_user.id,
        created_by_type=CreatedByType.ADMIN,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    await audit_event(
        db, AuditAction.TASK_CREATED, user_id=current_user.id, entity_type="tasks", entity_id=task.id
    )
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    technician_id: Optional[str] = None,
    task_date: Optional[date_type] = Query(None, alias="date"),
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    status: Optional[TaskStatus] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task)
    if technician_id:
        stmt = stmt.where(Task.technician_id == _parse_uuid(technician_id, "id del tecnico"))
    if task_date:
        stmt = stmt.where(Task.assigned_date == task_date)
    if date_from:
        stmt = stmt.where(Task.assigned_date >= date_from)
    if date_to:
        stmt = stmt.where(Task.assigned_date <= date_to)
    if status:
        stmt = stmt.where(Task.status == status)

    stmt = stmt.order_by(
        Task.assigned_date.desc(),
        Task.scheduled_time.asc().nulls_last(),
        Task.created_at.asc(),
    )
    return (await db.execute(stmt)).scalars().all()


@router.patch("/{id}", response_model=TaskResponse)
async def edit_task(
    id: str,
    body: TaskUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_task(db, id)

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Solo se pueden editar tareas pendientes",
        )

    update_data = body.model_dump(exclude_unset=True)
    unknown = set(update_data) - EDITABLE_FIELDS
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Campos no editables: {', '.join(sorted(unknown))}"
        )

    if "technician_id" in update_data and update_data["technician_id"]:
        tech = await _get_active_technician(db, update_data["technician_id"])
        update_data["technician_id"] = tech.id

    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/{id}/cancel", response_model=TaskResponse)
async def cancel_task(
    id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_task(db, id)
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="No se puede cancelar una tarea ya completada")
    if task.status == TaskStatus.CANCELLED:
        return task

    task.status = TaskStatus.CANCELLED
    await db.commit()
    await db.refresh(task)

    await audit_event(
        db, AuditAction.TASK_CANCELLED, user_id=current_user.id, entity_type="tasks", entity_id=task.id
    )
    return task
