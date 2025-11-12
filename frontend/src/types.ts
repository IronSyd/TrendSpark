export interface HealthResponse {
  ok: boolean;
  stream_enabled: boolean;
  keywords: string[];
  niche: string | null;
  watchlist: string[];
  growth_profile?: GrowthProfileSummary;
}

export interface Conversation {
  platform: 'x' | 'reddit' | string;
  post_id: string;
  url?: string | null;
  text: string;
  virality: number;
  velocity: number;
  trending: boolean;
  replies: Array<{ tone?: string; reply: string }>;
}

export interface ConversationDetail extends Conversation {
  author?: string | null;
  created_at: string;
  metrics: {
    likes: number;
    replies: number;
    reposts: number;
    quotes: number;
    views: number;
  };
  tones: string[];
}

export type IdeasResponse = string[];

export interface BrandProfile {
  adjectives: string[];
  voice_notes: string;
  examples: string[];
}

export interface BrandProfilePayload {
  adjectives: string[];
  voice_notes: string;
  examples: string[];
}

export interface NotificationItem {
  id: number;
  created_at: string;
  channel: string;
  category: string | null;
  message: string;
}

export interface StreamRule {
  id: number;
  value: string;
  created_at: string;
}

export interface SchedulerConfigPayload {
  config_id: number;
  job_id: string;
  name: string | null;
  cron: string;
  enabled: boolean;
  priority: number;
  concurrency_limit: number;
  lock_timeout_seconds: number;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  next_run?: string | null;
  paused?: boolean;
  growth_profile_id?: number | null;
  growth_profile?: GrowthProfileSummary | null;
}

export interface GrowthProfileSummary {
  id: number;
  name: string;
  is_default: boolean;
  is_active: boolean;
}

export interface GrowthProfile extends GrowthProfileSummary {
  niche: string | null;
  keywords: string[];
  watchlist: string[];
  created_at: string;
  updated_at: string;
}

export type GrowthSettings = GrowthProfile;

export interface GrowthProfilePayload {
  name: string;
  niche: string | null;
  keywords: string[];
  watchlist: string[];
  make_default?: boolean;
}

export interface GrowthProfileUpdatePayload {
  name?: string;
  niche: string | null;
  keywords?: string[];
  watchlist?: string[];
  is_active?: boolean;
  make_default?: boolean;
}

export interface WatchlistAnalyticsEntry {
  handle: string;
  total_posts: number;
  trending_posts: number;
  captured_engagements: number;
  last_seen: string | null;
  recent_posts: Array<{
    created_at: string | null;
    virality: number | null;
    velocity: number | null;
    url: string | null;
    trending: boolean;
  }>;
}

export interface WatchlistAnalytics {
  entries: WatchlistAnalyticsEntry[];
  days: number;
}
