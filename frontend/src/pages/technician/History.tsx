import React, { useEffect, useState } from 'react';
import { workdayApi, WorkdayHistoryItem } from '../../api/workdayApi';
import Card from '../../components/ui/Card';
import Spinner from '../../components/ui/Spinner';
import Badge from '../../components/ui/Badge';
import { Calendar } from 'lucide-react';

// Format time to 8:02 AM
function formatTime(isoString: string): string {
  return new Intl.DateTimeFormat('es-MX', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'America/Monterrey'
  }).format(new Date(isoString));
}

// Format duration
function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h} h ${m.toString().padStart(2, '0')} min`;
}

// Format history date to 'JUE 17 SEP'
function formatHistoryDate(dateStr: string): string {
  // Check if it's purely a date string YYYY-MM-DD to avoid timezone shift
  const dateObj = dateStr.includes('T') ? new Date(dateStr) : new Date(dateStr + 'T12:00:00');
  const formatted = new Intl.DateTimeFormat('es-MX', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'America/Monterrey'
  }).format(dateObj);
  
  // Clean up punctuation (e.g. remove dot from "jue." or "sep.")
  return formatted.replace(/\./g, '').toUpperCase();
}

const History: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<WorkdayHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    setLoading(true);
    setError(null);
    try {
      const response = await workdayApi.getHistory(1, 30);
      setHistory(response.items);
    } catch (err) {
      setError('No se pudo cargar el historial. Intenta de nuevo más tarde.');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Spinner size="lg" color="primary" />
        <p className="mt-4 text-slate-500">Cargando historial...</p>
      </div>
    );
  }

  return (
    <div className="pb-8 px-4 pt-4">
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Historial</h1>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6 text-sm">
          {error}
        </div>
      )}

      {!error && history.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <Calendar className="w-12 h-12 mb-4 text-slate-300" />
          <p>No hay jornadas registradas aún.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {history.map(item => (
            <Card key={item.id} className="p-4 border-l-4 border-l-primary">
              <h2 className="font-bold text-lg text-slate-800 mb-3 tracking-wide">
                {formatHistoryDate(item.work_date)} · {item.shift_kind === 'NIGHT' ? 'Nocturna' : 'Diurna'}
              </h2>
              
              <div className="space-y-2 text-slate-600 mb-4">
                <div className="flex justify-between">
                  <span>Entrada:</span>
                  <span className="font-medium text-slate-800">{formatTime(item.check_in_at)}</span>
                </div>
                
                {item.check_out_at ? (
                  <div className="flex justify-between">
                    <span>Salida:</span>
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-slate-800">{formatTime(item.check_out_at)}</span>
                      {item.duration_minutes !== undefined && (
                        <span className="text-sm bg-slate-100 px-2 py-0.5 rounded text-slate-500">
                          {formatDuration(item.duration_minutes)}
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-center py-1">
                    <span>Salida:</span>
                    <Badge variant="success">🟢 Jornada activa</Badge>
                  </div>
                )}
              </div>
              
              <div className="pt-3 border-t border-slate-100 text-sm text-slate-600">
                {item.tasks_count} actividades {item.completed_tasks_count > 0 && `(${item.completed_tasks_count} realizadas)`}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default History;
