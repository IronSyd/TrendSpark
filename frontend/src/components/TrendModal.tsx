import { useEffect, useMemo, useState } from 'react';

import { useConversationDetail } from '../hooks/useApi';
import type { Conversation } from '../types';

interface TrendModalProps {
  conversation: Conversation | null;
  onClose: () => void;
}

export function TrendModal({ conversation, onClose }: TrendModalProps) {
  const enabled = !!conversation;
  const { data, isLoading } = useConversationDetail(conversation?.platform, conversation?.post_id, enabled);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setCopiedIndex(null);
    }
  }, [enabled]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }
    if (enabled) {
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }
  }, [enabled, onClose]);

  const replies = useMemo(() => data?.replies ?? conversation?.replies ?? [], [data, conversation]);

  if (!enabled) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Conversation insight</h2>
          <button className="button" style={{ background: 'rgba(148,163,184,0.2)', color: '#e2e8f0' }} onClick={onClose}>
            Close
          </button>
        </div>

        {isLoading && <p style={{ color: 'rgba(148,163,184,0.8)' }}>Loading full context...</p>}

        {data && (
          <div style={{ marginTop: '1rem', display: 'grid', gap: '1.25rem' }}>
            <div>
              <span className="badge platform-x" style={{ marginRight: '0.5rem' }}>
                {data.platform.toUpperCase()}
              </span>
              {data.trending && <span className="badge trending">Trending</span>}
            </div>
            <div>
              <h3 style={{ margin: '0 0 0.5rem', color: '#bae6fd' }}>{data.author || 'Unknown author'}</h3>
              <p style={{ margin: 0, whiteSpace: 'pre-line', lineHeight: 1.6 }}>{data.text}</p>
              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem', color: 'rgba(148,163,184,0.75)', marginTop: '0.75rem' }}>
                <span>Posted {new Date(data.created_at).toLocaleString()}</span>
                {data.url && (
                  <a href={data.url} target="_blank" rel="noreferrer">
                    View on platform ↗
                  </a>
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: '0.75rem' }}>
              <MetricCard label="Virality" value={data.virality.toFixed(2)} />
              <MetricCard label="Velocity" value={data.velocity.toFixed(2)} />
              <MetricCard label="Likes" value={String(data.metrics.likes)} />
              <MetricCard label="Replies" value={String(data.metrics.replies)} />
              <MetricCard label="Reposts" value={String(data.metrics.reposts)} />
              <MetricCard label="Views" value={String(data.metrics.views)} />
            </div>

            <div>
              <h3 style={{ margin: '0 0 0.75rem', color: '#bae6fd' }}>Suggested replies</h3>
              {replies.length === 0 ? (
                <p style={{ color: 'rgba(148,163,184,0.75)' }}>No suggestions generated yet.</p>
              ) : (
                <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  {replies.map((reply, index) => (
                    <li
                      key={index}
                      style={{
                        background: 'rgba(30,41,59,0.65)',
                        borderRadius: '0.9rem',
                        border: '1px solid rgba(148,163,184,0.08)',
                        padding: '0.85rem 1rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.08em' }}>
                          {reply.tone || 'suggestion'}
                        </strong>
                        <button
                          className="button"
                          type="button"
                          style={{ padding: '0.4rem 0.8rem' }}
                          onClick={async () => {
                            await navigator.clipboard.writeText(reply.reply);
                            setCopiedIndex(index);
                            setTimeout(() => setCopiedIndex(null), 1500);
                          }}
                        >
                          {copiedIndex === index ? 'Copied!' : 'Copy reply'}
                        </button>
                      </div>
                      <p style={{ marginTop: '0.5rem', lineHeight: 1.5 }}>{reply.reply}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(148,163,184,0.75)' }}>
        {label}
      </span>
      <strong style={{ fontSize: '1.3rem', marginTop: '0.3rem', display: 'block' }}>{value}</strong>
    </div>
  );
}
