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

A user should see which provider/account still has quota and when its windows reset,
without opening every credential card. The first deliverable is the ledger UI, not a new routing strategy.

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

## Known differences and pending acceptance

This is a structural visual reconstruction, not a pixel-identical clone. The original is a compressed video
with a presenter overlay, unknown font/rendering environment, and unseen lower rows/states.
The upstream shell, localized text and existing management flows remain intact. Mobile reflows to stacked
quota windows; the original did not establish a mobile design. Additional modern providers are retained.
The preview sidebar is a reference-only scaffold; ledger/header/tabs are the production React components.
Owner review of the live result is pending. No new global design-system decision is implied.
