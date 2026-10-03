import pytest
from datetime import timedelta
from app.core.timezone import now_utc
from app.models.refresh_token import RefreshToken
from app.models.account_setup import PasswordReset
from sqlalchemy import select, func
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.workday import Workday
from app.models.task import Task
from app.models.attendance import AttendanceEvent
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_removal_preserves_history_revokes_access_and_restores_inactive(client, db, admin_token, tech_pedro_token):
    headers = {'Authorization': f'Bearer {admin_token}'}
    person = await db.scalar(select(User).where(User.username == 'pedro'))
    tech = await db.scalar(select(Technician).where(Technician.user_id == person.id))
    refresh = RefreshToken(user_id=person.id, token_hash='test-session', expires_at=now_utc() + timedelta(days=1))
    reset = PasswordReset(user_id=person.id, token_hash='test-reset', credential_version=0, expires_at=now_utc() + timedelta(minutes=30))
    db.add_all([refresh, reset])
    await db.commit()
    counts = [await db.scalar(select(func.count()).select_from(model)) for model in (Workday, Task)]
    url = f'/api/v1/admin/users/{person.id}'
    result = await client.post(url + '/delete', headers=headers, json={'reason': 'Baja de personal'})
    assert result.status_code == 200, result.text
    assert result.json()['deleted_at'] and not result.json()['is_active']
    assert result.json()['technician']['reminders_enabled'] is False
    await db.refresh(tech)
    await db.refresh(refresh)
    await db.refresh(reset)
    assert refresh.is_revoked and reset.used_at is not None
    assert not tech.is_active
    assert counts == [await db.scalar(select(func.count()).select_from(model)) for model in (Workday, Task)]
    listing = await client.get('/api/v1/admin/users', headers=headers)
    assert str(person.id) not in [u['id'] for u in listing.json()['items']]
    listing = await client.get('/api/v1/admin/users?include_deleted=true', headers=headers)
    assert str(person.id) in [u['id'] for u in listing.json()['items']]
    assert (await client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {tech_pedro_token}'})).status_code == 401
    for path in ('', '/disable'):
        assert (await client.patch(url + path, headers=headers, json={'is_active': True})).status_code == 409
    assert (await client.post(url + '/delete', headers=headers, json={'reason': 'Duplicado'})).status_code == 409
    restored = await client.post(url + '/restore', headers=headers, json={'reason': 'Reingreso autorizado'})
    assert restored.status_code == 200, restored.text
    assert restored.json()['deleted_at'] is None and not restored.json()['is_active']
    await client.patch(url, headers=headers, json={'is_active': True})
    assert (await client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {tech_pedro_token}'})).status_code == 401
    events = (await db.scalars(select(AttendanceEvent).where(AttendanceEvent.entity_id == person.id))).all()
    assert [e.action for e in events] == ['TECHNICIAN_DELETED', 'TECHNICIAN_RESTORED']


@pytest.mark.asyncio
async def test_removal_permissions_open_workday_and_reason(client, db, admin_token, tech_juan_token):
    admin = {'Authorization': f'Bearer {admin_token}'}
    juan = await db.scalar(select(User).where(User.username == 'juan'))
    admin_user = await db.scalar(select(User).where(User.username == 'admin'))
    url = f'/api/v1/admin/users/{juan.id}/delete'
    assert (await client.post(url, headers=admin, json={'reason': '   '})).status_code == 422
    result = await client.post(url, headers=admin, json={'reason': 'Baja justificada'})
    assert result.status_code == 409 and 'abierta' in result.text
    await db.refresh(juan)
    assert juan.deleted_at is None and juan.is_active
    assert (await client.post(f'/api/v1/admin/users/{admin_user.id}/delete', headers=admin, json={'reason': 'Baja'})).status_code == 409
    for action in ('delete', 'restore'):
        assert (await client.post(f'/api/v1/admin/users/{juan.id}/{action}', headers={'Authorization': f'Bearer {tech_juan_token}'}, json={'reason': 'Baja'})).status_code == 403
    reader = User(username='reader', email='reader@example.com', full_name='Reader', role=UserRole.READ_ONLY, is_active=True, must_change_password=False, password_hash='unused')
    db.add(reader)
    await db.commit()
    for action in ('delete', 'restore'):
        assert (await client.post(f'/api/v1/admin/users/{juan.id}/{action}', headers={'Authorization': f'Bearer {create_access_token(reader.id)}'}, json={'reason': 'Baja'})).status_code == 403
