# Persistent media-channel fix

## Behavior

Vendor `printf` diagnostics previously entered the binary `YAV1` media pipe,
causing the normal relay to exit with invalid native stream framing. The
normal relay now receives only media from the prepared worker's fd 3.
Vendor stdout goes to `/dev/null`; fixed native stage diagnostics still use
stderr. This also avoids publishing potentially private vendor log content.

`yi_native_worker.py` generates `android_pppp_av_stream.fd3` from the packaged
original during `docker build`. Normal `/run.sh` startup verifies the original
and prepared hashes and executable permissions before starting any backend.
Unknown originals or conflicting prepared files cause startup to fail rather
than silently using an unverified worker. The original worker and proprietary
`libPPPP_API.so` are not modified. No native worker source was found in this
checkout's history or the related upstream integration repository, so the
verified one-instruction patch remains an explicit version-locked dependency.

The runtime manifest records the derived worker hash and build-generated path.
The `.fd3` executable is generated inside the image, not committed to Git.
Both finite capability probes and managed streams use the same normal relay.
The historical proof tools no longer install temporary workers or QEMU wrappers.

## Build and deploy

```sh
docker build -t yi-rtsp:part2 --build-arg BUILD_VERSION=0.2.0-part2 yi_home
python3 -m unittest discover -s tests -v
```

Run the image using the existing persistent `/data` volume, private vendor
mount and localhost port bindings. Do not remove or reset the volume, replace
credentials, or bake the proprietary library into an image. In the investigated
setup the service retains API port `127.0.0.1:18099` and RTSP port
`127.0.0.1:18554`. Container restart policy is `unless-stopped`.

The original container was stopped and retained as `yi-rtsp-poc-before-part2`.
Its data was backed up locally in volume `yi-rtsp-poc-data-before-part2` before
starting the new image with the original `yi-rtsp-poc-data` volume.
The new service keeps the original name `yi-rtsp-poc`.

To reproduce a bounded capture using the installed fix:

```sh
sh tools/streaming-proof/run-proof.sh
```

The proof driver uses the installed stable relay and existing private material
broker. It selects Driveway only and strictly decodes the output with FFmpeg.
Starting multiple cameras is outside this milestone.

## Rollback

The retained container, original image and backup volume provide local rollback.
Stop the new container first so the old and new backends never write `/data`
concurrently. Rename the stopped new container to an unused backup name, rename
`yi-rtsp-poc-before-part2` back to `yi-rtsp-poc`, then start it. This reuses the
same volume; it does not remove any data. The old image retains the original
framing defect, so rollback restores the pre-fix behavior.

## Validation

See the adjacent sanitized Part 2 results for the completed runtime checks.
The unit suite covers repeatable preparation, unchanged original bytes,
unknown-version rejection, conflicting-output preservation and separation of
simulated vendor stdout, native diagnostics and binary media. The existing
upload tests continue to verify private vendor import behavior.
