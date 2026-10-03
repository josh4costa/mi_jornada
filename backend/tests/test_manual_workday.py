from datetime import timedelta
import pytest
from sqlalchemy import select, func
from app.models import User, Technician, Workday, UserRole
from app.models.attendance import AttendanceIncident, AttendanceEvent
from app.core.timezone import today_local
from app.core.security import create_access_token


async def person(db):
    user = User(username='manual-test', email='manual@example.com', full_name='Manual Test', role=UserRole.TECHNICIAN, password_hash='unused', must_change_password=False)
    db.add(user); await db.flush()
    tech = Technician(user_id=user.id)
    db.add(tech); await db.commit()
    return tech, user


@pytest.mark.asyncio
async def test_manual_creation_history_reconciliation_and_duplicate(client, db, admin_token):
    tech, user = await person(db)
    day = today_local() - timedelta(days=3)
    incident = AttendanceIncident(technician_id=tech.id, work_date=day, kind='MISSING_ENTRY', status='PENDING', reason='Sin entrada')
    db.add(incident); await db.commit()
    h = {'Authorization': 'Bearer ' + admin_token}
    body = dict(technician_id=str(tech.id), check_in_at=f'{day}T09:00:00', check_out_at=f'{day}T18:00:00', reason='Olvidó registrar; asistencia verificada')
    result = await client.post('/api/v1/admin/workdays', json=body, headers=h)
    assert result.status_code == 201, result.text
    assert result.json()['duration_minutes'] == 540
    await db.refresh(incident)
    assert incident.status == 'JUSTIFIED' and incident.reviewed_by
    events = (await client.get('/api/v1/attendance/events/' + result.json()['id'], headers=h)).json()
    assert events[0]['action'] == 'WORKDAY_CREATE' and events[0]['actor_name'] and events[0]['details']['before'] is None
    assert (await client.post('/api/v1/admin/workdays', json=body, headers=h)).status_code == 409
    row = await db.scalar(select(Workday).where(Workday.technician_id == tech.id))
    assert row.check_in_latitude is None


@pytest.mark.asyncio
async def test_manual_permissions_validation_and_overlap(client, db, admin_token, tech_juan_token):
    tech, user = await person(db)
    day = today_local() - timedelta(days=4)
    h = {'Authorization': 'Bearer ' + admin_token}
    body = dict(technician_id=str(tech.id), check_in_at=f'{day}T22:00:00', check_out_at=f'{day + timedelta(days=1)}T08:00:00', shift_kind='NIGHT', reason='Entrada nocturna omitida')
    assert (await client.post('/api/v1/admin/workdays', json=body, headers={'Authorization': 'Bearer ' + tech_juan_token})).status_code == 403
    user.role = UserRole.READ_ONLY; await db.commit()
    assert (await client.post('/api/v1/admin/workdays', json=body, headers={'Authorization': 'Bearer ' + create_access_token(user.id)})).status_code == 403
    for change in [dict(reason='   '), dict(check_out_at=f'{day}T21:00:00'), dict(check_in_at=f'{today_local()+timedelta(days=1)}T09:00:00', check_out_at=None)]:
        assert (await client.post('/api/v1/admin/workdays', json={**body, **change}, headers=h)).status_code == 422
    result = await client.post('/api/v1/admin/workdays', json=body, headers=h)
    assert result.status_code == 201 and result.json()['duration_minutes'] == 600, result.text
    overlapping = {**body, 'shift_kind': 'DAY', 'check_in_at': f'{day+timedelta(days=1)}T07:00:00', 'check_out_at': f'{day+timedelta(days=1)}T18:00:00'}
    assert (await client.post('/api/v1/admin/workdays', json=overlapping, headers=h)).status_code == 409


@pytest.mark.asyncio
async def test_open_manual_journey_and_confirmed_absence_preserved(client, db, admin_token):
    tech, user = await person(db)
    day = today_local() - timedelta(days=2)
    db.add(AttendanceIncident(technician_id=tech.id, work_date=day, kind='MISSING_ENTRY', status='UNJUSTIFIED', reason='Revisada'))
    await db.commit()
    body = dict(technician_id=str(tech.id), check_in_at=f'{day}T09:00:00', reason='Entrada validada por supervisor')
    h = {'Authorization': 'Bearer ' + admin_token}
    result = await client.post('/api/v1/admin/workdays', json=body, headers=h)
    assert result.status_code == 201 and result.json()['status'] == 'OPEN', result.text
    assert (await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == tech.id))).status == 'UNJUSTIFIED'
    assert (await client.post('/api/v1/admin/workdays', json={**body, 'check_in_at': f'{day+timedelta(days=1)}T09:00:00'}, headers=h)).status_code == 409
