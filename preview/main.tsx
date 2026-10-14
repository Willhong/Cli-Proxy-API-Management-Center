import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import i18n from '../src/i18n';
import { QuotaHeader } from '../src/features/quota/components/QuotaHeader';
import { QuotaLedger, QuotaLedgerSummary } from '../src/features/quota/components/QuotaLedger';
import { ProviderTabs } from '../src/features/authFiles/components/ProviderTabs';
import {
  IconChevronLeft,
  IconRefreshCw,
  IconKey,
  IconSidebarDashboard,
  IconSidebarQuickStart,
  IconSidebarProviders,
  IconSidebarAuthFiles,
  IconSidebarOauth,
  IconSidebarQuota,
  IconSidebarLogs,
  IconSidebarConfig,
  IconSidebarPlugins,
  IconSidebarStore,
  IconSidebarSystem,
} from '../src/components/ui/icons';
import { INLINE_LOGO_JPEG } from '../src/assets/logoInline';
import type { QuotaCardState } from '../src/features/quota/providers';
import { entries, quotas, fixtureNow } from './fixtures';
import '../src/styles/global.scss';
import '../src/styles/theo.scss';
import './preview.scss';

void i18n.changeLanguage('en');
document.documentElement.setAttribute('data-theme', 'dark');
const runtimeBase = import.meta.env.VITE_THEO_RUNTIME_URL || '/management.html';
const nav = [
  {
    title: 'OPERATE',
    items: [
      ['Dashboard', '/'],
      ['Quick Start', '/quick-start'],
    ],
  },
  {
    title: 'GATEWAY',
    items: [
      ['AI Providers', '/ai-providers'],
      ['Auth Files', '/auth-files'],
      ['OAuth Login', '/oauth'],
    ],
  },
  {
    title: 'OBSERVE',
    items: [
      ['Quota Management', '/quota'],
      ['Logs Viewer', '/logs'],
    ],
  },
  {
    title: 'CONTROL',
    items: [
      ['Config Panel', '/config'],
      ['Plugins', '/plugins'],
      ['Plugin Store', '/plugin-store'],
      ['Management Center', '/system'],
    ],
  },
];
const icons = [
  [IconSidebarDashboard, IconSidebarQuickStart],
  [IconSidebarProviders, IconSidebarAuthFiles, IconSidebarOauth],
  [IconSidebarQuota, IconSidebarLogs],
  [IconSidebarConfig, IconSidebarPlugins, IconSidebarStore, IconSidebarSystem],
];
export function Preview() {
  const [tab, setTab] = useState('all');
  const [showEmails, setShowEmails] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [state, setState] = useState('populated');
  const [notice, setNotice] = useState('');
  const [reference, setReference] = useState(false);
  const counts = Object.fromEntries(
    ['claude', 'antigravity', 'codex', 'xai', 'kimi'].map((type) => [
      type,
      entries.filter((e) => e.type === type).length,
    ])
  );
  const visible = state === 'empty' ? [] : entries.filter((e) => tab === 'all' || e.type === tab);
  const quotaFor = (e: (typeof entries)[number]): QuotaCardState | undefined =>
    state === 'error'
      ? { status: 'error', error: 'Preview: quota request failed. No provider request was sent.' }
      : state === 'idle'
        ? undefined
        : state === 'loading'
          ? { status: 'loading' }
          : quotas[e.file.name];
  const previewRefresh = () => {
    setNotice('미리보기 데이터야. 실제 계정 조회나 한도 초기화는 실행하지 않았어.');
  };
  return (
    <>
      <div className="preview-banner">
        <strong>REFERENCE PREVIEW</strong>
        <span>영상 재현용 샘플 · 실제 계정 아님</span>
        <select aria-label="Preview state" value={state} onChange={(e) => setState(e.target.value)}>
          <option value="populated">Populated</option>
          <option value="empty">Empty</option>
          <option value="idle">Not loaded</option>
          <option value="loading">Loading</option>
          <option value="error">Error</option>
        </select>
        <button onClick={() => setReference(!reference)}>
          {reference ? '구현 화면' : '영상 원본'}
        </button>
        <a href={`${runtimeBase}#/quota`} target="_blank" rel="noreferrer">
          실제 앱 ↗
        </a>
      </div>
      {reference ? (
        <main className="reference-image">
          <img src="./theo-18m07.png" alt="Theo video frame at 18:07; original reference" />
          <p>영상 18:07 원본. 카메라 오버레이에 가려진 부분은 확인하지 못했어.</p>
        </main>
      ) : (
        <div className={`reference-shell ${collapsed ? 'is-collapsed' : ''}`}>
          <aside className="reference-sidebar">
            <div className="reference-brand">
              <img src={INLINE_LOGO_JPEG} alt="" />
              {!collapsed && (
                <span>
                  <b>CPAMC</b>
                  <small>CLI Proxy API Console</small>
                </span>
              )}
            </div>
            <nav>
              {nav.map((group, g) => (
                <section key={group.title}>
                  {!collapsed && <h2>{group.title}</h2>}
                  {group.items.map(([label, route], index) => {
                    const Icon = icons[g][index];
                    return (
                      <a
                        key={label}
                        className={route === '/quota' ? 'selected' : ''}
                        href={route === '/quota' ? '#' : `${runtimeBase}#${route}`}
                        title={label}
                        onClick={
                          route === '/quota'
                            ? (e) => {
                                e.preventDefault();
                                setTab('all');
                              }
                            : undefined
                        }
                      >
                        <Icon size={17} />
                        {!collapsed && <span>{label}</span>}
                        {!collapsed && label === 'Auth Files' && <small>10</small>}
                      </a>
                    );
                  })}
                </section>
              ))}
            </nav>
          </aside>
          <button
            className="reference-collapse"
            aria-label="Toggle sidebar"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <IconSidebarDashboard size={13} /> : <IconChevronLeft size={13} />}
          </button>
          <main className="reference-main">
            <QuotaHeader
              totalCount={state === 'empty' ? 0 : entries.length}
              loadedCount={state === 'populated' ? entries.length : 0}
              attentionCount={state === 'error' ? entries.length : 0}
              refreshing={state === 'loading'}
              disableControls={false}
              onRefreshAll={previewRefresh}
              showEmails={showEmails}
              onToggleEmails={() => setShowEmails(!showEmails)}
            />
            <div className="reference-tabs">
              <ProviderTabs
                types={['all', ...Object.keys(counts)]}
                counts={{ all: entries.length, ...counts }}
                active={tab}
                resolvedTheme="dark"
                onChange={setTab}
              />
              <span className="reference-view">Ledger⌄</span>
            </div>
            {notice && (
              <div className="preview-notice" role="status">
                {notice}
                <button onClick={() => setNotice('')}>닫기</button>
              </div>
            )}
            <QuotaLedgerSummary
              entries={visible}
              quotaFor={quotaFor}
              resolvedTheme="dark"
              nowOverride={fixtureNow}
            />
            {!visible.length && (
              <section className="preview-empty">
                <IconKey size={28} />
                <h2>No credentials yet</h2>
                <p>계정을 연결하면 제공자별 잔여 한도가 여기에 표시돼.</p>
                <a href={`${runtimeBase}#/oauth`}>계정 연결 ↗</a>
              </section>
            )}
            <QuotaLedger
              entries={visible}
              quotaFor={quotaFor}
              resolvedTheme="dark"
              showEmails={showEmails}
              canRefresh={state !== 'loading'}
              onRefresh={previewRefresh}
              nowOverride={fixtureNow}
            />
            <footer className="preview-foot">
              <IconRefreshCw size={12} /> 이 페이지는 시각·상태 검증용이며 네트워크로 계정을
              조회하지 않아. 실서비스는 별도 인증이 필요해.
            </footer>
          </main>
        </div>
      )}
    </>
  );
}
createRoot(document.getElementById('root')!).render(<Preview />);
