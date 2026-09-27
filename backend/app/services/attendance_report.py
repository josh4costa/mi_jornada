from datetime import date, timedelta

from sqlalchemy import select

from sqlalchemy.orm import selectinload

from app.core.timezone import now_utc, to_local

from app.core.config import settings

from app.models import Technician, UserRole, Workday

from app.models.attendance import LeaveRequest, AttendanceIncident

from app.services.attendance import schedule

from app.services.night_shift import day_exception

from app.models.night_plan import NightPlan





def duration(minutes):

    return f'{minutes // 60} h {minutes % 60:02d} min'





async def report_data(db, start: date, end: date, technician_id=None):

    generated = now_utc()

    today = to_local(generated).date()

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    technicians = (await db.scalars(select(Technician).options(selectinload(Technician.user)).order_by(Technician.id))).all()

    workdays = (await db.scalars(select(Workday).where(Workday.work_date >= start, Workday.work_date <= end, Workday.is_void.is_(False)))).all()

    leaves = (await db.scalars(select(LeaveRequest).where(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start, LeaveRequest.status == 'APPROVED'))).all()

    incidents = (await db.scalars(select(AttendanceIncident).where(AttendanceIncident.work_date >= start, AttendanceIncident.work_date <= end))).all()

    result = []

    for tech in technicians:

        if technician_id and tech.id != technician_id:

            continue

        active = tech.is_active and tech.user.is_active and tech.user.role == UserRole.TECHNICIAN

        tw = {w.work_date: w for w in workdays if w.technician_id == tech.id and w.shift_kind == "DAY"}

        nights = [w for w in workdays if w.technician_id == tech.id and w.shift_kind == "NIGHT"]

        tl = [l for l in leaves if l.technician_id == tech.id]

        ti = [i for i in incidents if i.technician_id == tech.id]

        if not active and not tw and not tl and not ti and not nights:

            continue

        summary = dict(recorded=0, open=0, minutes=0, late=0, early=0, vacation=0, permission=0, pending=0, unjustified=0, justified=0)

        detail = []

        for day in days:

            exemption = await day_exception(db, tech.id, day)

            hours = schedule(day)

            wd = tw.get(day)

            leave = next((l for l in tl if l.start_date <= day <= l.end_date), None)

            missing = next((i for i in ti if i.work_date == day and i.kind == 'MISSING_ENTRY'), None)

            early = next((i for i in ti if i.work_date == day and i.kind == 'EARLY_EXIT'), None)

            notes = []

            if wd:

                summary['recorded'] += 1

                if wd.check_out_at:

                    summary['minutes'] += wd.duration_minutes or 0

                    state = 'Registrada'

                else:

                    summary['open'] += 1

                    state = 'Jornada abierta'

                if hours and to_local(wd.check_in_at) > hours[0]:

                    summary['late'] += 1

                    notes.append('Entrada después de 09:00')

                if hours and wd.check_out_at and to_local(wd.check_out_at) < hours[1]:

                    summary['early'] += 1

                    resolution = {'JUSTIFIED': 'justificada', 'UNJUSTIFIED': 'no justificada', 'PENDING': 'pendiente'}

                    notes.append('Salida anticipada: ' + resolution.get(early.status if early else 'PENDING', 'pendiente'))

                if leave:

                    notes.append('Registro durante ausencia aprobada; revisar')

                if not hours:

                    notes.append('Trabajo en día de descanso')

                if wd.duration_minutes and wd.duration_minutes > 16 * 60:

                    notes.append('Duración mayor a 16 horas; revisar')

            elif day > today:

                state = 'Día futuro'

            elif not hours:

                state = 'Descanso'

            elif to_local(tech.created_at).date() > day:

                state = 'Antes del alta en el sistema'

            elif leave:

                state = 'Vacaciones aprobadas' if leave.kind == 'VACATION' else 'Permiso aprobado'

                summary['vacation' if leave.kind == 'VACATION' else 'permission'] += 1

            elif exemption:

                state = 'Descanso diurno por noche autorizada'

            elif missing and missing.status == 'UNJUSTIFIED':

                state = 'Falta no justificada (revisada)'

                summary['unjustified'] += 1

            elif exemption:
                state = 'Descanso diurno por noche autorizada'
            elif missing and missing.status == 'JUSTIFIED':

                state = 'Inasistencia justificada'

                summary['justified'] += 1

            elif day == today:

                state = 'Día en curso, sin entrada'

            elif not active:

                state = 'Sin registro; cuenta inactiva'

                notes.append('Revisar vigencia del personal')

            else:

                state = 'Sin entrada, pendiente de revisión'

                summary['pending'] += 1

            detail.append({'date': day.isoformat(), 'schedule': 'Descanso autorizado' if exemption else (('09:00 - ' + hours[1].strftime('%H:%M')) if hours else 'Descanso'),

                'entry': to_local(wd.check_in_at).strftime('%d/%m %H:%M') if wd else '-',

                'exit': to_local(wd.check_out_at).strftime('%d/%m %H:%M') if wd and wd.check_out_at else '-',

                'hours': duration(wd.duration_minutes or 0) if wd and wd.check_out_at else '-',

                'state': state, 'notes': '; '.join(notes) or '-'})

        for wd in sorted(nights, key=lambda w: w.check_in_at):

            if wd.work_date not in tw:

                summary['recorded'] += 1

            summary['minutes'] += wd.duration_minutes or 0

            summary['open'] += int(wd.check_out_at is None)

            detail.append({'date': wd.work_date.isoformat(), 'schedule': 'Nocturno flexible',

                'entry': to_local(wd.check_in_at).strftime('%d/%m %H:%M'),

                'exit': to_local(wd.check_out_at).strftime('%d/%m %H:%M') if wd.check_out_at else '-',

                'hours': duration(wd.duration_minutes or 0) if wd.check_out_at else '-',

                'state': 'Nocturna registrada' if wd.check_out_at else 'Nocturna abierta',

                'notes': 'Duración mayor a 16 horas; revisar' if (wd.duration_minutes or 0) > 960 else 'Sin horario fijo. La fecha corresponde a la entrada.'})

        plans = (await db.scalars(select(NightPlan).where(NightPlan.technician_id == tech.id, NightPlan.work_date >= start, NightPlan.work_date <= end, NightPlan.status.in_(['PENDING', 'APPROVED'])))).all()

        for plan in plans:

            if not any(w.work_date == plan.work_date for w in nights):

                pending = plan.work_date < today

                if pending:

                    summary['pending'] += 1

                detail.append({'date': plan.work_date.isoformat(), 'schedule': 'Nocturno flexible', 'entry': '-', 'exit': '-', 'hours': '-',

                    'state': ({'JUSTIFIED': 'Noche sin entrada justificada', 'UNJUSTIFIED': 'Noche: falta no justificada (revisada)'}.get(resolved, 'Noche sin entrada; revisar')) if pending else 'Noche programada',

                    'notes': 'Programación pendiente de validación' if plan.status == 'PENDING' else 'Programación autorizada'})

        detail.sort(key=lambda row: row['date'])

        result.append({'name': tech.user.full_name, 'employee_number': tech.employee_number or '-', 'active': active, 'summary': summary, 'days': detail})

    result.sort(key=lambda row: row['name'].casefold())

    totals = {key: sum(row['summary'][key] for row in result) for key in ['recorded', 'open', 'minutes', 'late', 'early', 'vacation', 'permission', 'pending', 'unjustified', 'justified']}

    return {'start': start.isoformat(), 'end': end.isoformat(), 'generated': to_local(generated).strftime('%d/%m/%Y %H:%M'), 'timezone': settings.TIMEZONE, 'technicians': result, 'totals': totals}

