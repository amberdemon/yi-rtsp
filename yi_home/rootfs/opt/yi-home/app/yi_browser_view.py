"""Local browser viewer; backend credentials never enter browser responses."""
from __future__ import annotations
import argparse
import json
from http.cookies import SimpleCookie,CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from yi_stream_identity import media_stream_name
from yi_viewer_auth import ViewerAuth,LoginLimited

ASSETS=Path(__file__).with_name('viewer')
MEDIA=re.compile(r'^/media/([0-9a-f]{20})$')

class ViewerServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,backend_base,publisher_base,token,auth,allowed_hosts=('localhost','127.0.0.1','::1')):
        self.backend_base=backend_base
        self.publisher_base=publisher_base
        self.token=token
        self.auth=auth
        self.allowed_hosts=set(h.lower() for h in allowed_hosts)
        self.scheme='http'
        super().__init__(address,ViewerHandler)
    def enable_tls(self,context):
        # Defer handshakes to request workers; never block the accept loop.
        self.socket=context.wrap_socket(self.socket,server_side=True,do_handshake_on_connect=False)
        self.scheme='https'
    def get_request(self):
        connection,address=super().get_request()
        connection.settimeout(10)
        return connection,address
    def handle_error(self,request,client_address):
        # Interrupted media reads and failed TLS peers are normal disconnects.
        return
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
    def setup(self):
        if isinstance(self.request,ssl.SSLSocket):self.request.do_handshake()
        super().setup()
    def log_message(self,*args):pass
    def _local_request(self):
        host=self.headers.get('Host','')
        try: hostname=urlsplit('//'+host).hostname
        except ValueError:return False
        if hostname not in self.server.allowed_hosts:return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return False
        origin=self.headers.get('Origin')
        return not origin or origin==self.server.scheme+'://'+host
    def _cookie(self):
        try:
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
            value=cookie.get('__Host-yi_view_session')
            return value.value if value else None
        except CookieError:return None
    def _authorized(self):return self.server.auth.valid(self._cookie())
    def _headers(self,status,mime,length=None,cookie=None):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if cookie:self.send_header('Set-Cookie',cookie)
        if length is not None:self.send_header('Content-Length',str(length))
        else:
            self.send_header('Connection','close');self.close_connection=True
        self.end_headers()
    def _send(self,status,body,mime='text/plain; charset=utf-8',cookie=None):
        self._headers(status,mime,len(body),cookie=cookie);self.wfile.write(body)
    def do_GET(self):
        if not self._local_request():self._send(403,b'Local, same-origin access required.');return
        parsed=urlsplit(self.path)
        if parsed.query or parsed.fragment:self._send(400,b'Unsupported query.');return
        assets={'/':('index.html' if self._authorized() else 'login.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/login.js':('login.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if parsed.path in assets:
            name,mime=assets[parsed.path];self._send(200,(ASSETS/name).read_bytes(),mime);return
        if parsed.path=='/auth/session':
            self._send(200,json.dumps({'authenticated':self._authorized()}).encode(),'application/json');return
        if not self._authorized():self._send(401,b'Sign in to view your cameras.');return
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
                    if not self._authorized():break
                    chunk=upstream.read1(64*1024)
                    if not chunk:break
                    self.wfile.write(chunk);self.wfile.flush()
            except (OSError,ValueError):pass
    def do_POST(self):
        expected=self.server.scheme+'://'+self.headers.get('Host','')
        if not self._local_request() or self.headers.get('Origin')!=expected:
            self.close_connection=True;self._send(403,b'Same-origin access required.');return
        if self.path not in ('/auth/login','/auth/logout'):
            self.close_connection=True;self._send(404,b'Not found.');return
        try:
            size=int(self.headers.get('Content-Length','-1'))
            if self.headers.get('Transfer-Encoding') or not 0<size<=2048 or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
            data=json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(data,dict):raise ValueError()
        except (ValueError,UnicodeError):
            self.close_connection=True;self._send(400,b'Invalid request.');return
        if self.path=='/auth/logout':
            if not self._authorized():self._send(401,b'Sign in required.');return
            self.server.auth.logout(self._cookie())
            self._send(204,b'',cookie='__Host-yi_view_session=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0');return
        try:token=self.server.auth.login(data.get('password'),self.client_address[0])
        except LoginLimited:
            self._send(429,b'Too many sign-in attempts. Please wait five minutes.');return
        if token is None:self._send(401,b'Incorrect viewer password, or viewer is not configured.');return
        cookie=f'__Host-yi_view_session={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={self.server.auth.SESSION_SECONDS}'
        self._send(204,b'',cookie=cookie)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bind',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8097)
    parser.add_argument('--token-file',type=Path,default=Path('/data/backend-api-token'))
    parser.add_argument('--auth-file',type=Path,default=Path('/data/viewer/auth.json'))
    parser.add_argument('--network-file',type=Path,default=Path('/data/viewer/network.json'))
    parser.add_argument('--tls-directory',type=Path,default=Path('/data/viewer/tls'))
    args=parser.parse_args()
    token=args.token_file.read_text().strip()
    if not token:raise SystemExit('Backend token is unavailable')
    hosts=json.loads(args.network_file.read_text())['hosts'] if args.network_file.exists() else ['localhost','127.0.0.1']
    server=ViewerServer((args.bind,args.port),'http://127.0.0.1:8099','http://127.0.0.1:1984',token,ViewerAuth(args.auth_file,service=True),hosts)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.tls_directory/'server.pem',args.tls_directory/'server.key')
    server.enable_tls(context)
    print(f'browser_viewer=ready; port={args.port}; credentials_exposed=false',flush=True)
    server.serve_forever()
