import pytest


@pytest.mark.asyncio
async def test_personnel_profile_edit_and_conflict_are_atomic(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    listing = await client.get('/api/v1/admin/users?role=TECHNICIAN', headers=headers)
    people = listing.json()['items']
    assert people and all(p['role'] == 'TECHNICIAN' and p['technician'] for p in people)
    first, second = people[:2]
    url = '/api/v1/admin/users/' + first['id']
    result = await client.patch(url, headers=headers, json={"full_name": "Nombre editado", "phone": " 8112345678 ", "employee_number": "EDIT-01"})
    assert result.status_code == 200, result.text
    assert result.json()['technician']['id'] == first['technician']['id']
    assert result.json()['technician']['phone'] == '8112345678'
    conflict = await client.patch('/api/v1/admin/users/' + second['id'], headers=headers, json={"full_name": "No debe guardarse", "employee_number": "EDIT-01"})
    assert conflict.status_code == 409
    unchanged = await client.get('/api/v1/admin/users/' + second['id'], headers=headers)
    assert unchanged.json()['full_name'] == second['full_name']
    cleared = await client.patch(url, headers=headers, json={"phone": None, "employee_number": None})
    assert cleared.status_code == 200
    assert cleared.json()['technician']['phone'] is None
    assert cleared.json()['technician']['employee_number'] is None


@pytest.mark.asyncio
async def test_personnel_creation_and_access(client, admin_token, tech_juan_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    result = await client.post('/api/v1/admin/users', headers=headers, json={"username": "newperson", "email": "new@example.com", "full_name": "New Person", "password": "SafePass123!", "role": "TECHNICIAN", "phone": "1234567890", "employee_number": "NEW-01"})
    assert result.status_code == 201, result.text
    assert result.json()['technician']['employee_number'] == 'NEW-01'
    admins = await client.get('/api/v1/admin/users?role=ADMIN', headers=headers)
    assert all(p['role'] == 'ADMIN' for p in admins.json()['items'])
    denied = await client.get('/api/v1/admin/users', headers={"Authorization": f"Bearer {tech_juan_token}"})
    assert denied.status_code == 403
