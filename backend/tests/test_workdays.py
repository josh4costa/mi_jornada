import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_today_workday_status_open(client: AsyncClient, tech_juan_token: str):
    # Juan has an open workday from seed
    response = await client.get("/api/v1/workdays/today", headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "WORKING"

@pytest.mark.asyncio
async def test_today_workday_status_closed(client: AsyncClient, tech_pedro_token: str):
    # Pedro has a closed workday from seed
    response = await client.get("/api/v1/workdays/today", headers={"Authorization": f"Bearer {tech_pedro_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "FINISHED"

@pytest.mark.asyncio
async def test_check_in_duplicate(client: AsyncClient, tech_juan_token: str):
    # Juan already has an open workday
    response = await client.post("/api/v1/workdays/check-in", json={}, headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 409

@pytest.mark.asyncio
async def test_check_out_success(client: AsyncClient, tech_juan_token: str):
    # Juan checks out
    response = await client.post("/api/v1/workdays/check-out", json={"early_exit_reason": "Salida de prueba"}, headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"
    assert response.json()["duration_minutes"] is not None

@pytest.mark.asyncio
async def test_check_out_without_check_in(client: AsyncClient, tech_pedro_token: str):
    # Pedro's workday is already closed
    response = await client.post("/api/v1/workdays/check-out", json={"early_exit_reason": "Salida de prueba"}, headers={"Authorization": f"Bearer {tech_pedro_token}"})
    assert response.status_code == 400
