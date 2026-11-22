# First milestone: two simultaneous independent YI streams

## Scope

Driveway and Garden must publish and decode together through the normal
Docker bridge, without temporary worker modifications or YI Home/tinyCam
providing media. YI cloud authentication remains in use. The three unplugged
cameras are excluded from live streaming tests. This is the streaming
foundation; a browser viewer is a later milestone.

The underlying persistent media-channel fix is documented in
[persistent-media-channel.md](persistent-media-channel.md) and merged in PR #1.

## Bounded reproduction

With the updated `yi-rtsp-poc` container already configured, copy the manual
integration test into the container and run it:

```sh
docker cp tools/streaming-proof/check_two_cameras.py yi-rtsp-poc:/tmp/check_two_cameras.py
docker exec yi-rtsp-poc timeout -k 5 1915 python3 /tmp/check_two_cameras.py start 1800
```

The `start` mode requests the two existing managed runtimes through the
authenticated backend API. The `decode` mode verifies already-running sources
without issuing start requests. Both use the project's stream identity helper
to construct RTSP paths and run concurrent strict FFmpeg audio/video decoders.
Each run is bounded to 1–1800 seconds, plus connection/cleanup allowances.
Media is decoded to the null output, so this test does not record 30 minutes
of private camera video. Only numeric summaries and private local stderr and
progress files are written under `/tmp/two-camera-check`.

To verify restoration after restarting the container:

```sh
docker restart -t 25 yi-rtsp-poc
docker exec yi-rtsp-poc timeout -k 5 200 python3 /tmp/check_two_cameras.py decode 20
```

The script waits for backend discovery after restart. No explicit camera
start commands are sent in the second test. A successful
decode therefore checks that persisted running intent and normal startup
restore both streams. Reopening RTSP clients exercises consumer reconnection.
Physical camera power loss, remote access and browser playback remain outside
this milestone.

Both managed streams intentionally remain available after a successful test.
To stop their bridge sessions without changing camera configuration:

```sh
docker exec yi-rtsp-poc python3 /tmp/check_two_cameras.py stop
```

## Completed acceptance evidence — 22 November 2026

[Sanitized verification record](milestone1-verification.json).

- Simultaneous 1800-second strict RTSP decode: Driveway 36,000 video frames,
  Garden 35,981; both decoded to 1799.95 seconds, exited zero and emitted no
  decode errors. Both sources provide 1920x1080 H.264 and mono AAC at 16 kHz.
- 57 continuity samples recorded no runtime restarts and continuously attached
  publishers. An extra Driveway viewer decoded successfully alongside the
  existing long-running clients.
- Stopping and starting Garden's bridge session left Driveway decoding and
  publishing, with its runtime restart count unchanged. Both strict decodes
  exited zero with no error output.
- Both streams restored automatically after a container restart and passed
  a strict 20-second audio/video decode without issuing start commands.
- The final image `yi-rtsp:milestone1` was rebuilt and deployed by container
  recreation. Both streams again restored automatically and decoded
  successfully without temporary worker installation. Media component hashes
  match the image used in the long run. Account configuration, API token and
  proprietary library hashes are unchanged.
- All eight unit tests passed, the Docker build succeeded, and independent
  code review reported no remaining actionable findings.

The long run used `-map 0`, decoding all advertised tracks; independent
FFprobe verified both audio and video. The delivered utility additionally
requires explicit video/audio mappings and checks decoded duration, preventing
a missing audio track or early clean EOF from passing future tests.

The final suite rerun exposed an existing APK upload cleanup race. Both real
HTTP tests now deterministically check that the temporary APK has already been
deleted when success is emitted. Cleanup now occurs before that response,
and the original failure-path cleanup remains in place. This fix is included
in the final image; it does not change the streaming pipeline.

Do not infer success from
discovery, API start responses, publisher byte counters or process liveness
alone: both FFmpeg decoders must complete successfully with video frames.
