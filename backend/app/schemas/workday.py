from typing import Optional
from uuid import UUID
from datetime import datetime, date
from pydantic import BaseModel, Field
from app.models.workday import WorkdayStatus

class WorkdayLocation(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracy: Optional[float] = Field(default=None, ge=0, le=999999.99, allow_inf_nan=False)

class WorkdayCheckin(WorkdayLocation):
    night_plan_id: UUID | None = None

class WorkdayCheckout(WorkdayLocation):
    early_exit_reason: Optional[str] = Field(default=None, max_length=1000)

class WorkdayResponse(BaseModel):
    id: UUID
    technician_id: UUID
    work_date: date
    shift_kind: str = "DAY"
    check_in_at: datetime
    check_in_latitude: Optional[float] = None
    check_in_longitude: Optional[float] = None
    check_in_accuracy: Optional[float] = None
    check_out_at: Optional[datetime] = None
    check_out_latitude: Optional[float] = None
    check_out_longitude: Optional[float] = None
    check_out_accuracy: Optional[float] = None
    duration_minutes: Optional[int] = None
    status: WorkdayStatus
    
    model_config = {"from_attributes": True}
