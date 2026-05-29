Dune Admin Web App 0.6.4-alpha
================================

Public demonstration / RedBlink review build.

This is an alpha companion web panel for RedBlink's Dune Awakening self-hosted Docker stack.

IMPORTANT SECURITY NOTES
------------------------
- LAN/private use only.
- Do not expose directly to the public internet.
- Use a reverse proxy, HTTPS, and additional auth before any wider exposure.
- This panel can grant items, restart services, run direct SQL utilities, repair vehicles, and teleport offline characters.
- Direct SQL tools are intentionally restricted and should be treated as sharp objects.

TESTED FEATURES
---------------
- Login and first-run admin setup
- Role separation: viewer / operator / admin
- Viewer-safe Who's Online list
- Viewer-safe Hagga Basin map preview
- Item search and grants
- Mk6 Scout Ornithopter grant
- Mk6 Medium Ornithopter kit grant
- Live map with Hagga Basin and Deep Desert tabs
- Mouse-wheel zoom and click-drag pan
- Click map to populate teleport target coordinates
- Offline teleport
- Emergency Return to Safe Hagga Basin Point
- Action logs
- Server restart/map spawn controls
- Vehicle module repair at sane default value

KNOWN RISKS / ALPHA LIMITATIONS
-------------------------------
- Teleport is intended for offline characters.
- Vehicle repair writes directly to dune.vehicle_modules stats JSON.
- Gear overrepair requires items to be unequipped and in inventory.
- Deep Desert teleport partition should be verified on each stack/server setup.
- Map images are local assets and are not included unless explicitly copied in.
- This is not an official RedBlink release unless RedBlink accepts/blesses it.

REQUIRED LOCAL ASSETS
---------------------
Place these files in ./static:

- dune-admin.png
- arrakis_hb.webp
- deep_desert.webp

EXPECTED LAYOUT
---------------
~/dune-admin-web/
├── app.py
├── templates/
├── static/
│   ├── dune-admin.js
│   ├── dune-admin.png
│   ├── arrakis_hb.webp
│   └── deep_desert.webp
├── users.db
├── logs/
└── venv/

INSTALL / UPDATE NOTES
----------------------
Before replacing your running copy:

cp -a ~/dune-admin-web ~/dune-admin-web.backup-before-0.5.8

Then copy app.py, templates/, and static/dune-admin.js from this package.

Preserve:
- users.db
- logs/
- static/dune-admin.png
- static/arrakis_hb.webp
- static/deep_desert.webp

VERSION
-------
Panel: 0.6.4-alpha
Target RedBlink Stack: v1.3.1


0.5.9-alpha INFRASTRUCTURE FEATURES
-----------------------------------
New admin-only infrastructure page:

- Host command runner
- Guided RedBlink stack installer
- Optional full browser shell

These features are disabled by default.

Enable intentionally with environment variables:

export ENABLE_HOST_COMMAND_RUNNER=1
export ENABLE_STACK_INSTALLER=1
export ENABLE_HOST_SHELL=1

Optional install target override:

export REDBLINK_INSTALL_DIR=/home/steihl/dune-awakening-selfhost-docker

WARNING:
The full host shell runs with the permissions of the user running app.py.
Treat it as equivalent to SSH access to the VM host.


0.5.9.1-alpha PATCH NOTES
-------------------------
- Installer commands now use sudo -n to avoid hanging on sudo password prompts.
- Added installer steps/buttons for:
  - base packages
  - official Docker install
  - Ubuntu Docker fallback
  - Docker Compose plugin
  - Docker group membership
  - Docker service enable/start

NOTE:
For web-triggered installer steps that require sudo, configure passwordless sudo
for trusted admins or run the app under an account that can execute the required
commands without an interactive password prompt.


0.6.0-alpha PATCH NOTES
-----------------------
- dune init is now treated as an interactive shell workflow.
- Added Infrastructure buttons:
  - Open Shell and Run dune init
  - Open Shell and Run dune manager
- Removed the misleading non-interactive dune init installer flow from the UI.
- Included GPLv3 LICENSE in the release package.

NOTE:
Host Shell must be enabled with:

export ENABLE_HOST_SHELL=1

The shell runs as the same Linux user that launches app.py.


0.6.1-alpha PATCH NOTES
-----------------------
- Doubled host shell console height.
- Added Infrastructure passwordless sudo / visudo placard.
- Added dashboard system resource panel:
  - CPU usage
  - RAM usage
  - disk usage
  - network sent/received since boot
- Added dashboard world summary:
  - total players
  - online players
  - total vehicles
  - vehicles in Hagga Basin
  - vehicles in Deep Desert
- Added psutil dependency.


0.6.2-alpha PATCH NOTES
-----------------------
- Added /api/dashboard-metrics.
- Dashboard CPU/RAM/Disk now render as graphical usage bars.
- Dashboard metrics refresh by AJAX every 5 seconds.
- Network panel now shows RX/TX rate plus totals.
- World summary cards refresh live with dashboard metrics.


0.6.2.1-alpha PATCH NOTES
-------------------------
- Reduced live map marker/blip size by 50% for better map readability.
- Reduced Who's Online Hagga Basin preview markers by 50%.


0.6.3-alpha PATCH NOTES
-----------------------
- Added xterm.js FitAddon for the host shell.
- Host shell now fills the available terminal panel instead of rendering as a tiny viewport.
- Terminal refits after startup and browser resize.


0.6.4-alpha PATCH NOTES
-----------------------
- Target RedBlink stack updated to v1.3.2.
- Added Server Management controls for:
  - dune maps list
  - dune maps mode
  - dune maps set <map> dynamic
  - dune maps set <map> always-on
  - dune maps reconcile
- Added Deep Desert dual PvP/PvE controls:
  - status
  - enable
  - disable
  - force disable
  - bootstrap
  - repair
- Hardened browser shell fitting with FitAddon fallback/manual resize.
