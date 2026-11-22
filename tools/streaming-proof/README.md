# Reproduce the independent streaming proof

This is a bounded diagnostic for the updated `yi-rtsp-poc` Docker bridge,
not a viewer. It selects only the powered
camera named **Driveway** and uses the bridge's authenticated material broker.

## Prerequisites

- Docker is running on the existing Intel Mac / Linux amd64 setup.
- The `yi-rtsp-poc` container already exists, with its authenticated persistent
  configuration and privately supplied ARM64 YI library, and runs an image
  built from this fork's persistent media-channel fix.
- Driveway is powered on. Close YI Home and tinyCam for an isolated test.
- Do not replace, delete or recreate the existing volume for this proof.

No credentials need to be passed to the scripts. Never paste them into a
command, issue or commit. The scripts obtain the existing API token and
connection material inside the container without printing those values.

## Run

From a clean checkout of this fork:

```sh
python3 -m unittest discover -s tests -v
sh tools/streaming-proof/run-proof.sh
```

The first command tests the descriptor routing and version-locked patch,
alongside the upstream upload tests; it does not contact cameras or YI cloud.
It needs permission to bind temporary loopback sockets for the upstream tests.
The second command starts the existing container if stopped and copies only
the capture driver into `/tmp`. It runs the normal installed stable relay
with the material broker for 15 seconds, and
validates the resulting MPEG-TS with FFprobe and strict FFmpeg decoding.
A 60-second outer deadline (plus 5-second kill grace) bounds the relay run.

Success requires relay exit zero, H.264/AAC reported by FFprobe, and strict
audio/video decode exit zero. The decoded capture is copied into a timestamped
`tools/proof-*` directory, which is ignored by Git. The 15-second timer begins
before connection setup, so playable content will be shorter than 15 seconds.
Do not repeatedly probe a failing camera without examining the private logs.

This workflow reuses an existing configured runtime. It does not claim that
a fresh Docker installation can authenticate without initial private setup,
or that the newly checked-out image has been fully rebuilt and validated.

## How the normal fix works

The Dockerfile and normal startup run `yi_native_worker.py`, which accepts
exactly the verified original worker hash. At offset `0x8d4`, it changes the
media write descriptor from 1 to 3 in a separate `.fd3` executable. The normal
relay launches this executable through `tools/yi_media_worker.sh`, which
duplicates the media pipe onto fd 3 and discards vendor stdout. Native worker
stage diagnostics remain on stderr. The proprietary library and original
worker stay byte-for-byte unchanged. Preparation refuses unknown versions,
symlinks or conflicting outputs, and accepts an identical prepared worker.

`run_separated_relay.py` invokes the normal installed stable relay without
monkeypatching its target resolver, worker or QEMU executable. Diagnostics remain private at
`/tmp/yi-investigation/separated-relay.stderr` inside the container. Never
upload that file without reviewing and redacting it. No temporary worker or
wrapper is required. The image contains the fix, including after recreation.

`patch_worker_fd.py` and `qemu-media-fd3.sh` preserve the original isolated
investigation method for reference. The current run script does not use them.

`direct_probe.py` is the earlier bounded original-worker observation tool.
It intentionally captures mixed stdout privately for diagnosis; that output
is not safe to publish and must not be treated as a clean video recording.

## Next milestone

Verify simultaneous Driveway and Garden playback through go2rtc. The source
rebuild can replace the version-locked patch if the native source becomes
available. Multi-camera reliability and the viewer remain separate milestones.
