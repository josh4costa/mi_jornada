from datetime import timedelta
import uuid
import pytest
from sqlalchemy import select
from app.models import User, Technician, Task
from app.models.account_setup import PasswordReset, TaskLocation, location_id
from app.core.security import hash_token
from app.core.timezone import now_utc, today_local
from app.api.v1 import passwords

def h(token):
    return {'Authorization': 'Bearer '+token}

def test_recovery_email_tls_headers_and_fragment(monkeypatch):
    from app.services import passwords as mail
    from app.core.config import settings
    monkeypatch.setattr(settings, 'SMTP_SECURITY', 'STARTTLS')
    monkeypatch.setattr(settings, 'SMTP_FROM', 'notificaciones@pleg.com.mx')
    calls = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def ehlo(self): pass
        def starttls(self, context):
            assert context.check_hostname
            calls.append('tls')
        def login(self, *args): assert calls == ['tls']
        def send_message(self, message, **envelope): calls.append((message,envelope))
        def close(self): pass
    monkeypatch.setattr(mail.smtplib, 'SMTP', SMTP)
    mail.send_recovery_email('tech@example.com', 'safe-token')
    assert len(calls) == 2
    message, envelope = calls[1]
    assert message['Date'] and message['Message-ID']
    assert envelope['to_addrs'] == ['tech@example.com']
    assert '/recuperar-contrasena#token=safe-token' in message.get_content()
    assert '?token=' not in message.get_content()

@pytest.mark.asyncio
async def test_forced_password_change_and_session_revocation(client, db, admin_token):
    user = await db.scalar(select(User).where(User.username == 'admin'))
    user.must_change_password = True
    await db.commit()
    login = (await client.post('/api/v1/auth/login', json={'username_or_email': 'admin', 'password': 'Admin2024!'})).json()
    assert login['user']['must_change_password']
    denied = await client.get('/api/v1/admin/dashboard', headers=h(admin_token))
    assert denied.status_code == 403 and denied.json()['detail']['code'] == 'PASSWORD_CHANGE_REQUIRED'
    assert (await client.get('/api/v1/auth/me', headers=h(admin_token))).status_code == 200
    for payload, status in [({'current_password': 'wrong', 'new_password': 'PersonalPass123!'},400),
                            ({'current_password': 'Admin2024!', 'new_password': 'short'},422),
                            ({'current_password': 'Admin2024!', 'new_password': 'á'*40},422)]:
        assert (await client.post('/api/v1/auth/change-password', json=payload, headers=h(admin_token))).status_code == status
    changed = await client.post('/api/v1/auth/change-password', json={'current_password': 'Admin2024!', 'new_password': 'PersonalPass123!'}, headers=h(admin_token))
    assert changed.status_code == 200
    assert (await client.get('/api/v1/auth/me', headers=h(admin_token))).status_code == 401
    assert (await client.post('/api/v1/auth/refresh', json={'refresh_token': login['refresh_token']})).status_code == 401
    login = (await client.post('/api/v1/auth/login', json={'username_or_email': 'admin', 'password': 'PersonalPass123!'})).json()
    assert login['user']['must_change_password'] is False
    assert (await client.get('/api/v1/admin/dashboard', headers=h(login['access_token']))).status_code == 200

@pytest.mark.asyncio
async def test_admin_reset_forces_personal_password_and_invalidates_tokens(client, db, admin_token, tech_juan_token):
    user = await db.scalar(select(User).where(User.username == 'juan'))
    reset = await client.patch('/api/v1/admin/users/'+str(user.id), headers=h(admin_token), json={'password': 'Temporary2026!'})
    assert reset.status_code == 200 and reset.json()['must_change_password']
    assert (await client.get('/api/v1/auth/me', headers=h(tech_juan_token))).status_code == 401
    login = (await client.post('/api/v1/auth/login', json={'username_or_email': 'juan', 'password': 'Temporary2026!'})).json()
    assert login['user']['must_change_password']
    assert (await client.get('/api/v1/tasks/today', headers=h(login['access_token']))).status_code == 403

@pytest.mark.asyncio
async def test_recovery_generic_response_single_use_and_no_plain_token(db, client, monkeypatch, admin_token):
    user = await db.scalar(select(User).where(User.username == 'admin'))
    user.email = 'admin@example.com'
    await db.commit()
    sent = []
    monkeypatch.setattr(passwords, 'send_recovery_email', lambda email, token: sent.append((email, token)))
    a = await client.post('/api/v1/auth/forgot-password', json={'email':'missing@example.com'})
    b = await client.post('/api/v1/auth/forgot-password', json={'email':'ADMIN@example.com'})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len(sent) == 1 and sent[0][0] == 'admin@example.com'
    token = sent[0][1]
    row = await db.scalar(select(PasswordReset))
    assert row.token_hash == hash_token(token) and row.token_hash != token
    assert (await client.get('/api/v1/auth/me', headers=h(admin_token))).status_code == 200
    await client.post('/api/v1/auth/forgot-password', json={'email':'admin@example.com'})
    assert len(sent) == 1  # account cooldown
    payload = {'token':token, 'new_password':'RecoveredPersonal2026!'}
    assert (await client.post('/api/v1/auth/reset-password', json=payload)).status_code == 200
    assert (await client.post('/api/v1/auth/reset-password', json=payload)).status_code == 400
    assert (await client.get('/api/v1/auth/me', headers=h(admin_token))).status_code == 401

@pytest.mark.asyncio
async def test_expired_and_admin_invalidated_recovery_links(db, client, admin_token):
    user = await db.scalar(select(User).where(User.username == 'juan'))
    expired, live = 'e'*43, 'v'*43
    for token, expiry in [(expired, now_utc()-timedelta(seconds=1)), (live, now_utc()+timedelta(minutes=30))]:
        db.add(PasswordReset(user_id=user.id, token_hash=hash_token(token), credential_version=0, expires_at=expiry))
    await db.commit()
    assert (await client.post('/api/v1/auth/reset-password', json={'token':expired,'new_password':'RecoveredPersonal2026!'})).status_code == 400
    await client.patch('/api/v1/admin/users/'+str(user.id), headers=h(admin_token), json={'email':'newmail@example.com'})
    assert (await client.post('/api/v1/auth/reset-password', json={'token':live,'new_password':'RecoveredPersonal2026!'})).status_code == 400

@pytest.mark.asyncio
async def test_catalog_groups_permissions_duplicates_and_snapshot(db, client, admin_token, tech_juan_token):
    listed = (await client.get('/api/v1/locations', headers=h(tech_juan_token))).json()
    assert len(listed) == 19
    assert len([i for i in listed if i['name'] == 'Santiago']) == 2
    assert (await client.post('/api/v1/locations', headers=h(tech_juan_token), json={'group_name':'EL POLLO LOCO','name':'Nueva'})).status_code == 403
    assert (await client.post('/api/v1/locations', headers=h(admin_token), json={'group_name':'EL POLLO LOCO','name':' expo '})).status_code == 409
    assert (await client.post('/api/v1/locations', headers=h(admin_token), json={'group_name':'Otras ubicaciones','name':'Bodega'})).status_code == 201
    location = str(location_id('EL POLLO LOCO','Santiago'))
    for payload in [{'title':'Prueba'}, {'title':'Prueba','location_id':str(uuid.uuid4())}]:
        assert (await client.post('/api/v1/tasks/unplanned', headers=h(tech_juan_token), json=payload)).status_code == 422
    response = await client.post('/api/v1/tasks/unplanned', headers=h(tech_juan_token), json={'title':'Prueba','location_id':location,'location_name':'Texto manipulado'})
    assert response.status_code == 200
    task = response.json()
    assert task['location_name'] == 'EL POLLO LOCO · Santiago'
    assert (await client.patch('/api/v1/locations/'+location, headers=h(admin_token), json={'is_active':False,'revision':0})).status_code == 200
    assert (await client.patch('/api/v1/locations/'+location, headers=h(admin_token), json={'is_active':True,'revision':0})).status_code == 409
    assert (await client.post('/api/v1/tasks/unplanned', headers=h(tech_juan_token), json={'title':'Otra','location_id':location})).status_code == 422
    original = await db.get(Task, uuid.UUID(task['id']))
    assert original.location_name == 'EL POLLO LOCO · Santiago'

@pytest.mark.asyncio
async def test_admin_tasks_require_catalog_and_preserve_legacy_until_edited(db, client, admin_token):
    tech = (await db.scalars(select(Technician))).first()
    payload = {'title':'Nueva tarea', 'assigned_date':str(today_local()), 'technician_id':str(tech.id)}
    assert (await client.post('/api/v1/admin/tasks', headers=h(admin_token), json=payload)).status_code == 422
    payload['location_id'] = str(location_id('TACO PALENQUE','Santiago'))
    response = await client.post('/api/v1/admin/tasks', headers=h(admin_token), json=payload)
    assert response.status_code == 201 and response.json()['location_name'] == 'TACO PALENQUE · Santiago'
    legacy = await db.scalar(select(Task).where(Task.location_id.is_(None), Task.status == 'PENDING'))
    before = legacy.location_name
    assert (await client.patch('/api/v1/admin/tasks/'+str(legacy.id), headers=h(admin_token), json={'title':'Modificar'})).status_code == 422
    await db.refresh(legacy)
    assert legacy.location_name == before
    fixed = await client.patch('/api/v1/admin/tasks/'+str(legacy.id), headers=h(admin_token), json={'title':'Modificar','location_id':payload['location_id']})
    assert fixed.status_code == 200
