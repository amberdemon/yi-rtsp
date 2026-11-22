"""Run the existing relay against Driveway with an isolated worker copy."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

os.umask(0o077)
sys.path.insert(0, '/opt/yi-home/app')
from yi_cloud_session import request_runtime_material
import yi_native_av_relay as relay

root = Path('/tmp/yi-investigation')
root.mkdir(mode=0o700, exist_ok=True)
token = Path('/data/backend-api-token').read_text().strip()
req = urllib.request.Request('http://127.0.0.1:8099/api/v1/cameras',
                             headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=15) as response:
    cameras = json.load(response)['cameras']
camera = next(c for c in cameras if c['name'] == 'Driveway')
def resolve(timeout):
    material, descriptor = request_runtime_material(Path('/data/cloud-material.sock'), camera['stable_id'], timeout=32)
    return material, {'cloud_online_reported': descriptor.cloud_online_reported}
relay.phase3e._fresh_exact_target = resolve
sys.argv = ['yi_native_av_relay.py', '--skip-env-load', '--duration', '15',
            '--worker-dir', str(root / 'worker'), '--qemu', '/tmp/qemu-media-fd3.sh',
            '--output', str(root / 'driveway-separated.ts')]
with (root / 'separated-relay.stderr').open('wb', buffering=0) as log:
    os.dup2(log.fileno(), 2)
    code = relay.main()
print(json.dumps({'relay_exit_code': code}), flush=True)
raise SystemExit(code)
