import client from './client';
import { Task } from '../types';

export interface CompleteTaskPayload {
  completion_comment?: string;
}

export interface UnplannedTaskPayload {
  title: string;
  location_id?: string; location_name?: string;
  completion_comment?: string;
}

export const taskApi = {
  getToday: async (): Promise<Task[]> => {
    const { data } = await client.get('/tasks/today');
    return data;
  },
  completeTask: async (taskId: string, payload: CompleteTaskPayload): Promise<Task> => {
    const { data } = await client.patch(`/tasks/${taskId}/complete`, payload);
    return data;
  },
  addUnplanned: async (payload: UnplannedTaskPayload): Promise<Task> => {
    const { data } = await client.post('/tasks/unplanned', payload);
    return data;
  },
};
