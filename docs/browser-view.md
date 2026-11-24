# Home Wi-Fi browser viewer

The viewer shows active camera streams together over HTTPS with a separate
viewer password. It provides a responsive grid, fullscreen, audio from one
camera at a time and an optional list of offline cameras. Both videos start
muted. Layout persists in the browser. Returning after screen lock reconnects
muted; tap Listen to enable audio again. Physical Android Chrome acceptance passed on 24 November 2026: the user
confirmed sign-in, both camera feeds, fullscreen, exclusive audio, muted recovery
after screen lock and sign-out.

## Access and privacy

Container port 8097 serves HTTPS. Bind it only to loopback and the Mac's private
home-network address, for example `127.0.0.1:18097:8097` plus
`HOME_LAN_IP:18097:8097`. Open `https://HOME_LAN_IP:18097/` on the same Wi-Fi.
Keep the backend API (8099), RTSP (8554), and go2rtc private. Do not add router
port forwarding. The Docker Mac must remain awake and connected.

The server proxies fragmented MP4 from the existing private go2rtc publisher.
MediaSource plays H.264/AAC without video transcoding. No hosted scripts,
analytics, fonts, STUN servers or media services are added. YI cloud services
continue to provide account/session connectivity.

Only camera display names, opaque stable IDs and availability reach the camera
list. YI credentials and the backend bearer token stay inside the container.
Media paths accept known active camera IDs only. Explicit Host checks, exact
HTTPS Origin checks, cross-site data/action rejection and CSP constrain access. Top-level links from
other apps can open the public entry page; frames and cross-site API/media
requests remain rejected.

The separate viewer password uses salted scrypt. Secure, HttpOnly, SameSite
cookies contain opaque sessions; only session hashes are stored. Sessions expire
after eight hours or 30 minutes idle, survive bridge restarts, and are revoked on
logout or password change. Login is rate limited. Logout aborts browser media;
server streams check session validity between chunks. If logout cannot reach the
bridge, the page reports that revocation is still pending.

## Provision and build

```sh
docker build -t yi-rtsp:secure-lan --build-arg BUILD_VERSION=0.4.0-secure-lan yi_home
```

Reuse the existing private vendor mount and persistent `/data` volume. Stop the
bridge before provisioning or changing its password. Never run two backends
against that volume simultaneously. Retain the stopped previous container for
rollback; its earlier HTTP viewer lacks this milestone's access controls.

Set `/data/viewer/network.json` to a JSON object with a `hosts` array containing
only exact addresses used by clients: `localhost`, `127.0.0.1`, your private LAN
IP and optionally the Mac's `.local` name. Set file mode 0600 and directory 0700.
Wildcards and public addresses are rejected by certificate generation.

With the bridge stopped, this interactive helper prompts without echoing the
password (substitute your actual persistent volume name):

```sh
docker run --rm -it --entrypoint python3 \
  -v YOUR_DATA_VOLUME:/data yi-rtsp:secure-lan -c '
import getpass, sys
from pathlib import Path
sys.path.insert(0, "/opt/yi-home/app")
from yi_viewer_auth import ViewerAuth, lock_store
path = Path("/data/viewer/auth.json")
password = getpass.getpass("Separate viewer password (12+ characters): ")
if password != getpass.getpass("Repeat password: "):
    raise SystemExit("Passwords differ; nothing changed")
with lock_store(path):
    ViewerAuth(path).set_password(password)
print("Password stored; sessions revoked. Start the bridge.")'
```

The normal startup creates a private CA and HTTPS certificate under
`/data/viewer/tls`. Unconfigured viewers deny login. A running service holds an
exclusive auth-store lock, so the password helper refuses changes until it is
stopped. The lower-level `yi_viewer_auth.py` CLI accepts the password on stdin;
never put a password in command arguments or shell history.

## Trust on Android

Copy only `/data/viewer/tls/yi-view-home-ca.crt` to your Android device. Install it
through Android Settings under Encryption & credentials → Install a certificate
→ CA certificate (menu wording varies). This authorizes the private home CA on
that device. Do not transfer `ca.key`, `server.key` or `auth.json`.

Open Chrome at the configured HTTPS address after installation. There should be
no certificate warning; do not bypass one. Sign in with the separate viewer
password. Never enter the YI account password into this viewer. Android menu
background: [Google certificate help](https://support.google.com/pixelphone/answer/2844832?hl=en).

The CA is retained across leaf renewal and configured-address changes. Startup
renews the leaf when needed; update the network file and Docker binding if DHCP
changes the address, then restart. A DHCP reservation avoids that change. Back
up `/data/viewer` as private sensitive data alongside the existing bridge data;
losing the CA requires device trust setup again. Leaf certificates last one
year, the CA ten years; CA replacement requires a deliberate trust update.

## Verification and acceptance

```sh
python3 -m unittest discover -s tests -v
node --check yi_home/rootfs/opt/yi-home/app/viewer/app.js
node --check yi_home/rootfs/opt/yi-home/app/viewer/login.js
bash -n yi_home/run.sh
```

Tests cover auth hashing, session persistence/expiry, rate limits, password-store
locking, anonymous denial, Host/Origin checks, media restrictions, logout,
real verified-CA HTTPS cookies and concurrent TLS handshake handling. Fixtures
contain no real camera credentials. Automated LAN checks separately verified
both real streams with audio/video decode and recovery after Docker restart.
See [current HTTPS evidence](secure-lan-verification.json); the earlier
[browser evidence](browser-verification.json) records the previous desktop UI
milestone, not physical Android acceptance.

On an actual Android phone/tablet on home Wi-Fi, verify trusted HTTPS, sign-in,
both moving pictures, one-camera audio, fullscreen enter/exit, screen lock for
10 seconds then automatic muted recovery, and logout returning to sign-in.
Keep screenshots/recordings private. A mobile viewport or decoded MP4 alone
does not establish this physical-device acceptance.

## Android connection troubleshooting

For `ERR_TOO_MANY_RETRIES` before any page loads, check Android Settings → Apps
→ Chrome → Permissions → Nearby devices. If already enabled, toggle it off and
on, then reopen Chrome. A documented Android/Chrome permission bug can leave
local-network access blocked despite the displayed permission state:
[Chromium issue](https://issues.chromium.org/issues/579403238).
Keep using the explicit HTTPS URL and the installed private CA.

## Camera reconnect credentials

Each new supervised relay launch refreshes the device list and per-camera TNP
connection details through the existing authenticated YI cloud session. Active
relays continue without that refresh. This prevents a disconnected camera from
retrying indefinitely with an older cached password after YI rotates its camera
credentials. The regression test rotates synthetic encrypted passwords and TNP
details between two launches and verifies the new values are used without an
additional account login.
