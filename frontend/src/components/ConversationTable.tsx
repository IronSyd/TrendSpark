import { useMemo, useState } from 'react';

import type { Conversation } from '../types';
import { SkeletonList } from './skeletons';
import { PaginationControls } from './PaginationControls';

interface ConversationTableProps {
  data?: Conversation[];
  isLoading?: boolean;
  isFetching?: boolean;
  onRefresh?: () => void;
  lastUpdated?: Date | null;
  onSelect?: (item: Conversation) => void;
  pageSize?: number;
  enablePagination?: boolean;
  onViewAll?: () => void;
}

function platformBadge(platform: string) {
  if (platform === 'x') return 'platform-badge x';
  if (platform === 'reddit') return 'platform-badge reddit';
  return 'platform-badge';
}

function platformLabel(platform: string) {
  if (platform === 'x') return 'X';
  if (platform === 'reddit') return 'Reddit';
  return platform;
}

export function ConversationTable({
  data,
  isLoading,
  isFetching,
  onRefresh,
  lastUpdated,
  onSelect,
  pageSize = 24,
  enablePagination = false,
  onViewAll,
}: ConversationTableProps) {
  const conversations = data ?? [];
  const [page, setPage] = useState(1);
  const loading = Boolean(isLoading || isFetching);
  const effectivePageSize = enablePagination ? pageSize : conversations.length || 1;

  const visible = useMemo(() => {
    if (enablePagination) {
      const start = (page - 1) * effectivePageSize;
      return conversations.slice(start, start + effectivePageSize);
    }
    return conversations;
  }, [conversations, enablePagination, page, effectivePageSize]);

  const showEmptyState = !loading && visible.length === 0;
  const showPagination = enablePagination && conversations.length > effectivePageSize;

  return (
    <section className="section">
      <header className="page-header" style={{ marginBottom: '1rem' }}>
        <div>
          <h2>Top Conversations</h2>
          <p>Ranked by virality and velocity. Auto-refreshes every 60 seconds.</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.4rem' }}>
          <button className="button" onClick={onRefresh} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh now'}
          </button>
          {lastUpdated && (
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {loading && visible.length === 0 ? (
        <SkeletonList rows={4} rowHeight="160px" gap="1rem" />
      ) : showEmptyState ? (
        <div className="empty-state">No conversations yet. Configure keywords and ingestion will populate soon.</div>
      ) : (
        <div className="conversation-grid">
          {visible.map((conversation) => (
            <article
              key={`${conversation.platform}-${conversation.post_id}`}
              className="conversation-card"
              onClick={() => onSelect?.(conversation)}
            >
              <header>
                <span className={platformBadge(conversation.platform)}>{platformLabel(conversation.platform)}</span>
                <div className="conversation-metrics">
                  <span className="metric-chip">Virality {conversation.virality.toFixed(2)}</span>
                  <span className="metric-chip">Velocity {conversation.velocity.toFixed(2)}</span>
                  {conversation.trending && (
                    <span className="metric-chip" style={{ background: 'rgba(52, 211, 153, 0.16)', color: '#34d399' }}>
                      Trending
                    </span>
                  )}
                </div>
              </header>

              <div>
                <p className="title">{conversation.text.split('\n')[0]}</p>
                {conversation.text.split('\n').slice(1).map((line, idx) => (
                  <p key={idx}>{line}</p>
                ))}
              </div>

              <div className="conversation-metrics">
                {conversation.url && (
                  <a
                    href={conversation.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(event) => event.stopPropagation()}
                    className="metric-chip"
                  >
                    Open thread
                  </a>
                )}
                <span className="metric-chip">ID {conversation.post_id}</span>
              </div>

              {conversation.replies?.length ? (
                <div className="suggestions">
                  {conversation.replies.slice(0, 2).map((reply, idx) => (
                    <span key={idx} className="suggestion-pill">
                      {reply.tone && <small>{reply.tone}</small>}
                      <span>{reply.reply}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No suggestions yet</span>
              )}
            </article>
          ))}
        </div>
      )}

      {onViewAll && conversations.length > 0 && !enablePagination && (
        <div style={{ marginTop: '1.25rem', textAlign: 'center' }}>
          <button className="button subtle" type="button" onClick={onViewAll}>
            View full trending board
          </button>
        </div>
      )}

      {showPagination && (
        <PaginationControls
          page={page}
          pageSize={effectivePageSize}
          total={conversations.length}
          onPageChange={(next) => setPage(next)}
        />
      )}
    </section>
  );
}
