"""Durable weekly snapshots. Claim before network I/O; never retry ambiguous delivery."""
import asyncio
import logging
import smtplib
import ssl
import uuid
from datetime import datetime, time, timedelta
from email.message import EmailMessage
from email.utils import formataddr, format_datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.timezone import now_utc, to_local
from app.db.session import AsyncSessionLocal
from app.models.weekly_report import WeeklyReportConfig, WeeklyReportRun
from app.services.attendance_report import report_data
from app.services.report_pdf import render_pdf

logger = logging.getLogger(__name__)


def smtp_configured():
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD and settings.SMTP_FROM
                and settings.SMTP_SECURITY in ('SSL', 'STARTTLS'))


def send_report(run):
    """Return (status, safe_error). Do not expose SMTP replies or credentials."""
    if not smtp_configured():
        return 'FAILED', 'SMTP no configurado.'
    message = EmailMessage()
    message['From'] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM))
    message['To'] = ', '.join(run.to_emails)
    if run.cc_emails:
        message['Cc'] = ', '.join(run.cc_emails)
    message['Subject'] = run.subject
    message['Date'] = format_datetime(now_utc())
    message['Message-ID'] = f'<asistencia-{run.id}@pleg.com.mx>'
    message.set_content(f'Buen día.\n\nAdjuntamos el reporte de asistencias del {run.period_start:%d/%m/%Y} al {run.period_end:%d/%m/%Y}.\n\nIncluye resumen por técnico, entradas, salidas, horas registradas y ausencias. Los registros pendientes de revisión no se consideran faltas confirmadas.\n\nConsulta y revisión: {settings.APP_URL}/admin/reportes\n\nGRUPO EXPO - Recursos Humanos')
    message.add_attachment(run.pdf, maintype='application', subtype='pdf', filename=run.filename)
    smtp = None
    sending = False
    try:
        context = ssl.create_default_context()
        if settings.SMTP_SECURITY == 'SSL':
            smtp = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30, context=context)
        else:
            smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        sending = True
        refused = smtp.send_message(message, from_addr=settings.SMTP_FROM, to_addrs=run.to_emails + run.cc_emails)
        return ('PARTIAL', 'El servidor rechazó algunos destinatarios; revisar antes de reenviar.') if refused else ('ACCEPTED', None)
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError):
        return 'FAILED', 'El servidor rechazó el envío; no aceptó el mensaje.'
    except Exception as exc:
        if sending:
            return 'UNKNOWN', 'Respuesta de envío no confirmada. Revisar el buzón antes de reenviar.'
        return 'FAILED', f'No se pudo conectar o autenticar SMTP ({type(exc).__name__}).'
    finally:
        if smtp:
            try:
                smtp.close()
            except Exception:
                pass


async def get_config(db):
    config = await db.get(WeeklyReportConfig, 1)
    if config is None:
        config = WeeklyReportConfig(id=1)
        db.add(config)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            config = await db.get(WeeklyReportConfig, 1)
    return config


def scheduled_at(day):
    return datetime.combine(day, time(9), ZoneInfo(settings.TIMEZONE))


def latest_due(config, now):
    local = to_local(now)
    monday = local.date() - timedelta(days=local.weekday())
    if local < scheduled_at(monday):
        monday -= timedelta(days=7)
    return monday if monday >= config.first_send_date else None


async def config_view(db):
    config = await get_config(db)
    now = now_utc()
    local = to_local(now)
    monday = max(config.first_send_date, local.date() - timedelta(days=local.weekday()))
    if scheduled_at(monday) <= local:
        monday += timedelta(days=7)
    return dict(enabled=config.enabled, first_send_date=config.first_send_date, to_emails=config.to_emails,
                cc_emails=config.cc_emails, revision=config.revision, timezone=settings.TIMEZONE,
                next_send=scheduled_at(monday) if config.enabled else None,
                sender=settings.SMTP_FROM, sender_name=settings.SMTP_FROM_NAME, smtp_configured=smtp_configured())


async def tick(now=None):
    now = now or now_utc()
    async with AsyncSessionLocal() as db:
        config = await get_config(db)
        if not config.enabled:
            return
        due = latest_due(config, now)
        if due is None:
            return
        cutoff = scheduled_at(due) + timedelta(hours=24)
        run = await db.scalar(select(WeeklyReportRun).where(WeeklyReportRun.scheduled_date == due))
        if run is None:
            start, end = due - timedelta(days=7), due - timedelta(days=1)
            data = await report_data(db, start, end)
            pdf = await asyncio.to_thread(render_pdf, data)
            run = WeeklyReportRun(id=uuid.uuid4(), scheduled_date=due, period_start=start, period_end=end,
                                  to_emails=list(config.to_emails), cc_emails=list(config.cc_emails),
                                  status='READY' if now < cutoff else 'EXPIRED', pdf=pdf,
                                  filename=f'asistencias_{start}_{end}.pdf',
                                  subject=f'GRUPO EXPO | Asistencias del {start:%d/%m/%Y} al {end:%d/%m/%Y}', available_at=now)
            db.add(run)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return
        # A crashed process may have sent its message. Never automatically resend it.
        await db.execute(update(WeeklyReportRun).execution_options(synchronize_session=False).where(WeeklyReportRun.id == run.id, WeeklyReportRun.status == 'SENDING',
            WeeklyReportRun.claimed_at < now - timedelta(minutes=5)).values(status='UNKNOWN', last_error='Envío interrumpido; verificar recepción antes de reenviar.'))
        if now >= cutoff:
            await db.execute(update(WeeklyReportRun).execution_options(synchronize_session=False).where(WeeklyReportRun.id == run.id,
                WeeklyReportRun.status.in_(['READY', 'FAILED'])).values(status='EXPIRED', last_error='Se venció la ventana de envío de 24 horas. Descargar el PDF para revisión.'))
            await db.commit()
            return
        # UPDATE predicate is the cross-worker atomic claim (also portable to SQLite tests).
        claimed = await db.execute(update(WeeklyReportRun).execution_options(synchronize_session=False).where(WeeklyReportRun.id == run.id,
            WeeklyReportRun.status.in_(['READY', 'FAILED']), WeeklyReportRun.attempts < 3,
            WeeklyReportRun.available_at <= now).values(status='SENDING', claimed_at=now, attempts=WeeklyReportRun.attempts+1))
        await db.commit()
        if not claimed.rowcount:
            return
        await db.refresh(run)
        status, error = await asyncio.to_thread(send_report, run)
        await db.execute(update(WeeklyReportRun).execution_options(synchronize_session=False).where(WeeklyReportRun.id == run.id, WeeklyReportRun.status == 'SENDING').values(
            status=status, last_error=error, sent_at=now_utc() if status in ('ACCEPTED', 'PARTIAL') else None,
            available_at=now + timedelta(minutes=10)))
        await db.commit()


async def weekly_report_worker():
    while True:
        try:
            await tick()
        except Exception as exc:
            logger.error('Weekly report worker failed (%s)', type(exc).__name__)
        await asyncio.sleep(30)
