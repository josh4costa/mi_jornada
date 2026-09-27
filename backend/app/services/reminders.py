"""One reminder per person/day/kind. Ambiguous sends are never automatically repeated."""
import asyncio
import logging
import re
from datetime import date, timedelta, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.timezone import now_utc, to_local
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.workday import Workday, WorkdayStatus
from app.models.attendance import ReminderDelivery, AttendanceScan, AttendanceEvent
from app.models.task import Task, TaskStatus
from app.models.night_plan import NightPlan
from app.services.night_shift import day_exception
from app.services.attendance import schedule, approved_leave, generate_missing

logger = logging.getLogger(__name__)


def message(name, kind):
    greeting = f'Hola, {name} 👋 '
    if kind in ('TASKS_DAY', 'TASKS_NIGHT'):
        return (greeting + 'Ya registraste tu entrada, pero aún no aparecen tareas para tu jornada. Entra a Mi Jornada y registra las actividades que realizarás para mantener actualizado tu trabajo:\n' + settings.APP_URL + '\n\nSi todavía estás esperando asignación de actividades, comunícalo a tu supervisor.')
    if kind == 'NIGHT_ENTRY':
        return (greeting + 'Tienes programado trabajo nocturno. Si ya vas a comenzar, entra a Mi Jornada y pulsa Iniciar turno nocturno:\n' + settings.APP_URL + '\n\nEste mensaje no registra tu entrada. Si cambió la programación, avisa al supervisor y actualízala en la app.')
    if kind == 'ENTRY':
        return (greeting + 'Aún no tenemos tu registro de entrada de hoy. Tu horario comienza a las 9:00 a. m.\n\n'
                + f'Ingresa y registra tu entrada:\n{settings.APP_URL}\n\n'
                + 'Si no registras entrada durante el día y no tienes una ausencia autorizada o una incidencia validada, '
                + 'el día se marcará como posible falta injustificada, pendiente de revisión del administrador.\n\n'
                + 'Si hoy trabajarás de noche en lugar del turno diurno, entra a Ausencias y asistencia > Turnos nocturnos para avisarlo. Requiere validación del administrador. Si tienes algún problema para registrar, avisa a tu supervisor.')
    return (greeting + 'Tu jornada sigue abierta. Si ya terminaste, entra a Mi Jornada y registra tu salida:\n'
            + settings.APP_URL + '\n\nSi sigues trabajando, registra tu salida cuando termines.')


async def eligible(db, tech_id, day, kind, workday_id=None, current=None):
    tech = await db.scalar(select(Technician).options(selectinload(Technician.user)).where(Technician.id == tech_id))
    if not tech or not tech.is_active or not tech.user.is_active or tech.user.role != UserRole.TECHNICIAN or not tech.reminders_enabled:
        return None
    if not tech.phone or not re.fullmatch(r'\+[1-9]\d{7,14}', tech.phone) or await approved_leave(db, tech.id, day):
        return None
    if kind in ('TASKS_DAY', 'TASKS_NIGHT'):
        current = current or now_utc()
        wd = await db.get(Workday, workday_id) if workday_id else None
        if not wd or wd.technician_id != tech_id or wd.is_void or wd.status != WorkdayStatus.OPEN or wd.work_date != day or kind != 'TASKS_' + wd.shift_kind:
            return None
        entry = wd.check_in_at.replace(tzinfo=timezone.utc) if wd.check_in_at.tzinfo is None else wd.check_in_at
        if not entry + timedelta(minutes=30) <= current < entry + timedelta(minutes=60):
            return None
        dates = {wd.work_date, to_local(current).date()}
        # A continuous night/day shift inherits tasks and any reminder from its night.
        transitions = (await db.scalars(select(AttendanceEvent).where(AttendanceEvent.actor_id == tech.user_id, AttendanceEvent.action == 'NIGHT_CONTINUED_DAY'))).all()
        for transition in transitions:
            if transition.details.get('day_workday_id') != str(wd.id):
                continue
            night = await db.get(Workday, transition.entity_id)
            if night and night.technician_id == tech_id:
                dates.add(night.work_date)
                reminded = await db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.technician_id == tech_id, ReminderDelivery.work_date == night.work_date, ReminderDelivery.kind == 'TASKS_NIGHT', ReminderDelivery.status != 'SKIPPED'))
                if reminded:
                    return None
        task = await db.scalar(select(Task.id).where(Task.technician_id == tech_id, Task.assigned_date.in_(dates), Task.status != TaskStatus.CANCELLED).limit(1))
        return None if task else tech
    days = (await db.scalars(select(Workday).where(Workday.is_void.is_(False), Workday.technician_id == tech.id, (Workday.work_date == day) | (Workday.status == WorkdayStatus.OPEN)))).all()
    if kind == 'NIGHT_ENTRY':
        plan = await db.scalar(select(NightPlan.id).where(NightPlan.technician_id == tech.id, NightPlan.work_date == day, NightPlan.status.in_(['PENDING', 'APPROVED'])))
        return tech if plan and not any(w.work_date == day and w.shift_kind == 'NIGHT' for w in days) else None
    if await day_exception(db, tech.id, day, include_pending=True):
        return None
    if kind == 'ENTRY' and any((w.work_date == day and w.shift_kind == 'DAY') or w.status == WorkdayStatus.OPEN for w in days):
        return None
    if kind == 'EXIT' and not any(w.status == WorkdayStatus.OPEN and w.shift_kind == 'DAY' for w in days):
        return None
    return tech


async def provider_connected(client):
    response = await client.get(f'https://api.ultramsg.com/{settings.ULTRAMSG_INSTANCE}/instance/status', params={'token': settings.ULTRAMSG_TOKEN}, timeout=10)
    response.raise_for_status()
    data = response.json()
    status = data.get('status', {})
    if isinstance(status, dict):
        status = status.get('accountStatus', {})
    if isinstance(status, dict):
        status = status.get('status')
    return status == 'authenticated'


async def send_reminder(db, client, tech_id, day, kind, workday_id=None, current=None):
    tech = await eligible(db, tech_id, day, kind, workday_id, current)
    if not tech:
        return
    delivery = ReminderDelivery(technician_id=tech.id, work_date=day, kind=kind)
    db.add(delivery)
    try:
        await db.commit()  # Claim survives restarts and concurrent workers.
    except IntegrityError:
        await db.rollback()
        return
    # Re-evaluate immediately before sending, after the claim transaction.
    delivery_id = delivery.id
    db.expire_all()
    delivery = await db.get(ReminderDelivery, delivery_id)
    tech = await eligible(db, tech_id, day, kind, workday_id, current)
    if not tech:
        delivery.status = 'SKIPPED'
        await db.commit()
        return
    try:
        response = await client.post(f'https://api.ultramsg.com/{settings.ULTRAMSG_INSTANCE}/messages/chat', data={
            'token': settings.ULTRAMSG_TOKEN, 'to': tech.phone, 'body': message(tech.user.full_name.split()[0], kind)}, timeout=15)
        data = response.json()
        if response.is_success and str(data.get('sent')).lower() == 'true' and data.get('id'):
            delivery.status = 'ACCEPTED'
            delivery.provider_id = str(data['id'])[:100]
            delivery.sent_at = now_utc()
        else:
            delivery.status = 'FAILED'
            delivery.error = 'Proveedor rechazó el envío; revisar UltraMsg'
    except (httpx.HTTPError, ValueError):
        delivery.status = 'UNKNOWN'
        delivery.error = 'Resultado incierto; no se reenvía para evitar duplicados'
    await db.commit()


async def scan_one_day(db, current):
    if not settings.ATTENDANCE_START_DATE:
        return False
    start = date.fromisoformat(settings.ATTENDANCE_START_DATE)
    cursor = await db.scalar(select(AttendanceScan).where(AttendanceScan.id == 1).with_for_update())
    if cursor is None:
        db.add(AttendanceScan(id=1))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        return True
    day = max(start, cursor.last_day + timedelta(days=1)) if cursor.last_day else start
    if day >= to_local(current).date():
        await db.rollback()
        return False
    techs = (await db.scalars(select(Technician).join(User).where(Technician.is_active.is_(True), User.is_active.is_(True), User.role == UserRole.TECHNICIAN).order_by(Technician.id).with_for_update(of=Technician))).all()
    for tech in techs:
        await generate_missing(db, tech, day)
    cursor.last_day = day
    await db.commit()
    return True


async def tick(db, client, current=None):
    current = current or now_utc()
    local = to_local(current)
    while await scan_one_day(db, current):
        pass
    stale = (await db.scalars(select(ReminderDelivery).where(ReminderDelivery.status == 'CLAIMED', ReminderDelivery.created_at < current - timedelta(minutes=5)))).all()
    for row in stale:
        row.status, row.error = 'UNKNOWN', 'Envío interrumpido; comprobar en UltraMsg'
    await db.commit()
    hours = schedule(local.date())
    if not settings.REMINDERS_ENABLED or not settings.ULTRAMSG_TOKEN or not settings.ULTRAMSG_INSTANCE:
        return
    kinds = [kind for kind, at in zip(['ENTRY', 'EXIT'], hours or []) if at + timedelta(minutes=10) <= local < at + timedelta(minutes=40)]
    night_plans = (await db.execute(select(NightPlan.technician_id, NightPlan.work_date).where(NightPlan.status.in_(['PENDING', 'APPROVED']), NightPlan.reminder_at <= current, NightPlan.reminder_at > current - timedelta(minutes=30)))).all()
    task_shifts = (await db.execute(select(Workday.id, Workday.technician_id, Workday.work_date, Workday.shift_kind).where(
        Workday.is_void.is_(False), Workday.status == WorkdayStatus.OPEN,
        Workday.check_in_at <= current - timedelta(minutes=30), Workday.check_in_at > current - timedelta(minutes=60)))).all()
    if not kinds and not night_plans and not task_shifts:
        return
    ids = (await db.scalars(select(Technician.id).where(Technician.reminders_enabled.is_(True)))).all()
    if not ids or not await provider_connected(client):
        return
    for workday_id, tech_id, day, shift in task_shifts:
        kind = 'TASKS_' + shift
        exists = await db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.technician_id == tech_id, ReminderDelivery.work_date == day, ReminderDelivery.kind == kind))
        if not exists:
            await send_reminder(db, client, tech_id, day, kind, workday_id=workday_id, current=current)
    for plan_tech_id, plan_date in night_plans:
        exists = await db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.technician_id == plan_tech_id, ReminderDelivery.work_date == plan_date, ReminderDelivery.kind == 'NIGHT_ENTRY'))
        if not exists:
            await send_reminder(db, client, plan_tech_id, plan_date, 'NIGHT_ENTRY')
    for tech_id in ids:
        for kind in kinds:
            exists = await db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.technician_id == tech_id, ReminderDelivery.work_date == local.date(), ReminderDelivery.kind == kind))
            if not exists:
                await send_reminder(db, client, tech_id, local.date(), kind)


async def attendance_worker():
    from app.db.session import AsyncSessionLocal
    # HTTPX logs URLs including query tokens at INFO; disable request logs globally.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    async with httpx.AsyncClient(headers={"User-Agent": "MiJornada/1.0"}) as client:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    await tick(db, client)
            except Exception as exc:
                logger.error('Control de asistencia: %s', type(exc).__name__)
            await asyncio.sleep(30)
