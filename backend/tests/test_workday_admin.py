from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, func
from app.models import Workday, Task, User, Technician
from app.models.attendance import AttendanceEvent
from app.core.timezone import today_local


@pytest.mark.asyncio
async def test_edit_annul_restore_preserves_tasks_and_reports(client, db, admin_token, tech_pedro_token):
    h = {'Authorization': f'Bearer {admin_token}'}
    user = await db.scalar(select(User).where(User.username == 'pedro'))
    tech = await db.scalar(select(Technician).where(Technician.user_id == user.id))
    row = await db.scalar(select(Workday).where(Workday.technician_id == tech.id))
    id, day = str(row.id), str(row.work_date)
    tasks_before = await db.scalar(select(func.count(Task.id)))
    # 09:00 to 13:00 local, on a past date to avoid clock-dependent future times.
    old_day = today_local() - timedelta(days=10)
    row.work_date = old_day
    row.check_in_at = datetime.combine(old_day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=15)
    row.check_out_at = row.check_in_at + timedelta(hours=5)
    await db.commit()
    payload = {'revision': 0, 'reason': 'Corregir registro de prueba', 'check_in_at': f'{old_day}T09:00:00', 'check_out_at': f'{old_day}T13:00:00'}
    denied = await client.patch('/api/v1/admin/workdays/' + id, json=payload, headers={'Authorization': f'Bearer {tech_pedro_token}'})
    assert denied.status_code == 403
    result = await client.patch('/api/v1/admin/workdays/' + id, json=payload, headers=h)
    assert result.status_code == 200, result.text
    assert result.json()['duration_minutes'] == 240
    stale = await client.patch('/api/v1/admin/workdays/' + id, json=payload, headers=h)
    assert stale.status_code == 409
    voided = await client.patch('/api/v1/admin/workdays/' + id + '/void', json={'revision': 1, 'reason': 'Prueba eliminada'}, headers=h)
    assert voided.status_code == 200, voided.text
    listing = await client.get('/api/v1/admin/workdays', headers=h)
    assert id not in [w['id'] for w in listing.json()['items']]
    all_rows = await client.get('/api/v1/admin/workdays?include_void=true', headers=h)
    assert next(w for w in all_rows.json()['items'] if w['id'] == id)['is_void']
    report = await client.get('/api/v1/admin/reports?technician_id=' + str(tech.id), headers=h)
    assert report.json()[0]['days_worked'] == 0
    restored = await client.patch('/api/v1/admin/workdays/' + id + '/restore', json={'revision': 2, 'reason': 'Restaurar prueba'}, headers=h)
    assert restored.status_code == 200
    report = await client.get('/api/v1/admin/reports?technician_id=' + str(tech.id), headers=h)
    assert report.json()[0]['total_minutes'] == 240
    assert await db.scalar(select(func.count(Task.id))) == tasks_before
    events = (await client.get('/api/v1/attendance/events/' + id, headers=h)).json()
    assert [e['action'] for e in events] == ['WORKDAY_EDIT', 'WORKDAY_VOID', 'WORKDAY_RESTORE']
    assert events[0]['details']['before']['check_out_at'] != events[0]['details']['after']['check_out_at']
    assert events[0]['actor_name']


@pytest.mark.asyncio
async def test_void_open_allows_new_entry_but_blocks_restore_conflict(client, db, admin_token, tech_juan_token):
    h = {'Authorization': f'Bearer {admin_token}'}
    th = {'Authorization': f'Bearer {tech_juan_token}'}
    today = (await client.get('/api/v1/workdays/today', headers=th)).json()['workday']
    id = today['id']
    result = await client.patch('/api/v1/admin/workdays/' + id + '/void', headers=h, json={'revision': 0, 'reason': 'Eliminar prueba abierta'})
    assert result.status_code == 200
    result = await client.get('/api/v1/workdays/today', headers=th)
    assert result.json()['status'] == 'NOT_STARTED'
    new = await client.post('/api/v1/workdays/check-in', headers=th, json={})
    assert new.status_code == 200
    result = await client.patch('/api/v1/admin/workdays/' + id + '/restore', headers=h, json={'revision': 1, 'reason': 'Conflicto de prueba'})
    assert result.status_code == 409
    assert (await client.get('/api/v1/workdays/today', headers=th)).json()['workday']['id'] == new.json()['id']


@pytest.mark.asyncio
async def test_invalid_corrections_do_not_mutate(client, admin_token):
    h = {'Authorization': f'Bearer {admin_token}'}
    row = (await client.get('/api/v1/admin/workdays', headers=h)).json()['items'][0]
    for payload in [
        {'reason': ' ', 'check_in_at': row['check_in_at'], 'check_out_at': row['check_out_at']},
        {'reason': 'Fecha incorrecta', 'check_in_at': '2099-01-01T09:00', 'check_out_at': None},
        {'reason': 'Salida anterior', 'check_in_at': row['check_in_at'], 'check_out_at': '2000-01-01T00:00'},
    ]:
        result = await client.patch('/api/v1/admin/workdays/' + row['id'], headers=h, json={'revision': 0, **payload})
        assert result.status_code == 422
    result = await client.get('/api/v1/admin/workdays/' + row['id'], headers=h)
    assert result.json()['revision'] == 0
    assert result.json()['check_in_at'] == row['check_in_at']
