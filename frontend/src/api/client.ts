import axios from 'axios';
import {
  AuthResponse,
  ProjectSummaryCard,
  ProjectDetail,
  Deployment,
  HealthTarget,
  LatencyAndTimelineResponse,
  Incident,
  AlertConfig,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('pulseops_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Avoid redirecting if already on login page
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('pulseops_token');
        localStorage.removeItem('pulseops_user');
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<AuthResponse> => {
      const resp = await apiClient.post<AuthResponse>('/auth/login/json', { email, password });
      return resp.data;
    },
    register: async (email: string, password: string, role = 'developer') => {
      const resp = await apiClient.post('/auth/register', { email, password, role });
      return resp.data;
    },
    getMe: async () => {
      const resp = await apiClient.get('/auth/me');
      return resp.data;
    },
  },

  projects: {
    getOverviewCards: async (): Promise<ProjectSummaryCard[]> => {
      const resp = await apiClient.get<ProjectSummaryCard[]>('/projects/overview-cards');
      return resp.data;
    },
    list: async (): Promise<ProjectDetail[]> => {
      const resp = await apiClient.get<ProjectDetail[]>('/projects');
      return resp.data;
    },
    get: async (id: string): Promise<ProjectDetail> => {
      const resp = await apiClient.get<ProjectDetail>(`/projects/${id}`);
      return resp.data;
    },
    create: async (payload: { name: string; slug: string; repo_url: string; provider: 'github' | 'gitlab' }) => {
      const resp = await apiClient.post<ProjectDetail>('/projects', payload);
      return resp.data;
    },
    delete: async (id: string) => {
      await apiClient.delete(`/projects/${id}`);
    },
    regenerateSecret: async (id: string) => {
      const resp = await apiClient.post<{ message: string; new_webhook_secret: string }>(`/projects/${id}/regenerate-secret`);
      return resp.data;
    },
  },

  deployments: {
    list: async (params?: { project_id?: string; environment?: string; status?: string; search?: string; limit?: number }) => {
      const resp = await apiClient.get<Deployment[]>('/deployments', { params });
      return resp.data;
    },
    getStats: async (project_id?: string) => {
      const resp = await apiClient.get('/deployments/stats', { params: { project_id } });
      return resp.data;
    },
  },

  health: {
    listTargets: async (params?: { project_id?: string; environment?: string }): Promise<HealthTarget[]> => {
      const resp = await apiClient.get<HealthTarget[]>('/health/targets', { params });
      return resp.data;
    },
    createTarget: async (projectId: string, payload: Partial<HealthTarget>): Promise<HealthTarget> => {
      const resp = await apiClient.post<HealthTarget>(`/health/targets?project_id=${projectId}`, payload);
      return resp.data;
    },
    updateTarget: async (targetId: string, payload: Partial<HealthTarget>): Promise<HealthTarget> => {
      const resp = await apiClient.put<HealthTarget>(`/health/targets/${targetId}`, payload);
      return resp.data;
    },
    deleteTarget: async (targetId: string) => {
      await apiClient.delete(`/health/targets/${targetId}`);
    },
    probeTarget: async (targetId: string) => {
      const resp = await apiClient.post(`/health/targets/${targetId}/probe`);
      return resp.data;
    },
    getTimeline: async (targetId: string, window = '24h'): Promise<LatencyAndTimelineResponse> => {
      const resp = await apiClient.get<LatencyAndTimelineResponse>(`/health/targets/${targetId}/timeline`, {
        params: { range_window: window },
      });
      return resp.data;
    },
  },

  incidents: {
    list: async (params?: { project_id?: string; status?: string }): Promise<Incident[]> => {
      const resp = await apiClient.get<Incident[]>('/incidents', { params });
      return resp.data;
    },
    resolve: async (incidentId: string): Promise<Incident> => {
      const resp = await apiClient.post<Incident>(`/incidents/${incidentId}/resolve`);
      return resp.data;
    },
  },

  alerts: {
    list: async (projectId: string): Promise<AlertConfig[]> => {
      const resp = await apiClient.get<AlertConfig[]>('/alerts', { params: { project_id: projectId } });
      return resp.data;
    },
    create: async (projectId: string, payload: { channel_type: string; destination_url: string; notify_on_deployment_fail: boolean; notify_on_health_fail: boolean }) => {
      const resp = await apiClient.post<AlertConfig>(`/alerts?project_id=${projectId}`, payload);
      return resp.data;
    },
    delete: async (configId: string) => {
      await apiClient.delete(`/alerts/${configId}`);
    },
    test: async (configId: string) => {
      const resp = await apiClient.post(`/alerts/${configId}/test`);
      return resp.data;
    },
  },
};
