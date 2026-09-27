from fastapi import APIRouter
from app.api.v1 import auth, workdays, tasks, history, attendance
from app.api.v1.admin import dashboard, technicians, tasks as admin_tasks, workdays as admin_workdays, reports, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workdays.router, prefix="/workdays", tags=["workdays"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(history.router, prefix="/history", tags=["history"])

api_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["admin-dashboard"])
api_router.include_router(technicians.router, prefix="/admin/technicians", tags=["admin-technicians"])
api_router.include_router(admin_tasks.router, prefix="/admin/tasks", tags=["admin-tasks"])
api_router.include_router(admin_workdays.router, prefix="/admin/workdays", tags=["admin-workdays"])
api_router.include_router(reports.router, prefix="/admin/reports", tags=["admin-reports"])
api_router.include_router(users.router, prefix="/admin/users", tags=["admin-users"])

api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
from app.api.v1.admin import report_mail
api_router.include_router(report_mail.router, prefix="/admin/report-mail", tags=["admin-reports"])

from app.api.v1 import passwords, locations
api_router.include_router(passwords.router, prefix="/auth", tags=["auth"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])

from app.api.v1 import night_plans
api_router.include_router(night_plans.router, prefix="/night-plans", tags=["night-plans"])
