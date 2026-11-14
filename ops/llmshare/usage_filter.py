#!/usr/bin/env python3
"""llmshare usage filter: read-only llmproxy usage for the share node.

Listens on 127.0.0.1:8090 inside the llmshare container. nginx sends /v8/management/* here.
Only two calls are allowed, exactly what bb usage-tracker needs:
  GET  /v8/management/credentials          -> account list, reduced to the fields the plugin reads
  POST /v8/management/requests/api-call    -> only GET of the Codex/Claude usage URL for a known account
The caller presents a separate usage-read token; the real management key never leaves this node.
"""
import hmac
import json
import os
import ssl
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "https://llmproxy.hktlabs.com/v8/management"
SECRETS = json.load(open("/llmshare/usage-secrets.json"))
READ_TOKEN = SECRETS["usageReadToken"]
MGMT_KEY = SECRETS["managementKey"]
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")

USAGE = {
    "codex": "https://chatgpt.com/backend-api/wham/usage",
    "claude": "https://api.anthropic.com/api/oauth/usage",
}


def upstream(path, body=None):
    req = urllib.request.Request(
        UPSTREAM + path,
        data=None if body is None else json.dumps(body).encode(),
        method="GET" if body is None else "POST",
        headers={"Authorization": "Bearer " + MGMT_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        return json.load(r)


def accounts():
    out = []
    for f in upstream("/credentials").get("files", []):
        provider = f.get("provider") or f.get("type")
        if provider not in USAGE or f.get("disabled") is True or not f.get("auth_index"):
            continue
        item = {k: f.get(k) for k in ("provider", "type", "email", "name", "auth_index")}
        item["disabled"] = False
        tok = f.get("id_token") or {}
        if provider == "codex":
            item["id_token"] = {k: tok.get(k) for k in ("chatgpt_account_id", "plan_type") if tok.get(k)}
        out.append(item)
    return out


class H(BaseHTTPRequestHandler):
    server_version = "llmshare-usage"

    def log_message(self, fmt, *args):  # no request bodies or headers in logs
        print("%s %s" % (self.command, self.path.split("?")[0]), flush=True)

    def reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authed(self):
        got = self.headers.get("Authorization", "")
        ok = got.startswith("Bearer ") and hmac.compare_digest(got[7:].strip(), READ_TOKEN)
        if not ok:
            self.reply(401, {"error": "unauthorized"})
        return ok

    def do_GET(self):
        if self.path != "/v8/management/credentials":
            return self.reply(404, {"error": "not found"})
        if not self.authed():
            return
        try:
            self.reply(200, {"files": accounts()})
        except Exception:
            self.reply(502, {"error": "upstream"})

    def do_POST(self):
        if self.path != "/v8/management/requests/api-call":
            return self.reply(404, {"error": "not found"})
        if not self.authed():
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 8192:
                return self.reply(400, {"error": "bad request"})
            body = json.loads(self.rfile.read(n))
            idx = body.get("authIndex")
            if body.get("method") != "GET":
                return self.reply(403, {"error": "only usage reads are allowed"})
            acct = next((a for a in accounts() if a["auth_index"] == idx), None)
            if acct is None:
                return self.reply(403, {"error": "unknown account"})
            provider = acct.get("provider") or acct.get("type")
            if body.get("url") != USAGE[provider]:
                return self.reply(403, {"error": "only usage reads are allowed"})
            # Rebuild the request: never forward caller-supplied headers to the upstream call.
            if provider == "codex":
                header = {"Authorization": "Bearer $TOKEN$", "Content-Type": "application/json", "User-Agent": "codex-cli"}
                aid = (acct.get("id_token") or {}).get("chatgpt_account_id")
                if aid:
                    header["Chatgpt-Account-Id"] = aid
            else:
                header = {"Authorization": "Bearer $TOKEN$", "Content-Type": "application/json",
                          "Accept": "application/json", "anthropic-beta": "oauth-2025-04-20"}
            res = upstream("/requests/api-call", {"authIndex": idx, "method": "GET", "url": USAGE[provider], "header": header})
            self.reply(200, {"status_code": res.get("status_code"), "body": res.get("body")})
        except (ValueError, KeyError):
            self.reply(400, {"error": "bad request"})
        except Exception:
            self.reply(502, {"error": "upstream"})

    def _deny(self):
        self.reply(404, {"error": "not found"})

    do_PUT = do_PATCH = do_DELETE = do_HEAD = _deny


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8090), H).serve_forever()
