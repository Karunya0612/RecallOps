import {
  AnalysisRequestPayload,
  DefaultBankResponse,
  HealthCheckResponse,
  Incident,
  IncidentAnalysisResponse,
  IncidentCreatePayload,
  IncidentListResponse,
  IncidentOutcomePayload,
  IncidentOutcomeResponse,
} from '../types/api';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(url, { ...options, headers });
    
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const errorData = await response.json();
        if (errorData && typeof errorData.detail === 'string') {
          detail = errorData.detail;
        } else if (errorData && Array.isArray(errorData.detail)) {
          detail = errorData.detail.map((d: { msg?: string }) => d.msg || '').join(', ');
        }
      } catch {
        // Response was not JSON
      }
      throw new ApiError(response.status, detail);
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(0, err instanceof Error ? err.message : 'Network request failed. Ensure backend is running.');
  }
}

export const api = {
  getApiBaseUrl(): string {
    return API_BASE_URL;
  },

  async checkHealth(): Promise<HealthCheckResponse> {
    return request<HealthCheckResponse>('/health');
  },

  async getDefaultBank(): Promise<DefaultBankResponse> {
    return request<DefaultBankResponse>('/api/v1/banks/default');
  },

  async listIncidents(limit = 50, offset = 0): Promise<IncidentListResponse> {
    return request<IncidentListResponse>(`/api/v1/incidents?limit=${limit}&offset=${offset}`);
  },

  async getIncident(incidentId: string): Promise<Incident> {
    return request<Incident>(`/api/v1/incidents/${encodeURIComponent(incidentId)}`);
  },

  async createIncident(payload: IncidentCreatePayload): Promise<Incident> {
    return request<Incident>('/api/v1/incidents', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async analyzeIncident(
    incidentId: string,
    payload?: AnalysisRequestPayload,
  ): Promise<IncidentAnalysisResponse> {
    return request<IncidentAnalysisResponse>(
      `/api/v1/incidents/${encodeURIComponent(incidentId)}/analyze`,
      {
        method: 'POST',
        body: payload ? JSON.stringify(payload) : undefined,
      },
    );
  },

  async recordOutcome(
    incidentId: string,
    payload: IncidentOutcomePayload,
  ): Promise<IncidentOutcomeResponse> {
    return request<IncidentOutcomeResponse>(
      `/api/v1/incidents/${encodeURIComponent(incidentId)}/outcome`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },
};
