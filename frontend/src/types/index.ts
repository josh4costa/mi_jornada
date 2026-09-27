export type UserRole = 'ADMIN' | 'TECHNICIAN' | 'READ_ONLY';
export type WorkdayStatus = 'OPEN' | 'CLOSED';
export type TaskStatus = 'PENDING' | 'COMPLETED' | 'CANCELLED';
export type TaskPriority = 'NORMAL' | 'HIGH';
export type CreatedByType = 'ADMIN' | 'TECHNICIAN';

export interface User {
  must_change_password?: boolean;
  technician?: { id: string; employee_number: string | null; phone: string | null; reminders_enabled?: boolean } | null;
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
}

export interface Technician {
  id: string;
  user_id: string;
  employee_number?: string;
  phone?: string;
  is_active: boolean;
  user: User;
}

export interface Workday {
  id: string;
  technician_id: string;
  work_date: string;
  shift_kind?: "DAY" | "NIGHT";
  check_in_at: string;
  check_in_latitude?: number;
  check_in_longitude?: number;
  check_in_accuracy?: number;
  check_out_at?: string;
  check_out_latitude?: number;
  check_out_longitude?: number;
  check_out_accuracy?: number;
  duration_minutes?: number;
  status: WorkdayStatus;
}

export interface Task {
  id: string;
  technician_id: string;
  assigned_date: string;
  title: string;
  description?: string;
  location_id?: string | null;
  location_name?: string;
  scheduled_time?: string;
  priority: TaskPriority;
  status: TaskStatus;
  created_by: string;
  created_by_type: CreatedByType;
  completed_at?: string;
  completion_comment?: string;
  external_service_order_url?: string;
}

export interface DashboardSummary {
  working_now: number;
  not_started: number;
  finished: number;
  tasks_completed: number;
  tasks_pending: number;
  technicians: TechnicianDashboardRow[];
}

export interface TechnicianDashboardRow {
  id: string;
  full_name: string;
  status: 'WORKING' | 'NOT_STARTED' | 'FINISHED';
  check_in_time?: string;
  check_out_time?: string;
  tasks_completed: number;
  tasks_pending: number;
}
