Dune Admin Web App 0.5.9-alpha
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
Panel: 0.5.9-alpha
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
