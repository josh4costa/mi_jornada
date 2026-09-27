from typing import Optional
from uuid import UUID
from datetime import datetime, date, time
from pydantic import BaseModel
from app.models.task import TaskStatus, TaskPriority, CreatedByType

class TaskCreate(BaseModel):
    technician_id: UUID
    assigned_date: date
    title: str
    description: Optional[str] = None
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None
    scheduled_time: Optional[time] = None
    priority: TaskPriority = TaskPriority.NORMAL

class UnplannedTaskCreate(BaseModel):
    title: str
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None
    completion_comment: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None
    scheduled_time: Optional[time] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None

class TaskComplete(BaseModel):
    completion_comment: Optional[str] = None

class TaskResponse(BaseModel):
    id: UUID
    technician_id: UUID
    assigned_date: date
    title: str
    description: Optional[str] = None
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None
    scheduled_time: Optional[time] = None
    priority: TaskPriority
    status: TaskStatus
    created_by: UUID
    created_by_type: CreatedByType
    completed_at: Optional[datetime] = None
    completion_comment: Optional[str] = None
    external_service_order_url: Optional[str] = None
    
    model_config = {"from_attributes": True}
