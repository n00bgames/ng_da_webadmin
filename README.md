# n00bGame's Dune Awakening Web-Admin

A companion administration panel for RedBlink's self-hosted **Dune Awakening** Docker stack.

Built for private/LAN-hosted servers with a focus on:

* Live player visibility
* Live map visualization
* Teleportation and recovery tools
* Item grants
* Server administration
* Infrastructure management
* RedBlink stack management

---

# Current Version

```text
0.6.4-alpha
```

Target RedBlink Stack:

```text
v1.3.2
```

---

# Alpha Status

This project is currently in active development.

Features are tested on private self-hosted environments and may change between releases.

Always maintain backups of:

* Database
* World data
* Configuration files

before using administrative tools.

---

# Features

## Authentication & Roles

* First-run admin account creation
* Viewer / Operator / Admin roles
* Session authentication
* Role-based permissions

---

## Dashboard

### System Resources

Live AJAX-updating dashboard showing:

* CPU usage
* RAM usage
* Disk usage
* Network RX/TX
* World statistics

### World Summary

* Total players
* Online players
* Total vehicles
* Hagga Basin vehicle count
* Deep Desert vehicle count

---

## Who's Online

* Online player list
* Viewer-safe Hagga Basin map preview
* Live player visibility

---

## Live Map

### Hagga Basin

* Live player markers
* Live vehicle markers
* Live base markers
* Mouse-wheel zoom
* Click-drag panning

### Deep Desert

* Dedicated map support

### Teleportation

* Offline player teleport
* Click-to-select coordinates
* Emergency Return to Safe Hagga Basin Point

---

## Item Grants

* Item search
* Item grants
* Character selection dropdown

### Included Templates

* Mk6 Scout Ornithopter
* Mk6 Medium Ornithopter

Medium Ornithopter includes:

* Chassis
* Hull
* Components
* Inventory
* Scanner
* Launcher
* Fuel
* 250 Rocket Ammo

---

## Vehicle Tools

Experimental:

* Vehicle module repair
* Vehicle durability modification

---

## Server Management

### Service Controls

* Restart services
* Spawn maps
* Despawn maps
* View logs

### Runtime Information

* Ports
* Server status
* Running maps

---

## Map Runtime Controls (RedBlink v1.3.2)

Supports:

```bash
dune maps list
dune maps mode
dune maps set <map> dynamic
dune maps set <map> always-on
dune maps reconcile
```

Examples:

* Arrakeen always-on
* Arrakeen dynamic
* Harko Village always-on
* Harko Village dynamic
* Deep Desert always-on
* Deep Desert dynamic

---

## Infrastructure

### Host Diagnostics

* System information
* Docker status
* Dune status

### Host Shell

Optional browser-based terminal.

Supports:

* Interactive shell
* Open Shell + dune init
* Open Shell + dune manager

### RedBlink Installer

Guided installer for:

* Base packages
* Docker
* Docker Compose
* Docker permissions
* Dune command installation
* Stack deployment

---

# Installation

Clone the repository:

```bash
git clone https://github.com/n00bgames/ng_da_webadmin.git
cd ng_da_webadmin
```

Install Linux prerequisites:

```bash
sudo apt update
sudo apt install -y \
python3 \
python3-pip \
python3-venv \
git \
curl
```

Create virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install Python requirements:

```bash
pip install -r requirements.txt
```

---

# Setup

Run setup utility:

```bash
chmod +x setup.sh
./setup.sh
```

This creates a restricted sudo configuration required for Infrastructure installer functions.

---

# Starting The Panel

```bash
chmod +x start.sh
./start.sh
```

Browse to:

```text
http://127.0.0.1:8088
```

---

# Infrastructure Features

Infrastructure tooling is disabled by default.

Enabled by:

```bash
export ENABLE_HOST_COMMAND_RUNNER=1
export ENABLE_STACK_INSTALLER=1
export ENABLE_HOST_SHELL=1
```

or by using:

```bash
./start.sh
```

---

# Included Assets

Repository includes:

```text
static/
├── dune-admin.png
├── arrakis_hb.webp
└── deep_desert.webp
```

---

# Security Notes

This project is intended for:

* LAN environments
* VPN-hosted environments
* Private server administration

Do NOT expose directly to the public Internet without additional protections.

Administrative features include:

* Item spawning
* Database modification
* Teleportation
* Service control
* Docker management
* Interactive host shell

Use responsibly.

---

# Known Issues

* Vehicle repair remains experimental.
* Browser shell resizing continues to receive improvements.
* Map marker rendering may vary between releases.

---

# Planned Features

* Deep Desert PvP/PvE dual-mode controls
* Autoscaler controls
* Dynamic map configuration UI
* Backup management
* Remote RedBlink deployment improvements
* Infrastructure monitoring
* Host management tools

---

# Credits

* RedBlink and contributors
* Funcom
* Community researchers and testers

---

# License

GNU General Public License v3.0 (GPLv3)

See:

```text
LICENSE
```

for full license text.
