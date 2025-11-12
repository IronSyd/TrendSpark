import { useState } from 'react';

interface ErrorNoticeProps {
  message: string;
  onRetry?: () => Promise<unknown> | unknown;
  compact?: boolean;
}

export function ErrorNotice({ message, onRetry, compact = false }: ErrorNoticeProps) {
  const [pending, setPending] = useState(false);

  async function handleRetry() {
    if (!onRetry || pending) {
      return;
    }
    try {
      setPending(true);
      await onRetry();
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      role="alert"
      style={{
        background: 'rgba(248,113,113,0.12)',
        border: '1px solid rgba(248,113,113,0.38)',
        borderRadius: '0.9rem',
        padding: compact ? '0.6rem 0.85rem' : '0.85rem 1.15rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
      }}
    >
      <span style={{ color: '#fecdd3', fontSize: '0.9rem', lineHeight: 1.6 }}>{message}</span>
      {onRetry && (
        <button
          type="button"
          className="button subtle"
          onClick={handleRetry}
          disabled={pending}
          style={{ whiteSpace: 'nowrap' }}
        >
          {pending ? 'Retrying...' : 'Retry'}
        </button>
      )}
    </div>
  );
}
