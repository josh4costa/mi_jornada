import { useAuth } from '../../hooks/useAuth';
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Navigate, Link } from 'react-router-dom';
import { adminApi, TechnicianDetail } from '../../api/adminApi';
import client from '../../api/client';
import { User as Person } from '../../types';
import PersonEditor from '../../components/admin/PersonEditor';
import Spinner from '../../components/ui/Spinner';
import Button from '../../components/ui/Button';
import Modal from '../../components/ui/Modal';
import MapView from '../../components/admin/MapView';
import { Phone, Briefcase, ArrowLeft, MapPin } from 'lucide-react';

const Technicians: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  if (id) {
    return <TechnicianDetailView id={id} />;
  }
  return <Navigate to="/admin/personal" replace />;
};

const TechnicianDetailView: React.FC<{ id: string }> = ({ id }) => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [tech, setTech] = useState<TechnicianDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [revision, setRevision] = useState(0);
  const [person, setPerson] = useState<Person | null>(null);
  const [editing, setEditing] = useState(false);
  const [editError, setEditError] = useState('');
  async function edit() {
    if (!tech) return;
    setEditing(true);
    setEditError('');
    try { setPerson((await client.get<Person>(`/admin/users/${tech.user_id}`)).data); }
    catch { setEditError('No se pudo abrir la edición. Intenta de nuevo.'); }
    finally { setEditing(false); }
  }
  const [showMap, setShowMap] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const res = await adminApi.getTechnicianDetail(id);
        setTech(res);
        setError(null);
      } catch (err) {
        setError('No se pudo cargar el detalle del técnico.');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id, revision]);

  if (loading) return <div className="flex justify-center p-8"><Spinner size="lg" /></div>;
  if (error || !tech) return <div className="text-center text-red-500 p-8">{error || 'No encontrado'} <Button onClick={() => navigate(isAdmin ? '/admin/personal' : '/admin')} className="mt-4">Volver</Button></div>;

  const formatTime = (iso?: string | null) => {
    if (!iso) return '—';
    return new Intl.DateTimeFormat('es-MX', {
      hour: 'numeric', minute: '2-digit', hour12: true,
      timeZone: 'America/Monterrey'
    }).format(new Date(iso));
  };

  const hasLocation = tech.current_workday?.check_in_latitude != null && tech.current_workday?.check_in_longitude != null;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <button 
        onClick={() => navigate(isAdmin ? '/admin/personal' : '/admin')}
        className="flex items-center gap-1 text-muted hover:text-ink transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Volver
      </button>

      <div className="flex flex-wrap gap-3 items-center">
        {isAdmin && <Button onClick={edit} disabled={editing}>{editing ? 'Cargando…' : 'Editar'}</Button>}
        <Link className="text-primary underline" to={`/admin/jornadas?technician_id=${tech.id}`}>Historial de jornadas</Link>
        <Link className="text-primary underline" to={`/admin/tareas?technician_id=${tech.id}`}>Tareas</Link>
      </div>
      {editError && <p role="alert" className="text-red-700">{editError}</p>}
      <PersonEditor isOpen={!!person} person={person} onClose={() => setPerson(null)} onSaved={() => setRevision(value => value + 1)} />
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-2xl font-bold text-ink uppercase">{tech.full_name}</h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-muted">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${tech.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {tech.is_active ? 'Activo' : 'Inactivo'}
            </span>
            <span className="font-mono bg-ground px-2 py-0.5 rounded">{tech.employee_number || 'N/A'}</span>
            <span className="flex items-center gap-1"><Phone className="w-3 h-3" /> {tech.phone || 'N/A'}</span>
          </div>
        </div>

        <div className="p-6 bg-surface border-b border-slate-200">
          <h2 className="text-sm font-bold text-muted uppercase mb-4 tracking-wider flex items-center gap-2">
            <Briefcase className="w-4 h-4" /> Jornada actual
          </h2>
          
          {tech.current_workday ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-slate-400 mb-1">Entrada</div>
                <div className="font-medium text-ink">{formatTime(tech.current_workday.check_in_at)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-400 mb-1">Salida</div>
                <div className="font-medium text-ink">{formatTime(tech.current_workday.check_out_at)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-400 mb-1">Estado</div>
                <TechStatusBadge status={tech.current_workday.status} />
              </div>
              {hasLocation && (
                <div>
                  <div className="text-xs text-slate-400 mb-1">Ubicación</div>
                  <Button variant="secondary" size="sm" onClick={() => setShowMap(true)} className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" /> Ver mapa
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-muted text-sm">No ha iniciado jornada hoy.</div>
          )}
        </div>

        <div className="p-6">
          <h2 className="text-sm font-bold text-muted uppercase mb-4 tracking-wider">
            Actividades ({tech.today_tasks?.length || 0})
          </h2>
          
          <div className="space-y-3">
            {tech.today_tasks && tech.today_tasks.length > 0 ? (
              tech.today_tasks.map(task => (
                <div key={task.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 bg-white border border-slate-100 rounded-lg gap-2">
                  <div className="flex items-center gap-3">
                    {task.status === 'COMPLETED' ? (
                      <span className="text-green-500 font-bold">✓</span>
                    ) : task.status === 'CANCELLED' ? (
                      <span className="text-red-500 font-bold">✗</span>
                    ) : (
                      <span className="text-slate-400">○</span>
                    )}
                    <div>
                      <div className="font-medium text-ink">{task.title}</div>
                      <div className="text-xs text-muted">{task.location_name || 'Sin ubicación'}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {task.completed_at ? <span className="text-xs font-mono text-muted bg-ground px-2 py-1 rounded">{formatTime(task.completed_at)}</span> : (task.scheduled_time && <span className="text-xs font-mono text-muted bg-ground px-2 py-1 rounded">{task.scheduled_time}</span>)}
                    <span className="text-xs font-medium text-muted">{task.status === 'COMPLETED' ? 'COMPLETADA' : task.status === 'CANCELLED' ? 'CANCELADA' : 'PENDIENTE'}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-muted text-sm">No tiene tareas asignadas para hoy.</div>
            )}
          </div>
        </div>
      </div>

      <Modal isOpen={showMap} onClose={() => setShowMap(false)} title="Ubicación de Entrada">
        {hasLocation && (
          <MapView 
            latitude={tech.current_workday!.check_in_latitude!} 
            longitude={tech.current_workday!.check_in_longitude!} 
            label="Registro de entrada"
          />
        )}
      </Modal>
    </div>
  );
};

function TechStatusBadge({ status }: { status: string }) {
  if (status === 'OPEN' || status === 'WORKING') return <span className="flex w-fit items-center gap-1 text-green-700 bg-green-50 px-2 py-0.5 rounded-full text-xs font-medium"><span className="w-2 h-2 bg-green-500 rounded-full"/>Trabajando</span>;
  if (status === 'CLOSED' || status === 'FINISHED') return <span className="flex w-fit items-center gap-1 text-muted bg-ground px-2 py-0.5 rounded-full text-xs font-medium"><span className="text-green-600">✓</span>Terminada</span>;
  return <span className="flex w-fit items-center gap-1 text-muted bg-surface px-2 py-0.5 rounded-full text-xs font-medium"><span className="w-2 h-2 bg-slate-300 rounded-full"/>Sin iniciar</span>;
}

export default Technicians;
