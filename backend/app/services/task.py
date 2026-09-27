import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from app.models.task import Task, TaskStatus, CreatedByType
from app.models.user import User
from app.core.timezone import now_utc, today_local
from app.services.audit import audit_event, AuditAction
from app.services.webhook import enqueue_webhook

async def complete_task_service(db: AsyncSession, task_id: uuid.UUID, user: User, comment: str = None):
    stmt = select(Task).where(Task.id == task_id).with_for_update()
    res = await db.execute(stmt)
    task = res.scalars().first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
    if user.role == "TECHNICIAN" and task.technician_id != user.technician.id:
        raise HTTPException(status_code=403, detail="No puedes completar tareas de otro técnico")
        
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="La tarea ya está completada")
    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=409, detail="Solo se pueden completar tareas pendientes")
        
    task.status = TaskStatus.COMPLETED
    task.completed_at = now_utc()
    task.completion_comment = comment
    enqueue_webhook(db, "TASK_COMPLETED", {"task_id": str(task.id), "technician_id": str(task.technician_id), "at": task.completed_at.isoformat()})
    
    await db.commit()
    await db.refresh(task)
    
    await audit_event(db, AuditAction.TASK_COMPLETED, user_id=user.id, entity_type="tasks", entity_id=task.id)
    return task
