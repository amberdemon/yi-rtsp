#!/bin/sh
# Run from this bundle. Uses the existing container/account; creates no services.
set -eu
umask 077
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
docker start yi-rtsp-poc >/dev/null
docker cp "$bundle_dir/run_separated_relay.py" yi-rtsp-poc:/tmp/run_separated_relay.py
docker exec yi-rtsp-poc timeout -k 5 60 python3 /tmp/run_separated_relay.py
docker exec yi-rtsp-poc ffprobe -v error -show_entries stream=codec_name,codec_type,width,height,sample_rate,channels -show_entries format=duration,size -of json /tmp/yi-investigation/driveway-separated.ts
docker exec yi-rtsp-poc ffmpeg -hide_banner -v error -xerror -i /tmp/yi-investigation/driveway-separated.ts -map 0 -f null -
proof_dir="$bundle_dir/../proof-$(date +%Y%m%d-%H%M%S)"
mkdir "$proof_dir"
docker cp yi-rtsp-poc:/tmp/yi-investigation/driveway-separated.ts "$proof_dir/driveway-live.ts"
chmod 600 "$proof_dir/driveway-live.ts"
printf 'Validated capture saved in %s\n' "$proof_dir"
