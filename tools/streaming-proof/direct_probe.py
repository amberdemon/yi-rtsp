"""Bounded native-worker observation; never print raw library logs or material."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, '/opt/yi-home/app')
import yi_native_av_relay as relay
from yi_cloud_session import request_runtime_material

os.umask(0o077)
p = argparse.ArgumentParser()
p.add_argument('--camera', choices=['Driveway', 'Garden'], default='Driveway')
p.add_argument('--seconds', type=int, default=45)
p.add_argument('--label', default='direct')
p.add_argument('--worker', default='/opt/yi-home/runtime/bionic-root/data/local/tmp/yi-phase3g/android_pppp_av_stream')
p.add_argument('--gdb', type=int)
args = p.parse_args()
assert 1 <= args.seconds <= 90
assert re.fullmatch(r'[a-zA-Z0-9_-]+', args.label)
token = Path('/data/backend-api-token').read_text().strip()
def api(path):
    req = urllib.request.Request('http://127.0.0.1:8099/api/v1/' + path,
                                 headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=15) as f:
        return json.load(f)
health = api('health')
print(json.dumps({'camera_count': health['camera_count'], 'cloud_session': health['cloud_session']}), flush=True)
cameras = api('cameras')['cameras']
print(json.dumps([{'name': c.get('name'), 'availability_state': c.get('availability_state'),
                   'credential_status': c.get('credential_status'), 'raw_model': c.get('raw_model')} for c in cameras]), flush=True)
camera = next(c for c in cameras if c['name'] == args.camera)
material, descriptor = request_runtime_material(Path('/data/cloud-material.sock'), camera['stable_id'], timeout=32)
command = ['qemu-aarch64', '-L', '/opt/yi-home/runtime/bionic-root',
           '-E', 'LD_LIBRARY_PATH=/data/local/tmp/yi-phase3g:/system/lib64']
if args.gdb:
    command += ['-g', str(args.gdb)]
command += [args.worker, '/data/local/tmp/yi-phase3g/libPPPP_API.so']
directory = Path('/tmp/yi-investigation')
directory.mkdir(mode=0o700, exist_ok=True)
stdout_path = directory / (args.label + '.stdout')
stderr_path = directory / (args.label + '.stderr')
start = time.monotonic()
with stdout_path.open('wb') as out, stderr_path.open('wb') as err:
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err)
    try:
        child.stdin.write(relay.payload(material, relay.phase3e._build_units(material)))
        child.stdin.flush()
        print('worker_started=true', flush=True)
        try:
            child.wait(timeout=args.seconds)
            deadline = False
        except subprocess.TimeoutExpired:
            deadline = True
            child.stdin.write(b'\x00')
            child.stdin.flush()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        child.stdin.close()
        material.clear()
safe = re.compile(r'(?:phase3g_[a-z_]+=(?:START|STARTED|PASS|FAIL)|PPPP_[A-Za-z0-9_]+_rc_hex=0x[0-9A-Fa-f]{8}|tnp_[a-z_]+=\d+|channel[123]_records=\d+)')
lines = [line for line in stderr_path.read_text(errors='replace').splitlines() if safe.fullmatch(line)]
data = stdout_path.read_bytes()
summary = {'camera': args.camera, 'label': args.label, 'deadline_reached': deadline,
           'exit_code': child.returncode, 'elapsed_seconds': round(time.monotonic()-start, 2),
           'stdout_bytes': len(data), 'yav1_occurrences': data.count(b'YAV1'),
           'safe_worker_events': lines}
(directory / (args.label + '.json')).write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2), flush=True)
