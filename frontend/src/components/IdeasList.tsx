import { SkeletonCard } from './skeletons';

interface IdeasListProps {
  ideas?: string[];
  isLoading?: boolean;
  isFetching?: boolean;
  onRefresh?: () => void;
}

export function IdeasList({ ideas, isLoading, isFetching, onRefresh }: IdeasListProps) {
  const items = ideas ?? [];
  const loading = Boolean(isLoading || isFetching);
  const showSkeletons = loading && items.length === 0;

  return (
    <div className="section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Today's Tweet Ideas</h2>
        <button className="button" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {showSkeletons ? (
        <ol style={{ display: 'grid', gap: '1rem', paddingLeft: '1rem' }}>
          {Array.from({ length: 5 }).map((_, index) => (
            <li
              key={`idea-skeleton-${index}`}
              style={{
                listStyle: 'decimal',
                background: 'rgba(30,41,59,0.65)',
                borderRadius: '0.9rem',
                padding: '1rem 1.25rem',
                border: '1px solid rgba(148,163,184,0.08)',
              }}
            >
              <SkeletonCard lines={2} />
            </li>
          ))}
        </ol>
      ) : items.length === 0 ? (
        <div className="empty-state">No ideas have been generated yet today.</div>
      ) : (
        <ol style={{ display: 'grid', gap: '1rem', paddingLeft: '1rem' }}>
          {items.map((idea, index) => (
            <li
              key={index}
              style={{
                background: 'rgba(30,41,59,0.75)',
                borderRadius: '0.9rem',
                padding: '1rem 1.25rem',
                border: '1px solid rgba(148,163,184,0.08)',
              }}
            >
              <span
                style={{
                  fontSize: '0.8rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'rgba(148,163,184,0.75)',
                }}
              >
                Idea {index + 1}
              </span>
              <p style={{ marginTop: '0.5rem', fontSize: '1rem', lineHeight: 1.5 }}>{idea}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

