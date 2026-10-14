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
- Four CAS accounts are registered for usage verification: Claude slots 1/2 and Codex slots 1/2. Only current access tokens (and Codex identity metadata) were copied. No refresh tokens were imported; CAS and live CLI configuration remain unchanged.
- Local runtime directory: `/Users/hong-kyungtack/.local/share/theo-proxy` (0700).
- Local keys: `secrets.json` inside that directory (0600). Never put its content in chat, URLs, git or screenshots.
- Runtime config: `config.yaml`; separate `auths/` containing the four access-only CAS imports; custom built asset: `static/management.html`.
- `disable-auto-update-panel: true` prevents upstream from replacing this custom build.
- Management and inference both require their own generated keys. The listener binds only 127.0.0.1:18318.
- Serve-preview registration names: `theo-proxy-preview`, `theo-proxy-runtime`.
- A temporary incorrect preview mount was removed; port 8423 now intentionally points to the real runtime.

## Current CAS usage verification

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

- The owner accepted this screen and explicitly requested account import plus usage verification. Live quota fetch is verified for three accounts; one Claude account is rejected by its provider. New OAuth login and inference have not been performed.
- No soonest-reset routing algorithm has been implemented. The UI sort is not the backend routing policy.
- WebSocket behavior was not modified or benchmarked; the current core already has support but inference through the imported accounts is not tested.
- Session affinity was not changed. The limited access-only import is approved and completed; refresh ownership and CLI cutover remain pending.
- No public deployment, release or auto-start service was installed.
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
account import and usage verification. That limited step is now completed as documented below;
stopping sessions, full refresh-token transfer, client cutover, CAS removal and push are not performed.
