"""Printable attendance snapshot. All database text is escaped before rendering."""
from io import BytesIO
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from app.services.attendance_report import duration


def render_pdf(data):
    output = BytesIO()
    width = landscape(A4)[0] - 72
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#25344a'))
    heading = ParagraphStyle('heading', parent=body, fontName='Helvetica-Bold', fontSize=20, leading=25, spaceAfter=8)
    sub = ParagraphStyle('sub', parent=body, fontName='Helvetica-Bold', fontSize=12, leading=16, spaceAfter=8)
    white = ParagraphStyle('white', parent=body, fontName='Helvetica-Bold', textColor=colors.white)
    def p(value, style=body):
        return Paragraph(escape(str(value)), style)
    def table(headers, rows, widths):
        t = Table([[p(h, white) for h in headers]] + [[p(v) for v in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17283e')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#d9e1e9')),
        ]))
        return t
    period = f"{date.fromisoformat(data['start']):%d/%m/%Y} al {date.fromisoformat(data['end']):%d/%m/%Y}"
    story = [p('GRUPO EXPO · Recursos Humanos', sub), p('Reporte de asistencias', heading), p(period, sub),
             p(f"Generado: {data['generated']} · Zona horaria: {data['timezone']}"), Spacer(1, 16)]
    if data.get('sample'):
        story += [p('EJEMPLO ILUSTRATIVO · Datos ficticios', sub), Spacer(1, 8)]
    totals = data['totals']
    story += [p(f"{len(data['technicians'])} técnicos · {totals['recorded']} días con entrada · {duration(totals['minutes'])} registradas · {totals['open']} jornadas abiertas", sub)]
    rows = []
    for tech in data['technicians']:
        s = tech['summary']
        rows.append([tech['name'], s['recorded'], s['open'], duration(s['minutes']), s['late'], s['early'], s['vacation'], s['permission'], s['pending'], s['unjustified']])
    if rows:
        story += [table(['Técnico', 'Días con entrada', 'Sin cerrar', 'Horas registradas', 'Entradas después de 09:00', 'Salidas anticipadas', 'Vacaciones', 'Permisos', 'Sin entrada: por revisar', 'Faltas no justificadas: revisadas'], rows, [width*.22, width*.07, width*.06, width*.12, width*.09, width*.08, width*.08, width*.07, width*.10, width*.11])]
    else:
        story += [p('Sin personal ni movimientos para este período.')]
    story += [Spacer(1, 15), p('Criterios de lectura', sub)]
    for line in [
        'Horario: lunes a viernes 09:00–18:00; sábado 09:00–13:00. Domingo: descanso.',
        'Turnos nocturnos: horario flexible; se muestran por separado. Un día con turno diurno y nocturno cuenta una sola vez en días con entrada. Los indicadores de horario aplican solo al turno diurno.',
        'Las horas son el tiempo entre entrada y salida de jornadas cerradas; no descuentan comidas ni representan un cálculo de nómina. Las jornadas abiertas y anuladas no suman horas.',
        'Un día sin entrada queda pendiente de revisión. Solo las incidencias revisadas como no justificadas se muestran como faltas no justificadas.',
        'Vacaciones y permisos corresponden a ausencias aprobadas en días laborables. Entradas posteriores a las 09:00 y salidas anticipadas son indicadores para revisión.',
        'El detalle incluye las inasistencias justificadas. La fecha de alta corresponde al sistema; la vigencia histórica del personal debe revisarse cuando la cuenta esté inactiva.',
    ]:
        story += [p(line), Spacer(1, 6)]
    for tech in data['technicians']:
        s = tech['summary']
        story += [PageBreak(), p('Detalle por técnico', sub), p(tech['name'], heading),
                  p(f"No. empleado: {tech['employee_number']} · {period} · Cuenta {'activa' if tech['active'] else 'inactiva'}"), Spacer(1, 10),
                  p(f"{s['recorded']} días con entrada · {duration(s['minutes'])} registradas · {s['open']} sin cerrar · {s['justified']} inasistencias justificadas"), Spacer(1, 12)]
        rows = [[d['date'], d['schedule'], d['entry'], d['exit'], d['hours'], d['state'], d['notes']] for d in tech['days']]
        story += [table(['Fecha', 'Horario', 'Entrada', 'Salida', 'Horas', 'Estado', 'Observaciones'], rows,
                        [width*.085, width*.10, width*.085, width*.085, width*.10, width*.22, width*.325])]
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#d9e1e9'))
        canvas.line(36, 30, width+36, 30)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#566579'))
        canvas.drawString(36, 18, f"Mi Jornada · {'EJEMPLO FICTICIO' if data.get('sample') else 'Uso interno'} · {period}")
        canvas.drawRightString(width+36, 18, f'Página {doc.page}')
        canvas.restoreState()
    SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=32, bottomMargin=42,
                      title='Reporte de asistencias - GRUPO EXPO', author='GRUPO EXPO - Recursos Humanos').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
