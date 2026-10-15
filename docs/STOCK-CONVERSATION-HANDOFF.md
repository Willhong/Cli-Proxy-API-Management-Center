# Stock-client conversation routing handoff

## Current decision

The owner rejected changes to BB/Hermes themselves and asked to redo the implementation. **Only proxy code plus existing supported client settings are adopted.** The previous patched BB/Hermes worktrees and `STRICT-CONVERSATION-HANDOFF.md` are historical experiment artifacts, not deployment requirements. They were neither merged nor deleted.

Current contract: [STRICT-CONVERSATION-CONTRACT.md](STRICT-CONVERSATION-CONTRACT.md).

## What changed

`cli-proxy-api/sdk/cliproxy/auth/strict_conversation.go` now accepts the identities captured from unmodified clients:

- Codex native `Session-Id` (`Session_id` alias also supported) -> `codex:<id>`.
- Claude Code native `X-Claude-Code-Session-Id` -> `claude:<id>`.
- Stock Hermes existing per-provider setting `session_affinity_header: X-Hermes-Session-ID` -> `hermes:<id>`.

These replace the earlier requirement for a newly injected private header. The optional `X-CLIProxy-Conversation-ID` compatibility override remains, but none of the stock acceptance tests injects it. The proxy retains the existing transactional bbolt binding, no TTL, no unavailable-account failover, storage-failure rejection, and strict WebSocket error reporting. Malformed, duplicate or conflicting stock IDs reject; request IDs and prompt similarity are not fallback identity.

Only `~/workspace/cli-proxy-api` and console documentation/test drivers changed in this redo. Original `~/workspace/bb` at `e08a6d183f8c6c9c284bb4011e82051be5ee9492` has no tracked changes. Original Hermes at `c741bba2927bfc156aff7979e8af74e36740ea79` has no tracked changes; its preexisting untracked build directories and unrelated test remain untouched.

## Directly verified result

Evidence root: `/Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/stock-clients/`.

**Actual stock client processes -> compiled proxy process -> two local synthetic Gemini accounts** passed for Codex, Claude Code and Hermes ACP. Both client and proxy were restarted between the first turn and resume/load. Each target conversation was first assigned `synthetic-account-b` after a separate warm-up used the cold-start account; all resumed requests retained `synthetic-account-b`. This rules out a false pass caused by repeatedly choosing account A after cold start.

- Latest integrated evidence: `integrated-1791965216232158000/result.json`, `hits.json`, `acp.jsonl`, native/ACP process outcomes and `proxy.log`.
- Installed clients captured: Codex 0.162.1; Claude Code 2.1.296. Both use built-in native headers, no custom fixed ID.
- Stock Hermes uses the original ACP JSON-RPC process with isolated configuration and `session/new` / `session/load`; no identity monkeypatch, BB_THREAD_ID injection, source replacement or new production wrapper.
- Native-only capture `native/evidence.json`: first, resume in a new process, and separate new conversation for both CLIs completed with exit 0; resume retained the same native ID and a new conversation got a different ID.
- Hermes-only capture `hermes/{acp.jsonl,http.json,results.json,PASS}`: first/load/new/reset/fork. Its existing `/reset` retained the ACP identity; fork received a distinct one.
- Manual Hermes compression capture `hermes-compress/verified/`: actual `/compress` reported 12 -> 10 messages and the next request retained the same header. This proves identity continuity, not compression quality; the synthetic summary did not reduce estimated tokens.

Proxy tests were updated to run the real HTTP/SSE routing/error scenarios for all accepted native header families and the real WebSocket scenarios for native Codex `Session-Id`. Concurrent process tests now give opposing account priorities to child processes and reverse the preferred account after restart, instead of allowing every child to select the same default independently.

- `proxy-red.log`: native-header acceptance failed before the change.
- `proxy-green.log`: focused native tests passed after implementation.
- `regression-final.log`: auth, service, all API handler packages and config passed.
- `race-final.log`: strict auth and Responses handler race tests passed.
- Production server build and `git diff --check` passed.

These upstreams are explicitly synthetic. No real subscription inference, billing or cache-hit result is claimed.

## Configuration and artifacts

Core instructions: [proxy runbook](../../cli-proxy-api/docs/strict-conversation-routing.md).

```yaml
routing:
  strategy: round-robin
  strict-conversation-affinity: true
  conversation-bindings-file: /absolute/private/state/conversation-bindings.db
```

Initialize that DB once with `init-conversation-bindings`; preserve DB, client API key and credential identity across restarts. For Claude/Codex, configure the standard proxy base URL/client key only. Hermes adds its existing affinity header setting on the intended provider:

```yaml
providers:
  my-proxy:
    api: http://127.0.0.1:18318/v1
    transport: chat_completions
    default_model: your-configured-model
    session_affinity_header: X-Hermes-Session-ID
    # Supply api_key through the existing protected credential setup.
```

No source patch or new BB environment variable is required. The snippet is a configuration shape, not a change applied to live settings.

Built binary: `stock-clients/cli-proxy-api` under the evidence root's parent. Initializer: `../init-conversation-bindings`. Run the repeatable integrated verification using the existing Hermes Python environment:

```sh
/Users/hong-kyungtack/.hermes/hermes-agent/.venv/bin/python scripts/verify_stock_proxy_e2e.py \
  --evidence-root /Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/stock-clients \
  --proxy /Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/stock-clients/cli-proxy-api \
  --initializer /Users/hong-kyungtack/.bb/thread-storage/thr_czrmv7mpdk/init-conversation-bindings
```

`scripts/stock_probes/` contains test drivers only. Each integrated run creates a fresh isolated directory and cleans up its test processes. It does not change default client settings or use real tokens.

## Remaining limits: do not overclaim

- The guarantee holds while the client retains its native conversation identity. If saved history/identity is lost and a new ID is created, the proxy cannot tell whether this was recovery or an intentional new conversation. **That case is not solved.** It is not safe to infer the old ID from matching prompts.
- Original BB native Claude/Codex resume paths preserve provider IDs or return failure, supported by source inspection and original tests. However the generic ACP bridge at `packages/provider-bridge-acp/src/bridge/bridge.ts:1939-1974` catches load errors and can call `session/new`. That exceptional replacement creates a new identity from the proxy's perspective. BB was not patched to change this behavior.
- A full live BB-host restart followed through to model HTTP was not performed. Normal stock client process restart and full stock Hermes ACP restart were performed.
- Automatic Hermes compression was not exercised in the stock-client capture; manual `/compress` was.
- Home/plugin/raw SDK HTTP bypass paths remain unsupported in strict mode. The proxy rejects them rather than pretending to bind them.
- Update 2026-10-15: deployed live (core commit `22a67b7`) and verified with real Codex subscriptions on the Mac and nucbox, over HTTP and WebSocket, including proxy restarts. Codex refresh ownership moved to the proxy. Claude Code and Hermes are not cut over yet. See [HANDOFF.md](HANDOFF.md) for the current state. Not pushed.

The previous BB typecheck failures are not blockers for this adopted implementation because rebuilding or modifying BB is no longer part of the delivery. Do not deploy the earlier BB/Hermes patches to work around a missing identity.
