"""Version-locked investigation patch; contains no proprietary binary."""
import hashlib
from pathlib import Path
import sys

EXPECTED = 'e91dacc2182bf8371bfb19bf4a6063ead3a6560f5dcc898c8430f0e773f5f200'

def patch(data):
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('Worker version mismatch; refuse to patch')
    # ELF executable LOAD maps file offset == virtual address here.
    # write_exact_stdout+0x40: mov w0,#1 -> mov w0,#3 before sys_write.
    if data[0x8d4:0x8d8] != bytes.fromhex('20008052'):
        raise ValueError('Unexpected media-write instruction')
    result = bytearray(data)
    result[0x8d4:0x8d8] = bytes.fromhex('60008052')
    return bytes(result)

if __name__ == '__main__':
    source, destination = map(Path, sys.argv[1:])
    result = patch(source.read_bytes())
    if destination.exists():
        if destination.read_bytes() == result:
            raise SystemExit(0)
        raise SystemExit('Different destination exists; refuse to overwrite')
    destination.write_bytes(result)
    destination.chmod(0o700)
