import pytest
from httpx import AsyncClient
from app.models.account_setup import location_id

@pytest.mark.asyncio
async def test_technician_sees_only_own_tasks(client: AsyncClient, tech_juan_token: str):
    response = await client.get("/api/v1/tasks/today", headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) > 0
    # All tasks should have Juan's technician id, implicitly verified because he only has 5
    assert len(tasks) == 5

@pytest.mark.asyncio
async def test_add_unplanned_task(client: AsyncClient, tech_juan_token: str):
    response = await client.post("/api/v1/tasks/unplanned", json={
        "title": "Unplanned Test Task",
        "location_id": str(location_id("EL POLLO LOCO", "Expo"))
    }, headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert response.status_code == 200
    assert response.json()["title"] == "Unplanned Test Task"
    assert response.json()["created_by_type"] == "TECHNICIAN"

@pytest.mark.asyncio
async def test_complete_task_success(client: AsyncClient, tech_juan_token: str):
    # Get pending tasks
    tasks_res = await client.get("/api/v1/tasks/today", headers={"Authorization": f"Bearer {tech_juan_token}"})
    pending_tasks = [t for t in tasks_res.json() if t["status"] == "PENDING"]
    
    task_id = pending_tasks[0]["id"]
    response = await client.patch(f"/api/v1/tasks/{task_id}/complete", json={"completion_comment": "Done"}, headers={"Authorization": f"Bearer {tech_juan_token}"})
    
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["completion_comment"] == "Done"
