import { describe, expect, test } from 'bun:test';
import type { TFunction } from 'i18next';
import type { ClaudeQuotaState, CodexQuotaState, XaiQuotaState } from '../src/types';
import type { QuotaFileEntry } from '../src/features/quota/logic';
import {
  ledgerWindows,
  maskLedgerIdentity,
  remainingPercent,
  summarizeLedger,
} from '../src/features/quota/ledgerModel';
import { entries, quotas, fixtureNow } from '../preview/fixtures';
import { readFileSync } from 'node:fs';

const t = ((key: string) => key) as TFunction;
const claude = entries.filter((entry) => entry.type === 'claude');
const getQuota = (entry: QuotaFileEntry) => quotas[entry.file.name];

describe('Theo ledger view model', () => {
  test('remaining is the inverse of used, including boundaries', () => {
    expect([0, 42, 100, 120, -5].map(remainingPercent)).toEqual([100, 58, 0, 0, 100]);
  });
  test('unknown and non-finite values are not reported as zero or full quota', () => {
    expect([null, undefined, NaN, Infinity].map(remainingPercent)).toEqual([
      null,
      null,
      null,
      null,
    ]);
  });
  test('reproduces the reference sums from synthetic accounts', () => {
    const c = summarizeLedger(claude, getQuota, t, fixtureNow);
    expect(c.remaining).toBe(409);
    expect(c.capacity).toBe(500);
    expect(c.segments).toEqual([58, 100, 100, 51, 100]);
    const codex = summarizeLedger(
      entries.filter((e) => e.type === 'codex'),
      getQuota,
      t,
      fixtureNow
    );
    expect(codex.remaining).toBe(17);
    expect(codex.capacity).toBe(300);
  });
  test('secondary aggregate does not replace the primary Fable window', () => {
    expect(summarizeLedger(claude, getQuota, t, fixtureNow, 'weekly').remaining).toBe(454);
    expect(summarizeLedger(claude, getQuota, t, fixtureNow).windowId).toBe('fable');
  });
  test('Claude row order matches the reference: model, 5h, overall week', () => {
    expect(ledgerWindows('claude', getQuota(claude[0]), t).map((w) => w.id)).toEqual([
      'fable',
      'five-hour',
      'weekly',
    ]);
  });
  test('unknown xAI remaining stays unknown despite a known reset date', () => {
    const xai = entries.filter((e) => e.type === 'xai');
    expect(summarizeLedger(xai, getQuota, t, fixtureNow)).toMatchObject({
      remaining: null,
      capacity: 100,
      knownCount: 0,
    });
  });
  test('partial failure cannot produce an apparently complete total', () => {
    const result = summarizeLedger(
      claude,
      (e) => (e === claude[0] ? { status: 'error', error: 'offline' } : getQuota(e)),
      t,
      fixtureNow
    );
    expect(result.remaining).toBeNull();
    expect(result.knownCount).toBe(4);
    expect(result.capacity).toBe(500);
  });
  test('disabled accounts are excluded from usable capacity and total', () => {
    const disabled = claude.map((e, index) => ({
      ...e,
      file: { ...e.file, disabled: index === 0 },
    }));
    expect(summarizeLedger(disabled, getQuota, t, fixtureNow)).toMatchObject({
      remaining: 351,
      capacity: 400,
      disabledCount: 1,
    });
  });
  test('does not combine different window IDs as if they were the same quota', () => {
    const mismatch: ClaudeQuotaState = {
      status: 'success',
      windows: [
        { id: 'other-model', label: 'Other', usedPercent: 0, resetLabel: '', periodHours: 168 },
      ],
    };
    expect(
      summarizeLedger(claude, (e) => (e === claude[0] ? mismatch : getQuota(e)), t, fixtureNow)
        .remaining
    ).toBeNull();
  });
  test('a monthly xAI billing cycle is not a weekly quota', () => {
    const raw = quotas['xai-demo@example.invalid.json'] as XaiQuotaState;
    const monthly = { ...raw, billing: { ...raw.billing!, periodType: 'monthly' as const } };
    expect(ledgerWindows('xai', monthly, t)).toEqual([]);
  });
  test('window without a reset still renders its remaining percentage', () => {
    const state: CodexQuotaState = {
      status: 'success',
      windows: [
        { id: 'weekly', label: 'Weekly', usedPercent: 30, resetLabel: '', resetAtMs: null },
      ],
    };
    expect(ledgerWindows('codex', state, t)[0]).toMatchObject({ remaining: 70, resetAtMs: null });
  });
  test('masking applies to filenames and appended display identities', () => {
    const name = 'claude-alice@example.com.json · bob@another.dev';
    expect(maskLedgerIdentity(name)).toBe('claude-a•••@e•••.com.json · b•••@a•••.dev');
    expect(maskLedgerIdentity('opaque-account-42.json')).toBe('opaque-account-42.json');
  });
  test('idle and loading have no fabricated windows', () => {
    expect(ledgerWindows('claude', undefined, t)).toEqual([]);
    expect(ledgerWindows('claude', { status: 'loading' }, t)).toEqual([]);
    expect(summarizeLedger([], () => undefined, t, fixtureNow).remaining).toBeNull();
  });
  test('all supported locales contain the ledger keys', () => {
    const languages = ['en', 'ko', 'zh-CN', 'zh-TW', 'ru', 'vi'];
    const keySets = languages.map((lang) =>
      Object.keys(
        JSON.parse(
          readFileSync(new URL(`../src/i18n/locales/${lang}.json`, import.meta.url), 'utf8')
        ).quota_ledger
      ).sort()
    );
    for (const keys of keySets) expect(keys).toEqual(keySets[0]);
  });
});
