import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

APP=Path(__file__).resolve().parents[1]/'yi_home/rootfs/opt/yi-home/app'
sys.path.insert(0,str(APP))
from yi_browser_view import ViewerServer

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
        self.viewer=ViewerServer(('127.0.0.1',0),base,base,'private-test-token')
        self.thread=threading.Thread(target=self.viewer.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.viewer.server_port)
    def tearDown(self):
        for s in [self.viewer,self.upstream]:s.shutdown();s.server_close()
        self.thread.join();self.up_thread.join()
    def get(self,path,headers=None):return urllib.request.urlopen(urllib.request.Request(self.base+path,headers=headers or {}),timeout=5)
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

if __name__=='__main__':unittest.main()
