from pathlib import Path
import sys
import tempfile
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes

APP=Path(__file__).resolve().parents[1]/'yi_home/rootfs/opt/yi-home/app'
sys.path.insert(0,str(APP))
from yi_viewer_tls import prepare_tls

class ViewerTLSTest(unittest.TestCase):
    def test_private_ca_is_preserved_and_leaf_covers_only_configured_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            prepare_tls(root,['localhost','127.0.0.1','192.168.1.23'])
            ca=(root/'ca.pem').read_bytes();key=(root/'server.key').read_bytes()
            leaf=x509.load_pem_x509_certificate((root/'server.pem').read_bytes())
            self.assertIn('localhost',leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName))
            prepare_tls(root,['localhost','127.0.0.1','192.168.1.23'])
            self.assertEqual(ca,(root/'ca.pem').read_bytes());self.assertEqual(key,(root/'server.key').read_bytes())
            prepare_tls(root,['localhost','127.0.0.1','192.168.1.24'])
            self.assertEqual(ca,(root/'ca.pem').read_bytes())
            self.assertEqual((root/'ca.key').stat().st_mode&0o777,0o600)
    def test_public_addresses_and_wildcards_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for host in ['8.8.8.8','*.local','example.com']:
                with self.assertRaises(ValueError):prepare_tls(Path(directory),[host])

if __name__=='__main__':unittest.main()
