import asyncio
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.config import settings
async def create_admin():
    if not settings.ADMIN_PASSWORD:
        raise SystemExit('Falta ADMIN_PASSWORD en .env')
    async with AsyncSessionLocal() as db:
        admin = User(username='admin', email='admin@pleg.com.mx', password_hash=get_password_hash(settings.ADMIN_PASSWORD), full_name='Administrador', role=UserRole.ADMIN)
        db.add(admin)
        await db.commit()
        print('Admin OK')
asyncio.run(create_admin())
