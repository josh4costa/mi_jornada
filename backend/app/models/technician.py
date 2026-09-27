import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timezone import now_utc

class Technician(Base):
    __tablename__ = "technicians"
    __table_args__ = (Index("uq_technician_reminder_phone", "phone", unique=True, postgresql_where=text("reminders_enabled = true"), sqlite_where=text("reminders_enabled = 1")),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    employee_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user = relationship("User", back_populates="technician")
    workdays = relationship("Workday", back_populates="technician")
    tasks = relationship("Task", back_populates="technician")
