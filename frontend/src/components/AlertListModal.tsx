import type { NotificationItem } from '../types';

interface AlertListModalProps {
  alerts: NotificationItem[];
  onClose: () => void;
}

export function AlertListModal({ alerts, onClose }: AlertListModalProps) {
  if (!alerts.length) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal" style={{ maxWidth: '720px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <h2 style={{ margin: 0 }}>Recent alerts</h2>
          <button className="button" type="button" onClick={onClose} style={{ background: 'rgba(148,163,184,0.18)' }}>
            Close
          </button>
        </div>

        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.85rem', paddingRight: '0.4rem' }}>
          {alerts.map((alert) => (
            <article
              key={alert.id}
              style={{
                background: 'rgba(15,23,42,0.82)',
                border: '1px solid rgba(148,163,184,0.1)',
                borderRadius: 'var(--radius-md)',
                padding: '0.9rem 1rem',
              }}
            >
              <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.75rem' }}>
                <strong style={{ fontSize: '0.85rem', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  {alert.category || alert.channel}
                </strong>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {new Date(alert.created_at).toLocaleString()}
                </span>
              </header>
              <p style={{ marginTop: '0.55rem', whiteSpace: 'pre-line', lineHeight: 1.5 }}>{alert.message}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
