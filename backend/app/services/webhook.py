"""Transactional outbox; at-least-once delivery with stable idempotency keys."""
import asyncio
import logging
from datetime import timedelta
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.core.timezone import now_utc
from app.models.webhook_delivery import WebhookDelivery

logger = logging.getLogger(__name__)

def enqueue_webhook(db, event_type: str, payload: dict) -> None:
    url = {
        "CHECK_IN": settings.WEBHOOK_CHECK_IN_URL,
        "CHECK_OUT": settings.WEBHOOK_CHECK_OUT_URL,
        "TASK_COMPLETED": settings.WEBHOOK_TASK_COMPLETED_URL,
    }.get(event_type)
    if url:
        db.add(WebhookDelivery(event_type=event_type, url=url, payload=payload))

async def deliver_one(db, client: httpx.AsyncClient) -> bool:
    delivery = await db.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.delivered_at.is_(None),
            WebhookDelivery.attempts < 10,
            WebhookDelivery.available_at <= now_utc(),
        ).order_by(WebhookDelivery.available_at).with_for_update(skip_locked=True).limit(1)
    )
    if delivery is None:
        await db.rollback()
        return False
    delivery.attempts += 1
    try:
        response = await client.post(
            delivery.url,
            json={"id": str(delivery.id), "event": delivery.event_type, "data": delivery.payload},
            headers={"Idempotency-Key": str(delivery.id)}, timeout=5,
        )
        response.raise_for_status()
        delivery.delivered_at = now_utc()
        delivery.last_error = None
    except httpx.HTTPError as exc:
        delivery.last_error = type(exc).__name__
        delivery.available_at = now_utc() + timedelta(seconds=min(3600, 2 ** delivery.attempts * 5))
        logger.warning("Webhook %s: intento %s fallido (%s)", delivery.id, delivery.attempts, delivery.last_error)
    await db.commit()
    return True

async def delivery_worker() -> None:
    from app.db.session import AsyncSessionLocal
    async with httpx.AsyncClient() as client:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    found = await deliver_one(db, client)
                if found:
                    continue
            except Exception as exc:
                logger.error("Fallo de cola de webhooks: %s", type(exc).__name__)
            await asyncio.sleep(5)
