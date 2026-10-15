import type { AuthFileItem } from '@/types';
import type { CacheStatsCounts, CacheStatsCredential, CacheStatsSnapshot } from '@/services/api';

/** Match by auth index first; fall back to the auth file name, which the backend uses as its ID. */
export function cacheStatsFor(
  file: Pick<AuthFileItem, 'name' | 'authIndex'>,
  snapshot: CacheStatsSnapshot | null | undefined
): CacheStatsCredential | undefined {
  if (!snapshot) return undefined;
  const index =
    file.authIndex === null || file.authIndex === undefined ? '' : String(file.authIndex);
  return (
    (index && snapshot.credentials.find((c) => c.auth_index === index)) ||
    snapshot.credentials.find((c) => c.auth_id === file.name)
  );
}

export function sumCacheStats(rows: (CacheStatsCounts | undefined)[]): CacheStatsCounts {
  const total = rows.reduce<CacheStatsCounts>(
    (acc, row) =>
      row
        ? {
            ...acc,
            requests: acc.requests + row.requests,
            failed: acc.failed + row.failed,
            input_tokens: acc.input_tokens + row.input_tokens,
            cache_read_tokens: acc.cache_read_tokens + row.cache_read_tokens,
            cache_write_tokens: acc.cache_write_tokens + row.cache_write_tokens,
          }
        : acc,
    {
      requests: 0,
      failed: 0,
      input_tokens: 0,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      hit_rate: null,
    }
  );
  return {
    ...total,
    hit_rate: total.input_tokens > 0 ? total.cache_read_tokens / total.input_tokens : null,
  };
}

/** Whole-percent display; keeps "99%" from rounding up to a misleading "100%". */
export function formatHitRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return '--';
  const percent = rate * 100;
  return `${percent >= 99.5 && percent < 100 ? 99 : Math.round(percent)}%`;
}
