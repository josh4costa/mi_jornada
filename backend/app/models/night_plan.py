import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Boolean, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timezone import now_utc


class NightPlan(Base):
    __tablename__ = 'night_plans'
    __table_args__ = (Index('uq_night_plan_active', 'technician_id', 'work_date', unique=True,
        postgresql_where=text("status IN ('PENDING', 'APPROVED')"), sqlite_where=text("status IN ('PENDING', 'APPROVED')")),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('technicians.id'), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    reminder_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replaces_day: Mapped[bool] = mapped_column(Boolean, default=False)
    rest_next_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default='PENDING')
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
