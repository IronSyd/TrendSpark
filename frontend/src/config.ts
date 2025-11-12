const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const API_BASE_URL = rawBaseUrl.replace(/\/$/, '');

export const API_TOKEN = (import.meta.env.VITE_API_TOKEN || '').trim();

const defaultPollInterval = 30_000;
const parsedPollInterval = Number.parseInt(
  import.meta.env.VITE_API_POLL_INTERVAL || `${defaultPollInterval}`,
  10,
);

export const API_POLL_INTERVAL =
  Number.isFinite(parsedPollInterval) && parsedPollInterval > 0
    ? parsedPollInterval
    : defaultPollInterval;

if (!Number.isFinite(parsedPollInterval) || parsedPollInterval <= 0) {
  console.warn('Invalid VITE_API_POLL_INTERVAL, falling back to 30000ms');
}

export const featureFlags = {
  enableNewCharts: import.meta.env.VITE_ENABLE_NEW_CHARTS === 'true',
  enableExperimentalSidebar: import.meta.env.VITE_ENABLE_EXPERIMENTAL_SIDEBAR === 'true',
};
