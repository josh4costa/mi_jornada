import enum
import uuid
import os
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timezone import now_utc


class AuditAction(str, enum.Enum):
    LOGIN = 'LOGIN'
    CHECK_IN = 'CHECK_IN'
    CHECK_OUT = 'CHECK_OUT'
    TASK_CREATED = 'TASK_CREATED'
    TASK_COMPLETED = 'TASK_COMPLETED'
    TASK_CANCELLED = 'TASK_CANCELLED'
    USER_CREATED = 'USER_CREATED'
    USER_DISABLED = 'USER_DISABLED'


def _json_type():
    """Use JSONB in PostgreSQL, JSON in SQLite (for tests)."""
    if os.environ.get("TESTING") == "1":
        return JSON()
    try:
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB(astext_type=Text())
    except ImportError:
        return JSON()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[AuditAction]
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(_json_type(), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
