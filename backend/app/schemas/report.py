from typing import Optional
from fastapi import Request
from pydantic import BaseModel

class TechnicianStats(BaseModel):
    id: str
    full_name: str
    status: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    tasks_completed: int = 0
    tasks_pending: int = 0

class DashboardResponse(BaseModel):
    working_now: int
    not_started: int
    finished: int
    tasks_completed: int
    tasks_pending: int
    technicians: list[TechnicianStats]
