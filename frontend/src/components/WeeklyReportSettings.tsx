import { useEffect, useState } from 'react';
import client from '../api/client';
import Button from './ui/Button';

interface Config {
  enabled: boolean; first_send_date: string; to_emails: string[]; cc_emails: string[];
  revision: number; timezone: string; next_send: string | null; sender: string;
  sender_name: string; smtp_configured: boolean;
}
interface Run {
  id: string; period_start: string; period_end: string; status: string;
  to_emails: string[]; cc_emails: string[]; last_error: string | null;
}
const labels: Record<string, string> = {
  READY: 'Pendiente', SENDING: 'Enviando', ACCEPTED: 'Aceptado por el servidor de correo',
  PARTIAL: 'Aceptado parcialmente: revisar', FAILED: 'Error de envío', UNKNOWN: 'Recepción sin confirmar', EXPIRED: 'No enviado: plazo vencido',
};
const friendlyMessage = (error: unknown, fallback: string) => (error as {friendlyMessage?: string})?.friendlyMessage || fallback;
export async function downloadAttendancePdf(url: string, filename: string, params?: Record<string, string | undefined>) {
  const response = await client.get(url, { params, responseType: 'blob', timeout: 60000 });
  const blobUrl = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = blobUrl; anchor.download = filename;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
}
export default function WeeklyReportSettings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setError('');
    try {
      const [settings, history] = await Promise.all([client.get<Config>('/admin/report-mail'), client.get<Run[]>('/admin/report-mail/runs')]);
      setConfig(settings.data); setTo(settings.data.to_emails.join(', ')); setCc(settings.data.cc_emails.join(', ')); setRuns(history.data);
    } catch (e) { setError(friendlyMessage(e, 'No se pudo cargar la programación.')); }
  };
  useEffect(() => { void load(); }, []);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); if (!config) return;
    setBusy(true); setError(''); setMessage('');
    const emails = (value: string) => value.split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
    try {
      const response = await client.patch<Config>('/admin/report-mail', {
        enabled: config.enabled, first_send_date: config.first_send_date, revision: config.revision,
        to_emails: emails(to), cc_emails: emails(cc),
      });
      setConfig(response.data); setMessage('Programación guardada. Los cambios se aplican a reportes futuros.');
    } catch (e) { setError(friendlyMessage(e, 'No se pudo guardar la programación.')); }
    finally { setBusy(false); }
  };
  return <section className="bg-white p-4 sm:p-6 rounded-lg shadow-sm border border-slate-200 space-y-4">
    <h2 className="text-lg font-semibold text-slate-800">Envío semanal y destinatarios</h2>
    <p className="text-sm text-slate-600">Cada lunes a las 9:00 a. m., un PDF con el resumen y detalle de asistencias de la semana anterior, de lunes a domingo. Incluye el sábado laborable.</p>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="text-sm text-green-700">{message}</p>}
    {!config ? <Button variant="secondary" onClick={load}>Cargar programación</Button> : <form onSubmit={save} className="space-y-4">
      <label className="flex items-center gap-2"><input type="checkbox" checked={config.enabled} onChange={e => setConfig({...config, enabled: e.target.checked})} /> Activar envío semanal</label>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="text-sm"><label htmlFor="weekly-report-to">Para</label><textarea id="weekly-report-to" required className="block w-full border rounded p-2 mt-1" value={to} onChange={e => setTo(e.target.value)} /></div>
        <div className="text-sm"><label htmlFor="weekly-report-cc">Con copia</label><textarea id="weekly-report-cc" className="block w-full border rounded p-2 mt-1" value={cc} onChange={e => setCc(e.target.value)} /></div>
      </div>
      <p className="text-xs text-slate-500">Separa correos con coma. Máximo 20 destinatarios, sin repetidos.</p>
      <label className="block text-sm">Primer lunes de envío <input className="block border rounded p-2 mt-1" required type="date" value={config.first_send_date} onChange={e => setConfig({...config, first_send_date: e.target.value})} /></label>
      <div className="rounded bg-slate-50 p-3 text-sm space-y-1">
        <p>Remitente: {config.sender_name} · {config.sender || 'Pendiente de configurar'}</p>
        <p>Zona horaria: {config.timezone}</p>
        <p>Próximo envío: {config.next_send ? new Intl.DateTimeFormat('es-MX', {dateStyle: 'full', timeStyle: 'short', timeZone: config.timezone}).format(new Date(config.next_send)) : 'Pausado'}</p>
        {!config.smtp_configured && <p className="text-amber-800">Falta configurar el correo saliente en el servidor.</p>}
      </div>
      <div className="flex gap-3"><Button type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar programación'}</Button><Button type="button" variant="secondary" disabled={busy} onClick={load}>Recargar</Button></div>
    </form>}
    <h3 className="font-semibold pt-2">Historial de envíos</h3>
    <p className="text-xs text-slate-500">“Aceptado” confirma la aceptación por el servidor SMTP; no confirma la lectura ni la entrega en la bandeja de entrada. Ante un resultado incierto, el sistema evita reenviar automáticamente.</p>
    {!runs.length ? <p className="text-sm text-slate-500">Todavía no hay envíos registrados.</p> : <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">Período</th><th className="p-2">Destinatarios</th><th className="p-2">Resultado</th><th className="p-2">PDF</th></tr></thead><tbody>{runs.map(run => <tr key={run.id} className="border-t"><td className="p-2">{run.period_start} al {run.period_end}</td><td className="p-2">Para: {run.to_emails.join(', ')}<br />CC: {run.cc_emails.join(', ') || 'Sin copias'}</td><td className="p-2">{labels[run.status] || run.status}{run.last_error && <p className="text-xs text-red-700">{run.last_error}</p>}</td><td className="p-2"><Button variant="secondary" onClick={() => downloadAttendancePdf(`/admin/report-mail/runs/${run.id}/pdf`, `asistencias_${run.period_start}.pdf`).catch(() => setError('No se pudo descargar el PDF.'))}>Descargar</Button></td></tr>)}</tbody></table></div>}
  </section>;
}
