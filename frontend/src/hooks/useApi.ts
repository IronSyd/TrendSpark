import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '../api/client';
import { API_POLL_INTERVAL } from '../config';
import type {
  BrandProfile,
  BrandProfilePayload,
  Conversation,
  GrowthSettings,
  GrowthProfile,
  GrowthProfilePayload,
  GrowthProfileUpdatePayload,
  IdeasResponse,
  NotificationItem,
  SchedulerConfigPayload,
  StreamRule,
  WatchlistAnalytics,
} from '../types';

type QueryResultWithData<T> = Omit<UseQueryResult<T, unknown>, 'data'> & { data: T };

function withFallback<T>(query: UseQueryResult<T, unknown>, fallback: T): QueryResultWithData<T> {
  const data = query.data ?? fallback;
  return {
    ...query,
    data,
  } as QueryResultWithData<T>;
}

export function useHealth(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: API_POLL_INTERVAL,
    enabled: options?.enabled ?? true,
  });
}

export function useTopConversations(limit = 20) {
  const query = useQuery<Conversation[]>({
    queryKey: ['conversations', limit],
    queryFn: () => api.getTopConversations(limit),
    refetchInterval: API_POLL_INTERVAL,
  });
  return withFallback(query, []);
}

export function useClearConversations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.clearConversations,
    onSuccess: () => {
      queryClient.invalidateQueries({
        predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === 'conversations',
      });
    },
  });
}

export function useConversationDetail(platform?: string, postId?: string, enabled = false) {
  return useQuery({
    queryKey: ['conversation-detail', platform, postId],
    queryFn: () => api.getConversationDetail(platform!, postId!),
    enabled: enabled && !!platform && !!postId,
  });
}

export function useIdeas() {
  const query = useQuery<IdeasResponse>({
    queryKey: ['ideas'],
    queryFn: api.getIdeas,
    refetchInterval: API_POLL_INTERVAL,
  });
  return withFallback(query, []);
}

export function useBrandProfile() {
  return useQuery<BrandProfile>({
    queryKey: ['brand-profile'],
    queryFn: api.getBrandProfile,
  });
}

export function useUpdateBrandProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BrandProfilePayload) => api.updateBrandProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brand-profile'] });
    },
  });
}

export function useAlerts(limit = 25, options?: { enabled?: boolean }) {
  const query = useQuery<NotificationItem[]>({
    queryKey: ['alerts', limit],
    queryFn: () => api.getAlerts(limit),
    refetchInterval: API_POLL_INTERVAL,
    enabled: options?.enabled ?? true,
  });
  return withFallback(query, []);
}

export function useGrowthSettings() {
  return useQuery<GrowthSettings>({
    queryKey: ['growth-settings'],
    queryFn: () => api.getGrowthSettings(),
  });
}

export function useUpdateGrowthSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GrowthSettings) => api.updateGrowthSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['growth-settings'], data);
      queryClient.invalidateQueries({ queryKey: ['health'] });
      queryClient.invalidateQueries({ queryKey: ['stream-rules'] });
    },
  });
}

export function useGrowthProfiles(includeInactive = false) {
  const query = useQuery<GrowthProfile[]>({
    queryKey: ['growth-profiles', includeInactive],
    queryFn: () => api.getGrowthProfiles(includeInactive),
    refetchInterval: API_POLL_INTERVAL,
  });
  return withFallback(query, []);
}

export function useCreateGrowthProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GrowthProfilePayload) => api.createGrowthProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['growth-settings'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useUpdateGrowthProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      profileId,
      payload,
    }: {
      profileId: number;
      payload: GrowthProfileUpdatePayload;
    }) => api.updateGrowthProfile(profileId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['growth-settings'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useDeleteGrowthProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: number) => api.deleteGrowthProfile(profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useSetDefaultGrowthProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: number) => api.setDefaultGrowthProfile(profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['growth-settings'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useStreamRules(options?: { enabled?: boolean }) {
  const query = useQuery<StreamRule[]>({
    queryKey: ['stream-rules'],
    queryFn: api.getStreamRules,
    enabled: options?.enabled ?? true,
  });
  return withFallback(query, []);
}

export function useAddStreamRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.addStreamRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stream-rules'] });
    },
  });
}

export function useDeleteStreamRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteStreamRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stream-rules'] });
    },
  });
}

export function useSchedulerConfigs(options?: { enabled?: boolean }) {
  const query = useQuery<SchedulerConfigPayload[]>({
    queryKey: ['scheduler-configs'],
    queryFn: api.getSchedulerConfigs,
    refetchInterval: API_POLL_INTERVAL,
    enabled: options?.enabled ?? true,
  });
  return withFallback(query, []);
}

export function useRunSchedulerJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.runSchedulerJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useToggleSchedulerJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ config_id, action }: { config_id: number; action: 'pause' | 'resume' }) =>
      api.toggleSchedulerJob(config_id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useCreateSchedulerConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createSchedulerConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useUpdateSchedulerConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      config_id,
      payload,
    }: {
      config_id: number;
      payload: Partial<SchedulerConfigPayload>;
    }) => api.updateSchedulerConfig(config_id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useDeleteSchedulerConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteSchedulerConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-configs'] });
    },
  });
}

export function useWatchlistAnalytics(days = 14, options?: { enabled?: boolean }) {
  const query = useQuery<WatchlistAnalytics>({
    queryKey: ['watchlist-analytics', days],
    queryFn: () => api.getWatchlistAnalytics(days),
    refetchInterval: API_POLL_INTERVAL,
    enabled: options?.enabled ?? true,
  });
  return withFallback(query, { entries: [], days });
}
