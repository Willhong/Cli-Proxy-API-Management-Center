# Conversation account binding with unmodified clients

## Authority and boundary

Owner: “새 대화에서 새 계정을 배정하는건 OK, 각 요청마다 새계정은 NO”, “Hermes도 마찬가지”, then “그건 수정 안하고 해야할거같은데?” and “다시 작업해줘”.

BB, Hermes, Claude Code and Codex source/binaries must remain unmodified. Only CLIProxyAPI and existing supported client configuration are adoption targets. No new production wrapper/plugin or patched client is required. The earlier source-patch experiment is excluded and retained under `docs/archive/` and its isolated worktrees; its results do not prove stock-client behavior.

## Actual identity contract

The proxy accepts these explicit conversation identities:

- Codex: native `Session-Id` (case insensitive; `Session_id` spelling also supported), namespaced as `codex:<value>`.
- Claude Code: native `X-Claude-Code-Session-Id`, namespaced as `claude:<value>`.
- Hermes: existing per-provider `session_affinity_header: X-Hermes-Session-ID` setting, namespaced as `hermes:<value>`. This is supported configuration, not a Hermes patch.
- An explicitly supplied `X-CLIProxy-Conversation-ID` remains an advanced compatibility override. None of the stock-client acceptance tests injects this header.

Missing, malformed, duplicate or conflicting native identity headers reject before dispatch. Request IDs, WebSocket connection IDs, prompt hashes, text similarity and IP addresses are never used as fallback identity. The proxy-specific/Hermes affinity headers are removed before upstream execution; native provider headers retain their existing protocol handling.

Bind the authenticated caller plus conversation identity to one credential in a persistent transactional bbolt DB before the first upstream request. Do not include model or connection ID in the binding key. No TTL or silent reinitialization. Restarts keep the binding; missing/corrupt storage, removed/unavailable bound accounts and incompatible models fail closed. Concurrent first requests must agree. A new conversation can select a new account; continuing a known conversation cannot.

## Guarantee boundary

The guarantee is conditional on retaining the native conversation identity. Verified normal CLI resume and Hermes ACP load preserve it, so process/proxy restart does not change the account. Hermes manual `/compress` also retained its header in a full stock-ACP capture.

If a client loses its saved conversation and creates an unrelated new ID, the proxy cannot distinguish that from an intentional new conversation without additional information. Do not describe that case as guaranteed or join IDs by guessed prompt similarity. Stock BB native Claude/Codex resume/recovery tests preserve provider IDs or fail; the generic ACP bridge also contains a fallback-to-session/new path. Full live BB host restart plus model HTTP routing is not part of the current evidence. Automatic Hermes compaction is not yet captured in the stock-client suite.

Proxy restart guarantees also require retaining the DB, proxy client identity and credential identity. Administrative DB deletion/reinitialization, API-key namespace changes or replacing a credential ID with another account are not transport restarts.

## Verification and delivery

Use actual installed Codex/Claude CLI processes and unmodified Hermes ACP JSON-RPC processes against a compiled proxy and explicitly synthetic local provider accounts. Before the tested conversation, select another account with a separate warm-up conversation; verify the tested conversation is not on the default cold-start selection. Restart proxy and client, resume, and prove it retains the non-default account. This avoids a false pass where both fresh processes simply pick account A.

Also exercise native-header HTTP/SSE/WebSocket routing, missing/duplicate/conflicting identity, concurrent initial allocation, storage loss/corruption, unavailable credentials, and 401/403/429/500 without account failover.

Production endpoint changes, BB/Hermes restarts, real credential refresh ownership, CAS switching, publication and automatic commit/push remain outside this isolated implementation step. Real subscription acceptance, provider cache hits and billing require separate live verification.

Current results and instructions: `STOCK-CONVERSATION-HANDOFF.md`.
