import { Link } from 'react-router-dom';
import LocationSelect from '../../components/LocationSelect';
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { useGeolocation, GeoPosition } from '../../hooks/useGeolocation';
import { workdayApi } from '../../api/workdayApi';
import { taskApi } from '../../api/taskApi';
import type { Workday, Task } from '../../types';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import Spinner from '../../components/ui/Spinner';
import Modal from '../../components/ui/Modal';
import { MapPin, Clock, Plus, CheckCircle, AlertCircle, Calendar } from 'lucide-react';

type PageState = 'loading' | 'error' | 'not_started' | 'working' | 'finished';

// Format duration
function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h} h ${m.toString().padStart(2, '0')} min`;
}

// Format time from ISO string to '7:58 AM' in America/Monterrey
function formatTime(isoString: string): string {
  return new Intl.DateTimeFormat('es-MX', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'America/Monterrey'
  }).format(new Date(isoString));
}

// Get greeting based on hour
function getGreeting(): string {
  const hour = new Date().toLocaleString('en-US', { hour: 'numeric', hour12: false, timeZone: 'America/Monterrey' });
  const h = parseInt(hour, 10);
  if (h >= 5 && h < 12) return 'Buenos días';
  if (h >= 12 && h < 19) return 'Buenas tardes';
  return 'Buenas noches';
}

// Format today's date in Spanish
function formatTodayDate(): string {
  const dateStr = new Intl.DateTimeFormat('es-MX', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'America/Monterrey'
  }).format(new Date());
  return dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
}

// Format TIME string "HH:MM:SS" to "9:00 AM"
function formatScheduledTime(timeStr: string): string {
  const [hours, minutes] = timeStr.split(':').map(Number);
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const h12 = hours % 12 || 12;
  return `${h12}:${minutes.toString().padStart(2, '0')} ${suffix}`;
}

const Home: React.FC = () => {
  const { user } = useAuth();
  const { isOnline } = useOnlineStatus();
  const { getPosition } = useGeolocation();

  const [pageState, setPageState] = useState<PageState>('loading');
  const [workday, setWorkday] = useState<Workday | null>(null);
  const [canStartDay, setCanStartDay] = useState(true);
  const [dayRest, setDayRest] = useState(false);
  const [nightOptions, setNightOptions] = useState<{ id: string; status: string }[]>([]);
  const [continueModal, setContinueModal] = useState(false);
  const [exitReason, setExitReason] = useState('');
  const [scheduledExit, setScheduledExit] = useState<string | null>(null);
  const [absence, setAbsence] = useState<{ kind: string; end_date: string } | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<string | null>(null);

  // Check-in flow
  const [checkInLoading, setCheckInLoading] = useState(false);
  const [checkInGpsLoading, setCheckInGpsLoading] = useState(false);
  const [checkInError, setCheckInError] = useState<string | null>(null);

  // Check-out flow
  const [showCheckOutModal, setShowCheckOutModal] = useState(false);
  const [checkOutLoading, setCheckOutLoading] = useState(false);
  const [checkOutGpsLoading, setCheckOutGpsLoading] = useState(false);
  const [checkOutError, setCheckOutError] = useState<string | null>(null);
  const [checkOutPosition, setCheckOutPosition] = useState<GeoPosition | null>(null);

  // Complete task flow
  const [completingTask, setCompletingTask] = useState<Task | null>(null);
  const [completionComment, setCompletionComment] = useState('');
  const [completeLoading, setCompleteLoading] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);

  // Add unplanned task
  const [showAddTask, setShowAddTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskLocation, setNewTaskLocation] = useState('');
  const [addTaskLoading, setAddTaskLoading] = useState(false);
  const [addTaskError, setAddTaskError] = useState<string | null>(null);

  useEffect(() => {
    loadPageData();
  }, []);

  async function loadTasks() {
    setTasksLoading(true);
    setTasksError(null);
    try {
      setTasks(await taskApi.getToday());
    } catch {
      setTasksError('No se pudieron actualizar las tareas.');
    } finally {
      setTasksLoading(false);
    }
  }

  async function loadPageData() {
    setPageState('loading');
    const tasksRequest = loadTasks();
    try {
      const todayResponse = await workdayApi.getToday();
      setWorkday(todayResponse.workday);
      setCanStartDay(todayResponse.can_start_day ?? true);
      setDayRest(todayResponse.day_rest ?? false);
      setNightOptions(todayResponse.night_options || []);
      setScheduledExit(todayResponse.scheduled_exit || null);
      setAbsence(todayResponse.approved_absence || null);
      if (todayResponse.status === 'NOT_STARTED') setPageState('not_started');
      else if (todayResponse.status === 'WORKING') setPageState('working');
      else setPageState('finished');
    } catch {
      setPageState('error');
    }
    await tasksRequest;
  }

  const handleCheckIn = async (nightPlanId?: string, continuation = false) => {
    if (!isOnline) return;
    setCheckInError(null);
    setCheckInGpsLoading(true);
    let position: GeoPosition;
    try {
      position = await getPosition();
    } catch (err: any) {
      setCheckInGpsLoading(false);
      setCheckInError(err.message || 'Error al obtener ubicación.');
      return;
    }
    setCheckInGpsLoading(false);

    setCheckInLoading(true);
    try {
      const updatedWorkday = await (continuation ? workdayApi.continueDay : workdayApi.checkIn)({
        night_plan_id: nightPlanId,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy: position.accuracy
      });
      setWorkday(updatedWorkday);
      setPageState('working');
      try { setScheduledExit((await workdayApi.getToday()).scheduled_exit || null); } catch { /* Server validates checkout independently. */ }
      
      setContinueModal(false);
      await loadPageData();
    } catch (err: any) {
      setCheckInError(err.friendlyMessage || 'No pudimos registrar la entrada. Inténtalo de nuevo.');
    } finally {
      setCheckInLoading(false);
    }
  };

  const handleCompleteTask = async () => {
    if (!completingTask) return;
    setCompleteLoading(true);
    setCompleteError(null);
    try {
      const updatedTask = await taskApi.completeTask(completingTask.id, {
        completion_comment: completionComment
      });
      setTasks(prev => prev.map(t => t.id === updatedTask.id ? updatedTask : t));
      setCompletingTask(null);
      setCompletionComment('');
    } catch (err) {
      setCompleteError('No se pudo completar la actividad. Inténtalo de nuevo.');
    } finally {
      setCompleteLoading(false);
    }
  };

  const handleAddUnplannedTask = async () => {
    if (!newTaskLocation) { setAddTaskError('Selecciona la sucursal relacionada con la tarea.'); return; }
    if (!newTaskTitle.trim()) {
      setAddTaskError('El título es requerido.');
      return;
    }
    setAddTaskLoading(true);
    setAddTaskError(null);
    try {
      const newTask = await taskApi.addUnplanned({
        title: newTaskTitle,
        location_id: newTaskLocation
      });
      setTasks(prev => [newTask, ...prev]);
      setShowAddTask(false);
      setNewTaskTitle('');
      setNewTaskLocation('');
    } catch (err) {
      setAddTaskError('No se pudo guardar la actividad. Inténtalo de nuevo.');
    } finally {
      setAddTaskLoading(false);
    }
  };

  const handleInitiateCheckOut = async () => {
    if (!isOnline) return;
    setCheckOutError(null);
    setCheckOutGpsLoading(true);
    try {
      const pos = await getPosition();
      setCheckOutPosition(pos);
      setShowCheckOutModal(true);
    } catch (err: any) {
      setCheckOutError(err.message || 'Error al obtener ubicación.');
    } finally {
      setCheckOutGpsLoading(false);
    }
  };

  const handleConfirmCheckOut = async () => {
    if (!checkOutPosition) return;
    setCheckOutLoading(true);
    setCheckOutError(null);
    try {
      const updatedWorkday = await workdayApi.checkOut({
        latitude: checkOutPosition.latitude,
        longitude: checkOutPosition.longitude,
        accuracy: checkOutPosition.accuracy,
        early_exit_reason: exitReason.trim() || undefined
      });
      setWorkday(updatedWorkday);
      setPageState('finished');
      setShowCheckOutModal(false);
      await loadPageData();
    } catch (err: any) {
      setCheckOutError(err.friendlyMessage || 'No se pudo registrar la salida. Inténtalo de nuevo.');
    } finally {
      setCheckOutLoading(false);
    }
  };

  if (pageState === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Spinner size="lg" color="primary" />
        <p className="mt-4 text-slate-500">Cargando...</p>
      </div>
    );
  }

  if (pageState === 'error') {
    return <div className="p-6 space-y-4" role="alert"><p>No se pudo consultar tu jornada. Reintenta para conocer su estado.</p><Button onClick={loadPageData} disabled={!isOnline}>Reintentar</Button></div>;
  }

  const tasksCompleted = tasks.filter(t => t.status === 'COMPLETED').length;
  const tasksPending = tasks.filter(t => t.status === 'PENDING').length;

  return (
    <div className="pb-8">
      
      
      <div className="mb-6 mt-4 px-4">
        <h1 className="text-2xl font-bold text-slate-800">{getGreeting()}, {user?.full_name.split(' ')[0]}</h1>
        <p className="text-slate-500 flex items-center gap-2 mt-1">
          <Calendar className="w-4 h-4" />
          {formatTodayDate()}
        </p>
      </div>

      <div className="mx-4 mb-4 p-3 rounded-lg bg-white border text-sm text-slate-600">
        <p>Horario: lunes a viernes 9:00–18:00 · sábado 9:00–13:00 · domingo descanso.</p>
        {absence && <p className="mt-2 font-medium text-green-700">{absence.kind === 'VACATION' ? 'Vacaciones' : 'Permiso'} aprobado hasta {absence.end_date}. No recibirás recordatorios durante esta ausencia.</p>}
      </div>
      {pageState === 'not_started' && canStartDay && (
        <div className="px-4">
          <Card className="p-6 text-center border-t-4 border-t-slate-300">
            <h2 className="text-lg font-bold text-slate-700 mb-2">MI JORNADA</h2>
            <p className="text-slate-600 mb-6">
              Aún no has iniciado<br />tu jornada de hoy.
            </p>
            
            {checkInError && (
              <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm text-left flex items-start gap-2">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p>{checkInError}</p>
              </div>
            )}
            
            {!isOnline && (
              <p className="text-red-500 text-sm mb-4">Sin conexión — No se pudo registrar. Verifica tu red y reintenta.</p>
            )}

            <Button 
              fullWidth 
              variant="success" 
              size="lg"
              onClick={() => handleCheckIn()}
              disabled={!isOnline || checkInLoading || checkInGpsLoading}
              loading={checkInLoading}
            >
              {checkInGpsLoading ? 'Obteniendo ubicación...' : 'REGISTRAR ENTRADA'}
            </Button>
          </Card>
        </div>
      )}

      <div className="mx-4 my-4 space-y-3">
        <Link className="text-blue-700 underline" to="/ausencias">Avisar o consultar trabajo nocturno en Ausencias y asistencia</Link>
        {dayRest && <p className="text-green-800">Tienes descanso diurno autorizado por programación nocturna.</p>}
        {checkInError && (pageState !== 'not_started' || !canStartDay) && <p role="alert" className="text-red-700">{checkInError}</p>}
        {pageState !== 'working' && nightOptions.map(plan => <Card key={plan.id} className="space-y-3"><h2 className="font-semibold">Trabajo nocturno de hoy</h2>{plan.status === 'PENDING' && <p>Programación pendiente de validación del administrador.</p>}<Button fullWidth onClick={() => handleCheckIn(plan.id)} disabled={!isOnline || checkInLoading || checkInGpsLoading}>Iniciar turno nocturno</Button></Card>)}
        {pageState === 'finished' && canStartDay && <Button fullWidth onClick={() => handleCheckIn()} disabled={!isOnline || checkInLoading || checkInGpsLoading}>Iniciar turno diurno</Button>}
        {pageState === 'working' && workday?.shift_kind === 'NIGHT' && canStartDay && <Button fullWidth variant="secondary" onClick={() => { setContinueModal(true); setCheckInError(null); }} disabled={!isOnline}>Continuar con turno diurno</Button>}
      </div>
      <Modal isOpen={continueModal} onClose={() => !checkInLoading && setContinueModal(false)} title="Continuar con turno diurno" onConfirm={() => handleCheckIn(undefined, true)} confirmText="Registrar cambio de turno" loading={checkInLoading || checkInGpsLoading}><p>Se registrará tu salida nocturna y tu entrada diurna con la misma hora y ubicación actuales. No se perderán ni duplicarán minutos. Hazlo cuando comiences el trabajo diurno.</p>{checkInError && <p role="alert" className="text-red-700">{checkInError}</p>}</Modal>
      {pageState === 'working' && workday && (
        <div className="px-4 space-y-6">
          <Card className="p-4 border-t-4 border-t-green-500">
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="success">{workday.shift_kind === 'NIGHT' ? '🌙 NOCTURNA ACTIVA' : '✅ JORNADA ACTIVA'}</Badge>
            </div>
            <div className="text-slate-600 space-y-1">
              <p>Entrada: <strong>{workday.work_date} · {formatTime(workday.check_in_at)}</strong></p>
              {workday.check_in_latitude != null && (
                <p className="flex items-center gap-1 text-sm"><MapPin className="w-4 h-4 text-slate-400" /> Ubicación registrada</p>
              )}
            </div>
          </Card>

          <div>
            <h3 className="font-bold text-slate-700 mb-4 px-1">MIS TAREAS DE HOY</h3>
            
            <div className="space-y-4 mb-6">
              {tasksLoading ? <Spinner /> : tasksError ? <div role="alert"><p>{tasksError}</p><Button variant="secondary" onClick={loadTasks} disabled={!isOnline}>Reintentar tareas</Button></div> : tasks.length === 0 ? (
                <p className="text-slate-500 text-center py-4">No tienes tareas asignadas hoy.</p>
              ) : (
                tasks.map(task => (
                  <Card key={task.id} className={`p-4 ${task.status === 'COMPLETED' ? 'bg-green-50' : task.status === 'CANCELLED' ? 'bg-slate-50 opacity-75' : ''}`}>
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex flex-wrap gap-2 mb-2">
                        {task.priority === 'HIGH' && <Badge variant="warning">Alta prioridad</Badge>}
                        {task.created_by_type === 'TECHNICIAN' && <Badge variant="secondary">No programada</Badge>}
                      </div>
                    </div>
                    
                    <h4 className={`font-bold text-lg mb-2 ${task.status === 'CANCELLED' ? 'line-through text-slate-500' : 'text-slate-800'}`}>
                      {task.title}
                    </h4>
                    
                    <div className="space-y-1 mb-4 text-sm text-slate-600">
                      {task.location_name && (
                        <p className="flex items-center gap-1"><MapPin className="w-4 h-4" /> {task.location_name}</p>
                      )}
                      {task.scheduled_time && (
                        <p className="flex items-center gap-1"><Clock className="w-4 h-4" /> {formatScheduledTime(task.scheduled_time)}</p>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2 mb-4">
                      <span className="text-sm text-slate-500">Estado:</span>
                      {task.status === 'PENDING' && <Badge variant="secondary">● PENDIENTE</Badge>}
                      {task.status === 'COMPLETED' && <Badge variant="success">✓ REALIZADA</Badge>}
                      {task.status === 'CANCELLED' && <Badge variant="danger">✗ CANCELADA</Badge>}
                    </div>

                    {task.status === 'PENDING' && (
                      <Button fullWidth disabled={!isOnline} onClick={() => setCompletingTask(task)}>
                        MARCAR COMO REALIZADA
                      </Button>
                    )}
                    {task.status === 'COMPLETED' && task.completed_at && (
                      <p className="text-green-700 font-medium text-sm flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" /> REALIZADA — {formatTime(task.completed_at)}
                      </p>
                    )}
                  </Card>
                ))
              )}
            </div>

            <Button variant="secondary" fullWidth className="mb-6" disabled={!isOnline} onClick={() => setShowAddTask(true)}>
              <Plus className="w-5 h-5 mr-2" /> AGREGAR ACTIVIDAD
            </Button>
            
            {checkOutError && (
              <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm text-left flex items-start gap-2">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p>{checkOutError}</p>
              </div>
            )}
            
            {!isOnline && (
              <p className="text-red-500 text-sm mb-4 text-center">Sin conexión — No se pudo registrar. Verifica tu red y reintenta.</p>
            )}

            <Button 
              variant="danger" 
              fullWidth 
              size="lg"
              onClick={handleInitiateCheckOut}
              disabled={!isOnline || checkOutLoading || checkOutGpsLoading}
            >
              {checkOutGpsLoading ? 'Obteniendo ubicación...' : 'REGISTRAR SALIDA'}
            </Button>
          </div>
        </div>
      )}

      {pageState === 'finished' && workday && (
        <div className="px-4">
          <Card className="p-6 border-t-4 border-t-slate-500">
            <div className="flex items-center gap-2 mb-6">
              <Badge variant="success">✅ JORNADA FINALIZADA</Badge>
            </div>
            
            <div className="space-y-3 text-slate-700 mb-6 border-b pb-6">
              <div className="flex justify-between">
                <span className="text-slate-500">Entrada:</span>
                <strong>{formatTime(workday.check_in_at)}</strong>
              </div>
              {workday.check_out_at && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Salida:</span>
                  <strong>{formatTime(workday.check_out_at)}</strong>
                </div>
              )}
              {workday.duration_minutes !== undefined && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Duración:</span>
                  <strong>{formatDuration(workday.duration_minutes)}</strong>
                </div>
              )}
            </div>
            
            <p className="font-medium">
              Realizadas: {tasksCompleted} {tasksCompleted === 1 ? 'actividad' : 'actividades'}
            </p>
          </Card>
        </div>
      )}

      {/* Complete Task Modal */}
      <Modal
        isOpen={!!completingTask}
        onClose={() => { setCompletingTask(null); setCompletionComment(''); setCompleteError(null); }}
        title="¿Terminaste esta actividad?"
        confirmText="SÍ, TERMINAR"
        onConfirm={handleCompleteTask}
        confirmVariant="success"
        loading={completeLoading}
      >
        {completingTask && (
          <div className="space-y-4 py-2">
            <p className="font-bold text-slate-800 text-lg">{completingTask.title}</p>
            {completeError && <p className="text-red-600 text-sm">{completeError}</p>}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Comentario (opcional)</label>
              <textarea
                className="w-full border border-slate-300 rounded-lg p-3 focus:ring-primary focus:border-primary"
                rows={3}
                placeholder="Escribe tus observaciones..."
                value={completionComment}
                onChange={e => setCompletionComment(e.target.value)}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* Add Task Modal */}
      <Modal
        isOpen={showAddTask}
        onClose={() => { setShowAddTask(false); setNewTaskTitle(''); setNewTaskLocation(''); setAddTaskError(null); }}
        title="Nueva Actividad"
        confirmText="GUARDAR"
        onConfirm={handleAddUnplannedTask}
        loading={addTaskLoading}
      >
        <div className="space-y-4 py-2">
          {addTaskError && <p className="text-red-600 text-sm">{addTaskError}</p>}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Actividad *</label>
            <input
              type="text"
              className="w-full border border-slate-300 rounded-lg p-3 focus:ring-primary focus:border-primary"
              placeholder="Ej. Revisión de equipo"
              value={newTaskTitle}
              onChange={e => setNewTaskTitle(e.target.value)}
            />
          </div>
          <LocationSelect value={newTaskLocation} onChange={setNewTaskLocation} />
        </div>
      </Modal>

      {/* Check Out Confirm Modal */}
      <Modal
        isOpen={showCheckOutModal}
        onClose={() => setShowCheckOutModal(false)}
        title="¿Terminar tu jornada?"
        confirmText="TERMINAR JORNADA"
        onConfirm={handleConfirmCheckOut}
        confirmVariant="danger"
        loading={checkOutLoading}
      >
        <div className="space-y-3 py-2 text-slate-700">
          {checkOutError && <p role="alert" className="text-red-600">{checkOutError}</p>}
          {scheduledExit && <p>Salida programada: {formatTime(scheduledExit)}.</p>}
          {workday?.shift_kind !== 'NIGHT' && <><p className="text-sm">Si sales antes de tu horario, indica el motivo. Se registrará la hora real y el administrador revisará la salida anticipada.</p>
          <label className="block">Motivo de salida anticipada<textarea className="w-full border rounded-lg p-2 mt-1" maxLength={1000} value={exitReason} onChange={e => setExitReason(e.target.value)} placeholder="Obligatorio si sales antes de tu horario" /></label></>}
          <div className="flex justify-between">
            <span className="text-slate-500">Entrada:</span>
            <strong>{workday ? formatTime(workday.check_in_at) : ''}</strong>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Tareas realizadas:</span>
            <strong>{tasksCompleted}</strong>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Tareas pendientes:</span>
            <strong className={tasksPending > 0 ? 'text-amber-600' : ''}>{tasksPending}</strong>
          </div>
        </div>
      </Modal>

    </div>
  );
};

export default Home;
