import { useEffect, useState, useRef, useId } from 'react';
import {
  useAddStreamRule,
  useDeleteStreamRule,
  useSchedulerConfigs,
  useStreamRules,
  useRunSchedulerJob,
  useToggleSchedulerJob,
  useGrowthProfiles,
  useCreateGrowthProfile,
  useUpdateGrowthProfile,
  useDeleteGrowthProfile,
  useSetDefaultGrowthProfile,
  useWatchlistAnalytics,
  useHealth,
  useCreateSchedulerConfig,
  useUpdateSchedulerConfig,
  useDeleteSchedulerConfig,
} from '../hooks/useApi';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { useFeedback } from '../components/FeedbackProvider';
import { SkeletonCard, SkeletonChart } from '../components/skeletons';
import { ErrorNotice } from '../components/ErrorNotice';
import type { SchedulerConfigPayload, GrowthProfileSummary } from '../types';

type StreamRulesQueryResult = ReturnType<typeof useStreamRules>;
type SchedulerConfigsQueryResult = ReturnType<typeof useSchedulerConfigs>;

type AutomationTab = 'targeting' | 'rules' | 'watchlist' | 'scheduler';

const automationTabs: { id: AutomationTab; label: string }[] = [
  { id: 'targeting', label: 'Targeting' },
  { id: 'rules', label: 'Stream Rules' },
  { id: 'watchlist', label: 'Watchlist' },
  { id: 'scheduler', label: 'Scheduler' },
];

const schedulerJobOptions = [
  { value: 'ingest_rank', label: 'Ingest + rank' },
  { value: 'gen_replies', label: 'Generate trending replies' },
  { value: 'daily_ideas', label: 'Daily ideas blast' },
];

const schedulerJobLabelMap = schedulerJobOptions.reduce<Record<string, string>>((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {});

export default function AutomationPage() {
  const [loadedTabs, setLoadedTabs] = useState<Record<AutomationTab, boolean>>({
    targeting: true,
    rules: false,
    watchlist: false,
    scheduler: true,
  });
  const streamRulesQuery = useStreamRules({ enabled: loadedTabs.rules });
  const schedulerConfigsQuery = useSchedulerConfigs({ enabled: loadedTabs.scheduler });
  const watchlistQuery = useWatchlistAnalytics(14, { enabled: loadedTabs.watchlist });
  const healthQuery = useHealth({ enabled: loadedTabs.targeting });
  const rules = loadedTabs.rules ? streamRulesQuery.data : [];
  const schedulerConfigs = loadedTabs.scheduler ? schedulerConfigsQuery.data : [];
  const watchlistRaw = watchlistQuery.data;
  const watchlist = loadedTabs.watchlist ? watchlistRaw : { ...watchlistRaw, entries: [] };
  const health = healthQuery.data;
  const [activeTab, setActiveTab] = useState<AutomationTab>('targeting');
  const sectionRefs = {
    targeting: useRef<HTMLDivElement>(null),
    rules: useRef<HTMLDivElement>(null),
    watchlist: useRef<HTMLDivElement>(null),
    scheduler: useRef<HTMLDivElement>(null),
  } as const;

  function markLoaded(tab: AutomationTab) {
    setLoadedTabs((prev) => (prev[tab] ? prev : { ...prev, [tab]: true }));
  }

  function activateTab(tab: AutomationTab) {
    markLoaded(tab);
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        const target = sectionRefs[tab].current;
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }
  }

  const activeJobs = schedulerConfigs.filter((job) => job.enabled).length;
  const pausedJobs = schedulerConfigs.filter((job) => !job.enabled).length;
  const ruleCount = rules.length;
  const watchlistCount = watchlist.entries.length;
  const watchlistPreview = watchlist.entries.slice(0, 3);
  const rulePreview = rules.slice(0, 3);
  const streamLive = health?.stream_enabled ?? false;
  const streamLabel = streamLive ? 'Stream live' : 'Stream paused';
  const automationErrors: Array<{ key: string; message: string; retry: () => Promise<unknown> }> = [];

  if (loadedTabs.rules && streamRulesQuery.isError) {
    automationErrors.push({
      key: 'rules',
      message: rules.length
        ? 'Unable to refresh stream rules. Showing last saved values.'
        : 'Unable to load stream rules right now.',
      retry: () => streamRulesQuery.refetch(),
    });
  }
  if (loadedTabs.scheduler && schedulerConfigsQuery.isError) {
    automationErrors.push({
      key: 'scheduler',
      message: schedulerConfigs.length
        ? 'Unable to refresh scheduler status. Showing cached values.'
        : 'Unable to load scheduler status right now.',
      retry: () => schedulerConfigsQuery.refetch(),
    });
  }
  if (loadedTabs.watchlist && watchlistQuery.isError) {
    automationErrors.push({
      key: 'watchlist',
      message: watchlist.entries.length
        ? 'Unable to refresh watchlist analytics.'
        : 'Unable to load watchlist analytics right now.',
      retry: () => watchlistQuery.refetch(),
    });
  }
  if (healthQuery.isError) {
    automationErrors.push({
      key: 'health',
      message: 'Unable to refresh ingestion health status.',
      retry: () => healthQuery.refetch(),
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.6rem' }}>
      {automationErrors.map(({ key, message, retry }) => (
        <ErrorNotice key={key} message={message} onRetry={retry} />
      ))}
      <section className="section">
        <h2 style={{ marginTop: 0 }}>Automation overview</h2>
        <p style={{ margin: '0.35rem 0 1.2rem', color: 'var(--text-muted)' }}>
          Snapshot of your targeting, streaming rules, watchlist and scheduler health.
        </p>
        <div className="kpi-grid">
          <div className="kpi-card">
            <h3>Stream status</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.35rem' }}>
              <span
                style={{
                  width: '0.6rem',
                  height: '0.6rem',
                  borderRadius: '50%',
                  background: streamLive ? '#34d399' : '#f97316',
                  display: 'inline-block',
                }}
              />
              <strong>{streamLabel}</strong>
            </div>
            <p style={{ margin: '0.6rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Stream configuration lives in the Stream Rules tab.
            </p>
            <button
              className="button subtle"
              type="button"
              style={{ marginTop: '0.75rem' }}
              onClick={() => activateTab('rules')}
            >
              Go to stream controls
            </button>
          </div>
          <div className="kpi-card">
            <h3>Stream rules</h3>
            <strong>{ruleCount}</strong>
            {rulePreview.length > 0 && (
              <p style={{ margin: '0.45rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {rulePreview.map((rule) => rule.value).join(' | ')}
                {ruleCount > rulePreview.length ? ' ...' : ''}
              </p>
            )}
            <button
              className="button subtle"
              type="button"
              style={{ marginTop: '0.65rem' }}
              onClick={() => activateTab('rules')}
            >
              Manage rules
            </button>
          </div>
          <div className="kpi-card">
            <h3>Scheduler</h3>
            <strong>{activeJobs}</strong>
            <p style={{ margin: '0.45rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {pausedJobs} paused | {schedulerConfigs.length} total jobs
            </p>
            <button
              className="button subtle"
              type="button"
              style={{ marginTop: '0.65rem' }}
              onClick={() => activateTab('scheduler')}
            >
              View jobs
            </button>
          </div>
          <div className="kpi-card">
            <h3>Watchlist</h3>
            <strong>{watchlistCount}</strong>
            {watchlistPreview.length > 0 && (
              <p style={{ margin: '0.45rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {watchlistPreview.map((entry) => entry.handle).join(' | ')}
                {watchlistCount > watchlistPreview.length ? ' ...' : ''}
              </p>
            )}
            <button
              className="button subtle"
              type="button"
              style={{ marginTop: '0.65rem' }}
              onClick={() => activateTab('watchlist')}
            >
              Inspect watchlist
            </button>
          </div>
        </div>
      </section>

      <section className="section">
        <div
          role="tablist"
          aria-label="Automation panels"
          style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}
        >
          {automationTabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={activeTab === tab.id}
              className={`chip-tab${activeTab === tab.id ? ' active' : ''}`}
              onClick={() => activateTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      <div ref={sectionRefs.targeting} style={{ display: activeTab === 'targeting' ? undefined : 'none' }}>
        <GrowthProfilesManager />
      </div>
      <div ref={sectionRefs.rules} style={{ display: activeTab === 'rules' ? undefined : 'none' }}>
        {loadedTabs.rules ? <KeywordManager query={streamRulesQuery} /> : null}
      </div>
      <div ref={sectionRefs.watchlist} style={{ display: activeTab === 'watchlist' ? undefined : 'none' }}>
        <WatchlistTracker enabled={loadedTabs.watchlist} />
      </div>
      <div ref={sectionRefs.scheduler} style={{ display: activeTab === 'scheduler' ? undefined : 'none' }}>
        {loadedTabs.scheduler ? <SchedulerPanel query={schedulerConfigsQuery} /> : null}
      </div>
    </div>
  );
}

function KeywordManager({ query }: { query: StreamRulesQueryResult }) {
  const { isLoading, isFetching, isError, refetch } = query;
  const rules = query.data ?? [];
  const addRule = useAddStreamRule();
  const deleteRule = useDeleteStreamRule();
  const { notifySuccess, notifyError } = useFeedback();
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');

  function validateRule(value: string) {
    if (!value.trim()) {
      return 'Rule cannot be empty';
    }
    if (value.length > 512) {
      return 'Rule too long (max 512 characters)';
    }
    return '';
  }

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    const validation = validateRule(draft);
    if (validation) {
      setError(validation);
      return;
    }
    try {
      await addRule.mutateAsync(draft.trim());
      setDraft('');
      setError('');
      notifySuccess('Added stream rule.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add rule');
      notifyError(err instanceof Error ? err.message : 'Failed to add rule');
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteRule.mutateAsync(id);
      notifySuccess('Removed stream rule.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
      notifyError(err instanceof Error ? err.message : 'Failed to delete rule');
    }
  }

  return (
    <div className="section">
      <h2 style={{ marginTop: 0 }}>X Stream Rules</h2>
      <p style={{ color: 'rgba(148,163,184,0.75)' }}>
        These filter rules feed the real-time stream. Use X query syntax (e.g. <code>"ai" lang:en -is:retweet</code>).
      </p>

      <form onSubmit={handleAdd} style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <input
          style={{ flex: 1 }}
          className="keyword-input"
          placeholder='"ai" lang:en -is:retweet'
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setError('');
          }}
          disabled={addRule.isPending}
        />
        <button className="button" type="submit" disabled={addRule.isPending}>
          {addRule.isPending ? 'Adding...' : 'Add rule'}
        </button>
      </form>
      {error && <p style={{ color: '#f87171', marginTop: '0.5rem' }}>{error}</p>}

      {isError && (
        <div style={{ marginTop: '1rem' }}>
          <ErrorNotice
            message={
              rules.length
                ? 'Unable to refresh stream rules. Showing cached rules.'
                : 'Unable to load stream rules right now.'
            }
            onRetry={() => refetch()}
            compact
          />
        </div>
      )}

      <ul style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {(isLoading || isFetching) && (!rules || rules.length === 0) ? (
          Array.from({ length: 3 }).map((_, index) => (
            <li
              key={`rule-skeleton-${index}`}
              style={{
                background: 'rgba(30, 41, 59, 0.4)',
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.08)',
                padding: '0.85rem 1rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '1rem',
              }}
            >
              <span
                className="skeleton"
                style={{
                  height: '1rem',
                  width: `${65 + index * 5}%`,
                  borderRadius: '999px',
                  display: 'block',
                }}
              />
              <span
                className="skeleton"
                style={{
                  height: '1.8rem',
                  width: '5.5rem',
                  borderRadius: '999px',
                  display: 'block',
                }}
              />
            </li>
          ))
        ) : rules?.length ? (
          rules.map((rule) => (
            <li
              key={rule.id}
              style={{
                background: 'rgba(30, 41, 59, 0.65)',
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.08)',
                padding: '0.85rem 1rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>{rule.value}</span>
              <button
                type="button"
                className="button"
                style={{ background: 'rgba(239,68,68,0.2)', color: '#fca5a5' }}
                onClick={() => handleDelete(rule.id)}
                disabled={deleteRule.isPending}
              >
                Remove
              </button>
            </li>
          ))
        ) : (
          <li className="empty-state" style={{ background: 'rgba(30,41,59,0.4)', borderRadius: '0.9rem' }}>
            No custom rules yet. Defaults fall back to your KEYWORDS.
          </li>
        )}
      </ul>
    </div>
  );
}

function WatchlistTracker({ enabled }: { enabled: boolean }) {
  const [days, setDays] = useState(14);
  const { data, isLoading, isFetching, isError, refetch } = useWatchlistAnalytics(days, { enabled });
  const entries = enabled && data ? data.entries ?? [] : [];

  const chartData = entries.map((entry) => ({
    handle: entry.handle,
    trending: entry.trending_posts,
    engagements: entry.captured_engagements,
    gap: Math.max(entry.total_posts - entry.trending_posts, 0),
  }));

  const inactive = entries.filter((entry) => entry.total_posts === 0);
  const isPending = enabled ? (isLoading || isFetching) && entries.length === 0 : false;

  if (!enabled) {
    return (
      <div className="section">
        <h2 style={{ marginTop: 0 }}>Watchlist tracker</h2>
        <p style={{ color: 'rgba(148,163,184,0.75)' }}>Open the Watchlist tab to load analytics.</p>
      </div>
    );
  }

  return (
    <div className="section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginTop: 0 }}>Watchlist tracker</h2>
        <label
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.2rem',
            fontSize: '0.85rem',
            color: 'rgba(148,163,184,0.75)',
          }}
        >
          Days: {days}
          <input
            type="range"
            min={7}
            max={90}
            step={7}
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
          />
        </label>
      </div>
      <p style={{ marginTop: '0.4rem', color: 'rgba(148,163,184,0.75)' }}>
        Track how often watchlisted creators appear in trending feeds and how much engagement you capture after alerts.
      </p>

      {isPending ? (
        <SkeletonChart height={260} bars={6} />
      ) : chartData.length === 0 ? (
        <div className="empty-state">Add handles to your watchlist and let ingestion run to populate analytics.</div>
      ) : (
        <div style={{ width: '100%', height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="handle" stroke="rgba(148,163,184,0.75)" />
              <YAxis allowDecimals={false} stroke="rgba(148,163,184,0.75)" />
              <Tooltip
                cursor={{ fill: 'rgba(30,41,59,0.4)' }}
                contentStyle={{ background: 'rgba(15,23,42,0.92)', border: '1px solid rgba(148,163,184,0.2)' }}
              />
              <Legend />
              <Bar dataKey="trending" name="Trending posts" fill="#38bdf8" radius={[6, 6, 0, 0]} />
              <Bar dataKey="engagements" name="Captured engagements" fill="#22c55e" radius={[6, 6, 0, 0]} />
              <Bar dataKey="gap" name="Gaps" fill="#f97316" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {isPending ? (
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={`watchlist-card-skeleton-${index}`}
              style={{
                background: 'rgba(30,41,59,0.45)',
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.08)',
                padding: '0.85rem 1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                <span
                  className="skeleton"
                  style={{ width: '30%', height: '0.9rem', borderRadius: '999px' }}
                />
                <span
                  className="skeleton"
                  style={{ width: '20%', height: '0.75rem', borderRadius: '999px' }}
                />
              </div>
              <span className="skeleton" style={{ width: '65%', height: '0.8rem', borderRadius: '999px' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {Array.from({ length: 2 }).map((__, lineIdx) => (
                  <span
                    key={lineIdx}
                    className="skeleton"
                    style={{ width: `${55 - lineIdx * 10}%`, height: '0.75rem', borderRadius: '999px' }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : entries.length > 0 ? (
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {entries.map((entry) => (
            <div
              key={entry.handle}
              style={{
                background: 'rgba(30,41,59,0.6)',
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.08)',
                padding: '0.85rem 1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ textTransform: 'uppercase', letterSpacing: '0.08em', color: '#bae6fd' }}>
                  {entry.handle}
                </strong>
                <span style={{ fontSize: '0.85rem', color: 'rgba(148,163,184,0.75)' }}>
                  Last seen: {entry.last_seen ? formatDistanceToNow(parseISO(entry.last_seen), { addSuffix: true }) : 'never'}
                </span>
              </div>
              <p style={{ marginTop: '0.4rem', fontSize: '0.85rem', color: 'rgba(148,163,184,0.8)' }}>
                Trending posts: <strong>{entry.trending_posts}</strong> / {entry.total_posts} - captured engagements: <strong>{entry.captured_engagements}</strong>
              </p>
              {entry.recent_posts.length > 0 && (
                <div
                  style={{
                    marginTop: '0.4rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.3rem',
                    fontSize: '0.8rem',
                    color: 'rgba(148,163,184,0.75)',
                  }}
                >
                  {entry.recent_posts.map((post, idx) => (
                    <span key={idx}>
                      [{post.trending ? 'trend' : 'seen'}] {post.created_at ? formatDistanceToNow(parseISO(post.created_at), { addSuffix: true }) : 'n/a'} - virality {post.virality?.toFixed?.(2) ?? '-'}
                      {post.url && (
                        <>
                          {' '}<a href={post.url} target="_blank" rel="noreferrer">view</a>
                        </>
                      )}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {!isPending && inactive.length > 0 && (
        <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: '#f97316' }}>
          Handles with no activity in {days} days: {inactive.map((entry) => entry.handle).join(', ')}
        </div>
      )}

      {isError && (
        <div style={{ marginTop: '1rem' }}>
          <ErrorNotice
            message={
              entries.length
                ? 'Unable to refresh watchlist analytics. Showing cached results.'
                : 'Unable to load watchlist analytics.'
            }
            onRetry={() => refetch()}
            compact
          />
        </div>
      )}
    </div>
  );
}

function SchedulerPanel({ query }: { query: SchedulerConfigsQueryResult }) {
  const { isLoading, isFetching, isError, refetch, data } = query;
  const configs = data ?? [];
  const runJob = useRunSchedulerJob();
  const toggleJobMutation = useToggleSchedulerJob();
  const growthProfilesQuery = useGrowthProfiles();
  const availableProfiles = growthProfilesQuery.data;
  const createConfig = useCreateSchedulerConfig();
  const updateConfigMutation = useUpdateSchedulerConfig();
  const deleteConfigMutation = useDeleteSchedulerConfig();
  const { notifySuccess, notifyError } = useFeedback();
  const [editorState, setEditorState] = useState<SchedulerEditorState | null>(null);
  const isPending = (isLoading || isFetching) && configs.length === 0;

  function handleRun(config: SchedulerConfigPayload) {
    const label = config.name || config.job_id;
    runJob.mutate(config.config_id, {
      onSuccess: () => notifySuccess(`Triggered ${label}.`),
      onError: (err) => notifyError(err instanceof Error ? err.message : 'Failed to run job.'),
    });
  }

  function handleToggle(config: SchedulerConfigPayload) {
    const currentlyPaused = config.paused ?? !config.enabled;
    const action = currentlyPaused ? 'resume' : 'pause';
    const label = config.name || config.job_id;
    toggleJobMutation.mutate(
      { config_id: config.config_id, action },
      {
        onSuccess: () => notifySuccess(`${currentlyPaused ? 'Resumed' : 'Paused'} ${label}.`),
        onError: (err) => notifyError(err instanceof Error ? err.message : 'Failed to update scheduler job.'),
      },
    );
  }

  async function handleDelete(config: SchedulerConfigPayload) {
    const label = config.name || config.job_id;
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(`Delete "${label}"? This cannot be undone.`);
      if (!confirmed) {
        return;
      }
    }
    try {
      await deleteConfigMutation.mutateAsync(config.config_id);
      notifySuccess(`Deleted ${label}.`);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : 'Failed to delete scheduler job.');
    }
  }

  async function handleEditorSubmit(payload: SchedulerConfigInput): Promise<void> {
    if (!editorState) {
      return;
    }
    const label =
      payload.name || (editorState.mode === 'edit' ? editorState.config.name : null) || payload.job_id;
    try {
      if (editorState.mode === 'edit' && editorState.config) {
        await updateConfigMutation.mutateAsync({ config_id: editorState.config.config_id, payload });
        notifySuccess(`Updated ${label}.`);
      } else {
        await createConfig.mutateAsync(payload);
        notifySuccess(`Created ${label}.`);
      }
      setEditorState(null);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : 'Failed to save scheduler config.');
      throw err;
    }
  }

  const editorSubmitting =
    editorState?.mode === 'edit' ? updateConfigMutation.isPending : createConfig.isPending;

  const renderSchedulerJobCard = (config: SchedulerConfigPayload) => {
    const paused = config.paused ?? !config.enabled;
    const description = schedulerJobLabelMap[config.job_id] ?? config.job_id;
    const updatedAgo = formatDistanceToNow(parseISO(config.updated_at), { addSuffix: true });

    return (
      <div
        key={config.config_id}
        style={{
          borderRadius: '1rem',
          padding: '1.25rem',
          background: 'linear-gradient(135deg, rgba(30,41,59,0.9) 0%, rgba(15,23,42,0.85) 65%)',
          border: '1px solid rgba(148,163,184,0.12)',
          boxShadow: '0 30px 60px rgba(2,6,23,0.45)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto',
            gap: '1rem',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: '1.15rem' }}>{config.name || description}</strong>
              <span
                style={{
                  padding: '0.2rem 0.65rem',
                  borderRadius: '999px',
                  fontSize: '0.75rem',
                  background: paused ? 'rgba(127,29,29,0.25)' : 'rgba(22,163,74,0.2)',
                  color: paused ? '#fca5a5' : '#4ade80',
                  border: `1px solid ${paused ? 'rgba(248,113,113,0.35)' : 'rgba(34,197,94,0.35)'}`,
                }}
              >
                {paused ? 'Paused' : 'Active'}
              </span>
            </div>
            <div style={{ height: '0.4rem' }} />
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '0.65rem',
                fontSize: '0.82rem',
                color: 'rgba(148,163,184,0.8)',
              }}
            >
              <span>
                <strong style={{ color: 'rgba(248,250,252,0.85)' }}>Next run:</strong> {describeNextRun(config)}
              </span>
              <span>• Profile: {config.growth_profile?.name ?? 'Default'}</span>
              <span>• Updated {updatedAgo}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              className="button"
              type="button"
              style={{ minWidth: '6.2rem' }}
              onClick={() => handleRun(config)}
              disabled={runJob.isPending}
            >
              Run now
            </button>
            <button
              className="button"
              type="button"
              style={{
                minWidth: '6.2rem',
                background: paused ? 'rgba(22,163,74,0.2)' : 'rgba(185,28,28,0.2)',
                color: paused ? '#4ade80' : '#fca5a5',
                border: `1px solid ${paused ? 'rgba(34,197,94,0.35)' : 'rgba(248,113,113,0.35)'}`,
              }}
              onClick={() => handleToggle(config)}
              disabled={toggleJobMutation.isPending}
            >
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button
              className="button subtle"
              type="button"
              style={{ minWidth: '5.2rem' }}
              onClick={() => setEditorState({ mode: 'edit', config })}
              disabled={editorState?.mode === 'edit' && editorState.config?.config_id === config.config_id}
            >
              Edit
            </button>
            <button
              className="button ghost"
              type="button"
              style={{ minWidth: '5.2rem' }}
              onClick={() => handleDelete(config)}
              disabled={deleteConfigMutation.isPending}
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    );
  };

  function describeNextRun(config: SchedulerConfigPayload): string {
    const paused = config.paused ?? !config.enabled;
    if (paused) {
      return 'Paused';
    }
    if (!config.next_run) {
      return 'Waiting for next slot';
    }
    try {
      const nextRunDate = parseISO(config.next_run);
      return `${formatDistanceToNow(nextRunDate, { addSuffix: true })} (${nextRunDate.toLocaleString()})`;
    } catch {
      return config.next_run;
    }
  }

  return (
    <div className="section">
      <h2 style={{ marginTop: 0 }}>Scheduler Control</h2>
      <p style={{ color: 'rgba(148,163,184,0.75)' }}>
        Manage background jobs. Create, pause, or duplicate ingestion and alert workers without touching the CLI.
      </p>
      {growthProfilesQuery.isError && (
        <ErrorNotice
          message="Unable to load growth profiles for scheduler jobs."
          onRetry={() => growthProfilesQuery.refetch()}
        />
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
        <p style={{ margin: 0, color: 'rgba(148,163,184,0.75)', fontSize: '0.9rem' }}>
          Each job is backed by a DB config + lock, so multiple workers can run safely in parallel.
        </p>
        <button
          className="button"
          type="button"
          onClick={() => setEditorState({ mode: 'create' })}
          disabled={editorState?.mode === 'create' || availableProfiles.length === 0}
        >
          {editorState?.mode === 'create' ? 'Creating...' : 'Add scheduler job'}
        </button>
        {!availableProfiles.length && (
          <p style={{ margin: '0.4rem 0 0', color: '#fca5a5', fontSize: '0.85rem' }}>
            Create a growth profile before adding scheduler jobs.
          </p>
        )}
      </div>

      {editorState && (
        <SchedulerConfigForm
          key={
            editorState.mode === 'edit' && editorState.config
              ? `edit-${editorState.config.config_id}`
              : 'create'
          }
          mode={editorState.mode}
          initialValues={editorState.mode === 'edit' ? editorState.config : undefined}
          submitting={editorSubmitting}
          onSubmit={handleEditorSubmit}
          onCancel={() => setEditorState(null)}
          profiles={availableProfiles}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        {isPending ? (
          Array.from({ length: 2 }).map((_, index) => (
            <div
              key={`job-skeleton-${index}`}
              style={{
                background: 'rgba(30,41,59,0.65)',
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.08)',
                padding: '1rem 1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1.25rem' }}>
                <div style={{ flex: 1 }}>
                  <SkeletonCard lines={2} />
                </div>
                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <span className="skeleton" style={{ width: '5.5rem', height: '2.2rem', borderRadius: '999px' }} />
                  <span className="skeleton" style={{ width: '5.5rem', height: '2.2rem', borderRadius: '999px' }} />
                </div>
              </div>
              <span className="skeleton" style={{ width: '45%', height: '0.8rem', borderRadius: '999px' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {Array.from({ length: 2 }).map((__, lineIdx) => (
                  <span
                    key={lineIdx}
                    className="skeleton"
                    style={{ width: `${70 - lineIdx * 12}%`, height: '0.75rem', borderRadius: '999px' }}
                  />
                ))}
              </div>
            </div>
          ))
        ) : configs.length ? (
          configs.map((config) => renderSchedulerJobCard(config))
        ) : (
          <div className="empty-state">Scheduler details unavailable yet.</div>
        )}

        {isError && (
          <ErrorNotice
            message={
              configs.length
                ? 'Unable to refresh scheduler status. Showing cached jobs.'
                : 'Unable to load scheduler status.'
            }
            onRetry={() => refetch()}
            compact
          />
        )}
      </div>
    </div>
  );
}

type SchedulerEditorState =
  | { mode: 'create' }
  | { mode: 'edit'; config: SchedulerConfigPayload };

type SchedulerConfigInput = {
  job_id: string;
  name: string | null;
  cron: string;
  enabled: boolean;
  priority: number;
  concurrency_limit: number;
  lock_timeout_seconds: number;
  parameters: Record<string, unknown>;
  growth_profile_id: number | null;
};

type SchedulerConfigFormState = {
  job_id: string;
  name: string;
  cron: string;
  enabled: boolean;
  priority: number;
  concurrency_limit: number;
  lock_timeout_seconds: number;
  parametersText: string;
  growth_profile_id: number | null;
};

interface SchedulerConfigFormProps {
  mode: 'create' | 'edit';
  initialValues?: Partial<SchedulerConfigPayload>;
  submitting: boolean;
  onSubmit: (payload: SchedulerConfigInput) => Promise<void>;
  onCancel: () => void;
  profiles: GrowthProfileSummary[];
}

function buildFormState(
  initialValues: Partial<SchedulerConfigPayload> | undefined,
  profiles: GrowthProfileSummary[],
): SchedulerConfigFormState {
  const fallbackProfileId = initialValues?.growth_profile_id ?? profiles[0]?.id ?? null;
  return {
    job_id: initialValues?.job_id ?? schedulerJobOptions[0].value,
    name: initialValues?.name ?? '',
    cron: initialValues?.cron ?? '*/30 * * * *',
    enabled: initialValues?.enabled ?? true,
    priority: initialValues?.priority ?? 5,
    concurrency_limit: initialValues?.concurrency_limit ?? 1,
    lock_timeout_seconds: initialValues?.lock_timeout_seconds ?? 300,
    parametersText:
      initialValues?.parameters && Object.keys(initialValues.parameters).length
        ? JSON.stringify(initialValues.parameters, null, 2)
        : '',
    growth_profile_id: fallbackProfileId,
  };
}

function SchedulerConfigForm({
  mode,
  initialValues,
  submitting,
  onSubmit,
  onCancel,
  profiles,
}: SchedulerConfigFormProps) {
  const formId = useId();
  const [formState, setFormState] = useState<SchedulerConfigFormState>(() => buildFormState(initialValues, profiles));
  const [paramError, setParamError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    setFormState(buildFormState(initialValues, profiles));
    setParamError(null);
    setSubmitError(null);
  }, [initialValues, profiles]);

  function updateField<K extends keyof SchedulerConfigFormState>(key: K, value: SchedulerConfigFormState[K]) {
    setFormState((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setParamError(null);
    setSubmitError(null);
    let parameters: Record<string, unknown> = {};
    if (formState.parametersText.trim()) {
      try {
        parameters = JSON.parse(formState.parametersText);
      } catch {
        setParamError('Parameters must be valid JSON.');
        return;
      }
    }
    if (!formState.cron.trim()) {
      setSubmitError('Cron expression is required.');
      return;
    }
    try {
      if (!formState.growth_profile_id) {
        setSubmitError('Select a growth profile for this job.');
        return;
      }
      await onSubmit({
        job_id: formState.job_id,
        name: formState.name.trim() ? formState.name.trim() : null,
        cron: formState.cron.trim(),
        enabled: formState.enabled,
        priority: Number(formState.priority),
        concurrency_limit: Number(formState.concurrency_limit),
        lock_timeout_seconds: Number(formState.lock_timeout_seconds),
        parameters,
        growth_profile_id: formState.growth_profile_id,
      });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save scheduler config.');
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginTop: '1rem',
        padding: '1rem 1.25rem',
        borderRadius: '0.9rem',
        border: '1px solid rgba(148,163,184,0.12)',
        background: 'rgba(15,23,42,0.65)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}
    >
      <div>
        <h3 style={{ margin: 0 }}>{mode === 'create' ? 'New scheduler job' : 'Edit scheduler job'}</h3>
        <p style={{ margin: '0.25rem 0 0', color: 'rgba(148,163,184,0.7)', fontSize: '0.9rem' }}>
          Choose a handler, cron cadence, and optional JSON parameters.
        </p>
      </div>

      <div className="form-grid" style={{ gap: '1rem' }}>
        <div className="form-field">
          <label htmlFor={`${formId}-job-id`}>Job type</label>
          <select
            id={`${formId}-job-id`}
            value={formState.job_id}
            onChange={(event) => updateField('job_id', event.target.value)}
            disabled={mode === 'edit' || submitting}
          >
            {schedulerJobOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-profile`}>Growth profile</label>
          <select
            id={`${formId}-profile`}
            value={formState.growth_profile_id ?? ''}
            onChange={(event) => updateField('growth_profile_id', Number(event.target.value) || null)}
            disabled={submitting || profiles.length === 0}
          >
            {!profiles.length && <option value="">No profiles available</option>}
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
                {profile.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-name`}>Display name</label>
          <input
            id={`${formId}-name`}
            value={formState.name}
            onChange={(event) => updateField('name', event.target.value)}
            placeholder="e.g. X ingest primary"
            disabled={submitting}
          />
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-cron`}>Cron schedule</label>
          <input
            id={`${formId}-cron`}
            value={formState.cron}
            onChange={(event) => updateField('cron', event.target.value)}
            placeholder="*/15 * * * *"
            disabled={submitting}
          />
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-priority`}>Priority</label>
          <input
            id={`${formId}-priority`}
            type="number"
            min={1}
            max={100}
            value={formState.priority}
            onChange={(event) => updateField('priority', Number(event.target.value) || 1)}
            disabled={submitting}
          />
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-concurrency`}>Concurrency limit</label>
          <input
            id={`${formId}-concurrency`}
            type="number"
            min={1}
            max={20}
            value={formState.concurrency_limit}
            onChange={(event) => updateField('concurrency_limit', Number(event.target.value) || 1)}
            disabled={submitting}
          />
        </div>
        <div className="form-field">
          <label htmlFor={`${formId}-lock`}>Lock timeout (seconds)</label>
          <input
            id={`${formId}-lock`}
            type="number"
            min={30}
            max={7200}
            value={formState.lock_timeout_seconds}
            onChange={(event) => updateField('lock_timeout_seconds', Number(event.target.value) || 30)}
            disabled={submitting}
          />
        </div>
      </div>

      <div className="form-field" style={{ marginTop: '0.5rem' }}>
        <label htmlFor={`${formId}-params`}>Parameters (JSON)</label>
        <textarea
          id={`${formId}-params`}
          value={formState.parametersText}
          onChange={(event) => updateField('parametersText', event.target.value)}
          placeholder='{"max_x": 10}'
          rows={4}
          disabled={submitting}
        />
        {paramError && <p style={{ color: '#fca5a5', margin: '0.3rem 0 0' }}>{paramError}</p>}
      </div>

      {submitError && <p style={{ color: '#fca5a5', margin: 0 }}>{submitError}</p>}

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button className="button" type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : mode === 'create' ? 'Add job' : 'Save changes'}
        </button>
        <button className="button ghost" type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
      </div>
    </form>
  );
}

type ProfileFormState = {
  name: string;
  niche: string;
  keywordsText: string;
  watchlistText: string;
  makeDefault: boolean;
};

const emptyProfileForm: ProfileFormState = {
  name: '',
  niche: '',
  keywordsText: '',
  watchlistText: '',
  makeDefault: false,
};

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function GrowthProfilesManager() {
  const { data: profiles, isLoading, isFetching, isError, refetch } = useGrowthProfiles();
  const createProfile = useCreateGrowthProfile();
  const updateProfile = useUpdateGrowthProfile();
  const deleteProfile = useDeleteGrowthProfile();
  const setDefaultProfile = useSetDefaultGrowthProfile();
  const { notifySuccess, notifyError } = useFeedback();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mode, setMode] = useState<'edit' | 'create'>('edit');
  const [formState, setFormState] = useState<ProfileFormState>(emptyProfileForm);

  const loadingProfiles = (isLoading || isFetching) && profiles.length === 0;
  const selectedProfile = mode === 'edit' ? profiles.find((profile) => profile.id === selectedId) ?? null : null;

  useEffect(() => {
    if (mode === 'edit' && !selectedProfile && profiles.length > 0) {
      const preferred = profiles.find((profile) => profile.is_default) ?? profiles[0];
      setSelectedId(preferred.id);
    }
  }, [mode, profiles, selectedProfile]);

  useEffect(() => {
    if (mode === 'edit' && selectedProfile) {
      setFormState({
        name: selectedProfile.name,
        niche: selectedProfile.niche ?? '',
        keywordsText: selectedProfile.keywords.join(', '),
        watchlistText: selectedProfile.watchlist.join(', '),
        makeDefault: false,
      });
    }
  }, [mode, selectedProfile]);

  const saving = mode === 'create' ? createProfile.isPending : updateProfile.isPending;

  function handleSelect(profileId: number) {
    setMode('edit');
    setSelectedId(profileId);
  }

  function startCreate() {
    setMode('create');
    setSelectedId(null);
    setFormState({
      ...emptyProfileForm,
      name: '',
    });
  }

  function cancelCreate() {
    setMode('edit');
    setFormState(emptyProfileForm);
  }

  function handleFormChange<Key extends keyof ProfileFormState>(field: Key, value: ProfileFormState[Key]) {
    setFormState((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const keywords = splitList(formState.keywordsText);
    const watchlist = splitList(formState.watchlistText);
    const payloadBase = {
      niche: formState.niche.trim() || null,
      keywords,
      watchlist,
    };
    try {
      if (mode === 'create') {
        await createProfile.mutateAsync({
          name: formState.name.trim() || 'New profile',
          ...payloadBase,
          make_default: formState.makeDefault,
        });
        notifySuccess('Created growth profile.');
        setFormState(emptyProfileForm);
        setMode('edit');
        setSelectedId(null);
      } else if (selectedProfile) {
        await updateProfile.mutateAsync({
          profileId: selectedProfile.id,
          payload: {
            name: formState.name.trim() || selectedProfile.name,
            ...payloadBase,
          },
        });
        notifySuccess('Growth profile updated.');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save growth profile.';
      notifyError(message);
    }
  }

  async function handleArchive(profileId: number) {
    const profile = profiles.find((item) => item.id === profileId);
    if (!profile || profile.is_default) {
      return;
    }
    const confirmed = typeof window === 'undefined' ? true : window.confirm(`Archive ${profile.name}?`);
    if (!confirmed) {
      return;
    }
    try {
      await deleteProfile.mutateAsync(profileId);
      notifySuccess(`Archived ${profile.name}.`);
      if (selectedId === profileId) {
        setSelectedId(null);
      }
    } catch (err) {
      notifyError(err instanceof Error ? err.message : 'Failed to archive profile.');
    }
  }

  async function handleSetDefault(profileId: number) {
    try {
      await setDefaultProfile.mutateAsync(profileId);
      notifySuccess('Default profile updated.');
    } catch (err) {
      notifyError(err instanceof Error ? err.message : 'Failed to set default profile.');
    }
  }

  const showForm = mode === 'create' || (!!selectedProfile && mode === 'edit');

  return (
    <section className="section">
      <h2 style={{ marginTop: 0 }}>Growth Profiles</h2>
      <p style={{ color: 'rgba(148,163,184,0.75)', marginBottom: '1rem' }}>
        Run separate targeting tracks (keywords + watchlists) and map each scheduler job to the right profile.
      </p>
      {isError && <ErrorNotice message="Unable to load growth profiles." onRetry={() => refetch()} />}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem' }}>
        <div style={{ flex: '1 1 320px', minWidth: '300px', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          {loadingProfiles &&
            Array.from({ length: 2 }).map((_, idx) => (
              <div key={`profile-skel-${idx}`} className="card" style={{ padding: '1rem' }}>
                <SkeletonCard lines={3} />
              </div>
            ))}
          {!loadingProfiles && profiles.length === 0 && (
            <div className="empty-state" style={{ textAlign: 'left' }}>
              No profiles yet. Create one to start ingesting content.
            </div>
          )}
          {profiles.map((profile) => {
            const isSelected = mode === 'edit' && selectedProfile?.id === profile.id;
            return (
              <div
                key={profile.id}
                style={{
                  borderRadius: '0.85rem',
                  border: isSelected ? '1px solid rgba(34,197,94,0.45)' : '1px solid rgba(148,163,184,0.12)',
                  padding: '0.85rem 1rem',
                  background: isSelected ? 'rgba(34,197,94,0.08)' : 'rgba(15,23,42,0.4)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.35rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <strong>{profile.name}</strong>
                  {profile.is_default && (
                    <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '999px', background: 'rgba(34,197,94,0.25)', color: '#4ade80' }}>
                      Default
                    </span>
                  )}
                  {!profile.is_active && (
                    <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '999px', background: 'rgba(248,250,252,0.15)', color: '#e2e8f0' }}>
                      Archived
                    </span>
                  )}
                </div>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'rgba(148,163,184,0.8)' }}>
                  Keywords: {profile.keywords.length ? profile.keywords.slice(0, 4).join(', ') : '—'}
                </p>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'rgba(148,163,184,0.7)' }}>
                  Watchlist: {profile.watchlist.length ? profile.watchlist.slice(0, 3).join(', ') : '—'}
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.35rem' }}>
                  <button className="button subtle" type="button" onClick={() => handleSelect(profile.id)}>
                    Edit
                  </button>
                  {!profile.is_default && (
                    <button
                      className="button subtle"
                      type="button"
                      onClick={() => handleSetDefault(profile.id)}
                      disabled={setDefaultProfile.isPending}
                    >
                      Make default
                    </button>
                  )}
                  {!profile.is_default && (
                    <button
                      className="button ghost"
                      type="button"
                      onClick={() => handleArchive(profile.id)}
                      disabled={deleteProfile.isPending}
                    >
                      Archive
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          <button className="button ghost" type="button" onClick={startCreate} style={{ alignSelf: 'flex-start' }}>
            Add profile
          </button>
        </div>

        <div style={{ flex: '1 1 360px', minWidth: '320px' }}>
          {showForm ? (
            <form
              onSubmit={handleSubmit}
              style={{
                borderRadius: '0.9rem',
                border: '1px solid rgba(148,163,184,0.12)',
                background: 'rgba(15,23,42,0.65)',
                padding: '1rem 1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.85rem',
              }}
            >
              <div>
                <h3 style={{ margin: 0 }}>{mode === 'create' ? 'Create growth profile' : `Edit ${selectedProfile?.name ?? ''}`}</h3>
                <p style={{ margin: '0.25rem 0 0', color: 'rgba(148,163,184,0.75)', fontSize: '0.9rem' }}>
                  Keywords and watchlist drive ingestion and alerts for any scheduler job mapped to this profile.
                </p>
              </div>
              <div className="form-field">
                <label htmlFor="profile-name">Profile name</label>
                <input
                  id="profile-name"
                  value={formState.name}
                  onChange={(event) => handleFormChange('name', event.target.value)}
                  placeholder="UPI insights, Web3 creators, etc."
                  disabled={saving}
                />
              </div>
              <div className="form-field">
                <label htmlFor="profile-niche">Niche</label>
                <input
                  id="profile-niche"
                  value={formState.niche}
                  onChange={(event) => handleFormChange('niche', event.target.value)}
                  placeholder="Fintech infra, AI banking..."
                  disabled={saving}
                />
              </div>
              <div className="form-field">
                <label htmlFor="profile-keywords">Keywords (comma separated)</label>
                <textarea
                  id="profile-keywords"
                  rows={2}
                  value={formState.keywordsText}
                  onChange={(event) => handleFormChange('keywordsText', event.target.value)}
                  placeholder="upi, faster payments, crypto regulation"
                  disabled={saving}
                />
              </div>
              <div className="form-field">
                <label htmlFor="profile-watchlist">Watchlist handles (comma separated)</label>
                <textarea
                  id="profile-watchlist"
                  rows={2}
                  value={formState.watchlistText}
                  onChange={(event) => handleFormChange('watchlistText', event.target.value)}
                  placeholder="naval, tarunkrishna2"
                  disabled={saving}
                />
              </div>
              {mode === 'create' && (
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
                  <input
                    type="checkbox"
                    checked={formState.makeDefault}
                    onChange={(event) => handleFormChange('makeDefault', event.target.checked)}
                    disabled={saving}
                  />
                  Set as default for new jobs
                </label>
              )}
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button className="button" type="submit" disabled={saving}>
                  {saving ? 'Saving...' : mode === 'create' ? 'Create profile' : 'Save changes'}
                </button>
                {mode === 'create' ? (
                  <button className="button ghost" type="button" onClick={cancelCreate} disabled={saving}>
                    Cancel
                  </button>
                ) : (
                  <button className="button ghost" type="button" onClick={startCreate} disabled={saving}>
                    New profile
                  </button>
                )}
              </div>
            </form>
          ) : (
            <div className="empty-state">Select a profile to edit or create a new one.</div>
          )}
        </div>
      </div>
    </section>
  );
}





