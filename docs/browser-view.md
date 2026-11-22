# Local browser view

Open **http://127.0.0.1:18097/** on the Mac running Docker.

The viewer shows the existing active camera streams together. It provides a
responsive two-column or one-column layout, fullscreen viewing, audio from one
camera at a time, and an optional list of offline cameras. Both videos start
muted. Layout choice persists in the browser. Interrupted streams reconnect
automatically, including after bridge restarts and browser history restoration.

## Architecture and privacy

The normal Docker startup launches `yi_browser_view.py` on container port 8097.
Its small HTTP server serves the static viewer and forwards live fragmented
MP4 from the existing, private go2rtc publisher. The browser uses MediaSource
to play the original H.264/AAC tracks without video transcoding. No external
scripts, fonts, analytics, STUN servers or hosted media services are used.

The backend bearer token is read inside the container and stays there. The
browser camera list contains only display name, opaque stable ID, online state
and active-stream state. Media routes accept only known active camera IDs;
they are not general URL proxies. Requests reject unexpected hostnames,
cross-site browser requests and mismatched Origins. CSP prevents embedding.

This milestone is local to the Docker Mac. Publish port 8097 on loopback only;
the viewer deliberately accepts `localhost`, `127.0.0.1` and `::1` Host names.
LAN/remote access and a viewer login require a separate access-control change.
Do not expose the viewer publicly or forward its port.

## Build and run

```sh
docker build -t yi-rtsp:browser --build-arg BUILD_VERSION=0.3.0-browser yi_home
```

Recreate the existing bridge container with the same private vendor mount and
persistent `/data` volume, retaining the API and RTSP bindings and adding:

```text
127.0.0.1:18097:8097
```

Keep the old stopped container for rollback. Never run old and new backends
against the same volume simultaneously. The existing YI account configuration,
vendor library and persisted running-camera intent are reused; no account
credentials are entered in the browser. Camera start/stop configuration remains
in the bridge API in this milestone. The viewer itself is read-only.

## Verification

```sh
python3 -m unittest discover -s tests -v
node --check yi_home/rootfs/opt/yi-home/app/viewer/app.js
bash -n yi_home/run.sh
```

The HTTP tests use local synthetic camera metadata and fake MP4 bytes. They
verify server-side authorization, response filtering, known/active-camera
media restrictions, Host/Origin checks and cross-site rejection; no real camera
or cloud credentials are needed. Live playback must be verified separately
in a real browser, not inferred from those unit tests or API responses.

The browser acceptance check observes two video elements with 1920x1080
dimensions, no media error, unpaused playback and advancing `currentTime`.
It also checks desktop/mobile layouts, exclusive audio selection, fullscreen,
page reload/history, and recovery while the Docker bridge is recreated.
Screenshots and camera media remain local and are excluded from this repository.
