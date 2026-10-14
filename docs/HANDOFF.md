# Theo fork: local run and handoff

## Repositories

- UI fork: https://github.com/Willhong/Cli-Proxy-API-Management-Center
- UI checkout: `/Users/hong-kyungtack/workspace/cli-proxy-console`, branch `feat/theo-quota-ledger`.
- UI upstream starting commit: `390718e`.
- Existing core fork reused: https://github.com/Willhong/CLIProxyAPI
- Core checkout: `/Users/hong-kyungtack/workspace/cli-proxy-api`, branch `feat/theo-console`.
- Core branch starts from upstream `0d18d3b365be000eeaee7de4615f9da596b2059d`; no Go source changes.
- Existing remote core main and all older feature branches are untouched.
- The UI customization is local; no push, release, or upstream PR was requested or performed.

## Running surfaces

- Reference preview: https://macbookpro.tail29b79c.ts.net:8424/preview/
- Actual application: https://macbookpro.tail29b79c.ts.net:8423/management.html#/quota
- Both are tailnet-only. The actual application still requires a management key.
- The preview displays synthetic data and offers original-frame/state comparisons; it is not an account connection.
- Actual provider account count is zero. No existing Codex/Claude/proxy credentials or client configurations were read/imported/changed.
- Local runtime directory: `/Users/hong-kyungtack/.local/share/theo-proxy` (0700).
- Local keys: `secrets.json` inside that directory (0600). Never put its content in chat, URLs, git or screenshots.
- Runtime config: `config.yaml`; separate empty `auths/`; custom built asset: `static/management.html`.
- `disable-auto-update-panel: true` prevents upstream from replacing this custom build.
- Management and inference both require their own generated keys. The listener binds only 127.0.0.1:18318.
- Serve-preview registration names: `theo-proxy-preview`, `theo-proxy-runtime`.
- A temporary incorrect preview mount was removed; port 8423 now intentionally points to the real runtime.

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

Current binary is `/Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/cli-proxy-api`.
Use the serve-preview skill to publish at the ROOT, then append `/preview/` or `/management.html` to the URL.
Its `--path` is a proxy mount, not a browser page path; mounting Vite at `/preview/` strips that prefix and breaks absolute imports.

## Verified

- UI: `bun run verify`: 1600 tests passed, zero failures; ESLint clean; TypeScript and production single-file build passed.
- Preview entry: `bunx tsc --noEmit -p tsconfig.preview.json` passed.
- Added 14 model tests: remaining-vs-used, unknown/non-finite, sums, secondary aggregate, window ordering,
  failed/disabled accounts, mixed windows, monthly-vs-weekly, absent reset dates, masking, empty/loading and locale parity.
- Existing search-focus source test made whitespace-insensitive only; the same two calls/order remain required.
  Browser interaction independently verifies clearing and restored focus.
- Core: compiled from the pinned upstream commit. Full Go suite was not run because Go code was not modified.
- Real HTTP: protected v8 `/config` and `/credentials` return 200 with the local management key; credentials are empty.
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

- Owner visual acceptance, provider OAuth login, live provider quota fetch and inference have not been performed.
- No soonest-reset routing algorithm has been implemented. The UI sort is not the backend routing policy.
- WebSocket behavior was not modified or benchmarked; the current core already has support but is not authenticated here.
- Session affinity was not changed. Do not enable it or import old credentials as if already approved.
- No public deployment, release or auto-start service was installed.
- The preview is a reference reconstruction, not full behavioral or pixel parity with Theo's private fork.

## Implementation choices made here

- Fork CPAMC for the visible web UI and reuse the existing core fork rather than fork the native VibeProxy wrapper.
- Retain latest upstream API/auth management functionality and the original Cards view.
- Make Ledger and dark the fresh default; mask emails initially.
- Keep preview fixtures out of production and credentials out of both repos.
- Use a separately authenticated local runtime and Tailscale instead of changing current agent endpoints.

The next user-facing step is to review the reference preview. If accepted, connect an account in the real
instance with the owner performing provider login; then verify actual quota observations before touching routing.
