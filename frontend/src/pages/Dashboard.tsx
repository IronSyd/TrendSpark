import { useMemo, useState } from 'react';
import { useFeedback } from '../components/FeedbackProvider';

import { useAlerts, useTopConversations, useClearConversations } from '../hooks/useApi';
import { ConversationTable } from '../components/ConversationTable';
import { ConversationListModal } from '../components/ConversationListModal';
import { AlertListModal } from '../components/AlertListModal';
import { TrendModal } from '../components/TrendModal';
import { ErrorNotice } from '../components/ErrorNotice';
import type { Conversation, NotificationItem } from '../types';
import { SkeletonCard, SkeletonList } from '../components/skeletons';

export default function Dashboard() {
  const { notifySuccess, notifyError } = useFeedback();
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [activePanel, setActivePanel] = useState<'trending' | 'alerts'>('trending');
  const [showAllTrends, setShowAllTrends] = useState(false);
  const [showAllAlerts, setShowAllAlerts] = useState(false);

  const conversationsQuery = useTopConversations(20);
  const clearConversations = useClearConversations();
  const alertsQuery = useAlerts(40, { enabled: activePanel === 'alerts' || showAllAlerts });
  const conversations = conversationsQuery.data;
  const alerts = alertsQuery.data;

  const isLoadingConversations = conversationsQuery.isLoading;
  const isFetchingConversations = conversationsQuery.isFetching;
  const lastUpdated = conversationsQuery.dataUpdatedAt ? new Date(conversationsQuery.dataUpdatedAt) : null;
  const isAlertsLoading = alertsQuery.isLoading;
  const isAlertsFetching = alertsQuery.isFetching;
  const alertsError = alertsQuery.isError;
  const conversationsError = conversationsQuery.isError;

  const metrics = useMemo(() => {
    const list = conversations;
    if (!list.length) {
      return {
        trendingCount: 0,
        avgVirality: 0,
        avgVelocity: 0,
        platforms: {} as Record<string, number>,
      };
    }

    const trendingCount = list.filter((item) => item.trending).length;
    const avgVirality = list.reduce((sum, item) => sum + item.virality, 0) / list.length;
    const avgVelocity = list.reduce((sum, item) => sum + item.velocity, 0) / list.length;
    const platformCounts = list.reduce<Record<string, number>>((acc, item) => {
      acc[item.platform] = (acc[item.platform] || 0) + 1;
      return acc;
    }, {});

    return {
      trendingCount,
      avgVirality,
      avgVelocity,
      platforms: platformCounts,
    };
  }, [conversations]);

  const alertsList = alerts;

  const isMetricsLoading = (isLoadingConversations || isFetchingConversations) && conversations.length === 0;

  async function handleClearConversations() {
    if (clearConversations.isPending) {
      return;
    }
    const confirmed =
      typeof window !== 'undefined'
        ? window.confirm(
            'This will clear the cached top conversations and force the next ingest cycle to repopulate the dashboard. Continue?',
          )
        : true;
    if (!confirmed) {
      return;
    }
    try {
      await clearConversations.mutateAsync();
      await conversationsQuery.refetch();
      notifySuccess('Cleared stored conversations. Next ingest will repopulate.');
    } catch (err) {
      notifyError(err instanceof Error ? err.message : 'Failed to clear conversations.');
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.6rem' }}>
      <section className="section">
        <header className="page-header">
          <div>
            <h2 style={{ margin: 0 }}>Engagement Pulse</h2>
            <p style={{ margin: '0.35rem 0 0' }}>Snapshot of how your niche is moving right now.</p>
          </div>
        </header>
        <div className="kpi-grid" style={{ marginTop: '1.4rem' }}>
          {isMetricsLoading ? (
            Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="kpi-card">
                <SkeletonCard lines={3} />
              </div>
            ))
          ) : (
            <>
              <div className="kpi-card">
                <h3>Trending right now</h3>
                <strong>{metrics.trendingCount}</strong>
              </div>
              <div className="kpi-card">
                <h3>Average virality</h3>
                <strong>{metrics.avgVirality.toFixed(2)}</strong>
              </div>
              <div className="kpi-card">
                <h3>Average velocity</h3>
                <strong>{metrics.avgVelocity.toFixed(2)}</strong>
              </div>
              <div className="kpi-card">
                <h3>Platforms monitored</h3>
                <strong>{Object.keys(metrics.platforms).length}</strong>
                <p style={{ margin: '0.45rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {Object.entries(metrics.platforms).map(([platform, count]) => `${platform}: ${count}`).join(' | ') ||
                    'No data yet'}
                </p>
              </div>
            </>
          )}
        </div>
      </section>

      <section className="section">
        <div
          role="tablist"
          aria-label="Dashboard focus panels"
          style={{
            display: 'flex',
            gap: '0.75rem',
            marginTop: '1.2rem',
            flexWrap: 'wrap',
          }}
        >
          {tabOptions.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={activePanel === tab.id}
              className={`chip-tab${activePanel === tab.id ? ' active' : ''}`}
              onClick={() => setActivePanel(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ marginTop: '1.4rem' }}>
          {activePanel === 'trending' && (
          <>
            {conversationsError && (
              <ErrorNotice
                message={
                  conversations.length
                    ? 'Unable to refresh top conversations. Showing the last data we have.'
                    : 'Unable to load top conversations right now.'
                }
                onRetry={() => conversationsQuery.refetch()}
              />
            )}
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '0.75rem',
                margin: '0.5rem 0 0.75rem',
                flexWrap: 'wrap',
              }}
            >
              <button
                className="button subtle"
                type="button"
                onClick={handleClearConversations}
                disabled={clearConversations.isPending}
              >
                {clearConversations.isPending ? 'Clearing…' : 'Clear conversations'}
              </button>
            </div>
            <ConversationTable
              data={conversations}
              isLoading={isLoadingConversations}
              isFetching={isFetchingConversations}
              onRefresh={async () => {
                await conversationsQuery.refetch();
                notifySuccess('Top conversations refreshed.');
              }}
              lastUpdated={lastUpdated}
              onSelect={(item) => setSelected(item)}
              pageSize={6}
              enablePagination
              onViewAll={() => setShowAllTrends(true)}
            />
          </>
          )}

          {activePanel === 'alerts' && (
            <>
              {alertsError && (
                <ErrorNotice
                  message={
                    alertsList.length
                      ? 'Unable to refresh alerts. Showing the last notifications we fetched.'
                      : 'Unable to load alerts from Telegram right now.'
                  }
                  onRetry={() => alertsQuery.refetch()}
                />
              )}
              <AlertsPreview
                alerts={alertsList.slice(0, 5)}
                isLoading={isAlertsLoading || isAlertsFetching}
                total={alertsList.length}
                onViewAll={() => setShowAllAlerts(true)}
              />
            </>
          )}
        </div>
      </section>

      <TrendModal conversation={selected} onClose={() => setSelected(null)} />

      {showAllTrends && conversations && conversations.length > 0 && (
        <ConversationListModal
          conversations={conversations}
          onClose={() => setShowAllTrends(false)}
          onSelect={(item) => {
            setSelected(item);
            setShowAllTrends(false);
          }}
          lastUpdated={lastUpdated}
        />
      )}

      {showAllAlerts && alertsList.length > 0 && (
        <AlertListModal alerts={alertsList} onClose={() => setShowAllAlerts(false)} />
      )}
    </div>
  );
}

const tabOptions: { id: 'trending' | 'alerts'; label: string }[] = [
  { id: 'trending', label: 'Trending' },
  { id: 'alerts', label: 'Alerts' },
];

function AlertsPreview({
  alerts,
  isLoading,
  total,
  onViewAll,
}: {
  alerts: NotificationItem[];
  isLoading: boolean;
  total: number;
  onViewAll: () => void;
}) {
  if (isLoading) {
    return <SkeletonList rows={3} rowHeight="120px" gap="1rem" />;
  }

  if (!alerts.length) {
    return <div className="empty-state">No alerts yet. Once posts trend, they will pop up here.</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {alerts.map((alert) => (
        <article
          key={alert.id}
          style={{
            padding: '0.9rem 1rem',
            background: 'rgba(15,23,42,0.82)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(148, 163, 184, 0.1)',
          }}
        >
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '1rem' }}>
            <strong style={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.75rem' }}>
              {alert.category || alert.channel}
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {new Date(alert.created_at).toLocaleTimeString()}
            </span>
          </header>
          <p style={{ marginTop: '0.5rem', lineHeight: 1.5, whiteSpace: 'pre-line' }}>{alert.message}</p>
        </article>
      ))}

      {total > alerts.length && (
        <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
          <button className="button subtle" type="button" onClick={onViewAll}>
            View all alerts
          </button>
        </div>
      )}
    </div>
  );
}

