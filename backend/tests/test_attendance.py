from datetime import date, datetime, timezone
import uuid
import httpx
import pytest
from sqlalchemy import select, func
from app.models import User, Technician, Workday
from app.models.attendance import LeaveRequest, AttendanceIncident, ReminderDelivery, AttendanceEvent, AttendanceScan
from app.services.attendance import schedule, working_days
from app.services.reminders import tick
from app.core.config import settings


def headers(token):
    return {'Authorization': f'Bearer {token}'}


def test_schedule_and_weekend_count():
    assert schedule(date(2026, 9, 25))[1].hour == 18
    assert schedule(date(2026, 9, 26))[1].hour == 13
    assert schedule(date(2026, 9, 27)) is None
    assert working_days(date(2026, 9, 25), date(2026, 9, 28)) == 3


@pytest.mark.asyncio
async def test_leave_approval_privacy_overlap_and_cancellation(client, admin_token, tech_juan_token, tech_pedro_token):
    payload = {'kind': 'VACATION', 'start_date': '2027-01-08', 'end_date': '2027-01-11', 'reason': 'Vacaciones familiares'}
    created = await client.post('/api/v1/attendance/leaves', json=payload, headers=headers(tech_juan_token))
    assert created.status_code == 201, created.text
    assert created.json()['working_days'] == 3
    id = created.json()['id']
    duplicate = await client.post('/api/v1/attendance/leaves', json=payload, headers=headers(tech_juan_token))
    assert duplicate.status_code == 409
    other = await client.get('/api/v1/attendance/leaves?date_from=2027-01-01&date_to=2027-01-31', headers=headers(tech_pedro_token))
    assert other.json() == []
    unauthorized = await client.patch('/api/v1/attendance/leaves/' + id, json={'status': 'APPROVED', 'note': 'Autorizo'}, headers=headers(tech_juan_token))
    assert unauthorized.status_code == 403
    approved = await client.patch('/api/v1/attendance/leaves/' + id, json={'status': 'APPROVED', 'note': 'Autorizado por supervisor'}, headers=headers(admin_token))
    assert approved.status_code == 200
    repeat = await client.patch('/api/v1/attendance/leaves/' + id, json={'status': 'REJECTED', 'note': 'No procede'}, headers=headers(admin_token))
    assert repeat.status_code == 409
    denied = await client.patch('/api/v1/attendance/leaves/' + id, json={'status': 'CANCELLED', 'note': 'Cancelar viaje'}, headers=headers(tech_juan_token))
    assert denied.status_code == 409
    cancelled = await client.patch('/api/v1/attendance/leaves/' + id, json={'status': 'CANCELLED', 'note': 'Cambio autorizado'}, headers=headers(admin_token))
    assert cancelled.status_code == 200
    history = await client.get('/api/v1/attendance/events/' + id, headers=headers(admin_token))
    assert len(history.json()) == 3


@pytest.mark.asyncio
async def test_invalid_leave_dates(client, tech_juan_token):
    for start, end in [('2027-01-10', '2027-01-10'), ('2027-01-11', '2027-01-08'), ('2027-01-01', '2029-01-01')]:
        result = await client.post('/api/v1/attendance/leaves', json={'kind': 'VACATION', 'start_date': start, 'end_date': end, 'reason': 'Prueba'}, headers=headers(tech_juan_token))
        assert result.status_code == 422


@pytest.mark.asyncio
async def test_early_exit_requires_reason_and_is_reviewed(client, db, monkeypatch, tech_juan_token, admin_token):
    from app.services import workday as service
    user = await db.scalar(select(User).where(User.username == 'juan'))
    tech = await db.scalar(select(Technician).where(Technician.user_id == user.id))
    workday = await db.scalar(select(Workday).where(Workday.technician_id == tech.id, Workday.status == 'OPEN'))
    workday.work_date = date(2026, 9, 26)  # Saturday
    workday.check_in_at = datetime(2026, 9, 26, 15, tzinfo=timezone.utc)
    await db.commit()
    monkeypatch.setattr(service, 'now_utc', lambda: datetime(2026, 9, 26, 18, tzinfo=timezone.utc))  # 12:00 local
    result = await client.post('/api/v1/workdays/check-out', json={}, headers=headers(tech_juan_token))
    assert result.status_code == 422
    result = await client.post('/api/v1/workdays/check-out', json={'early_exit_reason': 'Cita personal autorizada'}, headers=headers(tech_juan_token))
    assert result.status_code == 200, result.text
    rows = (await client.get('/api/v1/attendance/incidents', headers=headers(admin_token))).json()['items']
    assert len(rows) == 1 and rows[0]['status'] == 'PENDING'
    result = await client.patch('/api/v1/attendance/incidents/' + rows[0]['id'], json={'status': 'JUSTIFIED', 'note': 'Permiso verificado'}, headers=headers(admin_token))
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_at_saturday_exit_time_does_not_require_reason(client, db, monkeypatch, tech_juan_token):
    from app.services import workday as service
    user = await db.scalar(select(User).where(User.username == 'juan'))
    tech = await db.scalar(select(Technician).where(Technician.user_id == user.id))
    workday = await db.scalar(select(Workday).where(Workday.technician_id == tech.id, Workday.status == 'OPEN'))
    workday.work_date = date(2026, 9, 26)
    workday.check_in_at = datetime(2026, 9, 26, 15, tzinfo=timezone.utc)
    await db.commit()
    monkeypatch.setattr(service, 'now_utc', lambda: datetime(2026, 9, 26, 19, tzinfo=timezone.utc))
    result = await client.post('/api/v1/workdays/check-out', json={}, headers=headers(tech_juan_token))
    assert result.status_code == 200
    assert await db.scalar(select(func.count(AttendanceIncident.id))) == 0


async def reminder_tech(db):
    user = User(id=uuid.uuid4(), username='reminder-test', full_name='Tecnico Prueba', email='reminder@example.com', password_hash='unused', role='TECHNICIAN', is_active=True)
    db.add(user)
    await db.flush()
    tech = Technician(user_id=user.id, phone='+528100000001', reminders_enabled=True, created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    db.add(tech)
    await db.commit()
    return tech, user


def reminder_settings(monkeypatch):
    monkeypatch.setattr(settings, 'ULTRAMSG_INSTANCE', 'instanceTEST')
    monkeypatch.setattr(settings, 'ULTRAMSG_TOKEN', 'test-only')
    monkeypatch.setattr(settings, 'REMINDERS_ENABLED', True)
    monkeypatch.setattr(settings, 'ATTENDANCE_START_DATE', '')


@pytest.mark.asyncio
async def test_reminders_once_correct_time_and_no_sunday(db, monkeypatch):
    reminder_settings(monkeypatch)
    tech, user = await reminder_tech(db)
    sent = []
    async def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'status': {'accountStatus': {'status': 'authenticated'}}})
        sent.append(request.content.decode())
        return httpx.Response(200, json={'sent': 'true', 'id': 1})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await tick(db, http, datetime(2026, 9, 26, 15, 9, tzinfo=timezone.utc))
        assert not sent
        await tick(db, http, datetime(2026, 9, 26, 15, 10, tzinfo=timezone.utc))
        await tick(db, http, datetime(2026, 9, 26, 15, 11, tzinfo=timezone.utc))
        assert len(sent) == 1
        await tick(db, http, datetime(2026, 9, 27, 15, 10, tzinfo=timezone.utc))
        assert len(sent) == 1
    assert await db.scalar(select(func.count(ReminderDelivery.id))) == 1


@pytest.mark.asyncio
async def test_reminders_skip_approved_leave_registered_entry_and_expired_window(db, monkeypatch):
    reminder_settings(monkeypatch)
    tech, user = await reminder_tech(db)
    leave = LeaveRequest(technician_id=tech.id, requested_by=user.id, kind='VACATION', start_date=date(2026, 9, 25), end_date=date(2026, 9, 26), reason='Vacaciones', status='APPROVED')
    db.add(leave)
    await db.commit()
    sent = []
    async def handler(request):
        if request.method == 'POST': sent.append(request)
        return httpx.Response(200, json={'status': {'accountStatus': {'status': 'authenticated'}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await tick(db, http, datetime(2026, 9, 26, 15, 10, tzinfo=timezone.utc))
        await tick(db, http, datetime(2026, 9, 28, 15, 40, tzinfo=timezone.utc))
        db.add(Workday(technician_id=tech.id, work_date=date(2026, 9, 28), check_in_at=datetime(2026, 9, 28, 14, tzinfo=timezone.utc), status='OPEN'))
        await db.commit()
        await tick(db, http, datetime(2026, 9, 28, 15, 10, tzinfo=timezone.utc))
        assert not sent


@pytest.mark.asyncio
async def test_saturday_exit_reminder_and_unknown_send_is_not_retried(db, monkeypatch):
    reminder_settings(monkeypatch)
    tech, user = await reminder_tech(db)
    db.add(Workday(technician_id=tech.id, work_date=date(2026, 9, 26), check_in_at=datetime(2026, 9, 26, 15, tzinfo=timezone.utc), status='OPEN'))
    await db.commit()
    sent = []
    async def handler(request):
        if request.method == 'GET': return httpx.Response(200, json={'status': {'accountStatus': {'status': 'authenticated'}}})
        sent.append(request)
        raise httpx.ReadTimeout('test', request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await tick(db, http, datetime(2026, 9, 26, 19, 10, tzinfo=timezone.utc))
        await tick(db, http, datetime(2026, 9, 26, 19, 11, tzinfo=timezone.utc))
    assert len(sent) == 1
    row = await db.scalar(select(ReminderDelivery))
    assert row.status == 'UNKNOWN' and row.kind == 'EXIT'


@pytest.mark.asyncio
async def test_missing_entries_review_only_after_day_ends_and_approved_leave_reconciles(db, client, admin_token, monkeypatch):
    reminder_settings(monkeypatch)
    monkeypatch.setattr(settings, 'ATTENDANCE_START_DATE', '2026-09-26')
    tech, user = await reminder_tech(db)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as http:
        await tick(db, http, datetime(2026, 9, 26, 23, 50, tzinfo=timezone.utc))
        assert await db.scalar(select(func.count(AttendanceIncident.id))) == 0
        await tick(db, http, datetime(2026, 9, 27, 6, 5, tzinfo=timezone.utc))
        await tick(db, http, datetime(2026, 9, 27, 6, 6, tzinfo=timezone.utc))
    await db.refresh(tech)
    incident = await db.scalar(select(AttendanceIncident).where(AttendanceIncident.technician_id == tech.id))
    assert incident.status == 'PENDING'
    created = await client.post('/api/v1/attendance/leaves', headers=headers(admin_token), json={'technician_id': str(tech.id), 'kind': 'PERMISSION', 'start_date': '2026-09-26', 'end_date': '2026-09-26', 'reason': 'Permiso previamente concedido'})
    assert created.status_code == 201, created.text
    result = await client.patch('/api/v1/attendance/leaves/' + created.json()['id'], headers=headers(admin_token), json={'status': 'APPROVED', 'note': 'Verificado'})
    assert result.status_code == 200
    await db.refresh(incident)
    assert incident.status == 'JUSTIFIED'


@pytest.mark.asyncio
async def test_reminder_phone_required_and_unique(client, admin_token):
    people = (await client.get('/api/v1/admin/users?role=TECHNICIAN', headers=headers(admin_token))).json()['items']
    first, second = people[:2]
    result = await client.patch('/api/v1/admin/users/' + first['id'], headers=headers(admin_token), json={'reminders_enabled': True, 'phone': '8112345678'})
    assert result.status_code == 422
    result = await client.patch('/api/v1/admin/users/' + first['id'], headers=headers(admin_token), json={'reminders_enabled': True, 'phone': '+528112345678'})
    assert result.status_code == 200
    result = await client.patch('/api/v1/admin/users/' + second['id'], headers=headers(admin_token), json={'reminders_enabled': True, 'phone': '+528112345678'})
    assert result.status_code == 409
