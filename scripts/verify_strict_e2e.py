#!/usr/bin/env python3
"""Run real Hermes -> compiled CLIProxyAPI -> LOCAL SYNTHETIC Gemini upstream.
No production config, credentials, or processes are used. Artifacts stay in --output.
"""
import argparse
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

HEADER = "X-CLIProxy-Conversation-ID"


def client(args):
    sys.path.insert(0, args.hermes_source)
    from unittest.mock import patch
    from hermes_state import SessionDB
    from run_agent import AIAgent
    db = SessionDB(db_path=Path(os.environ["HERMES_HOME"]) / "state.db")
    agent = AIAgent(api_key="synthetic-client", base_url=args.base, model="strict-e2e-model",
                    provider="strict-test", session_db=db, session_id=args.session,
                    platform="acp", api_mode="chat_completions", enabled_toolsets=[],
                    skip_memory=True, skip_context_files=True, quiet_mode=True, max_iterations=1)
    with patch("agent.turn_context._maybe_title_session_at_turn_start"):
        result = agent.run_conversation("Reply with the local synthetic test response.")
    print(json.dumps({"client_result": str(result)}))
    db.close()


def main(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run = out / f"run-{time.time_ns()}"
    run.mkdir(mode=0o700)
    (run / "auths").mkdir()
    home = run / "hermes-home"
    home.mkdir()
    hits = []
    class Fake(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            hits.append({"account": self.headers.get("x-goog-api-key"), "path": self.path,
                         "private_header": self.headers.get(HEADER), "bytes": len(body)})
            value = {"candidates": [{"content": {"role": "model", "parts": [{"text": "SYNTHETIC_OK"}]},
                                      "finishReason": "STOP"}],
                     "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2}}
            data = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, format, *unused):
            pass
    fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    worker = threading.Thread(target=fake.serve_forever, daemon=True)
    worker.start()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}/v1"
    config = {
        "host": "127.0.0.1", "port": port, "auth-dir": str(run / "auths"),
        "access": {"api-keys": ["synthetic-client"]},
        "remote-management": {"disable-control-panel": True},
        "routing": {"strict-conversation-affinity": True, "conversation-bindings-file": str(run / "bindings.db")},
        "api-keys": {"gemini": [{"name": "synthetic", "base-url": f"http://127.0.0.1:{fake.server_port}",
            "proxy-url": "direct", "models": [{"name": "strict-e2e-model", "alias": "strict-e2e-model"}],
            "keys": [{"api-key": "synthetic-account-a"}, {"api-key": "synthetic-account-b"}]}]},
    }
    (run / "config.yaml").write_text(json.dumps(config))
    (home / "config.yaml").write_text(json.dumps({"custom_providers": [{"name": "strict-test",
        "base_url": base, "api_key": "synthetic-client", "session_affinity_header": HEADER}],
        "memory": {"memory_enabled": False, "user_profile_enabled": False}}))
    subprocess.run([args.initializer, str(run / "bindings.db")], check=True, cwd=run)
    proxy = None
    proxy_log = (run / "proxy.log").open("w")
    def start():
        p = subprocess.Popen([args.proxy, "--config", str(run / "config.yaml"), "--local-model"],
                             cwd=run, stdout=proxy_log, stderr=subprocess.STDOUT,
                             env={k: v for k, v in os.environ.items() if not k.startswith(("PGSTORE_", "GITSTORE_", "OBJECTSTORE_"))})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if p.poll() is not None:
                raise RuntimeError("proxy exited; inspect proxy.log")
            try:
                req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer synthetic-client"})
                with urllib.request.urlopen(req, timeout=1) as res:
                    assert res.status == 200
                return p
            except (OSError, urllib.error.URLError):
                time.sleep(.1)
        p.terminate()
        p.wait(timeout=5)
        raise RuntimeError("proxy did not become ready")
    def stop(p):
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    def turn(label, native_session, thread_id):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "OPENAI_", "ANTHROPIC_", "BB_"))}
        env.update(HERMES_HOME=str(home), HERMES_RUNTIME_DIR=str(run / "runtime"), BB_THREAD_ID=thread_id,
                   TMPDIR=str(run), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([args.python, str(Path(__file__).resolve()), "--client", "--hermes-source",
             args.hermes_source, "--base", base, "--session", native_session],
             cwd=args.hermes_source, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
        (run / f"{label}.log").write_text(result.stdout)
        if result.returncode or "SYNTHETIC_OK" not in result.stdout:
            raise RuntimeError(f"Hermes turn failed: {label}; inspect log")
    try:
        proxy = start()
        turn("first", "native-a", "stable-thread")
        first_hits = len(hits)
        assert first_hits > 0
        assigned = hits[-1]["account"]
        assert assigned in {"synthetic-account-a", "synthetic-account-b"}
        stop(proxy)
        proxy = None
        proxy = start()
        turn("restored", "native-b-after-acp-recreation", "stable-thread")
        assert len(hits) > first_hits
        assert all(hit["account"] == assigned for hit in hits), hits
        assert all(hit["private_header"] is None for hit in hits), hits
        prior = len(hits)
        (run / "bindings.db").rename(run / "bindings-preserved.db")
        request = urllib.request.Request(base + "/chat/completions", method="POST",
            data=json.dumps({"model": "strict-e2e-model", "messages": [{"role": "user", "content": "hi"}]}).encode(),
            headers={"Authorization": "Bearer synthetic-client", "Content-Type": "application/json", HEADER: "bb:stable-thread"})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError("storage loss accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 503, exc.code
        assert len(hits) == prior
        report = {"status": "passed", "evidence_type": "real Hermes agent + real proxy processes; synthetic local upstream",
                  "proxy_restart": True, "hermes_process_restart": True, "changed_acp_native_session": True,
                  "stable_account": assigned, "storage_loss_status": 503, "upstream_hits": hits,
                  "artifact_dir": str(run)}
        (run / "result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        if proxy is not None:
            stop(proxy)
        proxy_log.close()
        fake.shutdown()
        fake.server_close()
        worker.join(timeout=3)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", action="store_true")
    for key in ("hermes-source", "python", "proxy", "initializer", "output", "base", "session"):
        p.add_argument("--" + key)
    args = p.parse_args()
    client(args) if args.client else main(args)
