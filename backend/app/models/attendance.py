import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, ForeignKey, UniqueConstraint, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timezone import now_utc


class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('technicians.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default='PENDING')
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AttendanceIncident(Base):
    __tablename__ = 'attendance_incidents'
    __table_args__ = (UniqueConstraint('technician_id', 'work_date', 'kind', name='uq_attendance_incident'),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('technicians.id'), index=True)
    workday_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('workdays.id'), nullable=True)
    work_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(1000), default='')
    status: Mapped[str] = mapped_column(String(20), default='PENDING')
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AttendanceEvent(Base):
    __tablename__ = 'attendance_events'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    entity_id: Mapped[uuid.UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ReminderDelivery(Base):
    __tablename__ = 'reminder_deliveries'
    __table_args__ = (UniqueConstraint('technician_id', 'work_date', 'kind', name='uq_reminder_day'),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('technicians.id'), index=True)
    work_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='CLAIMED')
    provider_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceScan(Base):
    __tablename__ = 'attendance_scan'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_day: Mapped[date | None] = mapped_column(Date, nullable=True)
