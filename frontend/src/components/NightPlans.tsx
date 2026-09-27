import { useCallback, useEffect, useState } from 'react';
import client from '../api/client';
import { adminApi } from '../api/adminApi';
import { useAuth } from '../hooks/useAuth';
import Button from './ui/Button';
import Card from './ui/Card';
import Modal from './ui/Modal';

const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Monterrey' }).format(new Date());
const input = 'w-full border rounded-lg p-2 mt-1 bg-white';
const labels: Record<string, string> = { PENDING: 'Pendiente de validación', APPROVED: 'Autorizada', REJECTED: 'Rechazada', CANCELLED: 'Cancelada' };
interface Plan { id: string; technician_name: string; work_date: string; reminder_at: string; replaces_day: boolean; rest_next_day: boolean; status: string; reason: string }

export default function NightPlans() {
  const { user } = useAuth();
  const admin = user?.role === 'ADMIN', readOnly = user?.role === 'READ_ONLY';
  const [month, setMonth] = useState(today().slice(0, 7));
  const [rows, setRows] = useState<Plan[]>([]);
  const [techs, setTechs] = useState<{ id: string; full_name: string }[]>([]);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [open, setOpen] = useState(false), [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState('');
  const [form, setForm] = useState({ technician_id: '', work_date: today(), reminder_time: '20:00', replaces_day: true, rest_next_day: false, reason: '' });
  const [decision, setDecision] = useState<{ id: string; status: string } | null>(null), [note, setNote] = useState('');
  const load = useCallback(async () => {
    try {
      const [y, m] = month.split('-').map(Number);
      setRows((await client.get('/night-plans', { params: { date_from: month + '-01', date_to: month + '-' + new Date(y, m, 0).getDate() } })).data);
      setError('');
    } catch (err: any) { setError(err.friendlyMessage || 'No se pudo cargar la programación nocturna.'); }
  }, [month]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (admin) adminApi.getTechnicians().then(setTechs).catch(() => setError('No se pudo cargar el personal.')); }, [admin]);
  async function save() {
    setSaving(true); setModalError('');
    try {
      await client.post('/night-plans', { ...form, technician_id: admin ? form.technician_id : undefined });
      setOpen(false); setMonth(form.work_date.slice(0, 7)); setNotice(admin ? 'Noche autorizada.' : 'Aviso guardado. El administrador debe validar el cambio de horario.'); await load();
    } catch (err: any) { setModalError(err.friendlyMessage || 'No se pudo guardar.'); }
    finally { setSaving(false); }
  }
  async function review() {
    if (!decision) return;
    setSaving(true); setModalError('');
    try { await client.patch('/night-plans/' + decision.id, { status: decision.status, note }); setDecision(null); setNotice('Decisión guardada con su motivo.'); await load(); }
    catch (err: any) { setModalError(err.friendlyMessage || 'No se pudo guardar.'); }
    finally { setSaving(false); }
  }
  return <div className="space-y-4">
    <Card className="space-y-2"><h2 className="font-semibold">Turnos nocturnos</h2>
      <p>Programa la fecha en que comenzarás y una hora para recibir el recordatorio. Esa hora no limita cuándo puedes registrar entrada o salida.</p>
      <p>Si la noche sustituye al turno diurno, se suspenden los avisos diurnos de esa fecha. El administrador debe validar el descanso; avisar no justifica automáticamente una ausencia.</p>
      <p>Una jornada nocturna permanece abierta al pasar medianoche. Puedes terminarla o continuar con el turno diurno registrando el cambio en Inicio. El día siguiente conserva su horario habitual salvo descanso autorizado.</p>
    </Card>
    <div className="flex flex-wrap items-end gap-3"><label>Mes<input className={input} type="month" value={month} onChange={e => e.target.value && setMonth(e.target.value)} /></label>{!readOnly && <Button onClick={() => { setOpen(true); setModalError(''); }}>{admin ? 'Programar noche' : 'Avisar trabajo nocturno'}</Button>}</div>
    {error && <p role="alert" className="text-red-700">{error}</p>}{notice && <p role="status" className="text-green-800">{notice}</p>}
    {!rows.length && <p>No hay noches programadas en este mes.</p>}
    {rows.map(row => <Card key={row.id} className="space-y-2"><h3 className="font-semibold">{user?.role !== 'TECHNICIAN' && row.technician_name + ' · '}{row.work_date}</h3><p>{labels[row.status]} · Recordatorio: {new Date(row.reminder_at).toLocaleTimeString('es-MX', { timeZone: 'America/Monterrey', hour: '2-digit', minute: '2-digit' })}</p><p>{row.replaces_day ? 'Sustituye el turno diurno de esa fecha' : 'Se suma al turno diurno de esa fecha'}{row.rest_next_day ? ' · Descanso al día siguiente autorizado' : ' · Sin descanso automático al día siguiente'}</p><p className="break-words">{row.reason}</p><div className="flex flex-wrap gap-2">{admin && row.status === 'PENDING' && ['APPROVED', 'REJECTED'].map(status => <Button key={status} variant="secondary" onClick={() => { setDecision({ id: row.id, status }); setNote(''); setModalError(''); }}>{status === 'APPROVED' ? 'Autorizar' : 'Rechazar'}</Button>)}{!readOnly && ['PENDING', 'APPROVED'].includes(row.status) && row.work_date >= today() && <Button variant="secondary" onClick={() => { setDecision({ id: row.id, status: 'CANCELLED' }); setNote(''); setModalError(''); }}>Cancelar programación</Button>}</div></Card>)}
    <Modal isOpen={open} onClose={() => !saving && setOpen(false)} title={admin ? 'Programar turno nocturno' : 'Avisar trabajo nocturno'} onConfirm={save} confirmText="Guardar programación" loading={saving}>
      <div className="space-y-3">{modalError && <p role="alert" className="text-red-700">{modalError}</p>}
        {admin && <label className="block">Técnico<select className={input} value={form.technician_id} onChange={e => setForm({ ...form, technician_id: e.target.value })}><option value="">Seleccionar</option>{techs.map(t => <option key={t.id} value={t.id}>{t.full_name}</option>)}</select></label>}
        <label className="block">Fecha de inicio de la noche<input type="date" min={today()} className={input} value={form.work_date} onChange={e => setForm({ ...form, work_date: e.target.value })} /></label>
        <label className="block">Hora del recordatorio (Monterrey)<input type="time" className={input} value={form.reminder_time} onChange={e => setForm({ ...form, reminder_time: e.target.value })} /></label>
        <p className="text-sm">Si comenzarás después de medianoche, selecciona la nueva fecha. Se envía un aviso por noche si tienes WhatsApp habilitado. Una hora ya pasada por más de 30 minutos no genera un envío retroactivo.</p>
        <label className="block"><input type="checkbox" checked={form.replaces_day} onChange={e => setForm({ ...form, replaces_day: e.target.checked })} /> Esa fecha descanso de día y trabajo de noche</label>
        {admin && <label className="block"><input type="checkbox" checked={form.rest_next_day} onChange={e => setForm({ ...form, rest_next_day: e.target.checked })} /> Autorizar también descanso diurno al día siguiente</label>}
        <label className="block">Motivo o trabajo programado<textarea className={input} maxLength={1000} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></label>
      </div>
    </Modal>
    <Modal isOpen={!!decision} onClose={() => !saving && setDecision(null)} title="Revisar programación nocturna" onConfirm={review} confirmText="Guardar decisión" loading={saving}><div className="space-y-3">{modalError && <p role="alert" className="text-red-700">{modalError}</p>}<p>{decision && labels[decision.status]}</p><label>Motivo<textarea className={input} value={note} maxLength={1000} onChange={e => setNote(e.target.value)} /></label></div></Modal>
  </div>;
}
