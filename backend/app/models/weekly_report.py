import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Integer, String, JSON, LargeBinary, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timezone import now_utc


class WeeklyReportConfig(Base):
    __tablename__ = 'weekly_report_config'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    first_send_date: Mapped[date] = mapped_column(Date, default=lambda: date(2026, 9, 28))
    to_emails: Mapped[list] = mapped_column(JSON, default=lambda: ['oscar.moncada@pleg.com.mx'])
    cc_emails: Mapped[list] = mapped_column(JSON, default=lambda: ['josue.acosta@pleg.com.mx', 'lupita.carrizales@pleg.com.mx'])
    revision: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class WeeklyReportRun(Base):
    __tablename__ = 'weekly_report_runs'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scheduled_date: Mapped[date] = mapped_column(Date, unique=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    to_emails: Mapped[list] = mapped_column(JSON)
    cc_emails: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(25), default='READY')
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    filename: Mapped[str] = mapped_column(String(100))
    subject: Mapped[str] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
