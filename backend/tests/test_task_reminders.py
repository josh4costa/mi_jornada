from datetime import datetime, timedelta, timezone
import httpx
import pytest
from sqlalchemy import select, func
from app.models import Workday, Task
from app.models.attendance import ReminderDelivery, AttendanceEvent, AttendanceIncident
from app.services.reminders import tick, eligible, send_reminder
from tests.test_attendance import reminder_tech, reminder_settings


ENTRY = datetime(2026, 9, 27, 5, 45, tzinfo=timezone.utc)  # Saturday 23:45, crosses midnight.


async def setup(db, monkeypatch, shift='NIGHT'):
    reminder_settings(monkeypatch)
    tech, user = await reminder_tech(db)
    wd = Workday(technician_id=tech.id, work_date=(ENTRY - timedelta(hours=6)).date(), check_in_at=ENTRY, status='OPEN', shift_kind=shift)
    db.add(wd); await db.commit()
    return tech.id, user.id, wd.id, wd.work_date


def fake(sent, fail=False):
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'status': {'accountStatus': {'status': 'authenticated'}}})
        sent.append(request.content)
        if fail:
            raise httpx.ReadTimeout('simulated', request=request)
        return httpx.Response(200, json={'sent': True, 'id': 'fake-task-reminder'})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
@pytest.mark.parametrize('shift', ['DAY', 'NIGHT'])
async def test_task_reminder_after_30_minutes_once_across_midnight(db, monkeypatch, shift):
    tech_id, user_id, wd_id, day = await setup(db, monkeypatch, shift)
    sent = []
    async with fake(sent) as client:
        await tick(db, client, ENTRY + timedelta(minutes=29, seconds=59))
        assert sent == []
        await tick(db, client, ENTRY + timedelta(minutes=30))
        await tick(db, client, ENTRY + timedelta(minutes=31))
    assert len(sent) == 1
    delivery = await db.scalar(select(ReminderDelivery).where(ReminderDelivery.technician_id == tech_id))
    assert delivery.status == 'ACCEPTED' and delivery.kind == 'TASKS_' + shift
    assert delivery.work_date == day
    assert await db.scalar(select(func.count(AttendanceIncident.id))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('condition', ['assigned', 'completed', 'closed', 'void', 'expired', 'disabled'])
async def test_no_task_reminder_when_not_needed(db, monkeypatch, condition):
    tech_id, user_id, wd_id, day = await setup(db, monkeypatch)
    wd = await db.get(Workday, wd_id)
    if condition in ('assigned', 'completed'):
        db.add(Task(technician_id=tech_id, assigned_date=day, title='Trabajo asignado', created_by=user_id, created_by_type='ADMIN', status='COMPLETED' if condition == 'completed' else 'PENDING'))
    if condition == 'closed': wd.status = 'CLOSED'
    if condition == 'void': wd.is_void = True
    if condition == 'disabled':
        from app.models import Technician
        (await db.get(Technician, tech_id)).reminders_enabled = False
    await db.commit()
    sent = []
    async with fake(sent) as client:
        await tick(db, client, ENTRY + timedelta(minutes=60 if condition == 'expired' else 30))
    assert sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize('prior', ['task', 'reminder'])
async def test_continuation_inherits_night_tasks_and_reminder(db, monkeypatch, prior):
    tech_id, user_id, wd_id, day = await setup(db, monkeypatch)
    night = await db.get(Workday, wd_id)
    night.status = 'CLOSED'
    night.check_out_at = ENTRY + timedelta(hours=9)
    await db.flush()
    day_shift = Workday(technician_id=tech_id, work_date=day + timedelta(days=1), check_in_at=night.check_out_at, status='OPEN', shift_kind='DAY')
    db.add(day_shift); await db.flush()
    db.add(AttendanceEvent(actor_id=user_id, entity_id=wd_id, action='NIGHT_CONTINUED_DAY', details={'day_workday_id': str(day_shift.id)}))
    if prior == 'task':
        db.add(Task(technician_id=tech_id, assigned_date=day, title='Trabajo de la noche', created_by=user_id, created_by_type='TECHNICIAN', status='PENDING'))
    else:
        db.add(ReminderDelivery(technician_id=tech_id, work_date=day, kind='TASKS_NIGHT', status='ACCEPTED'))
    await db.commit()
    assert await eligible(db, tech_id, day_shift.work_date, 'TASKS_DAY', day_shift.id, night.check_out_at + timedelta(minutes=30)) is None


@pytest.mark.asyncio
async def test_uncertain_task_send_never_repeats(db, monkeypatch):
    tech_id, user_id, wd_id, day = await setup(db, monkeypatch)
    sent = []
    async with fake(sent, fail=True) as client:
        await tick(db, client, ENTRY + timedelta(minutes=30))
        await tick(db, client, ENTRY + timedelta(minutes=31))
    assert len(sent) == 1
    row = await db.scalar(select(ReminderDelivery).where(ReminderDelivery.technician_id == tech_id))
    assert row.status == 'UNKNOWN'


@pytest.mark.asyncio
async def test_rechecks_tasks_after_claim_before_sending(db, monkeypatch):
    from app.services import reminders
    tech_id, user_id, wd_id, day = await setup(db, monkeypatch)
    original = reminders.eligible
    calls = 0
    async def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            db.add(Task(technician_id=tech_id, assigned_date=day, title='Asignación reciente', created_by=user_id, created_by_type='ADMIN', status='PENDING'))
            await db.flush()
        return await original(*args, **kwargs)
    monkeypatch.setattr(reminders, 'eligible', changed)
    sent = []
    async with fake(sent) as client:
        await send_reminder(db, client, tech_id, day, 'TASKS_NIGHT', wd_id, ENTRY + timedelta(minutes=30))
    assert sent == []
    row = await db.scalar(select(ReminderDelivery).where(ReminderDelivery.technician_id == tech_id))
    assert row.status == 'SKIPPED'
