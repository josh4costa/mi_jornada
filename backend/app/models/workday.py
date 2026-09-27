import enum
import uuid
from datetime import datetime, date
from sqlalchemy import Date, DateTime, Numeric, Integer, Boolean, ForeignKey, Index, text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timezone import now_utc

class WorkdayStatus(str, enum.Enum):
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'

class Workday(Base):
    __tablename__ = "workdays"
    __table_args__ = (
        Index("ix_workdays_technician_date", "technician_id", "work_date"),
        Index('uq_workday_date_shift', 'technician_id', 'work_date', 'shift_kind', unique=True,
              postgresql_where=text('is_void = false'), sqlite_where=text('is_void = false')),
        Index("uq_workday_open_per_technician", "technician_id", unique=True,
              postgresql_where=text("status='OPEN' AND is_void = false"), sqlite_where=text("status='OPEN' AND is_void = false")),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("technicians.id"))
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift_kind: Mapped[str] = mapped_column(String(10), default='DAY', server_default='DAY')
    night_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('night_plans.id'), nullable=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_in_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_in_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_in_accuracy: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_out_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_out_accuracy: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_void: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[WorkdayStatus] = mapped_column(default=WorkdayStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    technician = relationship("Technician", back_populates="workdays")
