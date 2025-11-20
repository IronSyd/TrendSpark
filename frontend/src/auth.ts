function getEnvTokenKey(): string | undefined {
  if (
    typeof import.meta !== 'undefined' &&
    (import.meta as any).env?.VITE_AUTH_TOKEN_KEY
  ) {
    return String((import.meta as any).env.VITE_AUTH_TOKEN_KEY);
  }
  return undefined;
}

const TOKEN_KEY =
  getEnvTokenKey() ||
  (typeof window !== 'undefined'
    ? `${window.location.hostname}-auth-token`
    : 'auth-token');

export function getStoredToken(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return localStorage.getItem(TOKEN_KEY) ?? '';
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') {
    return;
  }
  localStorage.removeItem(TOKEN_KEY);
}
