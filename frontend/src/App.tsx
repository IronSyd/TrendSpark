import { Navigate, Route, Routes } from 'react-router-dom';
import { Suspense, lazy, type ReactNode } from 'react';

import AppLayout from './layouts/AppLayout';
import { FeedbackProvider } from './components/FeedbackProvider';
import { AuthProvider, useAuth } from './components/AuthProvider';
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Ideas = lazy(() => import('./pages/Ideas'));
const BrandVoice = lazy(() => import('./pages/BrandVoice'));
const Automation = lazy(() => import('./pages/Automation'));
const Login = lazy(() => import('./pages/Login'));

function SplashScreen({ message }: { message: string }) {
  return (
    <div className="auth-shell">
      <div className="auth-card" style={{ gap: '0.75rem', textAlign: 'center' }}>
        <div className="auth-glow" />
        <p style={{ margin: 0, fontSize: '1rem', color: 'rgba(226,232,240,0.8)' }}>{message}</p>
      </div>
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isBootstrapping } = useAuth();
  if (isBootstrapping) {
    return <SplashScreen message="Checking access..." />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Suspense fallback={<SplashScreen message="Loading workspace..." />}>
      <Routes>
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="automation" element={<Automation />} />
          <Route path="ideas" element={<Ideas />} />
          <Route path="brand-voice" element={<BrandVoice />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
        <Route path="/login" element={<Login />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <FeedbackProvider>
        <AppRoutes />
      </FeedbackProvider>
    </AuthProvider>
  );
}
