from datetime import date, datetime, timezone, timedelta
import uuid
import httpx
import pytest
from sqlalchemy import select, delete
from app.models import User, Technician, Workday, UserRole
from app.models.attendance import AttendanceIncident, ReminderDelivery
from app.core.security import create_access_token
from app.core.config import settings
from app.services.night_shift import day_exception
from app.services.reminders import eligible, tick
from app.services.attendance import generate_missing
from app.services.attendance_report import report_data


def headers(token):
    return {'Authorization': 'Bearer ' + token}


async def fresh(db):
    user = User(username='night-test', email='night@example.com', full_name='Nocturno Prueba', role=UserRole.TECHNICIAN,
        password_hash='unused', is_active=True, must_change_password=False)
    db.add(user)
    await db.flush()
    tech = Technician(user_id=user.id, phone='+528100000009', reminders_enabled=True, created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    db.add(tech)
    await db.commit()
    return tech, user, headers(create_access_token(user.id))


def clock(monkeypatch, day, utc_hour):
    import app.services.workday as wd
    import app.api.v1.workdays as api
    import app.api.v1.night_plans as plans
    import app.core.timezone as tz
    import app.services.attendance_report as reports
    dt = datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=utc_hour)
    for module in [wd, api, plans]:
        monkeypatch.setattr(module, 'today_local', lambda: day)
    for module in [wd, tz, reports]:
        monkeypatch.setattr(module, 'now_utc', lambda: dt)
    return dt


@pytest.mark.asyncio
async def test_readonly_permissions(client, db, admin_token):
    user = User(username='reader', email='reader@example.com', full_name='Consulta', role=UserRole.READ_ONLY,
        password_hash='unused', is_active=True, must_change_password=False)
    db.add(user); await db.commit()
    h = headers(create_access_token(user.id))
    for path in ['/admin/dashboard', '/admin/technicians', '/admin/tasks', '/admin/workdays', '/admin/reports',
                 '/admin/reports/export/csv', '/attendance/incidents', '/attendance/summary',
                 '/attendance/leaves?date_from=2026-09-21&date_to=2026-09-22',
                 '/night-plans?date_from=2026-09-21&date_to=2026-09-22',
                 '/admin/report-mail/pdf?date_from=2026-09-21&date_to=2026-09-22']:
        response = await client.get('/api/v1' + path, headers=h)
        assert response.status_code == 200, (path, response.text)
    for path in ['/admin/users', '/admin/report-mail', '/attendance/reminders', '/workdays/today']:
        assert (await client.get('/api/v1' + path, headers=h)).status_code == 403, path
    for method, path in [('post', '/admin/tasks'), ('post', '/admin/users'), ('post', '/attendance/leaves'),
                         ('post', '/night-plans'), ('post', '/workdays/check-in'), ('post', '/workdays/continue-day'),
                         ('patch', '/admin/workdays/' + str(uuid.uuid4())), ('patch', '/admin/report-mail'),
                         ('patch', '/attendance/incidents/' + str(uuid.uuid4()))]:
        response = await getattr(client, method)('/api/v1' + path, json={}, headers=h)
        assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
async def test_declared_night_approval_and_continuous_day(client, db, admin_token, monkeypatch):
    tech, user, h = await fresh(db)
    monday = date(2026, 9, 21)
    clock(monkeypatch, monday, 15)
    payload = dict(work_date=str(monday), reminder_time='21:00', replaces_day=True, reason='Mantenimiento nocturno')
    result = await client.post('/api/v1/night-plans', json=payload, headers=h)
    assert result.status_code == 201, result.text
    id = result.json()['id']
    assert result.json()['status'] == 'PENDING'
    assert await day_exception(db, tech.id, monday) is None
    assert await eligible(db, tech.id, monday, 'ENTRY') is None
    await generate_missing(db, tech, monday)
    await db.commit()
    assert await db.scalar(select(AttendanceIncident.id).where(AttendanceIncident.technician_id == tech.id, AttendanceIncident.kind == 'MISSING_ENTRY'))
    approved = await client.patch('/api/v1/night-plans/' + id, json={'status': 'APPROVED', 'note': 'Cambio autorizado'}, headers=headers(admin_token))
    assert approved.status_code == 200, approved.text
    await db.refresh(await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == tech.id, AttendanceIncident.kind == 'MISSING_ENTRY')))
    assert (await client.post('/api/v1/workdays/check-in', json={}, headers=h)).status_code == 409
    clock(monkeypatch, monday, 28)  # Monday 22:00 local; UTC Tuesday 04:00.
    response = await client.post('/api/v1/workdays/check-in', json={'night_plan_id': id}, headers=h)
    assert response.status_code == 200, response.text
    assert response.json()['shift_kind'] == 'NIGHT'
    assert (await client.post('/api/v1/workdays/check-in', json={'night_plan_id': id}, headers=h)).status_code == 409
    assert (await client.patch('/api/v1/night-plans/' + id, json={'status': 'CANCELLED', 'note': 'No debe cancelar'}, headers=h)).status_code == 409
    clock(monkeypatch, monday + timedelta(days=1), 15)  # Tuesday 09:00.
    today = (await client.get('/api/v1/workdays/today', headers=h)).json()
    assert today['status'] == 'WORKING' and today['can_start_day'] and today['scheduled_exit'] is None
    assert today['workday']['work_date'] == str(monday)
    response = await client.post('/api/v1/workdays/continue-day', json={'latitude': 25, 'longitude': -100}, headers=h)
    assert response.status_code == 200, response.text
    night = await db.scalar(select(Workday).where(Workday.technician_id == tech.id, Workday.shift_kind == 'NIGHT'))
    assert night.duration_minutes == 660
    assert night.check_out_at.isoformat().replace('+00:00', '') == response.json()['check_in_at'].replace('Z', '').replace('+00:00', '')
    clock(monkeypatch, monday + timedelta(days=1), 24)  # Tuesday 18:00.
    assert (await client.post('/api/v1/workdays/check-out', json={}, headers=h)).status_code == 200
    tech_id = tech.id
    await db.rollback(); db.expire_all()
    report = await report_data(db, monday, monday + timedelta(days=1), tech_id)
    assert report['totals']['minutes'] == 1200
    assert report['totals']['recorded'] == 2
    assert report['totals']['late'] == 0 and report['totals']['early'] == 0


@pytest.mark.asyncio
async def test_same_date_day_night_report_and_rollback(client, db, admin_token, monkeypatch):
    tech, user, h = await fresh(db); tech_id = tech.id
    monday = date(2026, 9, 21)
    clock(monkeypatch, monday, 15)
    assert (await client.post('/api/v1/workdays/check-in', json={}, headers=h)).status_code == 200
    clock(monkeypatch, monday, 24)
    assert (await client.post('/api/v1/workdays/check-out', json={}, headers=h)).status_code == 200
    result = await client.post('/api/v1/night-plans', headers=headers(admin_token), json=dict(technician_id=str(tech_id), work_date=str(monday), reminder_time='20:00', reason='Servicio adicional', replaces_day=False))
    assert result.status_code == 201, result.text
    clock(monkeypatch, monday, 26)
    result = await client.post('/api/v1/workdays/check-in', headers=h, json={'night_plan_id': result.json()['id']})
    assert result.status_code == 200, result.text
    # There is already a daytime record: failed continuation must leave the night open.
    assert (await client.post('/api/v1/workdays/continue-day', headers=h, json={})).status_code == 409
    assert (await client.get('/api/v1/workdays/today', headers=h)).json()['workday']['shift_kind'] == 'NIGHT'
    clock(monkeypatch, monday + timedelta(days=1), 8)
    response = await client.post('/api/v1/workdays/check-out', headers=h, json={})
    assert response.status_code == 200 and response.json()['duration_minutes'] == 360
    report = await report_data(db, monday, monday, tech_id)
    assert report['totals']['recorded'] == 1 and report['totals']['minutes'] == 900
    assert report['totals']['late'] == report['totals']['early'] == 0
    csv = await client.get('/api/v1/admin/reports?date_from=2026-09-21&date_to=2026-09-21&technician_id=' + str(tech_id), headers=headers(admin_token))
    assert csv.json()[0]['days_worked'] == 1 and csv.json()[0]['total_minutes'] == 900


@pytest.mark.asyncio
async def test_night_reminder_sunday_once_and_day_not_suppressed(client, db, admin_token, monkeypatch):
    tech, user, h = await fresh(db); tech_id = tech.id
    sunday = date(2026, 9, 27)
    current = clock(monkeypatch, sunday, 26)
    monkeypatch.setattr(settings, 'REMINDERS_ENABLED', True)
    monkeypatch.setattr(settings, 'ULTRAMSG_INSTANCE', 'instanceTEST')
    monkeypatch.setattr(settings, 'ULTRAMSG_TOKEN', 'test-only')
    monkeypatch.setattr(settings, 'ATTENDANCE_START_DATE', '')
    result = await client.post('/api/v1/night-plans', headers=headers(admin_token), json=dict(technician_id=str(tech_id), work_date=str(sunday), reminder_time='20:00', reason='Trabajo domingo', replaces_day=False))
    assert result.status_code == 201, result.text
    sent = []
    def transport(request):
        if request.method == 'GET': return httpx.Response(200, json={'status': {'accountStatus': {'status': 'authenticated'}}})
        sent.append(request.content); return httpx.Response(200, json={'sent': True, 'id': 'fake'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as fake:
        await tick(db, fake, current); await tick(db, fake, current + timedelta(minutes=1))
    assert len(sent) == 1
    assert await eligible(db, tech_id, sunday + timedelta(days=1), 'ENTRY') is not None
    delivery = await db.scalar(select(ReminderDelivery).where(ReminderDelivery.technician_id == tech_id))
    assert delivery.kind == 'NIGHT_ENTRY' and delivery.status == 'ACCEPTED'
