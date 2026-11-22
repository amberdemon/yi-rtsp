"""Production media-descriptor routing, without cameras or vendor binaries."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'yi_home/rootfs/opt/yi-home/app'
WORKER = ROOT / 'yi_home/rootfs/opt/yi-home/runtime/bionic-root/data/local/tmp/yi-phase3g/android_pppp_av_stream'

class NativeWorkerTest(unittest.TestCase):
    def test_preparation_is_repeatable_and_preserves_original(self):
        original = WORKER.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            source, destination = Path(d) / 'original', Path(d) / 'media'
            source.write_bytes(original)
            command = [sys.executable, str(APP / 'yi_native_worker.py'), str(source), str(destination)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(hashlib.sha256(destination.read_bytes()).hexdigest(),
                             '949e4bbee3346a045d5c6371f7dfb780efc86f38616b997bc19ae172f60b6802')
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            destination.write_bytes(b'unexpected existing file')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(destination.read_bytes(), b'unexpected existing file')

    def test_unknown_worker_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            source, destination = Path(d) / 'original', Path(d) / 'media'
            source.write_bytes(b'unknown binary')
            result = subprocess.run([sys.executable, str(APP / 'yi_native_worker.py'), str(source), str(destination)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Worker version mismatch', result.stderr)
            self.assertFalse(destination.exists())

    def test_production_launcher_keeps_media_and_safe_worker_diagnostics_separate(self):
        result = subprocess.run(['sh', str(APP / 'tools/yi_media_worker.sh'), 'sh', '-c',
                                 'printf private-vendor-log; printf YAV1 >&3; printf worker-stage >&2'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'YAV1')
        self.assertEqual(result.stderr, b'worker-stage')

if __name__ == '__main__':
    unittest.main()
