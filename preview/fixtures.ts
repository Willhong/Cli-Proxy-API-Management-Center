import type {
  ClaudeQuotaState,
  CodexQuotaState,
  KimiQuotaState,
  XaiQuotaState,
} from '../src/types';
import type { QuotaFileEntry } from '../src/features/quota/logic';

// Synthetic fixture identities. Never import this module from src/.
// Visible percentages follow the reference; unseen rows are illustrative, not recovered data.
export const fixtureNow = Date.parse('2026-09-11T20:30:00Z');
const reset = (days: number) => fixtureNow + days * 86400000;
export const entries: QuotaFileEntry[] = [];
export const quotas: Record<string, ClaudeQuotaState | CodexQuotaState | KimiQuotaState | XaiQuotaState> = {};
[58, 100, 100, 51, 100].forEach((remaining, index) => {
  const name = `claude-demo${index + 1}@example.invalid.json`;
  entries.push({ type: 'claude', file: { name, type: 'claude', provider: 'claude' } });
  quotas[name] = {
    status: 'success',
    planType: 'max',
    windows: [
      {
        id: 'fable',
        label: '7-day Fable 5',
        usedPercent: 100 - remaining,
        resetLabel: '',
        resetAtMs: reset(index === 3 ? 1 : index + 2),
        periodHours: 168,
      },
      {
        id: 'five-hour',
        label: '5-hour limit',
        usedPercent: index === 3 ? 1 : 0,
        resetLabel: index === 3 ? '' : 'No reset pending',
        resetAtMs: index === 3 ? fixtureNow + 10800000 : null,
        periodHours: 5,
      },
      {
        id: 'weekly',
        label: '7-day limit',
        usedPercent: [21, 0, 0, 25, 0][index],
        resetLabel: '',
        resetAtMs: reset(index === 3 ? 1 : index + 2),
        periodHours: 168,
      },
    ],
  } satisfies ClaudeQuotaState;
});
[8, 5, 4].forEach((remaining, index) => {
  const name = `codex-demo${index + 1}@example.invalid.json`;
  entries.push({ type: 'codex', file: { name, type: 'codex', provider: 'codex' } });
  quotas[name] = {
    status: 'success',
    planType: 'pro',
    windows: [
      {
        id: 'weekly',
        label: 'Weekly limit',
        usedPercent: 100 - remaining,
        resetLabel: '',
        resetAtMs: reset(index + 2),
        periodHours: 168,
      },
      {
        id: 'five-hour',
        label: '5-hour limit',
        usedPercent: 0,
        resetLabel: 'No reset pending',
        periodHours: 5,
      },
    ],
  } satisfies CodexQuotaState;
});
entries.push({
  type: 'xai',
  file: { name: 'xai-demo@example.invalid.json', type: 'xai', provider: 'xai' },
});
quotas['xai-demo@example.invalid.json'] = {
  status: 'success',
  billing: {
    mode: 'billing',
    periodType: 'weekly',
    usagePercent: null,
    resetAtMs: reset(5),
    periodHours: 168,
    productUsage: [],
    monthlyLimitCents: null,
    usedCents: null,
    includedUsedCents: null,
    onDemandCapCents: null,
    onDemandUsedCents: null,
    onDemandUsedPercent: null,
    usedPercent: null,
  },
} satisfies XaiQuotaState;
entries.push({
  type: 'kimi',
  file: { name: 'kimi-demo@example.invalid.json', type: 'kimi', provider: 'kimi' },
});
quotas['kimi-demo@example.invalid.json'] = {
  status: 'success',
  rows: [
    {
      id: 'weekly',
      label: 'Weekly limit',
      used: 0,
      limit: 100,
      resetAtMs: reset(5),
      periodHours: 168,
    },
  ],
} satisfies KimiQuotaState;
