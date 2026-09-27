from datetime import date, datetime, timezone, timedelta
from types import SimpleNamespace
import smtplib
import uuid
import pytest
from sqlalchemy import select, delete
from app.models import Workday, Technician
from app.models.weekly_report import WeeklyReportRun
from app.models.attendance import AttendanceIncident, LeaveRequest
from app.services import weekly_reports as service
from app.services import attendance_report
from app.services.report_pdf import render_pdf
from app.core.config import settings

def headers(token):
    return {'Authorization': 'Bearer ' + token}

MONDAY = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)

@pytest.mark.asyncio
async def test_configuration_permissions_validation_and_revision(client, admin_token, tech_juan_token):
    endpoint = '/api/v1/admin/report-mail'
    assert (await client.get(endpoint, headers=headers(tech_juan_token))).status_code == 403
    initial = (await client.get(endpoint, headers=headers(admin_token))).json()
    assert initial['first_send_date'] == '2026-09-28'
    assert initial['to_emails'] == ['oscar.moncada@pleg.com.mx']
    assert 'password' not in str(initial).lower()
    payload = dict(enabled=True, first_send_date='2026-09-28', to_emails=['test@example.com'], cc_emails=[], revision=0)
    for change in [dict(first_send_date='2026-09-29'), dict(to_emails=[]), dict(cc_emails=['TEST@example.com']), dict(to_emails=['bad-address'])]:
        assert (await client.patch(endpoint, json={**payload, **change}, headers=headers(admin_token))).status_code == 422
    assert (await client.patch(endpoint, json=payload, headers=headers(admin_token))).status_code == 200
    assert (await client.patch(endpoint, json=payload, headers=headers(admin_token))).status_code == 409
    assert (await client.get(endpoint + '/pdf?date_from=2026-01-01&date_to=2026-12-31', headers=headers(admin_token))).status_code == 422
    result = await client.get(endpoint + '/pdf?date_from=2026-09-21&date_to=2026-09-27', headers=headers(admin_token))
    assert result.status_code == 200 and result.content.startswith(b'%PDF')
    assert result.headers['cache-control'] == 'private, no-store'

@pytest.mark.asyncio
async def test_schedule_boundary_snapshot_and_no_duplicate(db, monkeypatch):
    sent = []
    monkeypatch.setattr(service, 'send_report', lambda run: (sent.append((run.period_start, run.period_end, run.pdf)) or ('ACCEPTED', None)))
    await service.tick(MONDAY - timedelta(days=7))
    await service.tick(MONDAY - timedelta(seconds=1))
    assert await db.scalar(select(WeeklyReportRun)) is None
    await service.tick(MONDAY)
    await service.tick(MONDAY + timedelta(seconds=30))
    assert len(sent) == 1
    assert sent[0][:2] == (date(2026, 9, 21), date(2026, 9, 27))
    assert sent[0][2].startswith(b'%PDF')
    row = await db.scalar(select(WeeklyReportRun))
    assert row.status == 'ACCEPTED' and row.attempts == 1

@pytest.mark.asyncio
async def test_safe_retry_and_uncertain_delivery_not_retried(db, monkeypatch):
    calls = []
    def sender(run):
        calls.append(run.id)
        return ('FAILED', 'connection failed') if len(calls) == 1 else ('UNKNOWN', 'uncertain')
    monkeypatch.setattr(service, 'send_report', sender)
    await service.tick(MONDAY)
    await service.tick(MONDAY + timedelta(minutes=1))
    assert len(calls) == 1
    await service.tick(MONDAY + timedelta(minutes=11))
    await service.tick(MONDAY + timedelta(minutes=30))
    assert len(calls) == 2
    assert (await db.scalar(select(WeeklyReportRun))).status == 'UNKNOWN'

@pytest.mark.asyncio
async def test_expired_and_paused_do_not_send(db, monkeypatch):
    def forbidden(run):
        raise AssertionError('must not send')
    monkeypatch.setattr(service, 'send_report', forbidden)
    config = await service.get_config(db)
    config.enabled = False
    await db.commit()
    await service.tick(MONDAY)
    assert await db.scalar(select(WeeklyReportRun)) is None
    config.enabled = True
    await db.commit()
    await service.tick(MONDAY + timedelta(days=2))
    assert (await db.scalar(select(WeeklyReportRun))).status == 'EXPIRED'

def test_smtp_tls_envelope_pdf_and_ambiguous_timeout(monkeypatch):
    for key, value in dict(SMTP_HOST='smtp.example.com', SMTP_PORT=587, SMTP_SECURITY='STARTTLS', SMTP_USER='user', SMTP_PASSWORD='test', SMTP_FROM='sender@example.com').items():
        monkeypatch.setattr(settings, key, value)
    calls = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs): pass
        def ehlo(self): calls.append('ehlo')
        def starttls(self, **kwargs): calls.append('tls')
        def login(self, *args):
            assert 'tls' in calls
            calls.append('login')
        def send_message(self, msg, **kwargs):
            calls.append((msg, kwargs))
            return {}
        def close(self): pass
    monkeypatch.setattr(service.smtplib, 'SMTP', FakeSMTP)
    run = SimpleNamespace(id=uuid.uuid4(), to_emails=['to@example.com'], cc_emails=['cc@example.com'], subject='Asistencias',
        period_start=date(2026,9,21), period_end=date(2026,9,27), pdf=b'%PDF-test', filename='attendance.pdf')
    assert service.send_report(run) == ('ACCEPTED', None)
    msg, envelope = calls[-1]
    assert envelope['to_addrs'] == ['to@example.com', 'cc@example.com']
    assert msg['Cc'] == 'cc@example.com'
    assert list(msg.iter_attachments())[0].get_payload(decode=True) == b'%PDF-test'
    def timeout(*args, **kwargs): raise TimeoutError()
    monkeypatch.setattr(FakeSMTP, 'send_message', timeout)
    assert service.send_report(run)[0] == 'UNKNOWN'
    def rejected(*args, **kwargs): raise smtplib.SMTPDataError(550, b'rejected')
    monkeypatch.setattr(FakeSMTP, 'send_message', rejected)
    assert service.send_report(run)[0] == 'FAILED'

@pytest.mark.asyncio
async def test_report_absences_saturday_rest_and_void(db, monkeypatch):
    monkeypatch.setattr(attendance_report, 'now_utc', lambda: MONDAY)
    tech = (await db.scalars(select(Technician))).first()
    tech.created_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    await db.execute(delete(Workday).where(Workday.technician_id == tech.id))
    db.add(Workday(technician_id=tech.id, work_date=date(2026,9,21), check_in_at=MONDAY-timedelta(days=7),
                   check_out_at=MONDAY-timedelta(days=7)+timedelta(hours=9), duration_minutes=540, status='CLOSED', is_void=True))
    db.add(AttendanceIncident(technician_id=tech.id, work_date=date(2026,9,22), kind='MISSING_ENTRY', status='UNJUSTIFIED', reason='Reviewed'))
    db.add(LeaveRequest(technician_id=tech.id, start_date=date(2026,9,25), end_date=date(2026,9,27), kind='VACATION', status='APPROVED', reason='Private', requested_by=tech.user_id))
    await db.commit()
    data = await attendance_report.report_data(db, date(2026,9,21), date(2026,9,27), tech.id)
    row = data['technicians'][0]
    assert row['summary']['minutes'] == 0
    assert row['summary']['vacation'] == 2  # Friday, Saturday. Sunday is rest.
    assert row['summary']['unjustified'] == 1
    assert row['summary']['pending'] == 3
    assert row['days'][-1]['state'] == 'Descanso'
    row['name'] = 'Técnico <A> & B'
    assert render_pdf(data).startswith(b'%PDF')
