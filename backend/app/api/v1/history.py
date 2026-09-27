from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.user import User
from app.models.workday import Workday
from app.models.task import Task, TaskStatus
from app.api.deps import get_current_technician_user
from app.schemas.workday import WorkdayResponse
import math
import uuid

router = APIRouter()


@router.get("/workdays")
async def get_history_workdays(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * size
    technician_id = current_user.technician.id

    stmt = (
        select(Workday)
        .where(Workday.is_void.is_(False), Workday.technician_id == technician_id)
        .order_by(Workday.work_date.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    count_stmt = select(func.count(Workday.id)).where(Workday.is_void.is_(False), Workday.technician_id == technician_id)
    total = await db.scalar(count_stmt)

    # Build enriched items with task counts
    enriched = []
    for w in items:
        tasks_total = await db.scalar(
            select(func.count(Task.id)).where(
                Task.technician_id == technician_id,
                Task.assigned_date == w.work_date
            )
        )
        tasks_completed = await db.scalar(
            select(func.count(Task.id)).where(
                Task.technician_id == technician_id,
                Task.assigned_date == w.work_date,
                Task.status == TaskStatus.COMPLETED
            )
        )
        wd_data = WorkdayResponse.model_validate(w).model_dump()
        wd_data["tasks_count"] = tasks_total or 0
        wd_data["completed_tasks_count"] = tasks_completed or 0
        enriched.append(wd_data)

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total and total > 0 else 0
    }


@router.get("/workdays/{id}")
async def get_workday_detail(
    id: uuid.UUID,
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Workday).where(Workday.is_void.is_(False), 
        Workday.id == id,
        Workday.technician_id == current_user.technician.id
    )
    result = await db.execute(stmt)
    workday = result.scalars().first()

    if not workday:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")

    tasks_stmt = select(Task).where(
        Task.technician_id == current_user.technician.id,
        Task.assigned_date == workday.work_date
    )
    tasks_result = await db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    from app.schemas.task import TaskResponse
    return {
        "workday": WorkdayResponse.model_validate(workday),
        "tasks": [TaskResponse.model_validate(t) for t in tasks]
    }
