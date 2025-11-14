import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { api } from '../api/client';

type PrefetchTask = () => void;

function scheduleTask(task: PrefetchTask, delayMs: number, cancelToken: { cancelled: boolean }, timers: number[]) {
  if (typeof window === 'undefined') {
    return;
  }

  const id = window.setTimeout(() => {
    if (!cancelToken.cancelled) {
      task();
    }
  }, delayMs);

  timers.push(id);
}

export function useBackgroundPrefetch(enabled: boolean) {
  const queryClient = useQueryClient();
  const startedRef = useRef(false);

  useEffect(() => {
    if (!enabled || startedRef.current) {
      return;
    }
    startedRef.current = true;

    const cancelToken = { cancelled: false };
    const timers: number[] = [];

    const tasks: PrefetchTask[] = [
      () => queryClient.prefetchQuery({ queryKey: ['ideas'], queryFn: api.getIdeas }),
      () => queryClient.prefetchQuery({ queryKey: ['brand-profile'], queryFn: api.getBrandProfile }),
      () =>
        queryClient.prefetchQuery({
          queryKey: ['growth-settings'],
          queryFn: () => api.getGrowthSettings(),
        }),
      () =>
        queryClient.prefetchQuery({
          queryKey: ['growth-profiles', false],
          queryFn: () => api.getGrowthProfiles(false),
        }),
      () =>
        queryClient.prefetchQuery({
          queryKey: ['stream-rules'],
          queryFn: api.getStreamRules,
        }),
      () =>
        queryClient.prefetchQuery({
          queryKey: ['scheduler-configs'],
          queryFn: api.getSchedulerConfigs,
        }),
      () =>
        queryClient.prefetchQuery({
          queryKey: ['watchlist-analytics', 14],
          queryFn: () => api.getWatchlistAnalytics(14),
        }),
    ];

    tasks.forEach((task, index) => {
      scheduleTask(task, 1500 * (index + 1), cancelToken, timers);
    });

    return () => {
      cancelToken.cancelled = true;
      if (typeof window !== 'undefined') {
        timers.forEach((timerId) => window.clearTimeout(timerId));
      }
    };
  }, [enabled, queryClient]);
}

