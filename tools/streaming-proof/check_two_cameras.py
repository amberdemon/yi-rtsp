"""Bounded two-camera RTSP decode using the normal backend and publisher."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, '/opt/yi-home/app')
from yi_stream_identity import media_stream_name

os.umask(0o077)
token = Path('/data/backend-api-token').read_text().strip()
root = Path('/tmp/two-camera-check')
root.mkdir(mode=0o700, exist_ok=True)
def api(path, method='GET'):
    req = urllib.request.Request('http://127.0.0.1:8099/api/v1/'+path, method=method,
                                 headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

# A container restart returns before cloud discovery and the API are ready.
for _ in range(60):
    try:
        cameras = {c['name']:c for c in api('cameras')['cameras'] if c['name'] in ('Driveway','Garden')}
        if len(cameras)==2:break
    except OSError:
        pass
    time.sleep(1)
else:
    raise SystemExit('Backend camera discovery readiness deadline exceeded')
mode=sys.argv[1]
seconds=int(sys.argv[2]) if len(sys.argv)>2 else 20
assert 1<=seconds<=1800
if mode=='start':
    for name,camera in cameras.items():
        response=api('cameras/'+camera['stable_id']+'/start','POST')
        assert response['ok']
    print('Both normal managed camera runtimes requested',flush=True)
elif mode=='stop':
    for camera in cameras.values():
        assert api('cameras/'+camera['stable_id']+'/stop','POST')['ok']
    print('Both managed cameras stopped',flush=True)
    raise SystemExit(0)
assert mode in ('start','decode')

def decode(name,camera):
    url='rtsp://127.0.0.1:8554/'+media_stream_name(camera['stable_id'])
    # Camera paths stay local in process arguments and private stderr files.
    with (root/(name+'.stderr')).open('wb') as err, (root/(name+'.progress')).open('wb') as progress:
        command=['ffmpeg','-hide_banner','-v','error','-xerror','-nostdin','-rtsp_transport','tcp',
                 '-timeout','20000000','-i',url,'-t',str(seconds),'-map','0:v:0','-map','0:a:0','-f','null','-',
                 '-progress','pipe:1','-nostats']
        start=time.monotonic()
        result=subprocess.run(command, stdout=progress, stderr=err, timeout=seconds+75)
    fields={}
    for line in (root/(name+'.progress')).read_text().splitlines():
        if '=' in line:
            key,value=line.split('=',1)
            if key in ('frame','out_time_us','progress'): fields[key]=value
    summary={'camera':name,'decode_exit_code':result.returncode,'duration_requested_seconds':seconds,
             'elapsed_seconds':round(time.monotonic()-start,2),'frames_decoded':int(fields.get('frame','0')),
             'out_time_us':int(fields.get('out_time_us','0')),'completed':fields.get('progress')=='end',
             'error_bytes':(root/(name+'.stderr')).stat().st_size}
    print(json.dumps(summary),flush=True)
    return summary

# Give both publishers up to 40 seconds to acquire media before RTSP clients join.
for _ in range(40):
    states={c['name']:c for c in api('cameras')['cameras'] if c['name'] in cameras}
    if all((c.get('runtime') or {}).get('published_bytes',0)>65536 for c in states.values()):
        break
    time.sleep(1)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    results=list(executor.map(lambda item:decode(*item),cameras.items()))
summary_path=root/('results-'+mode+'-'+str(seconds)+'.json')
summary_path.write_text(json.dumps(results,indent=2))
assert all(r['decode_exit_code']==0 and r['frames_decoded']>0 and r['completed']
           and r['error_bytes']==0 and r['out_time_us'] >= max(0,seconds-1)*1_000_000 for r in results)
