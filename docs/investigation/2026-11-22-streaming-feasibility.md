# Independent YI streaming feasibility — 22 November 2026

**Verdict: PROVEN WORKING for a short Driveway capture.**

The original worker authenticated to the camera and received live media. An
isolated media-descriptor workaround then let the existing Python relay
produce 183 decodable H.264 video frames at 1920x1080, with 144 AAC audio frames
at 16 kHz mono. The MPEG-TS duration was 9.216 seconds, size 681,124 bytes.
Strict FFmpeg audio/video decoding exited zero with no error output.

No official YI app or tinyCam supplied media or participated in this pipeline.
Their state on other devices was not independently inspected. YI cloud remains
part of login, discovery and per-camera connection-material retrieval.

## Execution path

1. The existing authenticated `YiCloudSession` / `YiCameraManager` discovers
   cameras and decrypts the cloud-provided camera password.
2. `/v4/tnp/device_info` supplies connection material. The private Unix socket
   `/data/cloud-material.sock` supplies it to the proof without printing it.
3. `run_phase3e_tnp._build_units` constructs TNP-v2 startup commands
   `4881`, `9029`, `768`, and stop command `767`, including per-command auth.
4. `yi_native_av_relay` sends its `Y3F1` configuration over stdin to the ARM64
   `android_pppp_av_stream` worker under QEMU/Bionic.
5. The worker dynamically loads the privately supplied `libPPPP_API.so`,
   connects, sends startup commands, validates the camera response and emits
   `YAV1` media records.
6. The Python relay decrypts media, reorders video, and muxes H.264/AAC into
   MPEG-TS using FFmpeg. FFprobe and FFmpeg independently validate the capture.

The AV worker is supplied as a compiled binary. Its function symbols and
source filename are present, but corresponding C source was not found in
the investigated checkout. No guessed proprietary-library ABI was invoked.

## Confirmed stages

| Stage | Observed result |
| --- | --- |
| PPPP_Initialize | `0x00000000` |
| PPPP_Connect | `0x00000001`, session handle |
| Write 4881 | `0x00000038`, 56 bytes |
| Write 9029 | `0x00000034`, 52 bytes |
| Write 768 | `0x00000038`, 56 bytes |
| TNP response | version 2, command 4882, command number 1 |
| Camera auth result | 0; worker authentication PASS |
| Native worker / FFmpeg mux exits | 0 / 0 |
| Relay output | 183 video / 144 audio frames; PASS |
| Strict audio/video decode | exit 0, zero stderr bytes |

The worker does not invoke `PPPP_Check`; there is no result for that function.
Session validity is demonstrated functionally by the matching camera auth
response and independently decoded media, rather than inferred from cloud login.

## Earliest failure and controlled change

The unmodified Python relay expects binary-only stdout. The vendor library's
`PPPP_DebugTrace` functions call `printf`, placing timestamped TNP diagnostics
on that same channel. The relay rejects the text as invalid `YAV1` framing;
the stable adapter reports `relay_native_stream_header`, exit 93.
The packaged `liblog.so` Android logging stub returns zero without writing.

The workaround changes only the worker's media write descriptor from stdout
to fd 3, with a wrapper routing media separately from diagnostics. It changes
no credentials, authentication payloads or media decryption. The same runtime
then produces independently decoded video, establishing channel contamination
as a sufficient cause of the immediate framing failure in this environment.
It does not explain the termination of every historical bounded scan.

The linker-configuration warning also occurred during successful streaming.
No firmware, authentication or QEMU compatibility defect was demonstrated.

## Reproduction and source baseline

- Baseline upstream commit: `cd9408d38d5ffc95b81e0e9cc2d7a671f13bf09e`.
- [Reproduction commands and prerequisites](../../tools/streaming-proof/README.md).
- [Sanitized numeric verification](2026-11-22-verification.json).
- The Dockerfile uses the original FFmpeg archive host in place of the
  previously unavailable mirror, retaining the pinned version and checksum.

The workflow was repeated from this fork's clean preparation checkout on
22 November 2026 against the existing configured container. The relay exited
zero and produced a fresh 480,340-byte, 8.789-second H.264 1920x1080 / AAC
16 kHz mono capture; strict full audio/video decoding passed. All five unit
tests passed inside Docker. Python compilation, shell syntax and Git whitespace
checks passed. The Mac sandbox disallowed the upstream tests' temporary
loopback server, so the full suite was verified in the Linux container.
A full rebuild of the fork's image was not part of this preservation step.

Original worker SHA256:
`e91dacc2182bf8371bfb19bf4a6063ead3a6560f5dcc898c8430f0e773f5f200`

Patched worker SHA256:
`949e4bbee3346a045d5c6371f7dfb780efc86f38616b997bc19ae172f60b6802`

## Limits and next step

Only Driveway was streamed in this investigation. Garden was online but not
stream-tested, and unplugged cameras were not selected. Continuous RTSP,
multiple simultaneous cameras, reconnects and long-duration stability remain
unverified. The normal managed relay is unchanged; this is an isolated finite
proof, not a permanent startup fix.

Next: make the descriptor separation reproducible in normal startup, obtain
the native worker source if possible, and test two cameras through go2rtc.
No frontend has been built. No credentials, private camera identifiers,
proprietary YI binaries, raw logs or camera recordings accompany this report.
