import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
import os

# Set testing mode before importing anything
os.environ["TESTING"] = "1"

from app.main import app
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base
from app.db.init_db import seed_demo_data
from app.core.security import create_access_token
from app.models.user import User

@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    app.state.limiter.reset()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        await seed_demo_data(db)
        
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

from sqlalchemy import select

@pytest_asyncio.fixture
async def admin_token(db):
    user = await db.scalar(select(User).where(User.username == "admin"))
    return create_access_token(user.id)

@pytest_asyncio.fixture
async def tech_juan_token(db):
    user = await db.scalar(select(User).where(User.username == "juan"))
    return create_access_token(user.id)

@pytest_asyncio.fixture
async def tech_pedro_token(db):
    user = await db.scalar(select(User).where(User.username == "pedro"))
    return create_access_token(user.id)
