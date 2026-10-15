import { apiClient } from './client';

export type CacheStatsWindow = '1h' | '24h' | '7d';

export interface CacheStatsCounts {
  requests: number;
  failed: number;
  input_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  /** cache_read_tokens / input_tokens; null when there was no input. */
  hit_rate: number | null;
}

export interface CacheStatsModel extends CacheStatsCounts {
  model: string;
}

export interface CacheStatsCredential extends CacheStatsCounts {
  auth_id: string;
  auth_index?: string;
  provider?: string;
  models: CacheStatsModel[];
}

export interface CacheStatsSnapshot {
  window_seconds: number;
  since: string;
  generated_at: string;
  total: CacheStatsCounts;
  credentials: CacheStatsCredential[];
  models: CacheStatsModel[];
}

export const cacheStatsApi = {
  get: (window: CacheStatsWindow) =>
    apiClient.get<CacheStatsSnapshot>('/observability/usage/cache', {
      params: { window },
      timeout: 15 * 1000,
    }),
};
