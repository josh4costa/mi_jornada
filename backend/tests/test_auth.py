import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "Admin2024!"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "wrong"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, admin_token: str):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin"

@pytest.mark.asyncio
async def test_technician_cannot_access_admin(client: AsyncClient, tech_juan_token: str):
    response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 403
