"""app/api/v1/admin/technicians.py  —  CORREGIDO

Bug de contrato (rompia 4 pantallas): el front espera objetos PLANOS con full_name,
username, email, current_workday y today_tasks. El backend devolvia
TechnicianResponse con el usuario anidado y, en el detalle, {technician, workday, tasks}.
Resultado: nombres vacios en todos los selectores de Tareas / Jornadas / Reportes y
detalle del tecnico en blanco.

Ademas: GET admite ?include_inactive=, y la creacion valida contra correos duplicados
tanto en users como el numero de empleado.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user
from app.core.security import get_password_hash
from app.core.timezone import today_local
from app.db.session import get_db
from app.models.task import Task
from app.models.technician import Technician
from app.models.user import User, UserRole
from app.models.workday import Workday
from app.schemas.task import TaskResponse
from app.schemas.technician import TechnicianCreate
from app.services.audit import AuditAction, audit_event

router = APIRouter()


def _parse_uuid(value: str, label: str = "identificador") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"El {label} no es valido")


def _flat(tech: Technician) -> dict:
    return {
        "id": str(tech.id),
        "user_id": str(tech.user_id),
        "employee_number": tech.employee_number,
        "phone": tech.phone,
        "is_active": tech.is_active,
        "full_name": tech.user.full_name,
        "username": tech.user.username,
        "email": tech.user.email,
    }


@router.get("")
async def list_technicians(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Technician).options(selectinload(Technician.user))
    if not include_inactive:
        stmt = stmt.where(Technician.is_active == True)  # noqa: E712
    techs = (await db.execute(stmt)).scalars().all()
    return sorted((_flat(t) for t in techs), key=lambda t: t["full_name"])


@router.get("/{id}")
async def get_technician_detail(
    id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    tech_id = _parse_uuid(id, "id del tecnico")
    tech = (
        await db.execute(
            select(Technician).options(selectinload(Technician.user)).where(Technician.id == tech_id)
        )
    ).scalars().first()
    if not tech:
        raise HTTPException(status_code=404, detail="Tecnico no encontrado")

    today = today_local()
    workday = (
        await db.execute(
            select(Workday).where(Workday.technician_id == tech_id, Workday.work_date == today)
        )
    ).scalars().first()
    tasks = (
        await db.execute(
            select(Task)
            .where(Task.technician_id == tech_id, Task.assigned_date == today)
            .order_by(Task.scheduled_time.asc().nulls_last(), Task.created_at.asc())
        )
    ).scalars().all()

    data = _flat(tech)
    data["current_workday"] = (
        {
            "id": str(workday.id),
            "status": workday.status,
            "check_in_at": workday.check_in_at.isoformat(),
            "check_out_at": workday.check_out_at.isoformat() if workday.check_out_at else None,
            "duration_minutes": workday.duration_minutes,
            "check_in_latitude": float(workday.check_in_latitude) if workday.check_in_latitude is not None else None,
            "check_in_longitude": float(workday.check_in_longitude) if workday.check_in_longitude is not None else None,
        }
        if workday
        else None
    )
    data["today_tasks"] = [TaskResponse.model_validate(t).model_dump() for t in tasks]
    return data


@router.post("", status_code=201)
async def create_technician(
    body: TechnicianCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exists = (
        await db.execute(
            select(User).where((User.username == body.username) | (User.email == body.email))
        )
    ).scalars().first()
    if exists:
        raise HTTPException(status_code=409, detail="El nombre de usuario o email ya esta en uso")

    if body.employee_number:
        dup = (
            await db.execute(
                select(Technician).where(Technician.employee_number == body.employee_number)
            )
        ).scalars().first()
        if dup:
            raise HTTPException(status_code=409, detail="El numero de empleado ya esta en uso")

    user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        password_hash=get_password_hash(body.password),
        role=UserRole.TECHNICIAN,
    )
    db.add(user)
    await db.flush()

    tech = Technician(user_id=user.id, employee_number=body.employee_number, phone=body.phone)
    db.add(tech)
    await db.commit()

    await audit_event(
        db, AuditAction.USER_CREATED, user_id=current_user.id, entity_type="technicians", entity_id=tech.id
    )

    tech = (
        await db.execute(
            select(Technician).options(selectinload(Technician.user)).where(Technician.id == tech.id)
        )
    ).scalars().first()
    return _flat(tech)
