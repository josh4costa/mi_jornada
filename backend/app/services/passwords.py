import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, format_datetime, make_msgid
from sqlalchemy import update
from app.core.config import settings
from app.core.timezone import now_utc
from app.core.security import get_password_hash
from app.models.refresh_token import RefreshToken
from app.services.attendance import event


async def replace_password(db, user, password, *, temporary=False, actor_id=None):
    user.password_hash = get_password_hash(password)
    user.must_change_password = temporary
    user.credential_version += 1
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True))
    event(db, actor_id or user.id, user.id, 'PASSWORD_TEMPORARY_SET' if temporary else 'PASSWORD_CHANGED')


def send_recovery_email(email, token):
    """Background task: secrets/link are never logged. TLS certificate validation required."""
    smtp = None
    try:
        if settings.SMTP_SECURITY not in ('SSL', 'STARTTLS'):
            raise ValueError('TLS required')
        message = EmailMessage()
        message['From'] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM))
        message['To'] = email
        message['Subject'] = 'Mi Jornada | Establecer nueva contraseña'
        message['Date'] = format_datetime(now_utc())
        message['Message-ID'] = make_msgid(domain=settings.SMTP_FROM.split('@')[-1])
        # Fragment is not sent in web server requests or Referer headers.
        url = settings.APP_URL.rstrip('/') + '/recuperar-contrasena#token=' + token
        message.set_content(f'Se solicitó restablecer tu contraseña de Mi Jornada.\n\nAbre este enlace para elegir una nueva contraseña:\n{url}\n\nEl enlace vence en 30 minutos y puede usarse una sola vez. Si no solicitaste este cambio, ignora el correo; tu contraseña seguirá igual.\n\nGRUPO EXPO - Recursos Humanos')
        context = ssl.create_default_context()
        if settings.SMTP_SECURITY == 'SSL':
            smtp = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context)
        else:
            smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
            smtp.ehlo(); smtp.starttls(context=context); smtp.ehlo()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message, from_addr=settings.SMTP_FROM, to_addrs=[email])
    except Exception as exc:
        logging.getLogger(__name__).error('Password recovery email failed (%s)', type(exc).__name__)
    finally:
        if smtp:
            try:
                smtp.close()
            except Exception:
                pass
