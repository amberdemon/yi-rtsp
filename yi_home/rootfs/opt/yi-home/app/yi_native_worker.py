"""Prepare the version-checked media-fd worker without changing its original."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ORIGINAL_SHA256 = 'e91dacc2182bf8371bfb19bf4a6063ead3a6560f5dcc898c8430f0e773f5f200'
MEDIA_SHA256 = '949e4bbee3346a045d5c6371f7dfb780efc86f38616b997bc19ae172f60b6802'


def prepare_media_worker(source: Path, destination: Path) -> None:
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Worker version mismatch; refuse to patch')
    # Verified ELF LOAD mapping: file offset == virtual address at this site.
    # write_exact_stdout: mov w0,#1 -> mov w0,#3 before the write syscall.
    if original[0x8d4:0x8d8] != bytes.fromhex('20008052'):
        raise ValueError('Unexpected media-write instruction')
    media = original[:0x8d4] + bytes.fromhex('60008052') + original[0x8d8:]
    if hashlib.sha256(media).hexdigest() != MEDIA_SHA256:
        raise ValueError('Unexpected prepared worker hash')
    if destination.is_symlink():
        raise ValueError('Media worker must not be a symlink')
    if destination.exists():
        if destination.read_bytes() != media:
            raise ValueError('Different destination exists; refuse to overwrite')
    else:
        destination.write_bytes(media)
    destination.chmod(0o755)


if __name__ == '__main__':
    try:
        source, destination = map(Path, sys.argv[1:])
        prepare_media_worker(source, destination)
    except (ValueError, OSError) as exc:
        print(f'media_worker_unavailable: {exc}', file=sys.stderr)
        raise SystemExit(1)
