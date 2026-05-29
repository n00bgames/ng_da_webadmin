<h1 align="center">n00bGame's Dune Awakening Web-Admin</h1>

<p align="center">
  Companion administration platform for RedBlink's Dune Awakening self-hosted Docker stack.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.6.5--rc1-orange">
  <img src="https://img.shields.io/badge/license-GPLv3-green">
  <img src="https://img.shields.io/badge/RedBlink-v1.3.2-blue">
  <img src="https://img.shields.io/badge/status-release%20candidate-orange">
  <img src="https://img.shields.io/badge/platform-Linux-lightgrey">
  <img src="https://img.shields.io/badge/python-3.11+-blue">
</p>

<p align="center">
  <img src="images/logo.png" alt="Dune Awakening Web-Admin logo" width="720">
</p>

---

## Status

Current panel version: `0.6.5-rc1`

Target RedBlink Stack: `v1.3.2`

This release candidate is intended for private/LAN/VPN-hosted self-hosted servers.

---

## Screenshots

### Dashboard

![Dashboard](images/dashboard.png)

### Live Map

![Live map](images/live-map.png)

### Infrastructure

![Infrastructure](images/infrastructure.png)

### RedBlink Manager Shell Workflow

![Dune manager shell](images/dune-manager.png)

---

## Features

### Dashboard

- Live CPU/RAM/Disk usage bars
- Network RX/TX totals and rates
- AJAX auto-refresh
- World/player/vehicle summary cards

### Live Maps

- Hagga Basin live map
- Deep Desert map support
- Player, vehicle, and base markers
- Mouse-wheel zoom
- Drag panning
- Click-to-fill teleport coordinates

### Teleportation

- Offline teleportation
- Character dropdown targeting
- Emergency return to safe Hagga Basin point
- Hagga Basin partition: `1`
- Deep Desert partition: `8`

### Vehicle Teleport

- Admin-only vehicle relocation using `dune.actors`
- Preserves existing vehicle rotation while updating map, partition, and XYZ
- Supported actor families: Ornithopter, Sandbike, Buggy, TreadWheel, SandCrawler
- Zoomable, draggable admin vehicle map with double-click coordinate targeting
- Requires restarting the affected map/server instance before loaded vehicles appear at the new location
- Z-axis warning because below-terrain values can place vehicles underground

### Item Grants

- Item search
- Item grant tools
- Mk6 Scout Ornithopter grant
- Mk6 Medium Ornithopter grant
- Medium thopter kit includes 250 rockets

### Repair Tools

- Admin-only gear overrepair
- Admin-only vehicle module repair
- Sane default repair values with editable durability fields

### Server Management

- Grouped restart controls:
  - Gameplay Services: Survival, Deep Desert, Overmap
  - Infrastructure Services: Gateway, Director, Text Router
- Map spawn controls
- RedBlink v1.3.2 map runtime controls:
  - `dune maps list`
  - `dune maps mode`
  - `dune maps set <map> dynamic`
  - `dune maps set <map> always-on`
  - `dune maps reconcile`

### Deep Desert

- Dual PvP/PvE status
- Enable dual mode
- Disable dual mode
- Force disable dual mode
- Bootstrap dual mode
- Repair dual mode

### Database Tools

Safe database actions:

- DB Health
- DB Status
- List Backups
- Create Backup

Restore/import/delete database actions are intentionally not exposed yet.

### Infrastructure

- Host diagnostics
- Docker diagnostics
- Guided RedBlink installer
- Browser-based host shell
- Open Shell + `dune init`
- Open Shell + `dune manager`

---

## Requirements

```bash
sudo apt update
sudo apt install -y \
python3 \
python3-pip \
python3-venv \
git \
curl
```

---

## Installation

```bash
git clone https://github.com/n00bgames/ng_da_webadmin.git
cd ng_da_webadmin

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

chmod +x setup.sh
./setup.sh

chmod +x start.sh restart.sh shutdown.sh
./start.sh
```

Browse to:

```text
http://127.0.0.1:8088
```

---

## Runtime Control

```bash
./start.sh --screen       # detached GNU screen session
./start.sh --headless     # nohup background process with webadmin.pid
./restart.sh              # restarts using the detected/current launch mode
./shutdown.sh             # stops screen or headless mode
```

For screen mode:

```bash
screen -r dune-admin-web
```

Detach from screen with `Ctrl+A`, then `D`.

---

## Configuration

Default RedBlink stack path:

```bash
~/dune-awakening-selfhost-docker
```

Override with:

```bash
export DUNE_ROOT=/path/to/dune-awakening-selfhost-docker
```

Set a real secret before sharing or deploying:

```bash
export DUNE_SECRET_KEY='long-random-string'
```

Optional high-trust infrastructure features:

```bash
export ENABLE_HOST_COMMAND_RUNNER=1
export ENABLE_STACK_INSTALLER=1
export ENABLE_HOST_SHELL=1
```

Optional RedBlink installer target override:

```bash
export REDBLINK_INSTALL_DIR=/path/to/dune-awakening-selfhost-docker
```

---

## Upgrading

Before replacing a running copy, back it up:

```bash
cp -a ~/dune-admin-web ~/dune-admin-web.backup-before-0.6.5-rc1
```

Preserve local runtime data:

- `users.db`
- `logs/`
- `.env`, if used

Then update:

```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
./start.sh
```

---

## Runtime Assets

Runtime assets live in `static/`:

- `dune-admin.js`
- `dune-admin.png`
- `dune-admin-large.png`
- `arrakis_hb.webp`
- `deep_desert.webp`

The map image files are required for the live map pages to render properly.

GitHub README screenshots live in `images/`:

- `dashboard.png`
- `dune-manager.png`
- `infrastructure.png`
- `live-map.png`
- `logo.png`

When dashboard, live map, infrastructure, or README sections change, refresh the matching image before publishing.

---

## Line Endings

The repository includes `.gitattributes` rules to keep Linux shell scripts using LF line endings.

If shell scripts still fail with `cannot execute: required file not found` or `/bin/bash^M`, run:

```bash
find . -type f -name "*.sh" -exec sed -i 's/\r$//' {} \;
chmod +x setup.sh start.sh restart.sh shutdown.sh
```

---

## Security Notes

This project is intended for LAN/private/VPN environments. Do not expose it directly to the public internet.

`setup.sh` creates a restricted sudoers file under:

```text
/etc/sudoers.d/dune-web-admin
```

The optional browser host shell runs with the permissions of the Linux user that launches `app.py`. Treat it like SSH access to the host.

Viewer accounts are intentionally privacy-limited. They can see viewer-safe status, online player names, and map markers, but they cannot view sensitive database identifiers such as raw player IDs, account IDs, FLS IDs, Funcom IDs, direct logs, or admin database output.

---

## Known Issues

- Map marker styling is functional but still being refined.
- Autoscaler controls are planned.
- VIP role is planned for a later release.
- Vehicle repair writes directly to `dune.vehicle_modules` stats JSON.
- Vehicle teleport writes to `dune.actors`, but loaded vehicle actors do not reload their transform until the affected map/server instance restarts.
- Gear overrepair requires items to be unequipped and in inventory.
- Deep Desert teleport partition should be verified on each stack/server setup.

---

## Planned

- VIP role
- VIP self-only teleport
- VIP self-only item grants
- VIP self-only thopter grants
- Vehicle ownership discovery for VIP self-repair
- Live map side panel / scroll-safe layout
- Autoscaler controls
- Dynamic map discovery from RedBlink map runtime config

---

## Release Notes

### 0.6.5-rc1

- Updated RedBlink stack target to `v1.3.2`.
- Added RedBlink map runtime controls.
- Added Deep Desert dual PvP/PvE controls.
- Hardened browser shell fitting.
- Included runtime map and banner assets.
- Included GitHub README images under `images/`.
- Added `.gitattributes` line-ending guard.
- Added `setup.sh`.
- Improved `start.sh`.
- Added grouped restart services.
- Added DB health/status/list/backup controls.
- Added RedBlink v1.3.2 map controls.
- Added admin-only vehicle teleport for Ornithopter, Sandbike, Buggy, TreadWheel, and SandCrawler actor families.
- Documented that vehicle teleport requires an affected map/server restart before loaded vehicle actors move in-game.
- Added `restart.sh` and `shutdown.sh` runtime helpers for screen/headless daemon control.
- Updated release packaging and GPLv3 metadata.

---

## Credits

- RedBlink and contributors
- Funcom
- Community researchers and testers

---

## License

GPLv3. See `LICENSE`.
