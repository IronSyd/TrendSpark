import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';

const navLinks = [
  { to: '/', label: 'Dashboard', icon: '\u{1F3E0}' },
  { to: '/automation', label: 'Automation', icon: '\u2699\uFE0F' },
  { to: '/ideas', label: 'Ideas', icon: '\u{1F4A1}' },
  { to: '/brand-voice', label: 'Brand Voice', icon: '\u{1F399}\uFE0F' },
];

export default function AppLayout() {
  const { logout } = useAuth();
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <button type="button" className="logout-button logout-floating" onClick={logout}>
        Log out
      </button>
      <div className="app-shell">
        <aside className="sidebar" aria-labelledby="app-brand">
          <div className="brand">
            <h1 id="app-brand">{'Trend\u26A1'}</h1>
            <p>Ignite your growth</p>
          </div>

          <nav className="nav-links" aria-label="Primary navigation">
            {navLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                end={link.to === '/'}
              >
                <span className="nav-icon" aria-hidden="true">
                  {link.icon}
                </span>
                <span>{link.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <main id="main-content" className="content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </>
  );
}
