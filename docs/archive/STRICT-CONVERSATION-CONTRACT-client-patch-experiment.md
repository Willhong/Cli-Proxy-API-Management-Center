# Strict conversation account binding

Implementation authorized by the owner: "보장되게 구현을 해보자". This supersedes the implementation hold for conversation binding only. Reset-soon routing is not included.

## Current implementation boundary (owner correction)

Owner correction: “그건 수정 안하고 해야할거같은데?” refers to BB and Hermes themselves.

- Do not modify or require patched BB/Hermes source, binaries, core modules, or provider implementation code.
- The existing isolated BB/Hermes patches are excluded from adoption. Preserve them as prior experiment artifacts; do not merge, deploy or delete them without instruction.
- Pursue proxy-side changes and existing supported client configuration. A new wrapper/plugin is not implicitly approved as an equivalent substitute for source edits; disclose any such requirement before adopting it.
- The previous wire design below describes the tested experiment, not a verified integration contract for unmodified clients. In particular, do not require a new header that stock clients cannot supply consistently, and do not assume BB_THREAD_ID or Hermes lineage reaches HTTP requests.
- Capture unmodified clients' actual requests across reconnect/resume first. Reuse a stable existing identity if demonstrated. If no stable identity reaches the proxy, report the gap rather than infer identity from prompt similarity or claim a guarantee.
- Earlier modified-client test results remain valid only for that experiment. Acceptance with unmodified BB/Hermes is unverified.

## Required behavior

- Assign an account once per new logical conversation. Never rotate accounts per request.
- Reconnecting transport, restoring a conversation, restarting an agent or the proxy, and compaction must retain its account.
- If identity or storage cannot be read, or the assigned account is unavailable, fail closed before inference. Do not select another account on retry, stream bootstrap, model fallback, or WebSocket reconnection.
- New conversations may receive different accounts. Explicit forks are new conversations.
- Target clients: BB-native Claude/Codex, BB ACP Hermes, and standalone Hermes/Claude/Codex via an explicit conversation-aware launcher or supported client configuration.

## Wire and storage contract

- Header: `X-CLIProxy-Conversation-ID`. It identifies a logical conversation, not a transport connection, request, cache slot, or mutable prompt hash.
- Strict mode requires this header. No heuristic fallback to native ephemeral session IDs or prompt hashes.
- Opt-in per route. Never send this private identity to unrelated upstream model hosts.
- In BB, the BB thread ID is authoritative across ACP load failure/recreation. A newly created/forked BB thread gets a new value. Native in-agent reset that stays in the same BB thread does not authorize reassignment; start a new BB thread for a new assignment.
- Outside BB, use a persisted logical conversation identifier. Hermes compaction-lineage roots distinguish new/forked sessions from restoration; a standalone launcher can provide a named persistent conversation ID explicitly.
- Account binding is durable, transactional, and without TTL. Keys are caller scope plus logical conversation, NOT model or connection ID. A request that cannot use the bound account (including incompatible provider/model changes) stops rather than allocating another account.
- Credentials and tokens are never stored in the binding DB. Store only opaque caller/conversation keys and credential identity.
- Missing/corrupt storage after initialization must not silently create an empty replacement. Initialize storage explicitly; retain it as production state.
- Concurrent first requests, including across processes, must converge on one account before any inference is dispatched.

## Verification boundary

Use real local routing and client transport code with explicitly labelled fake upstreams for deterministic failure injection. Test restart with a new process, changed native session headers, duplicate/missing identity, concurrent first requests, bound-account 401/403/429/5xx, removed account, storage loss/corruption and HTTP/stream/WebSocket paths. Real provider acceptance and billing are separate from routing correctness.

No live BB/Hermes restart, default endpoint change, OAuth refresh migration, CAS switch, or production cutover is authorized by this implementation step. Isolated settings, artifacts and test processes only. No automatic commit or push.
