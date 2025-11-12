import { useEffect, useState } from "react";

import { useBrandProfile, useUpdateBrandProfile } from "../hooks/useApi";
import { useFeedback } from "../components/FeedbackProvider";
import { ErrorNotice } from "../components/ErrorNotice";

function splitList(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function BrandVoicePage() {
  const { data: profile, isLoading, isFetching, isError, refetch } = useBrandProfile();
  const updateProfile = useUpdateBrandProfile();
  const { notifySuccess, notifyError } = useFeedback();

  const [adjectives, setAdjectives] = useState('');
  const [examples, setExamples] = useState('');
  const [notes, setNotes] = useState('');
  const loadingProfile = (isLoading || isFetching) && !profile;

  useEffect(() => {
    if (profile) {
      setAdjectives(profile.adjectives.join(', '));
      setExamples(profile.examples.join("\n"));
      setNotes(profile.voice_notes ?? '');
    }
  }, [profile]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateProfile.mutateAsync({
        adjectives: splitList(adjectives),
        voice_notes: notes.trim(),
        examples: examples
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      });
      notifySuccess('Brand voice updated successfully.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save voice settings';
      notifyError(message);
    }
  }

  return (
    <form className="section" onSubmit={handleSave}>
      <h2 style={{ marginTop: 0 }}>Brand Voice</h2>
      <p style={{ color: 'rgba(148,163,184,0.75)', marginBottom: '1.25rem' }}>
        Shape how replies and ideas sound. Use comma-separated adjectives, long-form notes, and example posts to give
        the generator more context.
      </p>

      {isError && (
        <ErrorNotice
          message="Unable to refresh your brand profile. Fields below may be out of date."
          onRetry={() => refetch()}
        />
      )}

      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="adjectives">Adjectives</label>
          <input
            id="adjectives"
            placeholder={loadingProfile ? 'Loading brand voice...' : 'witty, helpful, contrarian'}
            value={adjectives}
            onChange={(event) => setAdjectives(event.target.value)}
            disabled={loadingProfile || updateProfile.isPending}
          />
        </div>

        <div className="form-field">
          <label htmlFor="examples">Example posts (one per line)</label>
          <textarea
            id="examples"
            rows={6}
            placeholder={
              loadingProfile ? 'Loading saved examples...' : 'Example tweet or reply that sounds like your brand'
            }
            value={examples}
            onChange={(event) => setExamples(event.target.value)}
            disabled={loadingProfile || updateProfile.isPending}
          />
        </div>
      </div>

      <div className="form-field" style={{ marginTop: '1rem' }}>
        <label htmlFor="notes">Voice guidance</label>
        <textarea
          id="notes"
          rows={6}
          placeholder={
            loadingProfile
              ? 'Loading voice guidance...'
              : "Key dos and don'ts, signature phrases, topics to emphasise"
          }
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          disabled={loadingProfile || updateProfile.isPending}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1.5rem' }}>
        <button type="submit" className="button" disabled={loadingProfile || updateProfile.isPending}>
          {updateProfile.isPending ? 'Saving...' : 'Save voice profile'}
        </button>
      </div>
    </form>
  );
}
