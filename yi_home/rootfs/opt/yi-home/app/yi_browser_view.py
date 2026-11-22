"""Local browser viewer; backend credentials never enter browser responses."""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from yi_stream_identity import media_stream_name

ASSETS=Path(__file__).with_name('viewer')
MEDIA=re.compile(r'^/media/([0-9a-f]{20})$')

class ViewerServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,backend_base,publisher_base,token):
        self.backend_base=backend_base
        self.publisher_base=publisher_base
        self.token=token
        super().__init__(address,ViewerHandler)
    def cameras(self):
        request=urllib.request.Request(self.backend_base+'/api/v1/cameras',headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(request,timeout=8) as response:
            cameras=json.loads(response.read(1024*1024))['cameras']
        result=[]
        for camera in cameras:
            runtime=camera.get('runtime') or {}
            result.append({'id':camera['stable_id'],'name':camera['name'],
                           'online':camera.get('availability_state')=='online',
                           'active':bool(runtime.get('process_alive') and runtime.get('media_publisher_attached'))})
        return result

class ViewerHandler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def _local_request(self):
        host=self.headers.get('Host','')
        try: hostname=urlsplit('//'+host).hostname
        except ValueError:return False
        if hostname not in ('localhost','127.0.0.1','::1'):return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return False
        origin=self.headers.get('Origin')
        return not origin or origin=='http://'+host
    def _headers(self,status,mime,length=None):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if length is not None:self.send_header('Content-Length',str(length))
        else:
            self.send_header('Connection','close');self.close_connection=True
        self.end_headers()
    def _send(self,status,body,mime='text/plain; charset=utf-8'):
        self._headers(status,mime,len(body));self.wfile.write(body)
    def do_GET(self):
        if not self._local_request():self._send(403,b'Local, same-origin access required.');return
        parsed=urlsplit(self.path)
        if parsed.query or parsed.fragment:self._send(400,b'Unsupported query.');return
        assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if parsed.path in assets:
            name,mime=assets[parsed.path];self._send(200,(ASSETS/name).read_bytes(),mime);return
        if parsed.path=='/api/cameras':
            try:body=json.dumps({'cameras':self.server.cameras()}).encode()
            except (OSError,ValueError,KeyError):self._send(503,b'Camera service is starting.');return
            self._send(200,body,'application/json');return
        match=MEDIA.fullmatch(parsed.path)
        if not match:self._send(404,b'Not found.');return
        try:
            camera=next((c for c in self.server.cameras() if c['id']==match.group(1)),None)
            if camera is None or not camera['active']:self._send(404,b'Camera is not streaming.');return
            url=self.server.publisher_base+'/api/stream.mp4?src='+media_stream_name(camera['id'])
            request=urllib.request.Request(url,headers={'User-Agent':'YI-Local-Viewer'})
            upstream=urllib.request.urlopen(request,timeout=12)
        except (OSError,ValueError,KeyError):self._send(503,b'Camera stream is temporarily unavailable.');return
        with upstream:
            mime=upstream.headers.get('Content-Type','')
            if not mime.startswith('video/mp4'):self._send(502,b'Unsupported stream format.');return
            self._headers(200,mime)
            try:
                while True:
                    chunk=upstream.read1(64*1024)
                    if not chunk:break
                    self.wfile.write(chunk);self.wfile.flush()
            except (OSError,ValueError):pass

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bind',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8097)
    parser.add_argument('--token-file',type=Path,default=Path('/data/backend-api-token'))
    args=parser.parse_args()
    token=args.token_file.read_text().strip()
    if not token:raise SystemExit('Backend token is unavailable')
    server=ViewerServer((args.bind,args.port),'http://127.0.0.1:8099','http://127.0.0.1:1984',token)
    print(f'browser_viewer=ready; port={args.port}; credentials_exposed=false',flush=True)
    server.serve_forever()
