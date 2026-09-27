from datetime import timedelta
from sqlalchemy import select, or_, and_
from app.models.night_plan import NightPlan


async def day_exception(db, technician_id, day, include_pending=False):
    """Declarations suppress reminders; only approval changes expected attendance."""
    statuses = ['APPROVED', 'PENDING'] if include_pending else ['APPROVED']
    return await db.scalar(select(NightPlan).where(
        NightPlan.technician_id == technician_id, NightPlan.status.in_(statuses),
        or_(and_(NightPlan.work_date == day, NightPlan.replaces_day.is_(True)),
            and_(NightPlan.work_date == day - timedelta(days=1), NightPlan.rest_next_day.is_(True), NightPlan.status == 'APPROVED'))))
