const TOKEN_KEY = 'trend-auth-token';

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
