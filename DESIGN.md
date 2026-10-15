# Theo quota ledger starting point

## Authority

The owner requested: “나도 Theo 처럼 포크해서 Theo 화면을 보고 복사해줘. 거기서 시작하자”.
The approved direction is the actual quota screen in Theo's video, not an invented alternate design.
Source: https://www.youtube.com/watch?v=D8PikZ1KhUo&t=17m46s
Captured reference: `preview/theo-18m07.png` (video time 18:07, original 1920×1080 frame).
Additional frames at 19:05 and 22:18 are retained in the originating thread's evidence directory.
The video describes VibeProxy as a starting point; the visible browser UI identifies itself as CPAMC.
The current VibeProxy repository is a native macOS wrapper. This web implementation therefore forks
`router-for-me/Cli-Proxy-API-Management-Center` and runs against CLIProxyAPI, rather than rebuilding the native wrapper.

## Purpose and scope

The owner clarified: “cas 에서 이걸로 전환하려고 하는건데”. The product goal is to replace
CAS account switching with this proxy, reusing the accounts already registered in CAS.
The ledger UI is the accepted starting point, not the full product scope. A user should see remaining
quota and reset times here, while clients use the proxy instead of switching live provider credentials.
The owner clarified the primary use case: “여기 등록해놓고 여러장비에서 여기서 관리되는걸 같이 쓰는 용도로 이해했음(Theo의설명)”. This is a central subscription gateway for the owner's multiple devices, not primarily an account-switching optimizer or a quota-only dashboard. Register the upstream accounts centrally; devices use the proxy endpoint and client authentication through supported settings, without patching BB/Hermes/client source. Central credential refresh ownership, multi-device reachability, shared quota visibility and conversation-stable routing are the core delivery. Quotas remain shared upstream limits, not additional capacity, and conversation-history synchronization is a separate feature. This describes the intended end state, not current deployment or completed refresh migration.
The intended migration is a one-time credential transfer and client cutover, not permanent CAS/proxy
two-way synchronization. Assess running clients and refresh ownership before cutover. Preserve rollback
material, but recognize that old copied refresh tokens may become stale after rotation.
The owner subsequently authorized account import and usage-page verification first. Four CAS
access-token snapshots are now registered; refresh ownership and client cutover remain pending.
No existing sessions were stopped.

## Confirmed account-assignment rule (implementation authorized; live cutover pending)

Owner instruction: “새 대화에서 새 계정을 배정하는건 OK, 각 요청마다 새계정은 NO”.

- Choose an account when a new conversation starts.
- Keep subsequent requests in that conversation on its assigned account; do not rotate per request.
- A different new conversation may be assigned a different account.
- The owner explicitly included Hermes ("Hermes도 마찬가지"). Apply the same conversation-level identity requirement to Hermes, including its BB/ACP usage, not only Codex and Claude Code.
- Reconnecting transport, restarting an agent process, or restoring an existing conversation must not by itself create a new account assignment. Preserve a stable logical conversation identity and its account binding across those events; do not assume ACP session IDs automatically reach model HTTP requests.
- The owner authorized implementation with “보장되게 구현을 해보자”, then clarified “그건 수정 안하고 해야할거같은데?”: do not modify BB or Hermes themselves. The isolated BB/Hermes source patches are excluded from adoption. Proxy-side persistence may be reused, but integration must use unmodified clients and supported configuration. The redo uses captured stock Codex/Claude native headers and Hermes' existing per-provider affinity-header setting. Actual stock clients and proxy restart tests passed; see `docs/STOCK-CONVERSATION-HANDOFF.md`. A client that loses its native identity and creates a new ID remains outside the guarantee. Prior tests in `docs/STRICT-CONVERSATION-HANDOFF.md` are historical patched-client evidence, not the adopted integration.
- Automatic mid-conversation switching on quota exhaustion or failure is not approved by this rule; do not silently introduce that exception.
- Live routing, account refresh ownership and default client endpoint cutover have not been changed. The implementation contract is `docs/STRICT-CONVERSATION-CONTRACT.md`.

## Visible reference contract

- Neutral charcoal background, darker page and slightly lighter sidebar/panels.
- Existing grouped CPAMC navigation is retained.
- Quota Management title and credential/loaded counts, email visibility and refresh actions.
- Provider filter tabs above a segmented provider-summary strip.
- Provider sections with account identity, plan, horizontal remaining-quota meters and per-account refresh.
- Claude order: model-specific weekly quota, five-hour window, overall weekly window.
- Remaining percentages, not used percentages. Unknown is `--`, never zero or 100.
- Email addresses hidden initially, including display tooltips.
- Dark is the fresh-install default; saved theme choices and light/white/auto remain available.

## Data and behavior boundary

`normalized API/store state → ledgerModel → QuotaLedger/QuotaLedgerSummary`.
No reference identities or percentages are imported into production `src/`.
`preview/fixtures.ts` contains explicitly synthetic account identities and reference-inspired values.
Unseen video rows are illustrative, not recovered data. Dates are fixed fixture dates, not current quotas.
The preview banner must always make this separation visible. Its refresh does not call a provider.

Provider totals sum equal per-account remaining percentages, not fungible token capacity. Disabled accounts
are excluded from usable capacity. Unknown/missing windows prevent a seemingly complete total.
Different window IDs are never silently added. The summary uses the current filtered set; rows retain
upstream pagination. Full plan/credit/reset actions remain available through the original Cards view.
Search/sort remains available in a disclosure. A zero-account screen links directly to OAuth onboarding.

## Known differences and starting-point acceptance

This is a structural visual reconstruction, not a pixel-identical clone. The original is a compressed video
with a presenter overlay, unknown font/rendering environment, and unseen lower rows/states.
The upstream shell, localized text and existing management flows remain intact. Mobile reflows to stacked
quota windows; the original did not establish a mobile design. Additional modern providers are retained.
The preview sidebar is a reference-only scaffold; ledger/header/tabs are the production React components.
The owner replied “맞아” after being asked whether this screen is the desired starting point.
The initial screen/direction is accepted as the starting point; this does not approve pixel parity,
all future screens, provider credentials, routing changes or publication. No global design-system decision is implied.
