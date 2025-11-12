import { API_BASE_URL, API_TOKEN } from '../config';
import { getStoredToken } from '../auth';
import type {
  BrandProfile,
  BrandProfilePayload,
  Conversation,
  ConversationDetail,
  GrowthSettings,
  GrowthProfile,
  GrowthProfilePayload,
  GrowthProfileUpdatePayload,
  HealthResponse,
  IdeasResponse,
  NotificationItem,
  SchedulerConfigPayload,
  StreamRule,
  WatchlistAnalytics,
} from '../types';

function resolveAuthToken(): string {
  const stored = getStoredToken();
  if (stored) {
    return stored;
  }
  return API_TOKEN;
}

function normalizeHeaders(input?: HeadersInit): Record<string, string> {
  if (!input) {
    return {};
  }
  if (input instanceof Headers) {
    return Object.fromEntries(input.entries());
  }
  if (Array.isArray(input)) {
    return Object.fromEntries(input);
  }
  return input;
}

async function request<T>(path: string, init?: RequestInit, tokenOverride?: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...normalizeHeaders(init?.headers),
  };
  const token = tokenOverride ?? resolveAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed: ${response.status} ${response.statusText} — ${body}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<HealthResponse>('/health'),
  validateToken: (token: string) => request<HealthResponse>('/health', undefined, token),

  getTopConversations: (limit = 20) =>
    request<Conversation[]>(`/conversations/top?limit=${encodeURIComponent(limit)}`),

  clearConversations: () =>
    request<{ ok: boolean; deleted: number }>('/conversations', {
      method: 'DELETE',
    }),

  getConversationDetail: (platform: string, postId: string) =>
    request<ConversationDetail>(`/conversations/${encodeURIComponent(platform)}/${encodeURIComponent(postId)}`),

  getIdeas: () => request<IdeasResponse>('/ideas/today'),

  getBrandProfile: () => request<BrandProfile>('/brand/profile'),

  updateBrandProfile: (payload: BrandProfilePayload) =>
    request<{ ok: boolean }>('/brand/profile', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getGrowthSettings: (profileId?: number) => {
    const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return request<GrowthSettings>(`/growth/settings${query}`);
  },

  updateGrowthSettings: (payload: GrowthSettings, profileId?: number) => {
    const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : '';
    return request<GrowthSettings>(`/growth/settings${query}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getGrowthProfiles: (includeInactive = false) => {
    const query = includeInactive ? '?include_inactive=true' : '';
    return request<GrowthProfile[]>(`/growth/profiles${query}`);
  },

  createGrowthProfile: (payload: GrowthProfilePayload) =>
    request<GrowthProfile>('/growth/profiles', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateGrowthProfile: (profileId: number, payload: GrowthProfileUpdatePayload) =>
    request<GrowthProfile>(`/growth/profiles/${profileId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  setDefaultGrowthProfile: (profileId: number) =>
    request<GrowthProfile>(`/growth/profiles/${profileId}/default`, {
      method: 'POST',
    }),

  deleteGrowthProfile: (profileId: number) =>
    request<GrowthProfile>(`/growth/profiles/${profileId}`, {
      method: 'DELETE',
    }),

  getAlerts: (limit = 25) => request<NotificationItem[]>(`/alerts/recent?limit=${encodeURIComponent(limit)}`),

  getStreamRules: () => request<StreamRule[]>('/stream/rules'),

  addStreamRule: (value: string) =>
    request<{ ok: boolean }>('/stream/rules', {
      method: 'POST',
      body: JSON.stringify({ value }),
    }),

  deleteStreamRule: (id: number) =>
    request<{ ok: boolean }>(`/stream/rules/${id}`, { method: 'DELETE' }),

  getSchedulerConfigs: () => request<SchedulerConfigPayload[]>('/scheduler/jobs'),

  runSchedulerJob: (config_id: number) =>
    request<{ ok: boolean }>('/scheduler/run', {
      method: 'POST',
      body: JSON.stringify({ config_id }),
    }),

  toggleSchedulerJob: (config_id: number, action: 'pause' | 'resume') =>
    request<{ ok: boolean }>('/scheduler/toggle', {
      method: 'POST',
      body: JSON.stringify({ config_id, action }),
    }),

  createSchedulerConfig: (payload: Partial<SchedulerConfigPayload>) =>
    request<SchedulerConfigPayload>('/scheduler/configs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSchedulerConfig: (config_id: number, payload: Partial<SchedulerConfigPayload>) =>
    request<SchedulerConfigPayload>(`/scheduler/configs/${config_id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deleteSchedulerConfig: (config_id: number) =>
    request<{ ok: boolean }>(`/scheduler/configs/${config_id}`, {
      method: 'DELETE',
    }),

  getWatchlistAnalytics: (days = 14) =>
    request<WatchlistAnalytics>(`/analytics/watchlist?days=${encodeURIComponent(days)}`),
};

export type ApiClient = typeof api;
