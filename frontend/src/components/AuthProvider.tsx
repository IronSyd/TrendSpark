import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import { clearStoredToken, getStoredToken, setStoredToken } from '../auth';

type AuthContextValue = {
  token: string | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  isAuthenticating: boolean;
  login: (accessCode: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<'bootstrapping' | 'idle' | 'authenticating'>('bootstrapping');

  useEffect(() => {
    const stored = getStoredToken();
    if (stored) {
      setToken(stored);
    }
    setStatus('idle');
  }, []);

  const login = useCallback(async (accessCode: string) => {
    const trimmed = accessCode.trim();
    if (!trimmed) {
      throw new Error('Access code is required.');
    }
    setStatus('authenticating');
    try {
      await api.validateToken(trimmed);
      setStoredToken(trimmed);
      setToken(trimmed);
    } catch (error) {
      throw error instanceof Error ? error : new Error('Unable to verify access code.');
    } finally {
      setStatus('idle');
    }
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      isBootstrapping: status === 'bootstrapping',
      isAuthenticating: status === 'authenticating',
      login,
      logout,
    }),
    [token, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
