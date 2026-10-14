#!/usr/bin/env python3
"""One-time CAS access-token import for quota verification; never refresh or switch CAS.

Reads Keychain into process memory only. Writes a whitelisted, access-only document
into an isolated CLIProxyAPI auth directory (0600). No credential values are printed.
Refresh ownership remains with the existing clients until an explicit later cutover.
"""
import argparse
import base64
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def keychain(service, account):
    result = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', service,
                             '-a', account, '-w'], capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(f'Keychain read failed for {service}/{account}, code {result.returncode}')
    return result.stdout.decode().rstrip('\r\n')


def read_slot(provider, slot):
    service = 'cas-credentials' if provider == 'claude' else 'cas-codex-credentials'
    value = keychain(service, f'slot-{slot}')
    if value.startswith('chunked-v1:'):
        _, count, digest = value.split(':')
        if not 1 <= int(count) <= 100 or len(digest) != 64:
            raise RuntimeError('Invalid CAS chunk manifest')
        encoded = ''.join(keychain(service, f'slot-{slot}-{digest}-part-{part}')
                          for part in range(int(count)))
        raw = gzip.decompress(base64.b64decode(encoded + '=' * (-len(encoded) % 4)))
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('CAS chunk checksum mismatch')
        value = raw.decode()
    return json.loads(value)


def jwt_claims(token):
    part = token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))


def convert(provider, slot, source):
    if provider == 'claude':
        cred = source['claudeAiOauth']
        access = cred['accessToken']
        expiry = cred['expiresAt'] / 1000
        result = {'type': 'claude', 'access_token': access, 'email': slot['email'],
                  'account_uuid': slot.get('accountUuid', ''),
                  'organization_uuid': slot.get('organizationUuid', '')}
    else:
        cred = source['tokens']
        access = cred['access_token']
        claims = jwt_claims(access)
        expiry = claims['exp']
        token_account = cred.get('account_id')
        if token_account != slot.get('accountId'):
            raise RuntimeError(f'Codex slot {slot["slot"]} identity mismatch')
        result = {'type': 'codex', 'access_token': access, 'id_token': cred.get('id_token', ''),
                  'account_id': token_account, 'email': slot['email'],
                  'plan_type': slot.get('plan', '')}
    if not access or expiry <= time.time() + 120:
        raise RuntimeError(f'{provider} slot {slot["slot"]}: access token expired or nearly expired; no refresh attempted')
    result['expired'] = dt.datetime.fromtimestamp(expiry, dt.timezone.utc).isoformat()
    result['note'] = f'CAS slot {slot["slot"]}: usage verification only; refresh token intentionally not imported'
    result['cas_source_slot'] = slot['slot']
    result['cas_import_mode'] = 'access-only'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cas-home', type=Path, default=Path.home() / '.cas')
    parser.add_argument('--auth-dir', type=Path, default=Path.home() / '.local/share/theo-proxy/auths')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    cas = args.cas_home.expanduser().resolve()
    destination = args.auth_dir.expanduser().resolve()
    if not destination.is_dir():
        raise RuntimeError('Prepare the isolated runtime auth directory first')
    pending = []
    # Use the existing CAS lock, without creating or rewriting its state files.
    with (cas / '.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        for provider, filename in [('claude', 'state.json'), ('codex', 'codex-state.json')]:
            raw_state = (cas / filename).read_bytes()
            state = json.loads(raw_state)
            if state.get('version') != 1:
                raise RuntimeError('Unsupported CAS state version')
            for slot in state['slots']:
                if slot.get('revoked'):
                    raise RuntimeError(f'{provider} slot {slot["slot"]} is revoked')
                target = destination / f'{provider}-cas-slot-{slot["slot"]}.json'
                if target.exists():
                    raise RuntimeError(f'Refusing to overwrite existing credential {target.name}')
                source = read_slot(provider, slot['slot'])
                converted = convert(provider, slot, source)
                pending.append((target, converted))
            if (cas / filename).read_bytes() != raw_state:
                raise RuntimeError('CAS state changed during import')
    if args.apply:
        for target, data in pending:
            temp = target.with_suffix('.importing')
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out)
                out.write('\n')
                out.flush()
                os.fsync(out.fileno())
            os.rename(temp, target)
            saved = json.loads(target.read_text())
            assert saved == data and 'refresh_token' not in saved and 'refreshToken' not in saved
    print(json.dumps({'applied': args.apply, 'count': len(pending), 'refreshTokensImported': 0,
                      'credentials': [{'file': p.name, 'provider': d['type'],
                                       'email': d['email'], 'expiresAt': d['expired']} for p, d in pending]}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception messages above are deliberately metadata-only; never dump provider responses.
        if isinstance(error, (KeyError, ValueError, json.JSONDecodeError)):
            raise SystemExit(f'Credential format validation failed ({type(error).__name__}); no token contents emitted')
        raise SystemExit(str(error))
