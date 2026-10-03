import { useAuth } from '../../hooks/useAuth';
import { useSearchParams } from 'react-router-dom';
import React, { useEffect, useState } from 'react';
import { adminApi, AdminTaskPayload } from '../../api/adminApi';
import { Task } from '../../types';
import LocationSelect from '../../components/LocationSelect';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Spinner from '../../components/ui/Spinner';
import Modal from '../../components/ui/Modal';
import { User, Plus, Edit2, XCircle, Search, MapPin, Calendar, Clock, AlertTriangle } from 'lucide-react';

const Tasks: React.FC = () => {
  const { isAdmin } = useAuth();
  const [searchParams] = useSearchParams();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [technicians, setTechnicians] = useState<{id: string, name: string}[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const todayStr = new Date().toISOString().split('T')[0];
  const [filterDate, setFilterDate] = useState(todayStr);
  const [filterTech, setFilterTech] = useState(searchParams.get('technician_id') || '');
  const [filterStatus, setFilterStatus] = useState('');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  
  // Form State
  const [formData, setFormData] = useState<AdminTaskPayload>({
    technician_id: '',
    assigned_date: todayStr,
    title: '',
    description: '',
    location_id: '',
    scheduled_time: '',
    priority: 'NORMAL'
  });
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState('');


  const fetchFilters = async () => {
    try {
      const techs = await adminApi.getTechnicians(true);
      setTechnicians(techs.map(t => ({ id: t.id, name: t.full_name })));
    } catch (e) {}
  };

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getTasks({
        date: filterDate || undefined,
        technician_id: filterTech || undefined,
        status: filterStatus || undefined
      });
      setTasks(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [filterDate, filterTech, filterStatus]);

  const handleOpenNew = () => {
    setEditingTask(null);
    setFormData({
      technician_id: technicians[0]?.id || '',
      assigned_date: filterDate || todayStr,
      title: '',
      description: '',
      location_id: '',
      scheduled_time: '',
      priority: 'NORMAL'
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (task: Task) => {
    setEditingTask(task);
    setFormData({
      technician_id: task.technician_id,
      assigned_date: task.assigned_date,
      title: task.title,
      description: task.description || '',
      location_id: task.location_id || '',
      scheduled_time: task.scheduled_time || '',
      priority: task.priority || 'NORMAL'
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.technician_id || !formData.title || !formData.assigned_date || !formData.location_id) {
      setFormError('Por favor completa los campos obligatorios (*).');
      return;
    }

    setFormLoading(true);
    setFormError('');
    try {
      if (editingTask) {
        await adminApi.updateTask(editingTask.id, { ...formData, scheduled_time: formData.scheduled_time || null });
      } else {
        await adminApi.createTask({ ...formData, scheduled_time: formData.scheduled_time || null });
      }
      setIsModalOpen(false);
      fetchTasks();
    } catch (err: any) {
      setFormError('Error al guardar la tarea. ' + (err?.response?.data?.detail || err.message || ''));
    } finally {
      setFormLoading(false);
    }
  };

  const handleCancelTask = async (task: Task) => {
    if (!window.confirm(`¿Estás seguro de cancelar la tarea "${task.title}"?`)) return;
    try {
      await adminApi.cancelTask(task.id);
      fetchTasks();
    } catch (err) {
      alert('Error al cancelar la tarea.');
    }
  };

  const getTechName = (id: string) => {
    const tech = technicians.find(t => t.id === id);
    return tech ? tech.name : 'Técnico ' + id.substring(0,6);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-ink">Tareas</h1>
        {isAdmin && <Button onClick={handleOpenNew} className="flex items-center gap-2">
          <Plus className="w-4 h-4" /> NUEVA TAREA
        </Button>}
      </div>

      <div className="bg-surface p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4 items-end">
        <div className="w-full md:w-1/3">
          <label className="block text-xs font-medium text-muted mb-1">Técnico</label>
          <select 
            value={filterTech} 
            onChange={e => setFilterTech(e.target.value)}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          >
            <option value="">Todos</option>
            {technicians.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="w-full md:w-1/3">
          <label className="block text-xs font-medium text-muted mb-1">Fecha</label>
          <input 
            type="date" 
            value={filterDate}
            onChange={e => setFilterDate(e.target.value)}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          />
        </div>
        <div className="w-full md:w-1/3">
          <label className="block text-xs font-medium text-muted mb-1">Estado</label>
          <select 
            value={filterStatus} 
            onChange={e => setFilterStatus(e.target.value)}
            className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
          >
            <option value="">Todos</option>
            <option value="PENDING">Pendiente</option>
            <option value="IN_PROGRESS">En Progreso</option>
            <option value="COMPLETED">Completada</option>
            <option value="CANCELLED">Cancelada</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tasks.map(task => (
            <Card key={task.id} className="p-4 flex flex-col border-l-4" style={{ borderLeftColor: task.priority === 'HIGH' ? '#ef4444' : '#3b82f6' }}>
              <div className="flex justify-between items-start mb-2">
                <div className="font-semibold text-ink line-clamp-1 flex items-center gap-2">
                  {task.priority === 'HIGH' && <AlertTriangle className="w-4 h-4 text-red-500" />}
                  {task.title}
                </div>
                <StatusBadge status={task.status} />
              </div>
              
              <div className="text-sm text-muted mb-4 space-y-1">
                <div className="flex items-center gap-2"><User className="w-4 h-4 text-muted" /> {getTechName(task.technician_id)}</div>
                {task.location_name && <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-muted" /> {task.location_name}</div>}
                <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-muted" /> {task.assigned_date} {task.scheduled_time && <span className="ml-2 flex items-center gap-1"><Clock className="w-3 h-3"/> {task.scheduled_time}</span>}</div>
              </div>

              <div className="mt-auto flex justify-end gap-2 pt-3 border-t border-slate-100">
                {isAdmin && task.status !== 'COMPLETED' && task.status !== 'CANCELLED' && (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => handleOpenEdit(task)} className="text-muted hover:text-blue-600 border-slate-200">
                      <Edit2 className="w-3.5 h-3.5 mr-1" /> Editar
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => handleCancelTask(task)} className="text-muted hover:text-red-600 border-slate-200 hover:border-red-200 hover:bg-red-50">
                      <XCircle className="w-3.5 h-3.5 mr-1" /> Cancelar
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
          {tasks.length === 0 && (
            <div className="col-span-full py-12 text-center text-muted bg-surface rounded-lg border border-slate-200">
              <Search className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              No se encontraron tareas con los filtros actuales.
            </div>
          )}
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => !formLoading && setIsModalOpen(false)} title={editingTask ? 'Editar Tarea' : 'Nueva Tarea'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <div className="bg-red-50 text-red-600 p-3 rounded-md text-sm">{formError}</div>}
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Técnico *</label>
              <select 
                required
                value={formData.technician_id}
                onChange={e => setFormData({...formData, technician_id: e.target.value})}
                className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                disabled={!!editingTask} // Usually shouldn't reassign, but depends on logic
              >
                <option value="">Selecciona un técnico</option>
                {technicians.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Fecha *</label>
              <input 
                required type="date"
                value={formData.assigned_date}
                onChange={e => setFormData({...formData, assigned_date: e.target.value})}
                className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">Título *</label>
            <input 
              required type="text"
              value={formData.title}
              onChange={e => setFormData({...formData, title: e.target.value})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              placeholder="Ej. Revisar equipo"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">Descripción</label>
            <textarea 
              value={formData.description}
              onChange={e => setFormData({...formData, description: e.target.value})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <LocationSelect value={formData.location_id || ''} onChange={value => setFormData({...formData, location_id: value})} legacyName={editingTask?.location_name} />
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Hora programada</label>
              <input 
                type="time"
                value={formData.scheduled_time ?? ''}
                onChange={e => setFormData({...formData, scheduled_time: e.target.value})}
                className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">Prioridad</label>
            <select 
              value={formData.priority}
              onChange={e => setFormData({...formData, priority: e.target.value as any})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
            >
              <option value="NORMAL">Normal</option>
              <option value="HIGH">Alta</option>
            </select>
          </div>



          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 mt-6">
            <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)} disabled={formLoading}>
              CANCELAR
            </Button>
            <Button type="submit" disabled={formLoading}>
              {formLoading ? 'GUARDANDO...' : editingTask ? 'GUARDAR CAMBIOS' : 'ASIGNAR TAREA'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string, color: string }> = {
    'PENDING': { label: 'PENDIENTE', color: 'bg-ground text-muted' },
    'IN_PROGRESS': { label: 'EN PROGRESO', color: 'bg-blue-100 text-blue-700' },
    'COMPLETED': { label: 'COMPLETADA', color: 'bg-green-100 text-green-700' },
    'CANCELLED': { label: 'CANCELADA', color: 'bg-red-100 text-red-700' }
  };
  const conf = map[status] || { label: status, color: 'bg-ground text-muted' };
  return <span className={`px-2 py-1 text-xs font-semibold rounded-md ${conf.color}`}>{conf.label}</span>;
}

export default Tasks;
