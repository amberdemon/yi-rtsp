import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import tempfile
import ssl
import http.cookiejar
import socket
import unittest
import urllib.error
import urllib.request

APP=Path(__file__).resolve().parents[1]/'yi_home/rootfs/opt/yi-home/app'
sys.path.insert(0,str(APP))
from yi_browser_view import ViewerServer
from yi_viewer_auth import ViewerAuth
from yi_viewer_tls import prepare_tls

class BrowserViewTest(unittest.TestCase):
    def setUp(self):
        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/api/v1/cameras':
                    if self.headers.get('Authorization')!='Bearer private-test-token':
                        self.send_error(401);return
                    body=json.dumps({'cameras':[{'stable_id':'a'*20,'name':'Driveway','availability_state':'online',
                        'password':'never-forward-this','runtime':{'process_alive':True,'media_publisher_attached':True}},
                        {'stable_id':'b'*20,'name':'Garden','availability_state':'offline','runtime':None}]}).encode()
                    mime='application/json'
                elif self.path=='/api/stream.mp4?src=yi_aaaaaaaaaaaa':
                    body=b'mp4-media';mime='video/mp4; codecs="avc1.640028,mp4a.40.2"'
                else:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.up_thread=threading.Thread(target=self.upstream.serve_forever,daemon=True);self.up_thread.start()
        base='http://127.0.0.1:'+str(self.upstream.server_port)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.auth=ViewerAuth(Path(self.temp.name)/'auth.json')
        self.auth.set_password('synthetic-viewer-password')
        self.cookie='__Host-yi_view_session='+self.auth.login('synthetic-viewer-password','test-client')
        self.viewer=ViewerServer(('127.0.0.1',0),base,base,'private-test-token',self.auth)
        self.thread=threading.Thread(target=self.viewer.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.viewer.server_port)
    def tearDown(self):
        for s in [self.viewer,self.upstream]:s.shutdown();s.server_close()
        self.thread.join();self.up_thread.join()
    def get(self,path,headers=None,authenticated=True):
        h={'Cookie':self.cookie} if authenticated else {}
        h.update(headers or {})
        return urllib.request.urlopen(urllib.request.Request(self.base+path,headers=h),timeout=5)
    def post(self,path,data,headers=None):
        h={'Content-Type':'application/json','Origin':self.base,'Cookie':self.cookie};h.update(headers or {})
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=json.dumps(data).encode(),headers=h),timeout=5)
    def test_page_and_camera_list_do_not_expose_backend_credentials(self):
        with self.get('/') as r:
            self.assertIn(b'YI View',r.read());self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
        with self.get('/api/cameras') as r:body=r.read()
        self.assertNotIn(b'private-test-token',body);self.assertNotIn(b'never-forward-this',body)
        cams=json.loads(body)['cameras'];self.assertTrue(cams[0]['active']);self.assertFalse(cams[1]['active'])
    def test_media_is_restricted_to_known_active_camera(self):
        with self.get('/media/'+'a'*20) as r:
            self.assertEqual(r.read(),b'mp4-media');self.assertIn('video/mp4',r.headers['Content-Type'])
        for path in ['/media/'+'b'*20,'/media/'+'c'*20,'/media/http://example.com','/../yi.env']:
            with self.assertRaises(urllib.error.HTTPError):self.get(path)
    def test_cross_site_requests_and_rebinding_are_rejected(self):
        for headers in [{'Host':'evil.example'},{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.get('/api/cameras',headers)
            self.assertEqual(e.exception.code,403)
    def test_unauthenticated_requests_cannot_read_cameras_or_media(self):
        with self.get('/',authenticated=False) as r:self.assertIn(b'Sign in',r.read())
        for path in ['/api/cameras','/media/'+'a'*20]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.get(path,authenticated=False)
            self.assertEqual(e.exception.code,401)
    def test_login_cookie_flags_and_logout_invalidate_session(self):
        with self.post('/auth/login',{'password':'synthetic-viewer-password'}) as r:
            cookie=r.headers['Set-Cookie'];self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
            self.cookie=cookie.split(';',1)[0]
        with self.get('/api/cameras') as r:self.assertEqual(r.status,200)
        with self.post('/auth/logout',{}) as r:self.assertEqual(r.status,204)
        with self.assertRaises(urllib.error.HTTPError) as e:self.get('/api/cameras')
        self.assertEqual(e.exception.code,401)
    def test_login_and_logout_require_same_origin(self):
        for path in ['/auth/login','/auth/logout']:
            with self.assertRaises(urllib.error.HTTPError) as e:self.post(path,{},headers={'Origin':'https://evil.example'})
            self.assertEqual(e.exception.code,403)
    def test_https_login_uses_verified_private_ca_and_secure_cookie(self):
        self.viewer.shutdown();self.thread.join()
        tls=Path(self.temp.name)/'tls';prepare_tls(tls,['localhost','127.0.0.1'])
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(tls/'server.pem',tls/'server.key')
        self.viewer.enable_tls(context)
        self.thread=threading.Thread(target=self.viewer.serve_forever,daemon=True);self.thread.start()
        base='https://localhost:'+str(self.viewer.server_port)
        trusted=ssl.create_default_context(cafile=str(tls/'ca.pem'))
        cookies=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=trusted),urllib.request.HTTPCookieProcessor(cookies))
        request=urllib.request.Request(base+'/auth/login',data=json.dumps({'password':'synthetic-viewer-password'}).encode(),headers={'Content-Type':'application/json','Origin':base})
        with opener.open(request,timeout=5) as r:self.assertEqual(r.status,204)
        with opener.open(base+'/api/cameras',timeout=5) as r:self.assertEqual(len(json.load(r)['cameras']),2)
        # An idle TCP peer must not hold the TLS accept loop hostage.
        with socket.create_connection(('127.0.0.1',self.viewer.server_port),timeout=2):
            with opener.open(base+'/api/cameras',timeout=2) as r:self.assertEqual(r.status,200)
        self.assertTrue(all(c.secure for c in cookies))
        with self.assertRaises(urllib.error.URLError):urllib.request.urlopen(base,context=ssl.create_default_context(),timeout=5)

if __name__=='__main__':unittest.main()
