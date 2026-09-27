import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timezone import now_utc


class PasswordReset(Base):
    __tablename__ = 'password_resets'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    credential_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class TaskLocation(Base):
    __tablename__ = 'task_locations'
    __table_args__ = (UniqueConstraint('group_name', 'name'),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_name: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)


INITIAL_LOCATIONS = {
    'EL POLLO LOCO': ['Expo', 'Juárez', 'Cadereyta', 'Linares', 'Montemorelos', 'Allende', 'Santiago', 'Las Quintas', 'Eloy Cavazos', 'Pablo Livas', 'Guerrero', 'Carrizo', 'Aeropuerto', 'San Roque'],
    'TACO PALENQUE': ['Santiago', 'Contry', 'Centrito'],
    'Otras ubicaciones': ['TP Cocina', 'Oficinas Centrales'],
}


def location_id(group, name):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'mi-jornada/location/' + group + '/' + name)
