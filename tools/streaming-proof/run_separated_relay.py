"""Run the installed stable relay against Driveway; no runtime patching."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

os.umask(0o077)
sys.path.insert(0, '/opt/yi-home/app')

root = Path('/tmp/yi-investigation')
root.mkdir(mode=0o700, exist_ok=True)
token = Path('/data/backend-api-token').read_text().strip()
req = urllib.request.Request('http://127.0.0.1:8099/api/v1/cameras',
                             headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=15) as response:
    cameras = json.load(response)['cameras']
camera = next(c for c in cameras if c['name'] == 'Driveway')
command = [sys.executable, '/opt/yi-home/app/yi_native_av_relay_stable.py',
           '--stable-id', camera['stable_id'], '--material-socket', '/data/cloud-material.sock',
           '--duration', '15', '--output', str(root / 'driveway-separated.ts')]
with (root / 'separated-relay.stderr').open('wb', buffering=0) as log:
    code = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=log, timeout=55).returncode
print(json.dumps({'relay_exit_code': code}), flush=True)
raise SystemExit(code)
