import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { adminApi, DashboardData } from '../../api/adminApi';
import Spinner from '../../components/ui/Spinner';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await adminApi.getDashboard();
      setData(res);
    } catch (err: any) {
      setError('No se pudo cargar la información del panel.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60000); // 60s
    return () => clearInterval(interval);
  }, []);

  const formatTime = (iso?: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    const time = new Intl.DateTimeFormat('es-MX', {
      hour: 'numeric', minute: '2-digit', hour12: true,
      timeZone: 'America/Monterrey'
    }).format(d).replace('am', 'a.m.').replace('pm', 'p.m.');
    return time;
  };

  const formatDuration = (minutes?: number | null) => {
    if (minutes == null) return '—';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h}:${m.toString().padStart(2, '0')}`;
  };

  if (loading && !data) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
        <div className="text-incident font-medium">{error}</div>
        <button onClick={fetchDashboard} className="px-4 py-2 bg-shell text-surface rounded-btn">Reintentar</button>
      </div>
    );
  }

  const todayStr = new Intl.DateTimeFormat('es-MX', { dateStyle: 'long' }).format(new Date());
  const totalActivos = data?.technicians.length || 0;
  
  return (
    <div className="space-y-8 font-sans">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted capitalize mb-1">{todayStr} · Monterrey</p>
          <h1 className="text-[26px] font-bold text-ink tracking-tight">Operación de hoy</h1>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 border border-border text-ink rounded-btn hover:bg-border/30 transition-colors font-medium">Exportar CSV</button>
          <button className="px-4 py-2 bg-accent text-ink rounded-btn hover:bg-accent/90 transition-colors font-medium">Asignar tarea</button>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded-card p-5">
          <div className="flex items-center gap-2 text-muted mb-3 text-[13px]">
            <span className="w-2 h-2 rounded-full bg-open"></span> En jornada
          </div>
          <div className="font-mono text-4xl text-ink font-medium mb-1">{data?.working_now || 0}</div>
          <div className="text-[13px] text-muted">de {totalActivos} técnicos activos</div>
        </div>

        <div className="bg-surface border border-border rounded-card p-5">
          <div className="flex items-center gap-2 text-muted mb-3 text-[13px]">
            <span className="w-2 h-2 rounded-full border border-muted"></span> Sin iniciar
          </div>
          <div className="font-mono text-4xl text-ink font-medium mb-1">{data?.not_started || 0}</div>
          <div className="text-[13px] text-muted">Pendientes de arranque</div>
        </div>

        <div className="bg-surface border border-border rounded-card p-5">
          <div className="flex items-center gap-2 text-muted mb-3 text-[13px]">
            <span className="w-2 h-2 rounded-full bg-closed"></span> Jornadas cerradas
          </div>
          <div className="font-mono text-4xl text-ink font-medium mb-1">{data?.finished || 0}</div>
          <div className="text-[13px] text-muted">Finalizadas hoy</div>
        </div>

        <div className="bg-surface border border-border rounded-card p-5">
          <div className="flex items-center gap-2 text-muted mb-3 text-[13px]">
            <span className="w-2 h-2 rounded-full bg-incident"></span> Tareas pendientes
          </div>
          <div className="font-mono text-4xl text-ink font-medium mb-1">{data?.tasks_pending || 0}</div>
          <div className="text-[13px] text-muted">Asignadas sin completar</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-card overflow-hidden">
        <div className="flex justify-between items-center p-5 border-b border-border">
          <h2 className="font-bold text-ink">Técnicos en campo</h2>
          <Link to="/admin/jornadas" className="text-sm text-muted hover:text-ink">Ver historial de jornadas</Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[14px]">
            <thead className="text-muted border-b border-border bg-surface">
              <tr>
                <th className="px-5 py-3 font-normal">Técnico</th>
                <th className="px-5 py-3 font-normal">Estado</th>
                <th className="px-5 py-3 font-normal">Entrada</th>
                <th className="px-5 py-3 font-normal">Salida</th>
                <th className="px-5 py-3 font-normal">Horas</th>
                <th className="px-5 py-3 font-normal">Tareas</th>
                <th className="px-5 py-3 font-normal">Última ubicación</th>
                <th className="px-5 py-3 font-normal text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.technicians.map((tech) => {
                const totalTareas = tech.tasks_completed + tech.tasks_pending;
                return (
                <tr key={tech.id} className="hover:bg-ground transition-colors group">
                  <td className="px-5 py-4 font-medium text-ink">{tech.full_name}{tech.day_note && <p className="text-xs text-muted mt-1">{tech.day_note}</p>}{tech.shift_kind === 'NIGHT' && <p className="text-xs text-blue-700">Turno nocturno</p>}</td>
                  <td className="px-5 py-4">
                    {tech.status === "WORKING" && <span className="flex items-center gap-2 text-open"><span className="w-2 h-2 bg-open rounded-full"></span>En jornada</span>}
                    {tech.status === "FINISHED" && <span className="flex items-center gap-2 text-muted"><span className="w-2 h-2 bg-closed rounded-full"></span>Cerrada</span>}
                    {tech.status === "NOT_STARTED" && <span className="flex items-center gap-2 text-muted"><span className="w-2 h-2 border border-muted rounded-full"></span>Sin iniciar</span>}
                  </td>
                  <td className="px-5 py-4 font-mono text-ink">{formatTime(tech.check_in_time)}</td>
                  <td className="px-5 py-4 font-mono text-ink">{formatTime(tech.check_out_time)}</td>
                  <td className="px-5 py-4 font-mono text-ink">{formatDuration(tech.duration_minutes)}</td>
                  <td className="px-5 py-4 font-mono text-ink">{tech.tasks_completed} / {totalTareas}</td>
                  <td className="px-5 py-4 text-muted">—</td>
                  <td className="px-5 py-4 text-right text-muted opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => navigate(`/admin/personal/tecnico/${tech.id}`)} className="hover:text-ink">Ver</button>
                  </td>
                </tr>
              )})}
              {(!data?.technicians || data.technicians.length === 0) && (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-muted">
                    No hay técnicos registrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
