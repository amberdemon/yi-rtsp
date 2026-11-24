import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

APP=Path(__file__).resolve().parents[1]/'yi_home/rootfs/opt/yi-home/app'
sys.path.insert(0,str(APP))
from yi_viewer_auth import ViewerAuth, LoginLimited

class ViewerAuthTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'auth.json';self.now=1000
        self.auth=ViewerAuth(self.path,clock=lambda:self.now)
        self.auth.set_password('test-only-strong-viewer-password')
    def test_hashing_and_session_survive_restart_then_logout_revokes(self):
        self.assertIsNone(self.auth.login('incorrect-password','client'))
        cookie=self.auth.login('test-only-strong-viewer-password','client')
        self.assertTrue(self.auth.valid(cookie))
        disk=self.path.read_text();self.assertNotIn('test-only-strong-viewer-password',disk);self.assertNotIn(cookie,disk)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        restarted=ViewerAuth(self.path,clock=lambda:self.now)
        self.assertTrue(restarted.valid(cookie))
        restarted.logout(cookie);self.assertFalse(restarted.valid(cookie))
        self.assertFalse(ViewerAuth(self.path).valid(cookie))
    def test_expiration_and_password_change_invalidate_sessions(self):
        cookie=self.auth.login('test-only-strong-viewer-password','client')
        self.now+=self.auth.IDLE_SECONDS+1;self.assertFalse(self.auth.valid(cookie))
        self.now=1000;cookie=self.auth.login('test-only-strong-viewer-password','client')
        self.auth.set_password('another-test-only-password');self.assertFalse(self.auth.valid(cookie))
    def test_bad_logins_are_bounded_and_unconfigured_store_is_locked(self):
        for _ in range(5):self.assertIsNone(self.auth.login('incorrect-password','client'))
        with self.assertRaises(LoginLimited):self.auth.login('incorrect-password','client')
        locked=ViewerAuth(Path(self.temp.name)/'missing.json');self.assertIsNone(locked.login('anything','other'))
        self.assertFalse(locked.valid('random-cookie'))
    def test_password_cli_refuses_to_overwrite_a_running_service(self):
        service=ViewerAuth(self.path,service=True)
        original=self.path.read_bytes()
        command=[sys.executable,str(APP/'yi_viewer_auth.py'),'--store',str(self.path)]
        try:
            result=subprocess.run(command,input=b'another-test-only-password\n',capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(self.path.read_bytes(),original)
        finally:service.close()
        result=subprocess.run(command,input=b'another-test-only-password\n',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIsNotNone(ViewerAuth(self.path).login('another-test-only-password','client'))

if __name__=='__main__':unittest.main()
