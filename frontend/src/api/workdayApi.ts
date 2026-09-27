import client from './client';
import { Workday, Task } from '../types';

export interface TodayWorkdayResponse {
  status: 'NOT_STARTED' | 'WORKING' | 'FINISHED';
  workday: Workday | null;
  can_start_day?: boolean;
  day_rest?: boolean;
  night_options?: { id: string; status: string; reminder_at: string }[];
  scheduled_exit?: string | null;
  early_exit?: boolean;
  approved_absence?: { kind: string; end_date: string } | null;
}

export interface CheckInPayload {
  night_plan_id?: string;
  early_exit_reason?: string;
  latitude?: number;
  longitude?: number;
  accuracy?: number;
}

export interface WorkdayHistoryItem {
  id: string;
  work_date: string;
  shift_kind?: string;
  check_in_at: string;
  check_out_at?: string;
  duration_minutes?: number;
  status: string;
  tasks_count: number;
  completed_tasks_count: number;
}

export interface WorkdayHistoryDetail extends WorkdayHistoryItem {
  tasks: Task[];
  check_in_latitude?: number;
  check_in_longitude?: number;
}

export const workdayApi = {
  getToday: async (): Promise<TodayWorkdayResponse> => {
    const { data } = await client.get('/workdays/today');
    return data;
  },
  checkIn: async (payload: CheckInPayload): Promise<Workday> => {
    const { data } = await client.post('/workdays/check-in', payload);
    return data;
  },
  continueDay: async (payload: CheckInPayload): Promise<Workday> => {
    const { data } = await client.post('/workdays/continue-day', payload); return data;
  },
  checkOut: async (payload: CheckInPayload): Promise<Workday> => {
    const { data } = await client.post('/workdays/check-out', payload);
    return data;
  },
  getHistory: async (page = 1, size = 30): Promise<{ items: WorkdayHistoryItem[]; total: number }> => {
    const { data } = await client.get(`/history/workdays?page=${page}&size=${size}`);
    return data;
  },
  getHistoryDetail: async (id: string): Promise<WorkdayHistoryDetail> => {
    const { data } = await client.get(`/history/workdays/${id}`);
    return data;
  },
};
