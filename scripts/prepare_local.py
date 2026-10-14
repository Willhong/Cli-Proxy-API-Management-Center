#!/usr/bin/env python3
"""Prepare an isolated CLIProxyAPI instance without reading existing credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--state-dir', type=Path, default=Path.home() / '.local/share/theo-proxy')
parser.add_argument('--port', type=int, default=18318)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
state = args.state_dir.expanduser().resolve()
state.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(state, 0o700)
(state / 'auths').mkdir(exist_ok=True, mode=0o700)
(state / 'static').mkdir(exist_ok=True)
secret_file = state / 'secrets.json'
if secret_file.exists():
    credentials = json.loads(secret_file.read_text())
else:
    credentials = {'managementKey': secrets.token_urlsafe(32), 'clientKey': secrets.token_urlsafe(32)}
    secret_file.write_text(json.dumps(credentials, indent=2) + '\n')
    os.chmod(secret_file, 0o600)
config_file = state / 'config.yaml'
# Never replace a user's subsequent configuration edits.
if not config_file.exists():
    config_file.write_text('\n'.join([
        'config-version: 8', 'server:', '  host: "127.0.0.1"', f'  port: {args.port}',
        'management:', '  allow-remote: true',
        f'  secret-key: {json.dumps(credentials["managementKey"])}',
        '  disable-auto-update-panel: true',
        '  panel-github-repository: "https://github.com/Willhong/Cli-Proxy-API-Management-Center"',
        'access:', '  api-keys:', f'    - {json.dumps(credentials["clientKey"])}',
        'oauth:', f'  auth-dir: {json.dumps(str(state / "auths"))}',
        'routing:', '  strategy: "round-robin"', '  session-affinity: false', '',
    ]))
    os.chmod(config_file, 0o600)
artifact = root / 'dist/index.html'
if not artifact.is_file():
    raise SystemExit('Run bun run build before preparing the local instance.')
shutil.copy2(artifact, state / 'static/management.html')
print(json.dumps({'stateDir': str(state), 'config': str(config_file), 'secretFile': str(secret_file),
                  'managementArtifact': str(state / 'static/management.html'),
                  'authFiles': len(list((state / 'auths').glob('*.json')))}))
