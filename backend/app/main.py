"""app/main.py  —  CORREGIDO

 - app.state.limiter registrado (sin esto, al pasar el limite de login devuelve 500).
 - CORS: '*' + allow_credentials=True es invalido; ahora se permite '*' solo sin
   credenciales y en produccion se exige lista explicita (ver config.py).
 - /health verifica la base de datos, no solo el proceso (util para healthcheck de Docker).
 - Logging basico configurado.
"""
import logging
import os
import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.limiter import limiter

logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("mi_jornada")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "development" and os.environ.get("TESTING") != "1":
        from app.db.init_db import seed_demo_data
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await seed_demo_data(db)
    logger.info("Mi Jornada API iniciada (env=%s, tz=%s)", settings.ENVIRONMENT, settings.TIMEZONE)
    from app.services.webhook import delivery_worker
    worker = asyncio.create_task(delivery_worker()) if os.environ.get("TESTING") != "1" else None
    from app.services.reminders import attendance_worker
    attendance = asyncio.create_task(attendance_worker()) if os.environ.get("TESTING") != "1" else None
    from app.services.weekly_reports import weekly_report_worker
    weekly_reports = asyncio.create_task(weekly_report_worker()) if os.environ.get("TESTING") != "1" else None
    try:
        yield
    finally:
        if weekly_reports:
            weekly_reports.cancel()
            with suppress(asyncio.CancelledError):
                await weekly_reports
        if attendance:
            attendance.cancel()
            with suppress(asyncio.CancelledError):
                await attendance
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        from app.db.session import engine
        await engine.dispose()


app = FastAPI(
    title="Mi Jornada API",
    version="1.0.0",
    description="API para control diario de personal tecnico en campo",
    lifespan=lifespan,
    # En produccion no publicar el esquema interactivo:
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

_allow_credentials = "*" not in settings.BACKEND_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check():
    from app.core.timezone import now_utc
    from app.db.session import AsyncSessionLocal

    db_ok = True
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        db_ok = False
        logger.error("Healthcheck DB fallo: %s", exc)

    body = {"status": "ok" if db_ok else "degraded", "database": db_ok,
            "timestamp": now_utc().isoformat()}
    return JSONResponse(body, status_code=200 if db_ok else 503)
