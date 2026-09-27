import enum
import uuid
from datetime import datetime, date, time
from sqlalchemy import String, Date, Time, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timezone import now_utc

class TaskStatus(str, enum.Enum):
    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class TaskPriority(str, enum.Enum):
    NORMAL = 'NORMAL'
    HIGH = 'HIGH'

class CreatedByType(str, enum.Enum):
    ADMIN = 'ADMIN'
    TECHNICIAN = 'TECHNICIAN'

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("technicians.id"), index=True)
    assigned_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_locations.id"), nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(default=TaskPriority.NORMAL)
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.PENDING)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_by_type: Mapped[CreatedByType]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_service_order_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    technician = relationship("Technician", back_populates="tasks")
