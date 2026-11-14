#!/bin/sh
set -e
command -v nginx >/dev/null 2>&1 || apk add --no-cache nginx >/dev/null
command -v python3 >/dev/null 2>&1 || apk add --no-cache python3 >/dev/null
mkdir -p /run/nginx
nginx -t
nginx
python3 /llmshare/usage_filter.py > /var/log/usage_filter.log 2>&1 &
# login state and serve config live in /var/lib/tailscale (set once with `tailscale up` / `tailscale serve`)
exec tailscaled --statedir=/var/lib/tailscale --socket=/var/run/tailscale/tailscaled.sock
