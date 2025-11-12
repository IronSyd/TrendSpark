import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../../components/AuthProvider', () => ({
  useAuth: () => ({
    logout: vi.fn(),
    isAuthenticated: true,
    isBootstrapping: false,
    isAuthenticating: false,
    login: vi.fn(),
  }),
}));

import AppLayout from '../AppLayout';

describe('AppLayout', () => {
  function renderLayout(initialPath = '/') {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<div>Home</div>} />
            <Route path="automation" element={<div>Automation</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
  }

  it('renders navigation links and brand text', () => {
    renderLayout();

    expect(screen.getByRole('heading', { name: /trend/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /automation/i })).toBeInTheDocument();
  });

  it('highlights the active link when navigating', async () => {
    const user = userEvent.setup();
    renderLayout();

    const automationLink = screen.getAllByRole('link', { name: /automation/i })[0];
    await user.click(automationLink);

    expect(automationLink).toHaveClass('active');
    expect(screen.getAllByText('Automation').length).toBeGreaterThan(0);
  });
});
