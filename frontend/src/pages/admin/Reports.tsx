import { useAuth } from '../../hooks/useAuth';
import React, { useEffect, useState } from 'react';
import { adminApi, ReportRow } from '../../api/adminApi';
import Button from '../../components/ui/Button';
import Spinner from '../../components/ui/Spinner';
import { Download, FileText, Search, AlertCircle } from 'lucide-react';
import WeeklyReportSettings, { downloadAttendancePdf } from '../../components/WeeklyReportSettings';

const Reports: React.FC = () => {
  const { isAdmin } = useAuth();
  const [reports, setReports] = useState<ReportRow[]>([]);
  const [technicians, setTechnicians] = useState<{id: string, name: string}[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Defaults: current month
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
  
  const formatDateForInput = (d: Date) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().split('T')[0];
  };

  const [filters, setFilters] = useState({
    date_from: formatDateForInput(firstDay),
    date_to: formatDateForInput(today),
    technician_id: ''
  });

  useEffect(() => {
    adminApi.getTechnicians().then(techs => {
      setTechnicians(techs.map(t => ({ id: t.id, name: t.full_name })));
    }).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!filters.date_from || !filters.date_to || filters.date_from > filters.date_to) {
      setError('Selecciona un rango de fechas válido');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.getReport({
        date_from: filters.date_from,
        date_to: filters.date_to,
        technician_id: filters.technician_id || undefined
      });
      setReports(res);
    } catch (e: any) {
      setError('Error al generar el reporte.');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async () => {
    if (!filters.date_from || !filters.date_to || filters.date_from > filters.date_to) {
      setError('Selecciona un rango de fechas válido');
      return;
    }
    
    try {
      await adminApi.downloadCsv({ ...filters, technician_id: filters.technician_id || undefined });
    } catch (e) {
      setError('Error al exportar CSV.');
    }
  };

  const formatDuration = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    return `${h} h ${minutes % 60} min`;
  };

  const handleExportPDF = async () => {
    const span = (Date.parse(filters.date_to) - Date.parse(filters.date_from)) / 86400000;
    if (!Number.isFinite(span) || span < 0 || span > 30) {
      setError('Selecciona un período de 1 a 31 días para el PDF.'); return;
    }
    setLoading(true); setError(null);
    try { await downloadAttendancePdf('/admin/report-mail/pdf', `asistencias_${filters.date_from}_${filters.date_to}.pdf`, {...filters, technician_id: filters.technician_id || undefined}); }
    catch { setError('No se pudo descargar el PDF de asistencias.'); }
    finally { setLoading(false); }
  };



  const totals = reports.reduce((acc, curr) => {
    acc.days_worked += curr.days_worked;
    acc.total_minutes += curr.total_minutes;
    acc.tasks_assigned += curr.tasks_assigned;
    acc.tasks_completed += curr.tasks_completed;
    acc.tasks_pending += curr.tasks_pending;
    return acc;
  }, { days_worked: 0, total_minutes: 0, tasks_assigned: 0, tasks_completed: 0, tasks_pending: 0 });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Reportes</h1>

      <div className="bg-white p-4 sm:p-6 rounded-lg shadow-sm border border-slate-200">
        <h2 className="text-sm font-semibold text-slate-700 uppercase mb-4 tracking-wider flex items-center gap-2">
          <Search className="w-4 h-4" /> Parámetros
        </h2>
        {error && (
          <div className="mb-4 bg-red-50 text-red-600 p-3 rounded-md text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}
        <div className="flex flex-col md:flex-row gap-4 items-end">
          <div className="w-full md:w-1/3">
            <label className="block text-xs font-medium text-slate-500 mb-1">Fecha inicio *</label>
            <input 
              type="date" 
              required
              value={filters.date_from}
              onChange={e => setFilters({...filters, date_from: e.target.value})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
            />
          </div>
          <div className="w-full md:w-1/3">
            <label className="block text-xs font-medium text-slate-500 mb-1">Fecha fin *</label>
            <input 
              type="date" 
              required
              value={filters.date_to}
              onChange={e => setFilters({...filters, date_to: e.target.value})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
            />
          </div>
          <div className="w-full md:w-1/3">
            <label className="block text-xs font-medium text-slate-500 mb-1">Técnico (Opcional)</label>
            <select 
              value={filters.technician_id} 
              onChange={e => setFilters({...filters, technician_id: e.target.value})}
              className="w-full border-slate-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm py-2 px-3 border"
            >
              <option value="">Todos los técnicos</option>
              {technicians.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>
        
        <div className="flex flex-col sm:flex-row gap-3 mt-6">
          <Button onClick={handleGenerate} disabled={loading} className="flex-1 sm:flex-none justify-center">
            <FileText className="w-4 h-4 mr-2" />
            GENERAR REPORTE
          </Button>
          <Button onClick={handleExportCSV} variant="secondary" disabled={loading} className="flex-1 sm:flex-none justify-center">
            <Download className="w-4 h-4 mr-2" />
            EXPORTAR CSV
          </Button>
          <Button onClick={handleExportPDF} variant="secondary" disabled={loading}><Download className="w-4 h-4 mr-2" />DESCARGAR PDF DE ASISTENCIAS</Button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : reports.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4">Técnico</th>
                  <th className="px-6 py-4 text-center">Días</th>
                  <th className="px-6 py-4 text-center">Horas</th>
                  <th className="px-6 py-4">Prom. Entrada</th>
                  <th className="px-6 py-4">Prom. Salida</th>
                  <th className="px-6 py-4 text-center">Asignadas</th>
                  <th className="px-6 py-4 text-center">Realizadas</th>
                  <th className="px-6 py-4 text-center">Pendientes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {reports.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-6 py-4 font-medium text-slate-800">{row.technician_name}</td>
                    <td className="px-6 py-4 text-center text-slate-600">{row.days_worked}</td>
                    <td className="px-6 py-4 text-center text-slate-600">{formatDuration(row.total_minutes)}</td>
                    <td className="px-6 py-4 text-slate-600">{row.avg_check_in ?? '—'}</td>
                    <td className="px-6 py-4 text-slate-600">{row.avg_check_out ?? '—'}</td>
                    <td className="px-6 py-4 text-center text-slate-600">{row.tasks_assigned}</td>
                    <td className="px-6 py-4 text-center text-slate-600">{row.tasks_completed}</td>
                    <td className="px-6 py-4 text-center text-slate-600">{row.tasks_pending}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50 font-semibold text-slate-800 border-t-2 border-slate-200">
                <tr>
                  <td className="px-6 py-4">TOTAL</td>
                  <td className="px-6 py-4 text-center">{totals.days_worked}</td>
                  <td className="px-6 py-4 text-center">{formatDuration(totals.total_minutes)}</td>
                  <td className="px-6 py-4"></td>
                  <td className="px-6 py-4"></td>
                  <td className="px-6 py-4 text-center">{totals.tasks_assigned}</td>
                  <td className="px-6 py-4 text-center">{totals.tasks_completed}</td>
                  <td className="px-6 py-4 text-center">{totals.tasks_pending}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : (
          <div className="py-16 text-center text-slate-500">
            <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p>Genera un reporte seleccionando el rango de fechas</p>
          </div>
        )}
      </div>
      {isAdmin && <WeeklyReportSettings />}
    </div>
  );
};

export default Reports;
