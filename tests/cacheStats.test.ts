import { describe, expect, test } from 'bun:test';
import type { CacheStatsSnapshot } from '../src/services/api/cacheStats';
import { cacheStatsFor, formatHitRate, sumCacheStats } from '../src/features/quota/cacheStatsModel';

const row = (auth_id: string, auth_index: string, input: number, read: number) => ({
  auth_id,
  auth_index,
  provider: 'codex',
  requests: 2,
  failed: 0,
  input_tokens: input,
  cache_read_tokens: read,
  cache_write_tokens: 0,
  hit_rate: input ? read / input : null,
  models: [],
});

const snapshot: CacheStatsSnapshot = {
  window_seconds: 86400,
  since: '2026-10-14T00:00:00Z',
  generated_at: '2026-10-15T00:00:00Z',
  total: row('', '', 300, 150),
  credentials: [row('codex-a.json', 'idx-a', 100, 90), row('codex-b.json', 'idx-b', 200, 60)],
  models: [],
};

describe('cache stats view model', () => {
  test('matches credentials by auth index, then by file name', () => {
    expect(cacheStatsFor({ name: 'other.json', authIndex: 'idx-b' }, snapshot)?.auth_id).toBe(
      'codex-b.json'
    );
    expect(cacheStatsFor({ name: 'codex-a.json', authIndex: null }, snapshot)?.auth_index).toBe(
      'idx-a'
    );
    expect(cacheStatsFor({ name: 'missing.json' }, snapshot)).toBeUndefined();
    expect(cacheStatsFor({ name: 'codex-a.json' }, null)).toBeUndefined();
  });

  test('summing weights by tokens instead of averaging rates', () => {
    const sum = sumCacheStats([snapshot.credentials[0], undefined, snapshot.credentials[1]]);
    expect(sum.input_tokens).toBe(300);
    expect(sum.cache_read_tokens).toBe(150);
    expect(sum.hit_rate).toBe(0.5);
    expect(sumCacheStats([]).hit_rate).toBeNull();
  });

  test('formats unknown as dashes and never rounds a partial hit up to 100%', () => {
    expect([null, undefined, NaN, 0, 0.456, 0.996, 1].map(formatHitRate)).toEqual([
      '--',
      '--',
      '--',
      '0%',
      '46%',
      '99%',
      '100%',
    ]);
  });
});
