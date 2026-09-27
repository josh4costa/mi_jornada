import { useCallback, useEffect, useState } from 'react';
import client from '../api/client';
import NightPlans from '../components/NightPlans';
import { adminApi } from '../api/adminApi';
import { useAuth } from '../hooks/useAuth';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Modal from '../components/ui/Modal';
import Spinner from '../components/ui/Spinner';

interface Leave { id: string; technician_name: string; kind: string; start_date: string; end_date: string; reason: string; status: string; working_days: number; review_note?: string }
interface Incident { id: string; technician_name: string; kind: string; work_date: string; reason: string; status: string; review_note?: string }
interface Delivery { id: string; technician_name: string; work_date: string; kind: string; status: string; error?: string }
const labels: Record<string, string> = { PENDING: 'Pendiente', APPROVED: 'Aprobada', REJECTED: 'Rechazada', CANCELLED: 'Cancelada', JUSTIFIED: 'Justificada', UNJUSTIFIED: 'No justificada', VACATION: 'Vacaciones', PERMISSION: 'Permiso', EARLY_EXIT: 'Salida anticipada', MISSING_NIGHT: 'Noche programada sin entrada', MISSING_ENTRY: 'Sin registro de entrada', TASKS_DAY: 'Registrar tareas (diurna)', TASKS_NIGHT: 'Registrar tareas (nocturna)', NIGHT_ENTRY: 'Entrada nocturna', ENTRY: 'Entrada', EXIT: 'Salida', CLAIMED: 'Procesando', ACCEPTED: 'Aceptado por UltraMsg', FAILED: 'Falló', UNKNOWN: 'Por comprobar en UltraMsg', SKIPPED: 'Omitido' };
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const localToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Monterrey' }).format(new Date());
const input = 'w-full border border-slate-300 rounded-lg p-2 mt-1 bg-white';

export default function Attendance() {
  const { user } = useAuth();
  const admin = user?.role === 'ADMIN';
  const readOnly = user?.role === 'READ_ONLY';
  const panel = admin || readOnly;
  const [tab, setTab] = useState('leaves');
  const [month, setMonth] = useState(localToday().slice(0, 7));
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [delivery, setDelivery] = useState<{ configured: boolean; enabled: boolean; items: Delivery[] } | null>(null);
  const [techs, setTechs] = useState<{ id: string; full_name: string }[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('PENDING');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState('');
  const [create, setCreate] = useState(false);
  const [form, setForm] = useState({ technician_id: '', kind: 'VACATION', start_date: localToday(), end_date: localToday(), reason: '' });
  const [review, setReview] = useState<{ id: string; type: string; status: string } | null>(null);
  const [note, setNote] = useState('');
  const [audit, setAudit] = useState<{ action: string; created_at: string; details: { status?: string; note?: string } }[] | null>(null);
  const [year, monthNumber] = month.split('-').map(Number);
  const lastDay = dateKey(new Date(year, monthNumber, 0));
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      if (tab === 'leaves') setLeaves((await client.get('/attendance/leaves', { params: { date_from: month + '-01', date_to: lastDay, include_pending: panel } })).data);
      if (tab === 'incidents') {
        const { data } = await client.get('/attendance/incidents', { params: { status: status || undefined, page } });
        setIncidents(data.items); setTotal(data.total);
      }
      if (tab === 'reminders') setDelivery((await client.get('/attendance/reminders')).data);
    } catch (err: any) { setError(err.friendlyMessage || 'No se pudo cargar la información.'); }
    finally { setLoading(false); }
  }, [tab, month, lastDay, panel, status, page]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (admin) adminApi.getTechnicians().then(setTechs).catch(() => setError('No se pudo cargar el personal. Actualiza la página.'));
  }, [admin]);
  async function saveLeave() {
    setSaving(true); setModalError('');
    try {
      await client.post('/attendance/leaves', { ...form, technician_id: admin ? form.technician_id : undefined });
      setCreate(false); setMonth(form.start_date.slice(0, 7)); setNotice('Solicitud enviada. Requiere aprobación del administrador.'); await load();
    } catch (err: any) { setModalError(err.friendlyMessage || 'No se pudo guardar la solicitud.'); }
    finally { setSaving(false); }
  }
  async function saveReview() {
    if (!review) return;
    setSaving(true); setModalError('');
    try {
      await client.patch(`/attendance/${review.type}/${review.id}`, { status: review.status, note });
      setReview(null); setNotice('Revisión guardada con su motivo.'); await load();
    } catch (err: any) { setModalError(err.friendlyMessage || 'No se pudo guardar la revisión.'); }
    finally { setSaving(false); }
  }
  function decision(id: string, type: string, next: string) { setReview({ id, type, status: next }); setNote(''); setModalError(''); }
  const dates = Array.from({ length: new Date(year, monthNumber, 0).getDate() }, (_, i) => dateKey(new Date(year, monthNumber - 1, i + 1)));
  const offset = (new Date(year, monthNumber - 1, 1).getDay() + 6) % 7;
  let requestedDays = 0;
  const start = new Date(form.start_date + 'T12:00:00'), end = new Date(form.end_date + 'T12:00:00');
  if (end >= start && (end.getTime() - start.getTime()) / 86400000 <= 365) {
    for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) if (day.getDay() !== 0) requestedDays++;
  }
  return <div className="space-y-5 max-w-6xl mx-auto">
    <h1 className="text-2xl font-bold">Ausencias y asistencia</h1>
    <p className="text-sm text-muted">Lunes a viernes 9:00–18:00 · sábado 9:00–13:00 · domingo descanso. Horario de Monterrey.</p>
    <div className="flex flex-wrap gap-2">
      {[['leaves', 'Vacaciones y permisos'], ['incidents', 'Incidencias'], ['nights', 'Turnos nocturnos'], ...(admin ? [['reminders', 'WhatsApp']] : [])].map(([value, label]) => <Button key={value} variant={tab === value ? 'primary' : 'secondary'} aria-pressed={tab === value} onClick={() => { setTab(value); setPage(1); }}>{label}</Button>)}
    </div>
    {notice && <p role="status" className="text-green-800">{notice}</p>}
    {error && <div role="alert" className="text-red-700"><p>{error}</p><Button onClick={load}>Reintentar</Button></div>}
    {tab === 'nights' && <NightPlans />}
    {tab === 'leaves' && <>
      <div className="flex flex-wrap gap-3 items-end"><label>Mes del calendario<input aria-label="Mes del calendario" className={input} type="month" value={month} onChange={e => { if (e.target.value) setMonth(e.target.value); }} /></label>{!readOnly && <Button onClick={() => { setCreate(true); setModalError(''); }}>Solicitar vacaciones o permiso</Button>}</div>
      <p className="text-sm text-muted">Selecciona el rango de fechas al solicitar. Verde: aprobado · amarillo: pendiente. Los domingos no se cuentan. Las solicitudes pendientes de otros meses también aparecen debajo.</p>
      {loading ? <Spinner /> : <>
        <div className="grid grid-cols-7 border rounded-lg overflow-hidden bg-white text-xs sm:text-sm" aria-label="Calendario de ausencias">
          {['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map(day => <div className="p-2 bg-ground text-center font-semibold" key={day}>{day}</div>)}
          {Array.from({ length: offset }, (_, i) => <div key={'empty' + i} />)}
          {dates.map(day => {
            const rows = leaves.filter(row => row.start_date <= day && row.end_date >= day && ['APPROVED', 'PENDING'].includes(row.status));
            const sunday = new Date(day + 'T12:00:00').getDay() === 0;
            return <div key={day} className={`min-h-20 p-1 sm:p-2 border-t border-r ${sunday ? 'bg-slate-50 text-muted' : ''}`}><span className="font-semibold">{Number(day.slice(-2))}</span>{sunday ? <p className="text-[10px]">Descanso</p> : rows.map(row => <p key={row.id} title={`${row.technician_name}: ${labels[row.kind]} (${labels[row.status]})`} className={`mt-1 rounded px-1 text-[10px] break-words ${row.status === 'APPROVED' ? 'bg-green-100 text-green-900' : 'bg-amber-100 text-amber-900'}`}><span className="sm:hidden">{panel ? row.technician_name.split(' ')[0] : row.kind === 'VACATION' ? 'Vac.' : 'Perm.'}</span><span className="hidden sm:inline">{panel ? row.technician_name : labels[row.kind]}</span></p>)}</div>;
          })}
        </div>
        {leaves.length === 0 && <p>No hay solicitudes para este mes.</p>}
        {leaves.map(row => <Card key={row.id} className="space-y-2">
          <div className="flex flex-wrap justify-between gap-2"><h2 className="font-semibold">{panel ? row.technician_name + ' · ' : ''}{labels[row.kind]}</h2><span>{labels[row.status]}</span></div>
          <p>{row.start_date} al {row.end_date} · {row.working_days} días laborales</p><p className="break-words">{row.reason}</p>
          {row.review_note && <p className="text-sm text-muted">Resolución: {row.review_note}</p>}
          <div className="flex flex-wrap gap-2">
            {admin && row.status === 'PENDING' && <><Button onClick={() => decision(row.id, 'leaves', 'APPROVED')}>Aprobar</Button><Button variant="secondary" onClick={() => decision(row.id, 'leaves', 'REJECTED')}>Rechazar</Button></>}
            {!readOnly && (row.status === 'PENDING' || (admin && row.status === 'APPROVED')) && <Button variant="secondary" onClick={() => decision(row.id, 'leaves', 'CANCELLED')}>Cancelar solicitud</Button>}
          </div>
        </Card>)}
      </>}
    </>}
    {tab === 'incidents' && <>
      <p className="text-sm">Una entrada ausente requiere revisión. La app no confirma faltas injustificadas automáticamente. Las salidas anticipadas conservan la hora real.</p>
      <label className="block max-w-xs">Estado<select className={input} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todos</option><option value="PENDING">Pendientes</option><option value="JUSTIFIED">Justificadas</option><option value="UNJUSTIFIED">No justificadas</option></select></label>
      {loading ? <Spinner /> : <>
        {!incidents.length && <p>No hay incidencias con este filtro.</p>}
        {incidents.map(row => <Card key={row.id} className="space-y-2"><h2 className="font-semibold">{panel ? row.technician_name + ' · ' : ''}{labels[row.kind]}</h2><p>{row.work_date} · {labels[row.status]}</p><p>{row.reason}</p>{row.review_note && <p>Resolución: {row.review_note}</p>}
          {admin && <div className="flex flex-wrap gap-2"><Button onClick={() => decision(row.id, 'incidents', 'JUSTIFIED')}>Justificar</Button><Button variant="secondary" onClick={() => decision(row.id, 'incidents', 'UNJUSTIFIED')}>Marcar no justificada</Button><Button variant="secondary" onClick={async () => { try { setAudit((await client.get(`/attendance/events/${row.id}`)).data); } catch { setError('No se pudo cargar el historial.'); } }}>Ver revisiones</Button></div>}
        </Card>)}
        <div className="flex justify-between items-center"><Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button><span>{page} / {Math.max(1, Math.ceil(total / 30))}</span><Button variant="secondary" disabled={page * 30 >= total} onClick={() => setPage(page + 1)}>Siguiente</Button></div>
      </>}
    </>}
    {tab === 'reminders' && (loading ? <Spinner /> : delivery && <>
      <Card className="space-y-2"><h2 className="font-semibold">Recordatorios de WhatsApp</h2><p>{delivery.configured && delivery.enabled ? 'Integración configurada y habilitada.' : 'Integración pendiente de configuración o desactivada.'}</p><p>Activa los recordatorios de cada técnico en Personal e indica su WhatsApp con código de país.</p><p>Entrada: 9:10. Salida: 18:10 de lunes a viernes y 13:10 los sábados. No se envían los domingos, durante ausencias aprobadas ni cuando ya existe el registro.</p><p>Tareas: 30 minutos después de la entrada, si la jornada sigue abierta y no tiene tareas vigentes. Aplica de día y de noche; un solo aviso, sin generar incidencias. Si continúa de noche a día, se consideran las tareas y el aviso de la noche anterior.</p><p className="text-sm text-muted">Un aviso por tipo y día. Si el servicio se retrasa más de 30 minutos, el aviso vence. «Aceptado» indica recepción por UltraMsg, no lectura del técnico. Los envíos inciertos deben comprobarse en UltraMsg antes de reenviar.</p><Button variant="secondary" onClick={load}>Actualizar estado</Button></Card>
      {!delivery.items.length && <p>Aún no hay envíos registrados.</p>}
      {delivery.items.map(row => <Card key={row.id}><p className="font-semibold">{row.technician_name} · {labels[row.kind]}</p><p>{row.work_date} · {labels[row.status]}</p>{row.error && <p className="text-sm text-muted">{row.error}</p>}</Card>)}
    </>)}
    <Modal isOpen={create} onClose={() => setCreate(false)} title="Solicitar vacaciones o permiso" onConfirm={saveLeave} confirmText="Enviar solicitud" loading={saving}>
      <div className="space-y-3">
        {modalError && <p role="alert" className="text-red-700">{modalError}</p>}
        {admin && <label className="block">Técnico<select className={input} value={form.technician_id} onChange={e => setForm({ ...form, technician_id: e.target.value })}><option value="">Seleccionar</option>{techs.map(tech => <option key={tech.id} value={tech.id}>{tech.full_name}</option>)}</select></label>}
        <label className="block">Tipo<select className={input} value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}><option value="VACATION">Vacaciones</option><option value="PERMISSION">Permiso de día completo</option></select></label>
        <label className="block">Primer día<input className={input} type="date" min={admin ? undefined : localToday()} value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} /></label>
        <label className="block">Último día<input className={input} type="date" min={form.start_date} value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} /></label>
        <p>{requestedDays} días laborales solicitados. Incluye sábados; excluye domingos.</p>
        <label className="block">Motivo<textarea className={input} maxLength={1000} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></label>
        <p className="text-sm text-muted">El administrador debe aprobar la solicitud antes de que cuente como ausencia autorizada.</p>
      </div>
    </Modal>
    <Modal isOpen={!!review} onClose={() => setReview(null)} title="Revisar solicitud o incidencia" onConfirm={saveReview} confirmText="Guardar resolución" loading={saving}><div className="space-y-3">{modalError && <p role="alert" className="text-red-700">{modalError}</p>}<p>Resolución: <strong>{review ? labels[review.status] : ''}</strong></p><label className="block">Motivo de la resolución<textarea className={input} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label><p className="text-sm">Se conservará quién hizo la revisión, cuándo y su motivo.</p></div></Modal>
    <Modal isOpen={audit !== null} onClose={() => setAudit(null)} title="Historial de revisiones"><div className="space-y-3">{audit?.map((entry, i) => <div key={i}><p>{new Date(entry.created_at).toLocaleString('es-MX', { timeZone: 'America/Monterrey' })} · {labels[entry.details.status || ''] || entry.action}</p><p>{entry.details.note}</p></div>)}{!audit?.length && <p>No hay revisiones registradas.</p>}</div></Modal>
  </div>;
}
