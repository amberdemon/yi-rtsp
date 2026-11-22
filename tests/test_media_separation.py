import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools' / 'streaming-proof'
sys.path.insert(0, str(TOOLS))
from patch_worker_fd import patch

class MediaSeparation(unittest.TestCase):
    def test_unknown_binary_is_rejected(self):
        with self.assertRaises(ValueError):
            patch(b'unknown worker version')

    def test_verified_worker_changes_only_media_descriptor(self):
        original = Path(os.environ.get('YI_PROOF_WORKER', str(ROOT / 'yi_home/rootfs/opt/yi-home/runtime/bionic-root/data/local/tmp/yi-phase3g/android_pppp_av_stream')))
        data = original.read_bytes()
        changed = patch(data)
        self.assertEqual(changed[:0x8d4], data[:0x8d4])
        self.assertEqual(changed[0x8d8:], data[0x8d8:])
        self.assertEqual(changed[0x8d4:0x8d8], bytes.fromhex('60008052'))
        with self.assertRaises(ValueError):
            patch(changed)

    def test_native_media_does_not_share_library_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / 'qemu-aarch64'
            fake.write_text('#!/bin/sh\nprintf library-log\nprintf YAV1 >&3\nprintf worker-log >&2\n')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=d + ':' + os.environ['PATH'])
            result = subprocess.run(['sh', str(TOOLS / 'qemu-media-fd3.sh')],
                                    env=env, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b'YAV1')
            self.assertEqual(result.stderr, b'library-logworker-log')

if __name__ == '__main__':
    unittest.main()
