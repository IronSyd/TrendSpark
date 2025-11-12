import { IdeasList } from '../components/IdeasList';
import { ErrorNotice } from '../components/ErrorNotice';
import { useIdeas } from '../hooks/useApi';
import { useFeedback } from '../components/FeedbackProvider';

export default function IdeasPage() {
  const ideasQuery = useIdeas();
  const ideas = ideasQuery.data;
  const isLoading = ideasQuery.isLoading;
  const isFetching = ideasQuery.isFetching;
  const isError = ideasQuery.isError;
  const { notifySuccess, notifyError } = useFeedback();

  async function handleRefresh() {
    try {
      await ideasQuery.refetch({ throwOnError: true });
      notifySuccess('Ideas refreshed.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to refresh ideas.';
      notifyError(message);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {isError && (
        <ErrorNotice
          message={
            ideas.length ? 'Unable to refresh today’s ideas. Showing cached results.' : 'Unable to load today’s ideas.'
          }
          onRetry={() => ideasQuery.refetch()}
        />
      )}
      <IdeasList ideas={ideas} isLoading={isLoading} isFetching={isFetching} onRefresh={handleRefresh} />
      <div className="section">
        <h2 style={{ marginTop: 0 }}>How these ideas are built</h2>
        <p style={{ color: 'rgba(148,163,184,0.8)', lineHeight: 1.6 }}>
          Every morning, Trend Spark AI blends your growth profile (niche, keywords, watchlist) with the latest
          conversations to produce five on-brand tweet ideas. Fine-tune your growth settings whenever you want to steer
          upcoming idea batches.
        </p>
      </div>
    </div>
  );
}

