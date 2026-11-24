"""A reconnect must not reuse cloud camera credentials from an older session."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

APP=Path(__file__).resolve().parents[1]/'yi_home/rootfs/opt/yi-home/app'
sys.path.insert(0,str(APP))
from yi_camera_manager import YiCameraManager,_stable_id
from yi_cloud_session import YiCloudSession

class CloudRuntimeRefreshTest(unittest.TestCase):
    def test_reconnect_receives_rotated_camera_password_and_connection_material(self):
        uid='synthetic-uid-123456789';version=0;calls=[]
        def encrypted(password):
            padder=padding.PKCS7(128).padder();data=padder.update(password.encode())+padder.finalize()
            encryptor=Cipher(algorithms.AES(uid[:16].encode()),modes.ECB()).encryptor()
            return (encryptor.update(data)+encryptor.finalize()).hex()
        def response(host,path,*args):
            calls.append(path)
            if path=='/v4/devices/list':
                return {'data':[{'uid':uid,'name':'Synthetic camera','model':'synthetic','type':2,
                    'password':encrypted('synthetic-password-'+str(version)),
                    'ipcParam':{'p2p_encrypt':True}}]},{}
            if path=='/v4/tnp/device_info':
                return {'data':{'DID':'synthetic-did-'+str(version),'InitString':'synthetic-server',
                    'License':'synthetic-key:license'}},{}
            raise AssertionError('Unexpected cloud request')
        manager=YiCameraManager(environment={'YI_COUNTRY':'GB','YI_DEVICE_MODEL':'Synthetic',
            'YI_ANDROID_VERSION':'17','YI_LANGUAGE':'en'})
        manager._user_id='synthetic-user';manager._token='synthetic-token';manager._token_secret='synthetic-secret'
        session=YiCloudSession();session._manager=manager
        with patch('yi_camera_manager.cloud.get_json',side_effect=response):
            first,_=session.runtime_material(_stable_id(uid))
            try:self.assertEqual(first.password,'synthetic-password-0')
            finally:first.clear()
            version=1
            second,_=session.runtime_material(_stable_id(uid))
            try:
                self.assertEqual(second.password,'synthetic-password-1')
                self.assertEqual(second.pppp_did,'synthetic-did-1')
            finally:second.clear()
        self.assertEqual(calls.count('/v4/devices/list'),2)
        self.assertEqual(calls.count('/v4/tnp/device_info'),2)
        self.assertEqual(session.safe_status()['cloud_login_attempt_total'],0)

if __name__=='__main__':unittest.main()
