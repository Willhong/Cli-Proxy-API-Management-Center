# Strict conversation binding: implementation handoff

Verified: 2026-10-14 15:43 KST. This is the latest implementation milestone; the older `HANDOFF.md` records the UI/usage milestone. Re-read current git/runtime state before resuming.

## Owner decisions and scope

- “새 대화에서 새 계정을 배정하는건 OK, 각 요청마다 새계정은 NO”.
- “Hermes도 마찬가지”.
- “보장되게 구현을 해보자” authorizes implementation; the earlier implementation hold is superseded.
- Same conversation retains its account through reconnect, agent/proxy restart, restoration and compaction. Unavailable account or unknown identity/storage stops inference rather than switching accounts.
- The parent announced isolated verification without changing live sessions or default authentication. No live BB/Hermes/proxy restart, CAS switch, refresh-token migration, default endpoint cutover, commit or push was performed.
- Reset-soon prioritization remains outside this change. Strict identity does not itself guarantee a provider cache hit; cache expiry, prompt changes and billing remain separate.

## Implemented artifacts

| Component | Location and base | State |
| --- | --- | --- |
| CLIProxyAPI | `/Users/hong-kyungtack/workspace/cli-proxy-api`, `feat/theo-console`, base `0d18d3b365be000eeaee7de4615f9da596b2059d` | Uncommitted durable binding, routing guards, WebSocket error reporting, initialization command, tests and runbook |
| Hermes | `/Users/hong-kyungtack/workspace/affinity-worktrees/hermes`, detached base `c741bba2927bfc156aff7979e8af74e36740ea79` | Uncommitted scoped header propagation, first-turn persistence, auxiliary context isolation, fork/model-switch persistence and tests |
| BB | `/Users/hong-kyungtack/workspace/affinity-worktrees/bb`, detached base `e08a6d183f8c6c9c284bb4011e82051be5ee9492` | Uncommitted native Claude/Codex header forwarding and authoritative ACP child thread ID, tests and docs |
| Console | `/Users/hong-kyungtack/workspace/cli-proxy-console`, `feat/theo-quota-ledger`, base `d1afecfa4b51311a118c553f8dd8a6d37b0acf98` | Contract, handoff, design status and repeatable cross-repository verification script |

A separate `affinity-worktrees/hermes-verify` clone carries exactly the Hermes patch for regression testing. It avoids worktree git metadata below the real Hermes home, which the existing test home-I/O guard correctly forbids. The guard was not disabled and tests were not weakened.

Evidence/artifact root: `/Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/`.

- Built server: `cli-proxy-api-strict`.
- Built initializer: `init-conversation-bindings`.
- Portable diffs: `strict-artifacts/{proxy,hermes,bb}.patch`; `manifest.json` records base commits and SHA-256 hashes. `git apply --reverse --check` passed against each changed source tree.
- Do not apply these patches on top of the already changed worktrees. For integration into another checkout, verify its current base, dirty files and `git apply --check` first.

## Behavior and configuration

See core [runbook](../../cli-proxy-api/docs/strict-conversation-routing.md), [contract](STRICT-CONVERSATION-CONTRACT.md), and BB [configuration](../../affinity-worktrees/bb/docs/cli-proxy-conversation-affinity.md).

The header is `X-CLIProxy-Conversation-ID`. The bbolt DB transaction commits the first account before upstream dispatch. Keys combine caller and logical conversation, not model/native connection ID. No TTL. Existing upstream soft affinity remains unchanged when strict mode is off.

```yaml
routing:
  strategy: round-robin
  strict-conversation-affinity: true
  conversation-bindings-file: /absolute/private/state/conversation-bindings.db
```

Initialize the DB once, explicitly. Missing/corrupt DB cannot silently become an empty replacement. Keep the client API key and credential identities stable; changing those deliberately changes the namespace/account identity and is not a transport restart. Unsupported Home/plugin/raw SDK HTTP routes fail closed; Antigravity credit fallback is disabled in strict mode.

Hermes opts in using `custom_providers[].session_affinity_header` on the exact proxy URL. BB uses `CLI_PROXY_AFFINITY_BASE_URL` in its host launch environment; only the configured root and its `/v1` route match. BB-native Codex currently requires the active provider/base URL in explicit launch overrides; config-file-only discovery is not supported automatically and results in a missing-header rejection. Standalone native Claude/Codex require an explicitly reused conversation header; no automatic standalone native-CLI launcher was added.

## Independently executed verification

All upstreams below are **synthetic local servers**. They are not real Anthropic/OpenAI subscription results.

1. **Real Hermes process -> real compiled proxy process -> synthetic Gemini upstream:** `scripts/verify_strict_e2e.py` passed. Both processes were restarted and the internal ACP session ID changed, while the BB thread ID stayed fixed. The account stayed `synthetic-account-a` for both requests. Removing the binding DB produced HTTP 503 and no further upstream request. The private header did not reach upstream.
   - Latest actual output: `strict-e2e/run-1791960200771845000/result.json`.
   - Each run retains proxy logs and both Hermes turn logs. Test processes terminate in `finally`; no test service is left running.
2. **Proxy regressions:** auth, service, all API-handler packages and config passed. `-race` strict tests passed for auth and Responses handlers. Production server and initializer built successfully after the last production edit.
   - `strict-go-final.log`, `strict-go-race.log`.
3. **HTTP/SSE/WebSocket routing:** real executors and two local synthetic accounts; same account after reconnect and manager restart, native Session_id changes ignored, missing/duplicate IDs rejected, no second-account dispatch after 401/403/429/500, no upstream dispatch after storage loss.
   - Tests: `strict_conversation_integration_test.go`, `strict_conversation_websocket_test.go`.
   - The parent reproduced the initially silent WebSocket 1006 failure, then changed strict mode to send an error frame. `strict-ws-error-red.log` and `strict-ws-error-green.log` retain both results.
4. **Storage/concurrency:** real concurrent child processes agree on one binding, later child process retains it, missing/corrupt storage and removed credentials reject. Unsupported Home execution was caught at the wrong boundary and fixed before dispatch.
   - `strict-parent-red.log`; final suite contains the passing regression.
5. **Hermes:** 115 tests passed across 9 real test files. First real agent turn, ACP create/load/recreation, explicit fork, compression, process reconstruction and all three main wire formats are covered. The fork/model-switch bug was independently found, reproduced, then fixed; unrelated saved metadata is preserved.
   - `strict-hermes-final.log`, `strict-fork-red.log`, `strict-fork-green.log`.
6. **BB:** 21 Codex + 92 Claude + 26 ACP tests passed (139 total), rerun by the parent after the final code edits. Tests include simultaneous threads and resume/environment forwarding.
   - `strict-bb-{codex,claude,acp}-final.log`.
7. **Installed CLI header capture:** local installed Codex and Claude sent `bb:raw-thread` to a fake endpoint. This capture script supplies the documented CLI settings directly; BB launch construction is tested separately. Codex exited 0; Claude rejected the intentionally incomplete fake response after its headers were captured. This is header transport evidence, not a successful Claude inference round.
   - `affinity-cli-capture.json`, `affinity-cli-capture.py`.
8. `git diff --check` passed in all changed repositories; patch reverse-application checks passed.

## Remaining before live adoption

- BB aggregate typecheck is not green: the existing Codex `sessionOptions`/model-type errors reproduce on the clean same-base checkout with the same dependencies. No new error category appeared. Logs: `bb-affinity-typecheck.log` and `bb-affinity-baseline-typecheck.log`. Do not claim a completely green BB build.
- Build/reload the intended live BB and Hermes installation only with a planned restart; those installations were not edited. The isolated worktrees are the implementation artifacts, not running production.
- Initialize and preserve a real binding DB; configure the dedicated proxy, BB route and Hermes provider together. A strict proxy deliberately rejects older clients that omit the identity.
- Verify a real allowed subscription request and usage with the actual imported credentials before broad cutover. Existing access-only snapshots still lack refresh ownership, and the previously rejected Claude organization was not bypassed.
- The management UI has no new control for these strict settings yet; configuration is in the documented YAML and BB launch environment. No new UI was requested or introduced.

## Implementation choices made by the agent

- bbolt (`go.etcd.io/bbolt`) for process-safe transactions without a separate database service.
- A required dedicated header rather than guessing identity from prompts/native temporary IDs.
- BB thread IDs as the authority across ACP recreation; explicit ACP forks use a separate persisted identity. A new BB thread receives a new assignment; resetting a provider inside the same BB thread alone does not authorize account rotation.
- Fail closed for unsupported bypass routes rather than pretending they meet the guarantee.
- No expiry/automatic cleanup or account reassignment API; operator edits/restores of the DB are administrative changes outside the restart guarantee.
- Local fake providers for deterministic failure injection, with real subscription acceptance left explicitly unverified.
