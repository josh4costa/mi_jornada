from datetime import datetime, timedelta, timezone, date
import uuid
import httpx
import pytest
from sqlalchemy import select
from app.core.security import create_access_token
from app.core.timezone import today_local, now_utc
from app.models import User, Technician, Workday, WorkdayStatus, Task, TaskStatus, WebhookDelivery
from app.api.v1.admin.reports import _avg_local_time
from app.core.config import settings
from app.services.webhook import deliver_one

pytestmark = pytest.mark.asyncio


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def test_refresh_rotation_and_reuse(client):
    login = await client.post('/api/v1/auth/login', json={"username_or_email": "admin", "password": "Admin2024!"})
    old = login.json()['refresh_token']
    refresh = await client.post('/api/v1/auth/refresh', json={"refresh_token": old})
    assert refresh.status_code == 200
    assert 'x-ratelimit-limit' in refresh.headers
    new = refresh.json()
    assert new['refresh_token'] != old
    assert (await client.get('/api/v1/auth/me', headers=bearer(new['access_token']))).status_code == 200
    assert (await client.get('/api/v1/auth/me', headers=bearer(new['refresh_token']))).status_code == 401
    assert (await client.post('/api/v1/auth/refresh', json={"refresh_token": old})).status_code == 401
    assert (await client.post('/api/v1/auth/refresh', json={"refresh_token": new['refresh_token']})).status_code == 401


async def test_user_creation_and_role_changes_create_profile(client, db, admin_token):
    response = await client.post('/api/v1/admin/users', headers=bearer(admin_token), json={
        'username': 'newtech', 'email': 'newtech@example.com', 'full_name': 'Nuevo Técnico',
        'password': 'StrongPass123!', 'role': 'TECHNICIAN',
    })
    assert response.status_code == 201
    uid = response.json()['id']
    assert response.json()['must_change_password'] is True
    setup_token = create_access_token(uid)
    changed = await client.post('/api/v1/auth/change-password', headers=bearer(setup_token), json={'current_password': 'StrongPass123!', 'new_password': 'PersonalPass2026!'})
    assert changed.status_code == 200
    headers = bearer(create_access_token(uid, credential_version=1))
    assert (await client.get('/api/v1/workdays/today', headers=headers)).status_code == 200
    assert (await client.patch(f'/api/v1/admin/users/{uid}', headers=bearer(admin_token), json={'role': 'ADMIN'})).status_code == 200
    assert (await client.get('/api/v1/workdays/today', headers=headers)).status_code == 403
    assert (await client.patch(f'/api/v1/admin/users/{uid}', headers=bearer(admin_token), json={'role': 'TECHNICIAN', 'username': 'renamed'})).status_code == 200
    assert (await client.get('/api/v1/workdays/today', headers=headers)).status_code == 200
    profile = await db.scalar(select(Technician).where(Technician.user_id == uuid.UUID(uid)))
    assert profile is not None


async def test_previous_workday_survives_and_can_be_closed(client, db):
    user = await db.scalar(select(User).where(User.username == 'carlos'))
    tech = await db.scalar(select(Technician).where(Technician.user_id == user.id))
    start = now_utc() - timedelta(hours=12)
    day = Workday(technician_id=tech.id, work_date=today_local() - timedelta(days=1), check_in_at=start, status=WorkdayStatus.OPEN)
    db.add(day)
    await db.commit()
    headers = bearer(create_access_token(user.id))
    today = await client.get('/api/v1/workdays/today', headers=headers)
    assert today.json()['status'] == 'WORKING'
    assert today.json()['workday']['id'] == str(day.id)
    assert (await client.post('/api/v1/workdays/check-in', headers=headers, json={})).status_code == 409
    await db.refresh(day)
    assert day.status == WorkdayStatus.OPEN and day.check_out_at is None
    closed = await client.post('/api/v1/workdays/check-out', headers=headers, json={})
    assert closed.status_code == 200 and closed.json()['duration_minutes'] >= 720
    assert (await client.post('/api/v1/workdays/check-in', headers=headers, json={})).status_code == 200


async def test_cancelled_task_cannot_be_completed(client, admin_token, tech_juan_token):
    headers = bearer(tech_juan_token)
    tasks = (await client.get('/api/v1/tasks/today', headers=headers)).json()
    task = next(t for t in tasks if t['status'] == 'PENDING')
    assert (await client.patch(f"/api/v1/admin/tasks/{task['id']}/cancel", headers=bearer(admin_token))).status_code == 200
    response = await client.patch(f"/api/v1/tasks/{task['id']}/complete", headers=headers, json={})
    assert response.status_code == 409


async def test_invalid_coordinates_rejected(client, tech_juan_token):
    for body in [{'latitude': 91}, {'longitude': -181}, {'accuracy': -1}]:
        assert (await client.post('/api/v1/workdays/check-in', headers=bearer(tech_juan_token), json=body)).status_code == 422


async def test_pagination_and_search(client, admin_token):
    headers = bearer(admin_token)
    first = (await client.get('/api/v1/admin/users?size=2&page=1', headers=headers)).json()
    second = (await client.get('/api/v1/admin/users?size=2&page=2', headers=headers)).json()
    assert first['pages'] >= 2
    assert {x['id'] for x in first['items']}.isdisjoint(x['id'] for x in second['items'])
    found = (await client.get('/api/v1/admin/users?search=juan', headers=headers)).json()
    assert found['total'] == 1


async def test_report_midnight_and_invalid_csv_range(client, admin_token):
    # Monterrey UTC-6: 23:30 on work date and 00:30 on the following date.
    days = [Workday(work_date=date(2026, 1, 1), check_out_at=datetime(2026, 1, 2, 5, 30, tzinfo=timezone.utc)),
            Workday(work_date=date(2026, 1, 2), check_out_at=datetime(2026, 1, 3, 6, 30, tzinfo=timezone.utc))]
    assert _avg_local_time(days, 'check_out_at') == '12:00 AM'
    assert _avg_local_time([], 'check_out_at') is None
    for path in ['/api/v1/admin/reports', '/api/v1/admin/reports/export/csv']:
        assert (await client.get(path+'?date_from=2026-02-01&date_to=2026-01-01', headers=bearer(admin_token))).status_code == 422


async def test_inactive_technician_remains_in_historical_reports(client, db, admin_token):
    tech = await db.scalar(select(Technician))
    tech.is_active = False
    await db.commit()
    rows = (await client.get('/api/v1/admin/reports', headers=bearer(admin_token))).json()
    assert any(r['technician_id'] == str(tech.id) for r in rows)


async def test_webhook_outbox_retry_and_stable_id(client, db, tech_juan_token, monkeypatch):
    monkeypatch.setattr(settings, 'WEBHOOK_CHECK_OUT_URL', 'https://receiver.invalid/event')
    result = await client.post('/api/v1/workdays/check-out', headers=bearer(tech_juan_token), json={'early_exit_reason': 'Validación de webhook con salida autorizada'})
    assert result.status_code == 200
    delivery = await db.scalar(select(WebhookDelivery))
    assert delivery is not None
    keys = []
    def receive(request):
        keys.append(request.headers['Idempotency-Key'])
        return httpx.Response(503 if len(keys) == 1 else 200)
    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as transport:
        assert await deliver_one(db, transport)
        await db.refresh(delivery)
        assert delivery.attempts == 1 and delivery.delivered_at is None
        delivery.available_at = now_utc()
        await db.commit()
        assert await deliver_one(db, transport)
        await db.refresh(delivery)
        assert delivery.delivered_at is not None
    assert keys == [str(delivery.id), str(delivery.id)]


async def test_bootstrap_admin_refuses_existing_admin(db):
    from app.manage import create_initial_admin
    with pytest.raises(ValueError, match='Ya existe'):
        await create_initial_admin(db, 'bootstrap', 'bootstrap@example.com', 'Admin', 'StrongPass123!')


async def test_migrations_on_empty_database():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import inspect
    from alembic.config import Config
    from alembic import command
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        def upgrade(connection):
            config = Config('alembic.ini')
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
            assert 'webhook_deliveries' in inspect(connection).get_table_names()
            assert any(i['name'] == 'uq_workday_open_per_technician' for i in inspect(connection).get_indexes('workdays'))
        await conn.run_sync(upgrade)
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.manage import create_initial_admin
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            await create_initial_admin(db, 'bootstrap', 'bootstrap@example.com', 'Administrador', 'StrongPass123!')
            user = await db.scalar(select(User).where(User.username == 'bootstrap'))
            assert user is not None and user.is_active and user.role == 'ADMIN'
    await engine.dispose()
