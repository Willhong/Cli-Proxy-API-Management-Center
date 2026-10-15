#!/usr/bin/env python3
"""Stock Codex/Claude CLIs and stock Hermes ACP -> real proxy -> synthetic Gemini.
All state is isolated. No client source patches, custom identity injection, or real credentials.
The two capture helpers are test drivers, not production launchers.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(args):
    root = Path(args.evidence_root).resolve()
    run = root / f"integrated-{time.time_ns()}"
    run.mkdir(parents=True, mode=0o700)
    probes = Path(__file__).resolve().parent / "stock_probes"
    n = module(probes / "native_capture.py", "native_capture")
    h = module(probes / "hermes_acp_probe.py", "hermes_acp_probe")
    hits, results, rpc = [], [], []
    phase = "boot"
    class FakeGemini(BaseHTTPRequestHandler):
        def log_message(self, format, *unused):
            pass
        def do_POST(self):
            data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            hits.append({"phase": phase, "account": self.headers.get("x-goog-api-key"),
                         "path": self.path, "bytes": len(data),
                         "private_identity_leaked": any(self.headers.get(k) for k in (
                             "X-CLIProxy-Conversation-ID", "X-Hermes-Session-ID"))})
            payload = {"candidates": [{"content": {"role": "model", "parts": [{"text": "Synthetic done."}]},
                                        "finishReason": "STOP"}],
                       "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}}
            value = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(value)))
            self.end_headers()
            self.wfile.write(value)
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeGemini)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    (run / "auths").mkdir()
    db = run / "bindings.db"
    config = {"host": "127.0.0.1", "port": port, "auth-dir": str(run / "auths"),
        "access": {"api-keys": ["synthetic-client"]}, "remote-management": {"disable-control-panel": True},
        "routing": {"strict-conversation-affinity": True, "conversation-bindings-file": str(db)},
        "api-keys": {"gemini": [{"name": "synthetic", "base-url": f"http://127.0.0.1:{upstream.server_port}",
            "proxy-url": "direct", "models": [{"name": model, "alias": model} for model in (
                "test-model", "claude-sonnet-4-5", "fake-model")],
            "keys": [{"api-key": "synthetic-account-a"}, {"api-key": "synthetic-account-b"}]}]}}
    (run / "config.yaml").write_text(json.dumps(config))
    subprocess.run([args.initializer, str(db)], check=True, cwd=run)
    proxy = None
    log = (run / "proxy.log").open("w")
    def start():
        p = subprocess.Popen([args.proxy, "--config", str(run / "config.yaml"), "--local-model"],
                             cwd=run, stdout=log, stderr=subprocess.STDOUT,
                             env={k:v for k,v in os.environ.items() if k in ("PATH", "HOME", "TMPDIR", "LANG")})
        until = time.monotonic() + 20
        while time.monotonic() < until:
            if p.poll() is not None:
                raise RuntimeError("proxy exited; see proxy.log")
            try:
                req = urllib.request.Request(base + "/v1/models", headers={"Authorization": "Bearer synthetic-client"})
                with urllib.request.urlopen(req, timeout=1) as r:
                    assert r.status == 200
                return p
            except (OSError, urllib.error.URLError):
                time.sleep(.1)
        stop(p)
        raise RuntimeError("proxy startup timeout")
    def stop(p):
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait()
    def restart():
        nonlocal proxy
        stop(proxy)
        proxy = None
        proxy = start()
    def account(label):
        values = {x["account"] for x in hits if x["phase"] == label}
        assert len(values) == 1, (label, values)
        assert values <= {"synthetic-account-a", "synthetic-account-b"}, values
        return next(iter(values))
    for p in ("home", "codex-home", "claude-config", "project", "hermes"):
        (run / p).mkdir()
    env = {k:v for k,v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TERM")}
    env.update(HOME=str(run / "home"), TMPDIR=str(run), CI="1", NO_COLOR="1", DO_NOT_TRACK="1",
               DISABLE_TELEMETRY="1")
    work = run / "project"
    ce = {**env, "CODEX_HOME": str(run / "codex-home"), "TEST_SYNTHETIC_KEY": "synthetic-client"}
    cx = ["-c", 'model_provider="synthetic"', "-c", f'model_providers.synthetic.base_url="{base}/v1"',
          "-c", 'model_providers.synthetic.name="Synthetic"', "-c", 'model_providers.synthetic.wire_api="responses"',
          "-c", 'model_providers.synthetic.env_key="TEST_SYNTHETIC_KEY"']
    ae = {**env, "CLAUDE_CONFIG_DIR": str(run / "claude-config"), "ANTHROPIC_BASE_URL": base,
          "ANTHROPIC_API_KEY": "synthetic-client", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    opts = [n.CLAUDE, "--bare", "-p", "--output-format", "json", "--model", "claude-sonnet-4-5", "--tools="]
    def cli(label, argv, environ):
        nonlocal phase
        phase = label
        value = n.run(label, argv, environ, work)
        value["request_indices"] = [i for i, hit in enumerate(hits) if hit["phase"] == label]
        value["error_kind"] = None if value["request_indices"] and value.get("exit") == 0 else "probe_failure"
        results.append(value)
        assert value.get("exit") == 0 and value.get("synthetic_answer_seen"), value
        return value["cli_ids"][0]
    def warmup(name, model, header):
        nonlocal phase
        phase = name + "-warmup"
        req = urllib.request.Request(base + "/v1/chat/completions", method="POST",
            data=json.dumps({"model": model, "messages": [{"role": "user", "content": "warmup"}]}).encode(),
            headers={"Authorization": "Bearer synthetic-client", "Content-Type": "application/json", header: "warmup-distinct-conversation"})
        with urllib.request.urlopen(req, timeout=10) as response:
            assert response.status == 200
            response.read()

    active_acp = None
    try:
        proxy = start()
        warmup("codex", "test-model", "Session-Id")
        cid = cli("codex-first", [n.CODEX, "exec", "--json", "--skip-git-repo-check", "-s", "read-only", "-m", "test-model", *cx, "Reply briefly without tools."], ce)
        assert account("codex-first") != account("codex-warmup"), "probe did not challenge cold re-selection"
        restart()
        resumed = cli("codex-resume", [n.CODEX, "exec", "resume", "--json", "--skip-git-repo-check", "-m", "test-model", *cx, cid, "Reply again without tools."], ce)
        assert cid == resumed and account("codex-first") == account("codex-resume")
        warmup("claude", "claude-sonnet-4-5", "X-Claude-Code-Session-Id")
        aid = cli("claude-first", [*opts, "Reply briefly without tools."], ae)
        assert account("claude-first") != account("claude-warmup"), "probe did not challenge cold re-selection"
        restart()
        resumed = cli("claude-resume", [*opts, "--resume", aid, "Reply again without tools."], ae)
        assert aid == resumed and account("claude-first") == account("claude-resume")
        setattr(h, "OUT", run / "hermes")
        (h.OUT / "project").mkdir()
        hh = h.OUT / "home"
        hh.mkdir()
        (hh / "config.yaml").write_text(json.dumps({
            "model": {"provider": "synthetic", "default": "fake-model", "context_length": 128000},
            "providers": {"synthetic": {"api": base + "/v1", "api_key": "synthetic-client", "transport": "chat_completions",
                "default_model": "fake-model", "session_affinity_header": "X-Hermes-Session-ID"}},
            "agent": {"api_max_retries": 1, "disabled_toolsets": ["memory", "web", "browser", "terminal", "file", "delegation"]},
            "memory": {"memory_enabled": False, "user_profile_enabled": False}, "compression": {"enabled": False},
            "updates": {"check": False}, "telemetry": {"shared_metrics": {"enabled": False, "send": False, "offer_version": 2}}
        }))
        (hh / ".env").write_text("")
        he = {**env, "HOME": str(h.OUT), "HERMES_HOME": str(hh), "PYTHONPATH": str(h.ROOT), "PYTHONUNBUFFERED": "1"}
        params = {"cwd": str(h.OUT / "project"), "mcpServers": []}
        def init(a):
            h.ok(a.req("initialize", {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
                     "clientInfo": {"name": "stock-proxy-probe", "version": "1"}}))
        active_acp = h.ACP(he, rpc, "first")
        init(active_acp)
        sid = h.ok(active_acp.req("session/new", params))["sessionId"]
        warmup("hermes", "fake-model", "X-Hermes-Session-ID")
        phase = "hermes-first"
        assert h.prompt(active_acp, sid, "Reply briefly without tools.")["stopReason"] == "end_turn"
        assert account("hermes-first") != account("hermes-warmup"), "probe did not challenge cold re-selection"
        assert active_acp.close() == 0
        active_acp = None
        restart()
        active_acp = h.ACP(he, rpc, "restored")
        init(active_acp)
        h.ok(active_acp.req("session/load", {**params, "sessionId": sid}))
        phase = "hermes-resume"
        assert h.prompt(active_acp, sid, "Reply again without tools.")["stopReason"] == "end_turn"
        assert account("hermes-first") == account("hermes-resume")
        assert active_acp.close() == 0
        active_acp = None
        assert not any(x["private_identity_leaked"] for x in hits)
        report = {"status": "passed", "synthetic_upstreams": True, "unmodified_clients": True,
            "proxy_restarted_between_each_first_and_resume": True, "native_runs": results,
            "hermes_acp_session_id": sid, "account_checks": {name: account(name + "-first") for name in ("codex", "claude", "hermes")},
            "upstream_hits": hits, "limits": ["No live provider subscriptions", "No full BB host restart", "Native identity loss is not recoverable by this proxy"]}
        (run / "result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"result": str(run / "result.json"), "status": report["status"], "accounts": report["account_checks"]}, indent=2))
    finally:
        if active_acp is not None:
            active_acp.close()
        if proxy is not None:
            stop(proxy)
        log.close()
        upstream.shutdown()
        upstream.server_close()
        (run / "hits.json").write_text(json.dumps(hits, indent=2))
        (run / "native-runs.json").write_text(json.dumps(results, indent=2))
        (run / "acp.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rpc))
        print("artifacts:", run)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-root", required=True)
    p.add_argument("--proxy", required=True)
    p.add_argument("--initializer", required=True)
    main(p.parse_args())
