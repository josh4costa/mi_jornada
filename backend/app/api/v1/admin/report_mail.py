import asyncio
import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from app.api.deps import get_current_admin_user, get_current_panel_user
from app.db.session import get_db
from app.models.weekly_report import WeeklyReportConfig, WeeklyReportRun
from app.services.weekly_reports import get_config, config_view
from app.services.attendance_report import report_data
from app.services.report_pdf import render_pdf
from app.services.attendance import event

router = APIRouter(dependencies=[Depends(get_current_panel_user)])


class ConfigUpdate(BaseModel):
    enabled: bool
    first_send_date: date
    to_emails: list[EmailStr] = Field(min_length=1, max_length=20)
    cc_emails: list[EmailStr] = Field(max_length=20)
    revision: int = Field(ge=0)

    @model_validator(mode='after')
    def validate_schedule(self):
        if self.first_send_date.weekday() != 0:
            raise ValueError('La fecha inicial debe ser lunes.')
        emails = [str(x).lower() for x in self.to_emails + self.cc_emails]
        if len(emails) != len(set(emails)) or len(emails) > 20:
            raise ValueError('Usa correos únicos; máximo 20 destinatarios en total.')
        return self


@router.get('')
async def read_config(db=Depends(get_db), user=Depends(get_current_admin_user)):
    return await config_view(db)


@router.patch('')
async def save_config(payload: ConfigUpdate, db=Depends(get_db), actor=Depends(get_current_admin_user)):
    await get_config(db)
    config = await db.scalar(select(WeeklyReportConfig).where(WeeklyReportConfig.id == 1).with_for_update().execution_options(populate_existing=True))
    if config.revision != payload.revision:
        raise HTTPException(409, 'Otro administrador cambió la configuración. Recarga antes de guardar.')
    before = dict(enabled=config.enabled, first_send_date=str(config.first_send_date), to_emails=config.to_emails, cc_emails=config.cc_emails)
    config.enabled = payload.enabled
    config.first_send_date = payload.first_send_date
    config.to_emails = [str(x).lower() for x in payload.to_emails]
    config.cc_emails = [str(x).lower() for x in payload.cc_emails]
    config.revision += 1
    config.updated_by = actor.id
    event(db, actor.id, uuid.UUID(int=1), 'WEEKLY_REPORT_CONFIG_UPDATED', before=before, after=payload.model_dump(mode='json'))
    await db.commit()
    return await config_view(db)


@router.get('/runs')
async def history(db=Depends(get_db), user=Depends(get_current_admin_user)):
    fields = [WeeklyReportRun.id, WeeklyReportRun.scheduled_date, WeeklyReportRun.period_start, WeeklyReportRun.period_end,
              WeeklyReportRun.status, WeeklyReportRun.to_emails, WeeklyReportRun.cc_emails, WeeklyReportRun.attempts,
              WeeklyReportRun.sent_at, WeeklyReportRun.last_error]
    return [dict(row) for row in (await db.execute(select(*fields).order_by(WeeklyReportRun.scheduled_date.desc()).limit(30))).mappings()]


def pdf_response(pdf, filename):
    return Response(pdf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'private, no-store'})


@router.get('/pdf')
async def preview(date_from: date, date_to: date, technician_id: uuid.UUID | None = None, db=Depends(get_db)):
    if not 0 <= (date_to-date_from).days <= 30:
        raise HTTPException(422, 'Selecciona un período de 1 a 31 días para el PDF.')
    data = await report_data(db, date_from, date_to, technician_id)
    return pdf_response(await asyncio.to_thread(render_pdf, data), f'asistencias_{date_from}_{date_to}.pdf')


@router.get('/runs/{run_id}/pdf')
async def stored_pdf(run_id: uuid.UUID, db=Depends(get_db)):
    run = await db.get(WeeklyReportRun, run_id)
    if not run:
        raise HTTPException(404, 'Reporte no encontrado.')
    return pdf_response(run.pdf, run.filename)
