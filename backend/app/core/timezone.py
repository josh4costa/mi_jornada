from zoneinfo import ZoneInfo
from datetime import datetime, date, timezone
from app.core.config import settings

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(settings.TIMEZONE))

def format_time_local(dt: datetime) -> str:
    local_dt = to_local(dt)
    return local_dt.strftime('%I:%M %p').lstrip('0')

def today_local() -> date:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()
