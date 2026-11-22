# Reproduce the independent streaming proof

This is a bounded diagnostic for the existing `yi-rtsp-poc` Docker bridge,
not the permanent streaming fix or a viewer. It selects only the powered
camera named **Driveway** and uses the bridge's authenticated material broker.

## Prerequisites

- Docker is running on the existing Intel Mac / Linux amd64 setup.
- The `yi-rtsp-poc` container already exists, with its authenticated persistent
  configuration and privately supplied ARM64 YI library.
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
the proof utilities into `/tmp`. It verifies the installed worker's SHA256,
creates a separate patched copy, runs the existing relay for 15 seconds, and
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

## How the workaround works

`patch_worker_fd.py` accepts exactly the verified original worker hash. At
offset `0x8d4`, it changes the media write descriptor from 1 to 3. The wrapper
duplicates the media pipe onto fd 3 and redirects ordinary stdout to stderr.
The proprietary library stays byte-for-byte unchanged. The installed worker
also stays unchanged. The patcher refuses unknown versions or conflicting
destination files, and accepts an identical existing patched output.

`run_separated_relay.py` reuses `request_runtime_material` and the existing
Python relay. Raw diagnostics remain private at
`/tmp/yi-investigation/separated-relay.stderr` inside the container. Never
upload that file without reviewing and redacting it. The setup is temporary;
container recreation removes it, and the script recreates it on its next run.

`direct_probe.py` is the earlier bounded original-worker observation tool.
It intentionally captures mixed stdout privately for diagnosis; that output
is not safe to publish and must not be treated as a clean video recording.

## Next milestone

Integrate media/diagnostic separation into normal startup, preferably by
obtaining and rebuilding the worker source. Then verify simultaneous Driveway
and Garden playback through go2rtc. Those changes are outside this proof.
