#!/bin/sh
# Run from this bundle. Uses the existing container/account; creates no services.
set -eu
umask 077
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
docker start yi-rtsp-poc >/dev/null
docker exec yi-rtsp-poc mkdir -p /tmp/yi-investigation/worker
docker exec yi-rtsp-poc chmod 700 /tmp/yi-investigation /tmp/yi-investigation/worker
docker cp "$bundle_dir/patch_worker_fd.py" yi-rtsp-poc:/tmp/patch_worker_fd.py
docker cp "$bundle_dir/qemu-media-fd3.sh" yi-rtsp-poc:/tmp/qemu-media-fd3.sh
docker cp "$bundle_dir/run_separated_relay.py" yi-rtsp-poc:/tmp/run_separated_relay.py
docker exec yi-rtsp-poc python3 /tmp/patch_worker_fd.py /opt/yi-home/runtime/bionic-root/data/local/tmp/yi-phase3g/android_pppp_av_stream /tmp/yi-investigation/worker/android_pppp_av_stream
docker exec yi-rtsp-poc sh -c 'chmod 700 /tmp/qemu-media-fd3.sh; test -e /tmp/yi-investigation/worker/libPPPP_API.so || ln -s /opt/yi-home/runtime/bionic-root/data/local/tmp/yi-phase3g/libPPPP_API.so /tmp/yi-investigation/worker/libPPPP_API.so'
docker exec yi-rtsp-poc timeout -k 5 60 python3 /tmp/run_separated_relay.py
docker exec yi-rtsp-poc ffprobe -v error -show_entries stream=codec_name,codec_type,width,height,sample_rate,channels -show_entries format=duration,size -of json /tmp/yi-investigation/driveway-separated.ts
docker exec yi-rtsp-poc ffmpeg -hide_banner -v error -xerror -i /tmp/yi-investigation/driveway-separated.ts -map 0 -f null -
proof_dir="$bundle_dir/../proof-$(date +%Y%m%d-%H%M%S)"
mkdir "$proof_dir"
docker cp yi-rtsp-poc:/tmp/yi-investigation/driveway-separated.ts "$proof_dir/driveway-live.ts"
chmod 600 "$proof_dir/driveway-live.ts"
printf 'Validated capture saved in %s\n' "$proof_dir"
