/**
 * src/api/adminApi.ts  —  CORREGIDO
 *
 * Los tipos de este archivo describían una API que el backend no implementaba.
 * Con los parches del backend (dashboard.py, technicians.py, workdays.py, tasks.py,
 * users.py) el contrato ya coincide. Cambios aquí:
 *
 * 1. exportCsv devolvía una URL "pelada" para abrir en el navegador: ese endpoint exige
 *    Bearer y respondía 401. Ahora descarga por blob con el token puesto.
 * 2. setUserStatus(): permite REACTIVAR usuarios (antes solo se podía desactivar).
 * 3. getUsers() tolera respuesta paginada { items } o arreglo plano.
 * 4. Se quita el campo "notes" del payload de tareas: no existe en el modelo y se
 *    perdía en silencio (usa description).
 * 5. Filtros de fecha por rango en tareas.
 */
import client from './client';
import { Task, User } from '../types';

/* ---------- Dashboard ---------- */
export interface TechnicianDashboardRow {
  id: string;
  user_id: string;
  full_name: string;
  status: 'WORKING' | 'NOT_STARTED' | 'FINISHED';
  check_in_time?: string | null;   // ISO-8601
  check_out_time?: string | null;  // ISO-8601
  duration_minutes?: number | null;
  tasks_completed: number;
  tasks_pending: number;
  check_in_latitude?: number | null;
  check_in_longitude?: number | null;
}

export interface DashboardData {
  working_now: number;
  not_started: number;
  finished: number;
  tasks_completed: number;
  tasks_pending: number;
  technicians: TechnicianDashboardRow[];
}

/* ---------- Técnicos ---------- */
export interface TechnicianListItem {
  id: string;
  user_id: string;
  employee_number?: string | null;
  phone?: string | null;
  is_active: boolean;
  full_name: string;
  username: string;
  email: string;
}

export interface TechnicianDetail extends TechnicianListItem {
  current_workday?: {
    id: string;
    status: string;
    check_in_at: string;
    check_out_at?: string | null;
    duration_minutes?: number | null;
    check_in_latitude?: number | null;
    check_in_longitude?: number | null;
  } | null;
  today_tasks: Task[];
}

/* ---------- Tareas ---------- */
export interface AdminTaskPayload {
  technician_id: string;
  assigned_date: string;   // YYYY-MM-DD  (el backend ya la respeta)
  title: string;
  description?: string;
  location_name?: string;
  scheduled_time?: string; // HH:MM
  priority?: 'NORMAL' | 'HIGH';
}

/* ---------- Jornadas ---------- */
export interface AdminWorkdayItem {
  id: string;
  technician_id: string;
  technician_name: string;
  work_date: string;
  check_in_at: string;
  check_out_at?: string | null;
  duration_minutes?: number | null;
  status: string;
  tasks_assigned: number;
  tasks_completed: number;
  check_in_latitude?: number | null;
  check_in_longitude?: number | null;
}

/* ---------- Reportes ---------- */
export interface ReportRow {
  technician_id: string;
  technician_name: string;
  days_worked: number;
  total_minutes: number;
  total_hours: number;
  avg_check_in: string;
  avg_check_out: string;
  tasks_assigned: number;
  tasks_completed: number;
  tasks_unplanned: number;
  tasks_pending: number;
  tasks_cancelled: number;
}

const clean = (params: Record<string, string | number | undefined | null>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') query.set(k, String(v));
  });
  return query;
};

export const adminApi = {
  /* Dashboard */
  getDashboard: async (): Promise<DashboardData> => {
    const { data } = await client.get('/admin/dashboard');
    return data;
  },

  /* Técnicos */
  getTechnicians: async (includeInactive = false): Promise<TechnicianListItem[]> => {
    const { data } = await client.get(
      `/admin/technicians?${clean({ include_inactive: includeInactive ? 'true' : '' })}`,
    );
    return Array.isArray(data) ? data : data.items ?? [];
  },
  getTechnicianDetail: async (id: string): Promise<TechnicianDetail> => {
    const { data } = await client.get(`/admin/technicians/${id}`);
    return data;
  },
  createTechnician: async (payload: {
    username: string; email: string; password: string;
    full_name: string; employee_number?: string; phone?: string;
  }): Promise<TechnicianListItem> => {
    const { data } = await client.post('/admin/technicians', payload);
    return data;
  },

  /* Tareas */
  getTasks: async (params?: {
    technician_id?: string; date?: string;
    date_from?: string; date_to?: string; status?: string;
  }): Promise<Task[]> => {
    const { data } = await client.get(`/admin/tasks?${clean({ ...params })}`);
    return data;
  },
  createTask: async (payload: AdminTaskPayload): Promise<Task> => {
    const { data } = await client.post('/admin/tasks', payload);
    return data;
  },
  updateTask: async (id: string, payload: Partial<AdminTaskPayload>): Promise<Task> => {
    const { data } = await client.patch(`/admin/tasks/${id}`, payload);
    return data;
  },
  cancelTask: async (id: string): Promise<Task> => {
    const { data } = await client.patch(`/admin/tasks/${id}/cancel`);
    return data;
  },

  /* Jornadas */
  getWorkdays: async (params?: {
    date_from?: string; date_to?: string; technician_id?: string;
    status?: string; page?: number; size?: number;
  }): Promise<{ items: AdminWorkdayItem[]; total: number; pages: number }> => {
    const query = clean({
      ...params,
      page: params?.page ?? 1,
      size: params?.size ?? 20,
    });
    const { data } = await client.get(`/admin/workdays?${query.toString()}`);
    return data;
  },

  /* Reportes */
  getReport: async (params: {
    date_from: string; date_to: string; technician_id?: string;
  }): Promise<ReportRow[]> => {
    const { data } = await client.get(`/admin/reports?${clean({ ...params })}`);
    return data;
  },
  /** Descarga el CSV con el token puesto (la URL directa respondía 401). */
  downloadCsv: async (params: { date_from: string; date_to: string; technician_id?: string }) => {
    const response = await client.get(`/admin/reports/export/csv?${clean({ ...params })}`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `reporte_${params.date_from}_${params.date_to}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  /* Usuarios */
  getUsers: async (search?: string): Promise<User[]> => {
    const { data } = await client.get(`/admin/users?${clean({ search })}`);
    return Array.isArray(data) ? data : data.items ?? [];
  },
  /** Activa o desactiva (antes /disable siempre desactivaba). */
  setUserStatus: async (id: string, isActive: boolean): Promise<User> => {
    const { data } = await client.patch(`/admin/users/${id}/disable`, { is_active: isActive });
    return data;
  },
};
