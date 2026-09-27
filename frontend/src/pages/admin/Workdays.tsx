import { useAuth } from '../../hooks/useAuth';
import { useSearchParams } from 'react-router-dom';
import React, { useEffect, useState } from 'react';
import { adminApi, AdminWorkdayItem } from '../../api/adminApi';
import client from '../../api/client';
import Modal from '../../components/ui/Modal';
import Button from '../../components/ui/Button';
import Spinner from '../../components/ui/Spinner';
import { Search, ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

const Workdays: React.FC = () => {
  const { isAdmin } = useAuth();
  const [searchParams] = useSearchParams();
  const [workdays, setWorkdays] = useState<AdminWorkdayItem[]>([]);
  const [technicians, setTechnicians] = useState<{id: string, name: string}[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [action, setAction] = useState<{ row: AdminWorkdayItem; type: 'edit' | 'void' | 'restore' } | null>(null);
  const [reason, setReason] = useState('');
  const [entry, setEntry] = useState('');
  const [exit, setExit] = useState('');
  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState('');
  const [history, setHistory] = useState<any[] | null>(null);
  function localInput(iso?: string | null) {
    if (!iso) return '';
    const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Monterrey', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(iso));
    const p = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}`;
  }
  function begin(row: AdminWorkdayItem, type: 'edit' | 'void' | 'restore') {
    setAction({ row, type }); setReason(''); setModalError(''); setEntry(localInput(row.check_in_at)); setExit(localInput(row.check_out_at));
  }
  async function save() {
    if (!action) return;
    setSaving(true); setModalError('');
    try {
      await client.patch(`/admin/workdays/${action.row.id}${action.type === 'edit' ? '' : '/' + action.type}`, {
        revision: action.row.revision, reason,
        ...(action.type === 'edit' ? { check_in_at: entry, check_out_at: exit || null } : {}),
      });
      setAction(null); setNotice('Cambio guardado. El historial de revisiones y las tareas se conservaron.'); await fetchWorkdays();
    } catch (err: any) { setModalError(err.friendlyMessage || 'No se pudo guardar el cambio.'); }
    finally { setSaving(false); }
  }
  function actions(row: AdminWorkdayItem) {
    return <div className="flex flex-wrap gap-2">
      {isAdmin && (row.is_void ? <Button size="sm" variant="secondary" onClick={() => begin(row, 'restore')}>Restaurar</Button> : <><Button size="sm" variant="secondary" onClick={() => begin(row, 'edit')}>Editar</Button><Button size="sm" variant="danger" onClick={() => begin(row, 'void')}>Eliminar</Button></>)}
      <Button size="sm" variant="secondary" onClick={async () => { try { setHistory((await client.get(`/attendance/events/${row.id}`)).data); } catch { setError('No se pudo cargar el historial.'); } }}>Historial</Button>
    </div>;
  }

  // Pagination
  const [page, setPage] = useState(1);
  const size = 20;

  // Defaults: last 7 days
  const today = new Date();
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(today.getDate() - 7);
  
  const formatDateForInput = (d: Date) => d.toISOString().split('T')[0];

  const [filters, setFilters] = useState({
    date_from: formatDateForInput(sevenDaysAgo),
    date_to: formatDateForInput(today),
    technician_id: searchParams.get('technician_id') || '',
    status: '',
    include_void: ''
  });

  const fetchFilters = async () => {
    try {
      const techs = await adminApi.getTechnicians(true);
      setTechnicians(techs.map(t => ({ id: t.id, name: t.full_name })));
    } catch (e) {}
  };

  const fetchWorkdays = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminApi.getWorkdays({ ...filters, page, size });
      setWorkdays(res.items || []);
      setTotal(res.total || 0);
    } catch (e) {
      setError('No se pudieron consultar las jornadas. Reintenta.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchWorkdays();
  }, [page]); // When page changes, fetch automatically

  const handleSearch = () => {
    if (page === 1) void fetchWorkdays();
    else setPage(1);
  };

  const formatTime = (iso?: string | null) => {
    if (!iso) return '—';
    return new Intl.DateTimeFormat('es-MX', {
      day: '2-digit', month: '2-digit', hour: 'numeric', minute: '2-digit', hour12: true,
      timeZone: 'America/Monterrey'
    }).format(new Date(iso));
  };

  const formatDuration = (minutes?: number | null) => {
    if (minutes == null) return '-';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h}h ${m.toString().padStart(2, '0')}min`;
  };

  const totalPages = Math.ceil(total / size);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Jornadas</h1>
      {notice && <p role="status" className="text-green-800">{notice}</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <label className="flex gap-2 items-center"><input type="checkbox" checked={!!filters.include_void} onChange={e => setFilters({ ...filters, include_void: e.target.checked ? 'true' : '' })} />Mostrar también jornadas anuladas (pulsa Buscar)</label>

      <div className="bg-surface p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4 items-end">
        <div className="w-full md:w-1/4">
          <label className="block text-xs font-medium text-muted mb-1">Fecha inicio</label>
          <input 
            type="date" 
            value={filters.date_from}
            onChange={e => setFilters({...filters, date_from: e.target.value})}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          />
        </div>
        <div className="w-full md:w-1/4">
          <label className="block text-xs font-medium text-muted mb-1">Fecha fin</label>
          <input 
            type="date" 
            value={filters.date_to}
            onChange={e => setFilters({...filters, date_to: e.target.value})}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          />
        </div>
        <div className="w-full md:w-1/4">
          <label className="block text-xs font-medium text-muted mb-1">Técnico</label>
          <select 
            value={filters.technician_id} 
            onChange={e => setFilters({...filters, technician_id: e.target.value})}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          >
            <option value="">Todos</option>
            {technicians.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="w-full md:w-1/4">
          <label className="block text-xs font-medium text-muted mb-1">Estado</label>
          <select 
            value={filters.status} 
            onChange={e => setFilters({...filters, status: e.target.value})}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          >
            <option value="">Todos</option>
            <option value="OPEN">Abierta</option>
            <option value="CLOSED">Cerrada</option>
          </select>
        </div>
        <div>
          <Button onClick={handleSearch} disabled={loading} className="w-full md:w-auto px-6">
            Buscar
          </Button>
        </div>
      </div>

      <div className="bg-surface rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        ) : (
          <>
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-surface text-muted uppercase text-xs font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-4">Acciones</th><th className="px-6 py-4">Fecha</th>
                    <th className="px-6 py-4">Técnico</th>
                    <th className="px-6 py-4">Entrada</th>
                    <th className="px-6 py-4">Salida</th>
                    <th className="px-6 py-4">Duración</th>
                    <th className="px-6 py-4 text-center">Asignadas del día</th>
                    <th className="px-6 py-4 text-center">Realizadas del día</th>
                    <th className="px-6 py-4">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {workdays.map((w) => (
                    <tr key={w.id} className="hover:bg-surface">
                      <td className="px-6 py-4">{actions(w)}</td>
                      <td className="px-6 py-4 text-ink flex items-center gap-2"><Calendar className="w-4 h-4 text-muted"/> {w.work_date} · {w.shift_kind === 'NIGHT' ? 'Nocturna' : 'Diurna'}</td>
                      <td className="px-6 py-4 font-medium text-ink">{w.technician_name}</td>
                      <td className="px-6 py-4 text-muted">{formatTime(w.check_in_at)}</td>
                      <td className="px-6 py-4 text-muted">{formatTime(w.check_out_at)}</td>
                      <td className="px-6 py-4 text-muted">{formatDuration(w.duration_minutes)}</td>
                      <td className="px-6 py-4 text-center text-muted">{w.tasks_assigned}</td>
                      <td className="px-6 py-4 text-center text-muted">{w.tasks_completed}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-md ${w.status === 'OPEN' ? 'bg-green-100 text-green-700' : 'bg-ground text-muted'}`}>
                          {w.is_void ? 'ANULADA' : w.status === 'OPEN' ? 'ABIERTA' : 'CERRADA'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {workdays.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-6 py-8 text-center text-muted">
                        <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                        No se encontraron jornadas.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden divide-y divide-slate-200">
              {workdays.map((w) => (
                <div key={w.id} className="p-4 space-y-2">
                  <div className="flex justify-between items-start">
                    <div className="font-semibold text-ink">{w.technician_name}</div>
                    <span className={`px-2 py-1 text-xs font-semibold rounded-md ${w.status === 'OPEN' ? 'bg-green-100 text-green-700' : 'bg-ground text-muted'}`}>
                      {w.is_void ? 'ANULADA' : w.status === 'OPEN' ? 'ABIERTA' : 'CERRADA'}
                    </span>
                  </div>
                  <div className="text-sm text-muted flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> {w.work_date} · {w.shift_kind === 'NIGHT' ? 'Nocturna' : 'Diurna'}</div>
                  
                  <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm mt-3 bg-surface p-3 rounded-md">
                    <div><span className="block text-xs text-muted">Entrada</span> {formatTime(w.check_in_at)}</div>
                    <div><span className="block text-xs text-muted">Salida</span> {formatTime(w.check_out_at)}</div>
                    <div><span className="block text-xs text-muted">Duración</span> {formatDuration(w.duration_minutes)}</div>
                    <div><span className="block text-xs text-muted">Tareas (Asig/Realiz)</span> {w.tasks_assigned} / {w.tasks_completed}</div>
                  </div>
                  {actions(w)}
                </div>
              ))}
              {workdays.length === 0 && (
                <div className="p-8 text-center text-muted">
                  <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  No se encontraron jornadas.
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between">
                <span className="text-sm text-muted">
                  Página {page} de {totalPages}
                </span>
                <div className="flex gap-2">
                  <Button 
                    variant="secondary" 
                    size="sm" 
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="w-4 h-4" /> Anterior
                  </Button>
                  <Button 
                    variant="secondary" 
                    size="sm" 
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                  >
                    Siguiente <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
      <Modal isOpen={!!action} onClose={() => setAction(null)} title={action?.type === 'edit' ? 'Editar jornada' : action?.type === 'void' ? 'Anular jornada' : 'Restaurar jornada'} onConfirm={save} confirmText={action?.type === 'void' ? 'Anular jornada' : 'Guardar cambio'} confirmVariant={action?.type === 'void' ? 'danger' : 'primary'} loading={saving}>
        <div className="space-y-4">
          {modalError && <p role="alert" className="text-red-700">{modalError}</p>}
          <p className="font-semibold">{action?.row.technician_name} · {action?.row.work_date}</p>
          {action?.type === 'edit' && <>
            <p className="text-sm">Horas de Monterrey. La entrada debe conservar la fecha de la jornada para mantener las tareas vinculadas a ese día.</p>
            <label className="block">Entrada<input type="datetime-local" step="1" className="w-full border rounded-lg p-2 mt-1" value={entry} onChange={e => setEntry(e.target.value)} /></label>
            <label className="block">Salida<input type="datetime-local" step="1" className="w-full border rounded-lg p-2 mt-1" value={exit} onChange={e => setExit(e.target.value)} /></label>
            <p className="text-sm text-muted">Dejar la salida vacía reabre la jornada. La duración se recalcula al guardar.</p>
          </>}
          {action?.type === 'void' && <p>Se quitará de la lista habitual y de los totales de asistencia. Sus tareas y el registro original se conservan. Podrás recuperarla con «Mostrar también jornadas anuladas» y «Restaurar».</p>}
          {action?.type === 'restore' && <p>Volverá a contar en la asistencia. Si ya existe otra jornada del mismo día o hay un conflicto de horarios, deberás resolverlo primero.</p>}
          <label className="block">Motivo del cambio<textarea className="w-full border rounded-lg p-2 mt-1" value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} /></label>
        </div>
      </Modal>
      <Modal isOpen={history !== null} onClose={() => setHistory(null)} title="Historial de cambios de jornada">
        <div className="space-y-4">{!history?.length && <p>No hay cambios administrativos registrados.</p>}{history?.map(item => <div key={item.id} className="border-b pb-3 text-sm"><p className="font-semibold">{({ WORKDAY_EDIT: 'Edición', WORKDAY_VOID: 'Anulación', WORKDAY_RESTORE: 'Restauración' } as Record<string, string>)[item.action] || item.action}</p><p>{new Date(item.created_at).toLocaleString('es-MX', { timeZone: 'America/Monterrey' })} · {item.actor_name || 'Administrador'}</p><p>{item.details.note}</p>{item.details.before && <><p>Antes: {formatTime(item.details.before.check_in_at)} → {formatTime(item.details.before.check_out_at)} · {formatDuration(item.details.before.duration_minutes)}</p><p>Después: {formatTime(item.details.after.check_in_at)} → {formatTime(item.details.after.check_out_at)} · {formatDuration(item.details.after.duration_minutes)}</p></>}</div>)}</div>
      </Modal>
    </div>
  );
};

export default Workdays;
