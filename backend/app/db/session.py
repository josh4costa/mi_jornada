"""app/db/session.py  —  CORREGIDO

 - pool_pre_ping: evita "connection was closed" cuando Postgres reinicia o
   la conexion muere por inactividad (muy comun en VPS).
 - pool_recycle y tamano de pool explicitos.
 - StaticPool en tests para que la SQLite en memoria sea la misma en todas las conexiones.
"""
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings

TESTING = os.environ.get("TESTING") == "1"

if TESTING:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=10,
        max_overflow=20,
    )

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
