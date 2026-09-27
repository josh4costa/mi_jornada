from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.models.technician import Technician


async def sync_technician_profile(db: AsyncSession, user: User) -> Technician | None:
    """Keep the operational profile consistent without deleting historical records."""
    await db.flush()
    profile = await db.scalar(select(Technician).where(Technician.user_id == user.id))
    active = user.role == UserRole.TECHNICIAN and user.is_active
    if profile is None and user.role == UserRole.TECHNICIAN:
        profile = Technician(user_id=user.id, is_active=active)
        db.add(profile)
    elif profile is not None:
        profile.is_active = active
    return profile
