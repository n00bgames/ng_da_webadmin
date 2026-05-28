n00bGame's Dune Awakening Web-Admin

A companion administration panel for RedBlink's self-hosted Dune Awakening Docker stack.

Built for private/LAN-hosted servers with a focus on:

live player visibility
quality-of-life admin tools
item grants
map visualization
offline teleportation
operational convenience

⚠️ Alpha Status:

This project is currently in alpha and under active development.

Some systems are stable and tested.
Others are experimental and intended for controlled/private environments only.

Use at your own risk and always maintain database/world backups.

Current Features:
Authentication & Roles
First-run admin account creation
Viewer / Operator / Admin roles
Session-based authentication
Player Visibility
Who's Online page
Live Hagga Basin map preview
Live actor markers from dune.actors.transform
Vehicle/base/player visualization
Item & Vehicle Tools
Item search and grants
Mk6 Scout Ornithopter grant
Mk6 Medium Ornithopter kit grant
Vehicle module repair (experimental)
Live Map System
Hagga Basin map
Deep Desert map
Mouse-wheel zoom
Click-drag panning
Click-to-select teleport coordinates
Teleportation
Offline teleportation
Emergency Return to Safe Hagga Basin Point
Character dropdown targeting
Administrative Utilities
Action logging
Server/service controls
SQL utility integration
Recovery/unstuck tooling
Included Assets

The repository already includes the required UI/map assets inside:

./static/

Included assets:

dune-admin.png
arrakis_hb.webp
deep_desert.webp

Requirements:
Python 3.11+
Docker
RedBlink Dune Awakening self-hosted stack
Linux host (Ubuntu 24.0.4)

Installation:
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

Running:
source venv/bin/activate

python app.py

Then browse to:

http://127.0.0.1:8088

Recommended Security Practices:

This project is intended for:

LAN use
private servers
trusted operators/admins

Strongly recommended:

reverse proxy
HTTPS
VPN or private network access
additional auth layers if internet exposed

This panel contains tools capable of:

direct SQL modification
player teleportation
item spawning
service control

Treat it accordingly.

Known Experimental Features:
Vehicle Repair

Vehicle module repair currently writes durability values directly into:

dune.vehicle_modules.stats

Behavior may vary depending on:

runtime caching
vehicle respawn state
server updates
Offline Teleport

Teleportation is intended for offline characters.

Online teleports may not apply correctly because the live server owns actor state.

Planned Features:
Infrastructure management layer
Remote RedBlink stack deployment
Automated prerequisite installation
Backup tooling
VM/container monitoring
Optional host console integration
Improved map overlays
Deep Desert enhancements

Philosophy:

This project exists to improve the self-hosted Dune Awakening experience through practical tooling and experimentation while remaining respectful of:

RedBlink's work
Funcom's data structures
private server operators
player safety

Credits:
RedBlink and contributors for the self-hosted stack
Funcom for Dune Awakening
Community researchers documenting DB structures and server behavior
