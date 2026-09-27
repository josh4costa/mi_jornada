import asyncio
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(username='admin', email='admin@pleg.com.mx', password_hash=get_password_hash('Admin2024!'), full_name='Administrador', role=UserRole.ADMIN)
        db.add(admin)
        await db.commit()
        print('Admin OK')
asyncio.run(create_admin())
