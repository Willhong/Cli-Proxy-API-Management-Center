import type { TFunction } from 'i18next';
import type {
  AntigravityQuotaState,
  ClaudeQuotaState,
  CodexQuotaState,
  DevinQuotaState,
  KimiQuotaState,
  MetaQuotaState,
  XaiQuotaState,
} from '@/types';
import type { QuotaCardState } from './providers';
import type { QuotaProviderType } from './providers/types';
import type { QuotaFileEntry } from './logic';

export interface LedgerWindow {
  id: string;
  label: string;
  remaining: number | null;
  resetAtMs?: number | null;
  resetLabel?: string;
  periodHours?: number | null;
}

export function remainingPercent(used: number | null | undefined): number | null {
  return typeof used === 'number' && Number.isFinite(used)
    ? Math.max(0, Math.min(100, 100 - used))
    : null;
}

/** Mask email addresses everywhere in display text, including filenames and tooltips. */
export function maskLedgerIdentity(name: string): string {
  return name.replace(/([^\s@]+)@([^\s@]+)/g, (_match, left: string, right: string) => {
    const prefix = left.match(/^(?:claude|codex|kimi|xai|antigravity)-/i)?.[0] ?? '';
    const local = left.slice(prefix.length);
    const suffix = right.endsWith('.json') ? '.json' : '';
    const domain = suffix ? right.slice(0, -suffix.length) : right;
    const dot = domain.lastIndexOf('.');
    return `${prefix}${local.slice(0, 1)}•••@${domain.slice(0, 1)}•••${dot >= 0 ? domain.slice(dot) : ''}${suffix}`;
  });
}

/** Read only normalized provider states. Never read credentials or raw API payloads here. */
export function ledgerWindows(
  provider: QuotaProviderType,
  quota: QuotaCardState | undefined,
  t: TFunction
): LedgerWindow[] {
  if (quota?.status !== 'success') return [];
  if (provider === 'claude' || provider === 'codex') {
    const windows = (quota as ClaudeQuotaState | CodexQuotaState).windows ?? [];
    return windows
      .map((w) => ({
        ...w,
        label: w.labelKey
          ? t(w.labelKey, 'labelParams' in w ? (w.labelParams ?? {}) : {})
          : w.label,
        remaining: remainingPercent(w.usedPercent),
      }))
      .sort((a, b) => windowRank(provider, a) - windowRank(provider, b));
  }
  if (provider === 'kimi') {
    return ((quota as KimiQuotaState).rows ?? []).map((w) => ({
      id: w.id,
      label: w.labelKey ? t(w.labelKey, w.labelParams ?? {}) : (w.label ?? w.id),
      remaining: w.limit > 0 ? remainingPercent((w.used / w.limit) * 100) : null,
      resetAtMs: w.resetAtMs,
      resetLabel: w.resetHint,
      periodHours: w.periodHours,
    }));
  }
  if (provider === 'xai') {
    const b = (quota as XaiQuotaState).billing;
    // A monthly billing period is not a weekly quota window.
    return b?.periodType === 'weekly'
      ? [
          {
            id: 'weekly',
            label: t('quota_ledger.weekly'),
            remaining: remainingPercent(b.usagePercent),
            resetAtMs: b.resetAtMs,
            periodHours: b.periodHours ?? 168,
          },
        ]
      : [];
  }
  if (provider === 'devin') {
    return ((quota as DevinQuotaState).windows ?? []).map((w) => ({
      ...w,
      label: w.label ?? w.id,
      remaining: w.remainingPercent === null ? null : remainingPercent(100 - w.remainingPercent),
    }));
  }
  if (provider === 'meta') {
    return ((quota as MetaQuotaState).data?.windows ?? []).map((w) => ({
      id: w.id,
      label: w.id === 'weekly' ? t('quota_ledger.weekly') : t('quota_ledger.session'),
      remaining: remainingPercent(w.usedPercent),
      resetAtMs: w.resetAt === undefined ? null : w.resetAt * 1000,
      periodHours: w.durationMinutes === undefined ? null : w.durationMinutes / 60,
    }));
  }
  return ((quota as AntigravityQuotaState).groups ?? []).flatMap((group) =>
    group.buckets.map((w) => ({
      id: `${group.id}:${w.id}`,
      label: w.label,
      remaining: remainingPercent(100 - w.remainingFraction * 100),
      resetAtMs: w.resetAtMs,
      resetLabel: w.resetTime,
      periodHours: w.periodHours,
    }))
  );
}

function windowRank(provider: QuotaProviderType, w: LedgerWindow): number {
  if (provider === 'claude' && /fable|iguana_necktie/i.test(`${w.id} ${w.label}`)) return 0;
  if (provider === 'claude' && w.periodHours === 5) return 1;
  if (w.periodHours === 168 || /^(weekly|seven_day|seven-day)$/.test(w.id))
    return provider === 'claude' ? 2 : 1;
  if (w.periodHours === 5) return 2;
  return 3;
}

export function summarizeLedger(
  entries: QuotaFileEntry[],
  quotaFor: (entry: QuotaFileEntry) => QuotaCardState | undefined,
  t: TFunction,
  now: number,
  preferredWindowId?: string
) {
  const provider = entries[0]?.type;
  const active = entries.filter((entry) => !entry.file.disabled);
  const windows = active.map((entry) => ledgerWindows(entry.type, quotaFor(entry), t));
  const candidates = windows.flat();
  const candidate = preferredWindowId
    ? candidates.find((w) => w.id === preferredWindowId)
    : (candidates.find(
        (w) => provider === 'claude' && /fable|iguana_necktie/i.test(`${w.id} ${w.label}`)
      ) ??
      candidates.find(
        (w) => w.periodHours === 168 || /^(weekly|seven_day|seven-day)$/.test(w.id)
      ) ??
      candidates[0]);
  // A single summary must compare the same window, not whichever each account happens to expose.
  const selected = windows.map((items) => items.find((w) => w.id === candidate?.id));
  const known = selected.filter((w) => w?.remaining !== null && w?.remaining !== undefined);
  const resets = selected
    .map((w) => w?.resetAtMs)
    .filter((ms): ms is number => typeof ms === 'number' && Number.isFinite(ms) && ms > now);
  return {
    windowId: candidate?.id,
    label: candidate?.label ?? t('quota_ledger.not_loaded'),
    count: active.length,
    disabledCount: entries.length - active.length,
    knownCount: known.length,
    remaining:
      known.length === active.length && active.length > 0
        ? known.reduce((sum, w) => sum + (w?.remaining ?? 0), 0)
        : null,
    capacity: active.length * 100,
    segments: selected.map((w) => w?.remaining ?? null),
    resetAtMs: resets.length ? Math.min(...resets) : null,
  };
}
