import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { IconRefreshCw } from '@/components/ui/icons';
import { getAuthFileIcon, getTypeLabel } from '@/features/authFiles/constants';
import { getQuotaCacheKey, getQuotaDisplayName } from '@/utils/quota/identity';
import { buildResetDisplay, resolveQuotaErrorMessage } from '@/utils/quota';
import { useNow } from '@/hooks/useNow';
import type { ResolvedTheme } from '@/types';
import { QUOTA_TAB_ORDER } from '../constants';
import type { QuotaFileEntry } from '../logic';
import type { QuotaCardState } from '../providers';
import {
  ledgerWindows,
  maskLedgerIdentity,
  summarizeLedger,
  type LedgerWindow,
} from '../ledgerModel';
import type { CacheStatsCounts, CacheStatsSnapshot } from '@/services/api';
import { cacheStatsFor, formatHitRate, sumCacheStats } from '../cacheStatsModel';
import styles from './QuotaLedger.module.scss';

export interface QuotaLedgerProps {
  entries: QuotaFileEntry[];
  quotaFor: (entry: QuotaFileEntry) => QuotaCardState | undefined;
  resolvedTheme: ResolvedTheme;
  showEmails: boolean;
  /** Prompt-cache statistics for the selected window; null when unavailable. */
  cacheStats?: CacheStatsSnapshot | null;
  cacheWindowLabel?: string;
  canRefresh: boolean;
  onRefresh: (entry: QuotaFileEntry) => void;
  /** Fixed only in the reference preview; production uses the shared clock. */
  nowOverride?: number;
}

function fillColor(value: number | null) {
  return value === null
    ? 'transparent'
    : value >= 70
      ? 'var(--success-color)'
      : value >= 30
        ? 'var(--quota-medium-color)'
        : 'var(--danger-color)';
}

function Meter({ value, label }: { value: number | null; label: string }) {
  return (
    <div
      className={styles.track}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value ?? undefined}
      aria-valuetext={value === null ? '--' : `${Math.round(value)}%`}
    >
      <span style={{ width: `${value ?? 0}%`, background: fillColor(value) }} />
    </div>
  );
}

function CacheHit({
  stats,
  windowLabel,
  className,
}: {
  stats: CacheStatsCounts | undefined;
  windowLabel: string;
  className: string;
}) {
  const { t, i18n } = useTranslation();
  const number = new Intl.NumberFormat(i18n.resolvedLanguage);
  const title = stats?.input_tokens
    ? t('quota_ledger.cache_hint', {
        window: windowLabel,
        cached: number.format(stats.cache_read_tokens),
        input: number.format(stats.input_tokens),
      })
    : t('quota_ledger.cache_none', { window: windowLabel });
  return (
    <span className={className} title={title}>
      {t('quota_ledger.cache_hit')} <strong>{formatHitRate(stats?.hit_rate)}</strong>
      {stats && stats.requests > 0 && (
        <> · {t('quota_ledger.cache_requests', { count: stats.requests })}</>
      )}
    </span>
  );
}

function Reset({
  window: w,
  now,
}: {
  window: Pick<LedgerWindow, 'resetAtMs' | 'resetLabel'>;
  now: number;
}) {
  const { t, i18n } = useTranslation();
  const display = buildResetDisplay(w.resetLabel, w.resetAtMs, now, i18n.resolvedLanguage);
  return (
    <span className={styles.reset}>
      {display ? (
        <>
          {display.relative && <>{display.relative} · </>}
          {display.absolute}
        </>
      ) : (
        t('quota_ledger.reset_unknown')
      )}
    </span>
  );
}

export function QuotaLedgerSummary({
  entries,
  quotaFor,
  resolvedTheme,
  nowOverride,
  cacheStats,
  cacheWindowLabel = '',
}: Pick<
  QuotaLedgerProps,
  'entries' | 'quotaFor' | 'resolvedTheme' | 'nowOverride' | 'cacheStats' | 'cacheWindowLabel'
>) {
  const { t } = useTranslation();
  const tick = useNow();
  const now = nowOverride ?? tick;
  const [expanded, setExpanded] = useState<string[]>([]);
  const groups = QUOTA_TAB_ORDER.map((type) => ({
    type,
    entries: entries.filter((e) => e.type === type),
  })).filter((group) => group.entries.length > 0);
  if (!groups.length) return null;
  return (
    <section className={styles.summaries} aria-label={t('quota_ledger.provider_summary')}>
      {groups.map((group) => {
        const summary = summarizeLedger(group.entries, quotaFor, t, now);
        const secondaryWindow =
          group.type === 'claude'
            ? group.entries
                .flatMap((entry) => ledgerWindows(entry.type, quotaFor(entry), t))
                .find(
                  (w) =>
                    w.periodHours === 168 &&
                    /^(weekly|seven_day|seven-day)$/.test(w.id) &&
                    w.id !== summary.windowId
                )
            : undefined;
        const secondary = secondaryWindow
          ? summarizeLedger(group.entries, quotaFor, t, now, secondaryWindow.id)
          : null;
        return (
          <article className={styles.summary} key={group.type} data-provider-summary={group.type}>
            <header>
              <span className={styles.provider}>
                <img src={getAuthFileIcon(group.type, resolvedTheme) ?? undefined} alt="" />
                {getTypeLabel(t, group.type)}
              </span>
              <span className={styles.count}>
                {t('quota_management.meta_credentials', { count: group.entries.length })}
              </span>
            </header>
            <div className={styles.summaryLabel}>{summary.label}</div>
            <div className={styles.total} title={t('quota_ledger.sum_hint')}>
              <strong>
                {summary.remaining === null ? '--' : `${Math.round(summary.remaining)}%`}
              </strong>
              <span>{t('quota_ledger.of_capacity', { capacity: summary.capacity })}</span>
            </div>
            <div className={styles.segments} aria-label={t('quota_ledger.sum_hint')}>
              {summary.segments.map((value, index) => (
                <div key={index} className={styles.segment}>
                  <span style={{ width: `${value ?? 0}%`, background: fillColor(value) }} />
                </div>
              ))}
            </div>
            <Reset window={summary} now={now} />
            {cacheStats !== undefined && (
              <CacheHit
                className={styles.cacheSummary}
                stats={
                  cacheStats
                    ? sumCacheStats(group.entries.map((e) => cacheStatsFor(e.file, cacheStats)))
                    : undefined
                }
                windowLabel={cacheWindowLabel}
              />
            )}
            {secondary && (
              <div className={styles.secondary}>
                <span>
                  {secondary.label}{' '}
                  <strong>
                    {secondary.remaining === null ? '--' : `${Math.round(secondary.remaining)}%`}
                  </strong>
                </span>
                <button
                  className={styles.textAction}
                  aria-expanded={expanded.includes(group.type)}
                  onClick={() =>
                    setExpanded((current) =>
                      current.includes(group.type)
                        ? current.filter((type) => type !== group.type)
                        : [...current, group.type]
                    )
                  }
                >
                  {t(expanded.includes(group.type) ? 'quota_ledger.hide' : 'quota_ledger.show')}
                </button>
                {expanded.includes(group.type) && (
                  <div className={styles.secondaryDetail}>
                    <Meter
                      value={
                        secondary.remaining === null || !secondary.capacity
                          ? null
                          : (secondary.remaining / secondary.capacity) * 100
                      }
                      label={secondary.label}
                    />
                    <Reset window={secondary} now={now} />
                  </div>
                )}
              </div>
            )}
            {summary.knownCount < summary.count && (
              <span className={styles.note}>
                {t('quota_ledger.known', { known: summary.knownCount, count: summary.count })}
              </span>
            )}
            {summary.disabledCount > 0 && (
              <span className={styles.note}>
                {t('quota_ledger.disabled_count', { count: summary.disabledCount })}
              </span>
            )}
          </article>
        );
      })}
    </section>
  );
}

function LedgerRow({
  entry,
  quota,
  showEmails,
  cacheStats,
  cacheWindowLabel,
  canRefresh,
  onRefresh,
  now,
}: {
  entry: QuotaFileEntry;
  quota: QuotaCardState | undefined;
  resolvedTheme: ResolvedTheme;
  showEmails: boolean;
  cacheStats?: CacheStatsSnapshot | null;
  cacheWindowLabel: string;
  canRefresh: boolean;
  onRefresh: () => void;
  now: number;
}) {
  const { t } = useTranslation();
  const [showAll, setShowAll] = useState(false);
  const windows = ledgerWindows(entry.type, quota, t);
  const fullName = getQuotaDisplayName(entry.file);
  const email = entry.file.email?.trim();
  const name = showEmails
    ? email && !fullName.includes(email)
      ? `${email} · ${fullName}`
      : fullName
    : maskLedgerIdentity(fullName);
  const rawPlan =
    quota && 'planType' in quota && typeof quota.planType === 'string' ? quota.planType : '';
  const plan =
    entry.type === 'claude' && rawPlan.startsWith('plan_') ? t(`claude_quota.${rawPlan}`) : rawPlan;
  const status = quota?.status ?? 'idle';
  return (
    <article className={styles.row} data-ledger-row={entry.type} aria-busy={status === 'loading'}>
      <div className={styles.identity}>
        <span className={styles.filename} title={name}>
          {name}
        </span>
        <span className={styles.plan}>
          {plan}
          {entry.file.disabled && <> · {t('quota_ledger.disabled')}</>}
        </span>
        {cacheStats !== undefined && (
          <CacheHit
            className={styles.cacheRow}
            stats={cacheStatsFor(entry.file, cacheStats)}
            windowLabel={cacheWindowLabel}
          />
        )}
      </div>
      <div className={styles.windows}>
        {status === 'success' && windows.length > 0 ? (
          (showAll ? windows : windows.slice(0, 3)).map((w) => (
            <div className={styles.window} key={w.id}>
              <div className={styles.windowHeading}>
                <span>{w.label}</span>
                <strong>{w.remaining === null ? '--' : `${Math.round(w.remaining)}%`}</strong>
              </div>
              <Meter value={w.remaining} label={`${w.label} ${t('quota_ledger.remaining')}`} />
              <Reset window={w} now={now} />
            </div>
          ))
        ) : (
          <div className={styles.status} role={status === 'error' ? 'alert' : 'status'}>
            {status === 'error' ? (
              <>
                <span>
                  {resolveQuotaErrorMessage(
                    t,
                    quota?.errorStatus,
                    quota?.error ?? t('common.unknown_error')
                  )}
                </span>
                {quota?.error && <small className={styles.note}>{quota.error}</small>}
              </>
            ) : (
              t(`quota_ledger.${status === 'success' ? 'no_windows' : status}`)
            )}
          </div>
        )}
        {windows.length > 3 && (
          <button className={styles.textAction} onClick={() => setShowAll(!showAll)}>
            {t(showAll ? 'quota_ledger.less' : 'quota_ledger.more', { count: windows.length - 3 })}
          </button>
        )}
      </div>
      <button
        className={styles.refresh}
        disabled={!canRefresh || entry.file.disabled || status === 'loading'}
        onClick={onRefresh}
        aria-label={`${t('auth_files.quota_refresh_single')} · ${name}`}
      >
        <IconRefreshCw size={13} className={status === 'loading' ? styles.spinning : undefined} />
        {t('auth_files.quota_refresh_single')}
      </button>
    </article>
  );
}

export function QuotaLedger(props: QuotaLedgerProps) {
  const { t } = useTranslation();
  const tick = useNow();
  const now = props.nowOverride ?? tick;
  return (
    <div className={styles.ledger}>
      {QUOTA_TAB_ORDER.map((type) => {
        const entries = props.entries.filter((e) => e.type === type);
        if (!entries.length) return null;
        return (
          <section key={type} className={styles.group} aria-label={getTypeLabel(t, type)}>
            <h2>
              {getTypeLabel(t, type)} <span>{entries.length}</span>
            </h2>
            {entries.map((entry) => (
              <LedgerRow
                key={getQuotaCacheKey(entry.file)}
                entry={entry}
                quota={props.quotaFor(entry)}
                resolvedTheme={props.resolvedTheme}
                showEmails={props.showEmails}
                cacheStats={props.cacheStats}
                cacheWindowLabel={props.cacheWindowLabel ?? ''}
                canRefresh={props.canRefresh}
                onRefresh={() => props.onRefresh(entry)}
                now={now}
              />
            ))}
          </section>
        );
      })}
    </div>
  );
}
