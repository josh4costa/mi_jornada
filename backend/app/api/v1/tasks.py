from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User
from app.models.workday import Workday, WorkdayStatus
from app.models.task import Task, CreatedByType, TaskStatus
from app.api.deps import get_current_technician_user
from app.schemas.task import TaskResponse, TaskComplete, UnplannedTaskCreate
from app.services.task import complete_task_service
from app.services.audit import audit_event, AuditAction
from app.core.timezone import today_local
import uuid

from app.api.v1.locations import selected_location

router = APIRouter()

@router.get("/today", response_model=list[TaskResponse])
async def get_today_tasks(
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    today = today_local()
    active = await db.scalar(select(Workday).where(Workday.technician_id == current_user.technician.id, Workday.status == WorkdayStatus.OPEN, Workday.is_void.is_(False)))
    stmt = select(Task).where(
        Task.technician_id == current_user.technician.id,
        Task.assigned_date.in_({today, active.work_date} if active else {today})
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    body: TaskComplete,
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    return await complete_task_service(db, task_id, current_user, body.completion_comment)

@router.post("/unplanned", response_model=TaskResponse)
async def create_unplanned_task(
    body: UnplannedTaskCreate,
    current_user: User = Depends(get_current_technician_user),
    db: AsyncSession = Depends(get_db)
):
    today = today_local()
    active = await db.scalar(select(Workday).where(Workday.technician_id == current_user.technician.id, Workday.status == WorkdayStatus.OPEN, Workday.is_void.is_(False)))
    location_id, location_name = await selected_location(db, body.location_id)
    task = Task(
        technician_id=current_user.technician.id,
        assigned_date=active.work_date if active else today,
        title=body.title,
        location_id=location_id,
        location_name=location_name,
        completion_comment=body.completion_comment,
        status=TaskStatus.PENDING,
        created_by=current_user.id,
        created_by_type=CreatedByType.TECHNICIAN
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    await audit_event(db, AuditAction.TASK_CREATED, user_id=current_user.id, entity_type="tasks", entity_id=task.id)
    return task
