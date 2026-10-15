# Theo fork: local run and handoff

## Current state (2026-10-16)

The proxy runs on nucbox and is the only LLM gateway for Codex, Claude Code and Hermes on the Mac and nucbox.
CAS is uninstalled (code preserved at Willhong/claude-account-switch `5f7db1d`).

- **Address:** https://llmproxy.hktlabs.com (management UI `/management.html`, OpenAI-compatible base `/v1`,
  Anthropic base `/`). Tailnet only: nucbox k3s Ingress -> EndpointSlice `10.42.0.1:18318` (nucbox cni0 address).
  Domain/ingress details, rollback and the full change log: `~/k8s-lab/llmproxy/HANDOFF.md`.
- **Process:** nucbox systemd user service `theo-proxy` (linger on, `Restart=always`) runs
  `~/.local/share/theo-proxy/bin/cli-proxy-api-strict` (linux/amd64) built from core commit `4cf8c85`.
  Manage with `systemctl --user restart|status theo-proxy`; logs in `~/.local/share/theo-proxy/auths/logs/main.log`.
  The Mac launchd agent and Mac SSH tunnel are removed; Mac copies of credentials are archived as do-not-restore.
- **Routing (core `4cf8c85`):** strict conversation affinity, bindings in `state/conversation-bindings.db`.
  One account per (caller, conversation, provider), so Hermes can mix Claude and Codex in one conversation.
  A conversation moves to another account of the same provider only when its account is cooling down after a
  quota/rate-limit error; other failures fail closed. Image generation/edit requests without a conversation ID are
  one-shot (any account, no binding). See `cli-proxy-api/docs/strict-conversation-routing.md`.
- **Accounts (all with refresh tokens, the proxy is the only refresh owner):** Codex `hongkyungtack` (Pro Lite),
  Codex `hbilly2002` (Pro), Claude `hbilly2002` (separate OAuth login made for the proxy on 2026-10-15).
  Automatic refresh observed for both Codex accounts and Claude. Only one Claude account: no Claude move target.
- **Clients:**
  - Codex (Mac, nucbox): `~/.codex/config.toml` provider `cliproxy` -> domain `/v1`, WebSocket on.
  - Mac `~/.codex/auth.json` is a separate ChatGPT login used only by BB voice transcription and HongCore's
    login check; Codex inference ignores it (provider `cliproxy`). Its token family differs from the proxy's.
  - Claude Code (Mac, nucbox): `~/.claude/settings.json` env `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`
    (proxy client key), `ENABLE_TOOL_SEARCH=true` (without it every MCP schema is inlined and cache is lost).
    claude.ai connectors are disabled while an auth token is set.
  - Hermes (default + 8 profiles): custom provider `llmproxy` with `session_affinity_header: X-Hermes-Session-ID`,
    `chat_completions` transport; model, fallback, auxiliary, MoA and image generation use it.
  - BB sidebar usage (`usage-tracker` plugin) reads the proxy management API at the domain.
- **Cache hit rate / logs:** as before (cache-stats in `state/cache-stats.json`, file logs capped at 200 MB,
  request bodies not logged; error logs do keep request bodies, up to 10 files).

Verified live 2026-10-15/16: new and resumed conversations for Codex CLI, BB Codex/Claude threads on Mac and nucbox,
Claude Code and Hermes CLI keep their account and recall context; cache reuse ~88-99% after the first request;
same-conversation Claude + Codex (Hermes title generation) works; image generation through the proxy works.
Not observed live: an actual quota-triggered account move, Hermes fallback and MoA calls.

BB/Hermes source patches from the earlier experiment are excluded from adoption.
The sections below the next heading record the earlier UI/usage milestone.

## Repositories

- UI fork: https://github.com/Willhong/Cli-Proxy-API-Management-Center
- UI checkout: `/Users/hong-kyungtack/workspace/cli-proxy-console`, branch `feat/theo-quota-ledger`.
- UI upstream starting commit: `390718e`.
- Existing core fork reused: https://github.com/Willhong/CLIProxyAPI
- Core checkout: `/Users/hong-kyungtack/workspace/cli-proxy-api`, branch `feat/theo-console`.
- Core branch starts from upstream `0d18d3b365be000eeaee7de4615f9da596b2059d`; strict conversation routing `22a67b7`,
  cache hit rates `e3e4bef`, per-provider bindings / quota move / one-shot images `4cf8c85`.
- Existing remote core main and all older feature branches are untouched.
- Both branches are pushed to the Willhong forks as new branches. No release or upstream PR was made.

## Running surfaces

- Application: https://llmproxy.hktlabs.com/management.html (tailnet only, management key required).
- The reference preview (`:8424`) and the old Tailscale runtime address (`:8423`) were shut down on 2026-10-15
  and removed from serve-preview. Start the preview again with the commands under Rebuild/restart when needed.
- Runtime directory: nucbox `/home/will/.local/share/theo-proxy` (0700). The Mac directory of the same name now only
  keeps binaries, backups and the management `secrets.json` used by local tools.
- Local keys: `secrets.json` inside that directory (0600). Never put its content in chat, URLs, git or screenshots.
- Runtime config: `config.yaml`; `auths/` holds two Codex and one Claude credential, all with refresh tokens; custom built asset: `static/management.html`.
- `disable-auto-update-panel: true` prevents upstream from replacing this custom build.
- Management and inference both require their own generated keys. The listener binds only nucbox 10.42.0.1:18318.

## First CAS usage verification (2026-10-14, superseded for Codex)

The user authorized the first import/usage check, not the full CLI cutover.
`scripts/import_cas_usage.py` was exercised in dry-run and apply modes. It reads CAS slot
credentials from macOS Keychain (including chunked/gzip Codex entries), preserves CAS state,
and writes only whitelisted access-token/identity fields to isolated 0600 files. No refresh token,
SIWC refresh document or provider API key is copied. The backend read-back confirms four records.

Latest observed remaining quotas (live upstream responses, not fixtures; values change with use):

| Provider / CAS slot | Account | Result |
| --- | --- | --- |
| Claude 1 | hbilly2002@gmail.com | Fable weekly 100%, 5-hour 98%, overall weekly 95% |
| Claude 2 | hongkyungtack@gmail.com | HTTP 403 permission_error: OAuth authentication is currently not allowed for this organization. |
| Codex 1 | hongkyungtack@gmail.com | Weekly remaining 27% |
| Codex 2 | hbilly2002@gmail.com | Weekly remaining 46% |

The rejected organization was not bypassed or refreshed. Do not misdiagnose its 403 as token expiry.
Claude summary is deliberately `--` because one account is unknown; do not hide the failed account
or fabricate a complete aggregate. The actual browser reads “4 credentials / 3 loaded / 1 attention”.
Emails are hidden by default and can be revealed. Fixed the actual `plan_max` label to localized Max,
and show the upstream error detail beside the generic error text.

**Temporary validity:** these are access-only connections. Expiry is preserved in each auth file.
They cannot automatically renew here; that capability is intentionally reserved for the later
refresh-ownership cutover. The script refuses to overwrite existing entries. Do not silently turn
it into a daemon or add refresh tokens while existing clients still own them.

Verification after these UI changes: 1600 tests, lint and production build passed. Browser verified
real identity reveal/hide, localized plan, three successful quotas and the exact 403 message.
Credential files were read back as mode 0600 with no refresh material. CAS active slots remain
Claude 1 / Codex 2. No inference request, client-setting change or CAS switch was performed.

Evidence: `theo-reference/cas-real-usage.json`, `theo-reference/cas-real-usage.png`,
`cas-usage-verify.log` in the originating thread storage.

## Rebuild/restart

UI:

```sh
bun install --frozen-lockfile
bunx tsc --noEmit -p tsconfig.preview.json
bun run verify
python3 scripts/prepare_local.py
```

`prepare_local.py` copies the single-file production build and prepares isolated keys/config on first use.
It never overwrites an existing config. `preview/` is a separate Vite HTML entry and is not included in `dist/index.html`.
For preview links, use ignored `.env.local`: `VITE_THEO_RUNTIME_URL=<runtime origin>/management.html` (no credentials).
Run the preview with `bun run dev --host 127.0.0.1 --port 4518 --strictPort`.

Core (in the sibling checkout):

```sh
GOMAXPROCS=4 go build -p 4 -o <binary-path> ./cmd/server
GOMAXPROCS=4 <binary-path> --config <state-dir>/config.yaml --local-model
```

The live binary is nucbox `~/.local/share/theo-proxy/bin/cli-proxy-api-strict`. Build with
`GOOS=linux GOARCH=amd64 CGO_ENABLED=0`, copy it there, back up the binary and bindings DB, then `systemctl --user restart theo-proxy`.
For the preview only, use the serve-preview skill to publish at the ROOT, then append `/preview/` to the URL.
Its `--path` is a proxy mount, not a browser page path; mounting Vite at `/preview/` strips that prefix and breaks absolute imports.

## Verified

- UI: `bun run verify`: 1600 tests passed, zero failures; ESLint clean; TypeScript and production single-file build passed.
- Preview entry: `bunx tsc --noEmit -p tsconfig.preview.json` passed.
- Added 14 model tests: remaining-vs-used, unknown/non-finite, sums, secondary aggregate, window ordering,
  failed/disabled accounts, mixed windows, monthly-vs-weekly, absent reset dates, masking, empty/loading and locale parity.
- Existing search-focus source test made whitespace-insensitive only; the same two calls/order remain required.
  Browser interaction independently verifies clearing and restored focus.
- Core: compiled from the pinned upstream commit. Full Go suite was not run because Go code was not modified.
- Real HTTP: protected v8 `/config` and `/credentials` return 200 with the local management key. Initially empty; after the approved import `/credentials` lists four active records.
- Actual UI: management login, zero-account state, Ledger/Cards switching, search/clear/focus,
  and empty-state account link reaching the rendered OAuth login page. No provider login was started.
- Preview: 17 browser assertions passed, including provider filter, email hide/show and tooltip masking,
  secondary summary disclosure, truthful refresh notice, populated/empty/idle/loading/error states,
  1920px/390px horizontal overflow, mobile access to the last provider, reduced motion and resource failures.
- Source frame and desktop/mobile/runtime screenshots were visually inspected.

Evidence is retained in `/Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/`:

- `console-verify.log`
- `verify-preview.mjs`
- `theo-reference/browser-checks.json`
- `theo-reference/runtime-checks.json`
- `theo-reference/preview-desktop-settled.png` (use this, not the earlier capture during count animation)
- `theo-reference/preview-mobile.png`
- `theo-reference/runtime-empty.png`
- `theo-reference/theo-18m07.png`, `theo-19m05.png`, `theo-22m18.png`

## What is not done

- Quota-triggered account move is covered by tests only; not yet observed on a real exhausted account.
- Hermes fallback and MoA through the proxy were not exercised live.
- The ChatGPT desktop app's built-in Codex still talks to OpenAI directly; it was not restarted onto the proxy.
- Soonest-reset routing is on hold by the owner's decision. The UI sort is not the backend routing policy.
- WebSocket latency was not benchmarked against HTTP.
- If a client loses its conversation identity (for example a failed ACP `session/load` that falls back to
  `session/new`), the proxy treats it as a new conversation. Not solvable without client changes.
- Per-request account attribution is not logged (usage statistics are off); account checks rely on credential counters and bindings.
- nucbox REA MCP calls fail; unrelated to the proxy.
- The preview is a reference reconstruction, not full behavioral or pixel parity with Theo's private fork.

## Implementation choices made here

- Fork CPAMC for the visible web UI and reuse the existing core fork rather than fork the native VibeProxy wrapper.
- Retain latest upstream API/auth management functionality and the original Cards view.
- Make Ledger and dark the fresh default; mask emails initially.
- Keep preview fixtures out of production and credentials out of both repos.
- Use a separately authenticated local runtime and Tailscale instead of changing current agent endpoints.

The initial screen is accepted. The owner then clarified: “cas 에서 이걸로 전환하려고 하는건데”.
The objective is CAS replacement, not coexistence: reuse CAS-registered accounts, migrate their usable
credentials once, and switch intended CLI clients to this proxy. Permanent CAS/proxy token sync is not
the default design. Inspect source credential formats and running consumers first; ensure only one
owner refreshes a migrated credential. Verify one-account quota/inference before wider cutover.
Do not require fresh login by default; ask only for credentials that cannot actually be reused.
CAS/client backup preservation does not guarantee old refresh tokens remain valid after rotation.
The subsequent request “일단 계정 연결만 먼저 옮겨서 usage 페이지 잘 나오나 보자” authorized
account import and usage verification. On 2026-10-15 the owner asked to move only Codex: refresh tokens
were transferred, CAS Codex slots removed, and the Mac and nucbox Codex clients cut over. Claude stays on CAS.
On 2026-10-15/16 the owner then approved: moving the proxy to nucbox, migrating Claude (new proxy login) and
switching Claude Code on the Mac and nucbox, connecting Hermes and all its profiles, per-provider bindings,
moving off quota-exhausted accounts, one-shot image requests, retiring the old nucbox CLIProxyAPI (port 8317,
archived under nucbox `~/archive/`) and uninstalling CAS.
