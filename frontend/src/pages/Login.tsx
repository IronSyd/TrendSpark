import { type FormEvent, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';

export default function Login() {
  const { login, isAuthenticated, isAuthenticating, isBootstrapping } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isBootstrapping) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-glow" />
          <p className="auth-subtitle">Preparing your workspace…</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await login(code);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to verify access code.');
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-glow" />
        <div>
          <p className="auth-kicker">Trend ⚡ Intelligence Hub</p>
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-subtitle">Enter the shared access key to unlock the dashboard.</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <input
            id="access-code"
            type="password"
            className="auth-input"
            placeholder="Enter access code"
            aria-label="Access code"
            autoComplete="current-password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            disabled={isAuthenticating}
          />
          {error && <p className="auth-error">{error}</p>}
          <button className="auth-button" type="submit" disabled={isAuthenticating}>
            {isAuthenticating ? 'Verifying…' : 'Unlock workspace'}
          </button>
        </form>
        <p className="auth-hint">Need access? Ping your workspace admin for the latest code.</p>
      </div>
    </div>
  );
}
