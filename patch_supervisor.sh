#!/bin/bash
#
# patch_supervisor.sh
#
# Patches Home Assistant Supervisor to work in DevContainer environments.
# Fixes the "unhealthy" state (docker_gateway_unprotected / dbus errors)
# that blocks Add-on installation.
#
# Usage:
#   chmod +x ./patch_supervisor.sh && ./patch_supervisor.sh
#
# Idempotent — kann beliebig oft ausgeführt werden.
# Nach jedem Supervisor-Neustart / Container-Rebuild erneut ausführen!

set -euo pipefail

echo "[patch_supervisor] Patching diagnostics (dbus/agent error)..."
docker exec hassio_supervisor python3 -c "
path = '/usr/src/supervisor/supervisor/api/supervisor.py'
with open(path, 'r') as f:
    content = f.read()
old = '        if ATTR_DIAGNOSTICS in body:\n            self.sys_config.diagnostics = body[ATTR_DIAGNOSTICS]\n            await self.sys_dbus.agent.set_diagnostics(body[ATTR_DIAGNOSTICS])'
new = '        if ATTR_DIAGNOSTICS in body:\n            self.sys_config.diagnostics = body[ATTR_DIAGNOSTICS]\n            try:\n                await self.sys_dbus.agent.set_diagnostics(body[ATTR_DIAGNOSTICS])\n            except Exception:\n                pass'
if old in content:
    with open(path, 'w') as f:
        f.write(content.replace(old, new))
    print('  -> PATCHED')
else:
    print('  -> already patched or pattern changed')
"

echo "[patch_supervisor] Scanning all supervisor files for DOCKER_GATEWAY_UNPROTECTED..."
docker exec hassio_supervisor python3 -c "
import re, os

base = '/usr/src/supervisor'

# Match add_unhealthy_reason(...DOCKER_GATEWAY_UNPROTECTED...) across line breaks
pattern_unhealthy = re.compile(
    r'self\.sys_resolution\.add_unhealthy_reason\(\s*\n?\s*UnhealthyReason\.DOCKER_GATEWAY_UNPROTECTED\s*\n?\s*\)',
    re.MULTILINE
)

# Also match create_issue calls that reference docker_gateway (newer supervisor versions)
pattern_issue = re.compile(
    r'Issue\.from_enum\s*\(\s*IssueType\.DOCKER_GATEWAY_UNPROTECTED[^)]*\)',
    re.MULTILINE
)

found = False
for root, dirs, files in os.walk(base):
    for fname in files:
        if not fname.endswith('.py'):
            continue
        path = os.path.join(root, fname)
        try:
            with open(path, 'r') as f:
                content = f.read()
        except Exception:
            continue
        if 'DOCKER_GATEWAY_UNPROTECTED' not in content:
            continue

        new_content = pattern_unhealthy.sub('pass  # DevContainer: skip firewall check', content)
        new_content = pattern_issue.sub('None  # DevContainer: skip firewall issue', new_content)

        rel = os.path.relpath(path, base)
        if new_content != content:
            with open(path, 'w') as f:
                f.write(new_content)
            print(f'  -> PATCHED: {rel}')
            found = True
        else:
            print(f'  -> already patched or different pattern: {rel}')
            found = True

if not found:
    print('  -> no files found with DOCKER_GATEWAY_UNPROTECTED (supervisor version may differ)')
"

echo "[patch_supervisor] Restarting Supervisor..."
docker restart hassio_supervisor

echo "[patch_supervisor] Waiting for Supervisor to initialize..."
sleep 8

echo "[patch_supervisor] Clearing any remaining unhealthy state via API..."
docker exec hassio_supervisor python3 -c "
import urllib.request, json, time

# Give the supervisor a moment to finish startup
time.sleep(3)

try:
    # Internal supervisor API is accessible from within the container
    req = urllib.request.Request(
        'http://localhost/resolution',
        headers={'Authorization': 'Bearer ' + open('/run/secrets/supervisor_token').read().strip()}
    )
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    unhealthy = data.get('data', {}).get('unhealthy', [])
    print(f'  -> Unhealthy reasons after patch: {unhealthy}')
    if not unhealthy:
        print('  -> System is healthy!')
    else:
        print('  -> Warning: still unhealthy — check supervisor logs')
except Exception as e:
    print(f'  -> Could not query resolution API: {e}')
" 2>/dev/null || true

echo "[patch_supervisor] Done! Supervisor ist gepatcht — Add-on Installation sollte funktionieren."
