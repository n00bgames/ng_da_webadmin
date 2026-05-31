#!/usr/bin/env python3
"""
Easy Dune Admin
Panel version: 0.7.0-beta
RedBlink stack compatibility target: v1.3.2

0.7.0-beta RedBlink v1.3.2 support:
- Updates RedBlink stack target to v1.3.2.
- Adds Server Management controls for dune maps runtime modes.
- Adds controls for dynamic vs always-on map runtime behavior.
- Adds map reconcile command.
- Adds Deep Desert dual PvP/PvE status, enable, disable, bootstrap, and repair controls.
- Hardens browser shell fitting with FitAddon fallback/manual resize.
- Adds VIP self-service tools for linked characters.
- Adds admin market seeding tools with IceHunter attribution.
- Splits the former app.py monolith into launcher, core helpers, and routes.

SECURITY NOTES
--------------
- Do not expose this directly to the public internet.
- Viewer role cannot see raw player IDs or logs.
- Operator/admin can grant items, spawn maps, and restart services.
- Admin can run direct SQL utilities and manage users.
"""

import json
import os
import sqlite3
import subprocess
import select
import shlex
import signal
import pty
import fcntl
import termios
import struct
import threading
import time
import psutil
import re
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, jsonify

# Flask-SocketIO is required only for the optional full host shell.
# The app still imports it at startup for the /infrastructure terminal page.
from flask_socketio import SocketIO, emit, disconnect
from werkzeug.security import check_password_hash, generate_password_hash

import market_seed


# =========================================================
# CONFIGURABLE VALUES
# =========================================================

PANEL_VERSION = "0.7.0-beta"
REDBLINK_STACK_VERSION = "v1.3.2"

# RedBlink stack path. Change this if your install lives elsewhere.
DUNE_ROOT = Path(
    os.environ.get(
        "DUNE_ROOT",
        str(Path.home() / "dune-awakening-selfhost-docker"),
    )
)

# Official RedBlink wrapper script.
DUNE_SCRIPT = DUNE_ROOT / "runtime/scripts/dune"

# RedBlink item catalog.
ITEMS_FILE = DUNE_ROOT / "runtime/data/admin-items.json"

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "users.db"

# IceHunter / Ryan Wilson's MIT-licensed dune-admin project includes a richer
# exchange catalog than RedBlink's admin item list. We use this local copy for
# market seeding because it includes tradeable flags, stack sizes, category
# paths, rarity, tiers, and vendor prices. See README credits/third-party notes.
MARKET_ITEM_DATA_FILE = BASE_DIR / "data" / "icehunter-item-data.json"

# Market seed pricing is intentionally inflated from IceHunter's baseline so
# Solari keeps some value on small private servers. Set to 1 to use the
# original-style pricing scale, or tune higher/lower for your economy.
MARKET_PRICE_MULTIPLIER = int(os.environ.get("MARKET_PRICE_MULTIPLIER", "5"))

# Optional explicit Dune Exchange id for market seeding. Leave blank to use the
# game's Global exchange function. If seeded rows succeed but do not appear in
# the in-game exchange, set this to the exchange_id observed from a real player
# listing on your server.
MARKET_SEED_EXCHANGE_ID = os.environ.get("MARKET_SEED_EXCHANGE_ID", "").strip()

# Bot actor class used for NPC exchange listings. IceHunter's marketbot uses
# "Revy"; keeping the same value makes attribution and future compatibility
# straightforward. Change only if you know you need a separate market owner.
MARKET_BOT_CLASS = os.environ.get("MARKET_BOT_CLASS", "Revy")

# Preset stock counts. Equippable items and schematics are individual listings
# because most stack to 1. Resource-like stackables get one large listing.
MARKET_EQUIPPABLE_LISTINGS = int(os.environ.get("MARKET_EQUIPPABLE_LISTINGS", "2"))
MARKET_SCHEMATIC_LISTINGS = int(os.environ.get("MARKET_SCHEMATIC_LISTINGS", "2"))
MARKET_RESOURCE_STACK_SIZE = int(os.environ.get("MARKET_RESOURCE_STACK_SIZE", "1000"))

# Extra seed coverage for vehicle mobility parts that tend to be pain points.
# Matching checks both the template id and display name, case-insensitively.
# Override with, for example:
#   export MARKET_SPECIAL_NAME_TERMS='wing,track,locomotion,tread'
#   export MARKET_SPECIAL_NAME_LISTINGS=8
MARKET_SPECIAL_NAME_TERMS = [
    term.strip().casefold()
    for term in os.environ.get("MARKET_SPECIAL_NAME_TERMS", "wing,track,locomotion").split(",")
    if term.strip()
]
MARKET_SPECIAL_NAME_LISTINGS = int(os.environ.get("MARKET_SPECIAL_NAME_LISTINGS", "8"))

# Refined resources are more progression-critical than common raw mats. This
# multiplier is applied before the per-run market multiplier, so the default
# total for refined resources is baseline * 2.5 * 5.
MARKET_REFINED_RESOURCE_PRICE_MULTIPLIER = float(
    os.environ.get("MARKET_REFINED_RESOURCE_PRICE_MULTIPLIER", "2.5")
)

# Raw resource market tuning. The general raw-resource multiplier is separate
# from the browser's per-run market multiplier. Specific template overrides are
# keyed by the exact item template id from IceHunter's item-data catalog so they
# do not accidentally match unrelated item names.
MARKET_RAW_RESOURCE_PRICE_MULTIPLIER = float(
    os.environ.get("MARKET_RAW_RESOURCE_PRICE_MULTIPLIER", "5")
)
MARKET_RAW_RESOURCE_PRICE_OVERRIDES = {
    "SpiceSand": 10.0,
    "SpiceResidue": 10.0,
    "Basalt": 0.2,
    "T6ResourceA": 8.0,        # Titanium Ore
    "T6ResourceB": 8.0,        # Stravidium Mass
    "SaguaroResourceRaw": 10.0, # Agave Seeds
}

# Revy will buy player listings at or below this percentage of the price the
# current preset would list that same item for. Keep below 100 so players can
# profit by selling to each other, while still letting the bot provide liquidity.
MARKET_BUY_THRESHOLD_PERCENT = int(os.environ.get("MARKET_BUY_THRESHOLD_PERCENT", "60"))
MARKET_BUY_MAX_PER_CLICK = int(os.environ.get("MARKET_BUY_MAX_PER_CLICK", "500"))
MARKET_BUYBACK_INTERVAL_MINUTES = int(os.environ.get("MARKET_BUYBACK_INTERVAL_MINUTES", "30"))

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
ACTION_LOG = LOG_DIR / "actions.log"

POSTGRES_CONTAINER = "dune-postgres"

# Change with:
# export DUNE_SECRET_KEY='long-random-string'
SECRET_KEY = os.environ.get("DUNE_SECRET_KEY", "change-this-secret-before-sharing")

# =========================================================
# INFRASTRUCTURE / HOST ACCESS CONFIGURATION
# =========================================================
#
# These features are intentionally disabled by default.
# Enable only on a trusted LAN/VPN and only for trusted admins.
#
# Example:
#   export ENABLE_HOST_COMMAND_RUNNER=1
#   export ENABLE_HOST_SHELL=1
#   export ENABLE_STACK_INSTALLER=1
#
ENABLE_HOST_COMMAND_RUNNER = os.environ.get("ENABLE_HOST_COMMAND_RUNNER", "0") == "1"
ENABLE_HOST_SHELL = os.environ.get("ENABLE_HOST_SHELL", "0") == "1"
ENABLE_STACK_INSTALLER = os.environ.get("ENABLE_STACK_INSTALLER", "0") == "1"

# Where the RedBlink stack should be cloned/managed by the installer.
REDBLINK_REPO_URL = "https://github.com/Red-Blink/dune-awakening-selfhost-docker.git"
REDBLINK_INSTALL_DIR = Path(
    os.environ.get(
        "REDBLINK_INSTALL_DIR",
        str(Path.home() / "dune-awakening-selfhost-docker"),
    )
)

# Commands allowed in the simple command runner.
# This is separate from the full shell and intended for safer diagnostics.
ALLOWED_INFRA_COMMANDS = {
    "system_info": {
        "label": "Host System Info",
        "cmd": ["bash", "-lc", "uname -a && echo && free -h && echo && df -h / && echo && lscpu | grep -E 'Model name|CPU\\(s\\)|avx|avx2' || true"],
        "timeout": 30,
    },
    "docker_ps": {
        "label": "Docker Containers",
        "cmd": ["bash", "-lc", "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"],
        "timeout": 30,
    },
    "docker_compose_ps": {
        "label": "Docker Compose Status",
        "cmd": ["bash", "-lc", f"cd {shlex.quote(str(REDBLINK_INSTALL_DIR))} && docker compose ps"],
        "timeout": 30,
    },
    "dune_status": {
        "label": "Dune Status",
        "cmd": ["bash", "-lc", f"cd {shlex.quote(str(REDBLINK_INSTALL_DIR))} && dune status || true"],
        "timeout": 45,
    },
}

# Manual prewarm map list. Names must match:
# ./runtime/scripts/dune sietches list
MAPS = [
    "DeepDesert_1",
    "SH_Arrakeen",
    "SH_HarkoVillage",
]

# Supported restart targets from:
# ./runtime/scripts/dune restart
RESTART_TARGETS = [
    "gateway",
    "director",
    "text-router",
    "survival",
    "overmap",
]

INFRASTRUCTURE_RESTART_TARGETS = {
    "gateway",
    "director",
    "text-router",
}

# RedBlink built-in template alias.
SCOUT_THOPTER_TEMPLATE = "scout-ornithopter-mk6"

# Curated Mk6 Medium Ornithopter bundle.
# NOTE: Inventory is intentionally Mk5 in the current known-good kit.
MEDIUM_THOPTER_BUNDLE = [
    ("OrnithopterMediumBoost_Unique_LessHeat_6", 1),
    ("OrnithopterMediumChassis_6", 1),
    ("OrnithopterMediumEngine_6", 1),
    ("OrnithopterMediumGenerator_PolarCap_6", 1),
    ("OrnithopterMediumHull_6", 1),
    ("OrnithopterMediumHullBack_6", 1),
    ("OrnithopterMediumHullFront_6", 1),
    ("OrnithopterMediumInventory_5", 1),
    ("OrnithopterMediumLauncher_6", 1),
    ("OrnithopterMediumLocomotion_Unique_Strafe_6", 6),
    ("FuelCanister_Large", 5),
    ("RocketAmmo", 250),
]

# Admin-only gift bundle derived from the freely shared lasgun SQL example.
# These are granted through RedBlink's normal grant-item-id command instead of
# direct item-row inserts, so inventory slot placement and item construction
# stay with the supported admin grant path.
LASGUN_AUGMENT_BUNDLE = [
    ("UniqueAr6_Electric", 1),
    ("T6_Augment_Lasgun1", 1),
    ("T6_Augment_Damage2", 1),
    ("T6_Augment_Acuracy1", 1),
]

# Admin-only Solari grant. Keep this as the SolarisCoin template id so money
# gifts use the same grant path as item grants instead of direct SQL edits.
SOLARIS_COIN_ITEM_ID = "SolarisCoin"

# Preset Solari amounts exposed in the admin dropdown. Server owners can tune
# these values without touching the route logic below.
SOLARIS_GRANT_AMOUNTS = [
    10000,
    50000,
    100000,
    250000,
    500000,
    1000000,
]

# Player specialization XP tracks observed in IceHunter's MIT-licensed
# dune-admin project and backed by dune.specializationtracktype. The XP helper
# below uses these exact values and refuses arbitrary browser-supplied tracks.
SPECIALIZATION_XP_TRACKS = [
    "Combat",
    "Crafting",
    "Gathering",
    "Exploration",
    "Sabotage",
]

# IceHunter's implementation caps specialization XP at this value. Keep this
# configurable here so server owners can adjust if Funcom changes progression.
SPECIALIZATION_MAX_XP = 44182

# Character XP controls the displayed character level. This is separate from
# specialization-track XP and is stored on the character's DuneCharacter FGL
# entity. IceHunter's MIT-licensed dune-admin research identifies 344,440 as
# the XP required for level 200, the current hard cap.
CHARACTER_MAX_XP = 344440
CHARACTER_LEVEL_XP = {
    0: 0, 1: 40, 2: 215, 3: 440, 4: 740, 5: 1240, 6: 1790, 7: 2390, 8: 2990, 9: 3590, 10: 4190,
    11: 4790, 12: 5390, 13: 5990, 14: 6590, 15: 7190, 16: 7790, 17: 8390, 18: 8990, 19: 9590, 20: 10190,
    21: 10790, 22: 11390, 23: 11990, 24: 12590, 25: 13190, 26: 13790, 27: 14390, 28: 14990, 29: 15590, 30: 16190,
    31: 16790, 32: 17390, 33: 17990, 34: 18590, 35: 19190, 36: 19790, 37: 20390, 38: 20990, 39: 21590, 40: 22190,
    41: 22790, 42: 23390, 43: 23990, 44: 24590, 45: 25190, 46: 25790, 47: 26390, 48: 26990, 49: 27590, 50: 28190,
    51: 28790, 52: 29390, 53: 29990, 54: 30590, 55: 31190, 56: 31790, 57: 32390, 58: 32990, 59: 33590, 60: 34190,
    61: 34790, 62: 35390, 63: 35990, 64: 36590, 65: 37190, 66: 37790, 67: 38390, 68: 38990, 69: 39590, 70: 40190,
    71: 40790, 72: 41390, 73: 41990, 74: 42590, 75: 43190, 76: 43790, 77: 44390, 78: 44990, 79: 45590, 80: 46190,
    81: 46790, 82: 47390, 83: 47990, 84: 48590, 85: 49190, 86: 49790, 87: 50390, 88: 50990, 89: 51590, 90: 52190,
    91: 52790, 92: 53390, 93: 53990, 94: 54590, 95: 55190, 96: 55790, 97: 56390, 98: 56990, 99: 57590, 100: 58190,
    101: 58840, 102: 59490, 103: 60140, 104: 60790, 105: 61440, 106: 62090, 107: 62740, 108: 63390, 109: 64040, 110: 64690,
    111: 65340, 112: 65990, 113: 66640, 114: 67290, 115: 67940, 116: 68590, 117: 69240, 118: 69890, 119: 70540, 120: 71190,
    121: 71840, 122: 72490, 123: 73140, 124: 73790, 125: 74440, 126: 75090, 127: 75740, 128: 76391, 129: 77044, 130: 77699,
    131: 78357, 132: 79018, 133: 79683, 134: 80353, 135: 81030, 136: 81714, 137: 82407, 138: 83110, 139: 83825, 140: 84554,
    141: 85298, 142: 86060, 143: 86842, 144: 87646, 145: 88475, 146: 89332, 147: 90220, 148: 91141, 149: 92100, 150: 93099,
    151: 94143, 152: 95235, 153: 96380, 154: 97582, 155: 98845, 156: 100175, 157: 101576, 158: 103054, 159: 104614, 160: 106263,
    161: 108006, 162: 109849, 163: 111799, 164: 113862, 165: 116046, 166: 118358, 167: 120806, 168: 123397, 169: 126139, 170: 129041,
    171: 132112, 172: 135360, 173: 138795, 174: 142426, 175: 146263, 176: 150316, 177: 154596, 178: 159114, 179: 163880, 180: 168906,
    181: 174203, 182: 179784, 183: 185661, 184: 191846, 185: 198353, 186: 205195, 187: 212385, 188: 219938, 189: 227868, 190: 236190,
    191: 244918, 192: 254069, 193: 263657, 194: 273700, 195: 284213, 196: 295214, 197: 306719, 198: 318746, 199: 331314, 200: 344440,
}

# Curated journey-node presets adapted from IceHunter's MIT-licensed
# dune-admin progression preset catalog. These intentionally operate only on
# journey story nodes; they are for testing and small private-server recovery,
# not a guarantee that every in-game side effect/tag has been reproduced.
PROGRESSION_PRESETS = [
    {
        "id": "skip_npe",
        "name": "Skip NPE / Tutorial",
        "description": "Marks the tutorial/new-player experience root as complete.",
        "nodes": ["DA_MQ_NPEAutocompleted"],
    },
    {
        "id": "a_new_beginning",
        "name": "Complete: A New Beginning",
        "description": "Completes the early main-story root around crafting, harvesting, and fabricator research.",
        "nodes": ["DA_MQ_ANewBeginning"],
    },
    {
        "id": "find_the_fremen",
        "name": "Complete: Find the Fremen",
        "description": "Completes the Trials of Aql / Fremen discovery root.",
        "nodes": ["DA_MQ_FindTheFremen"],
    },
    {
        "id": "act1_complete",
        "name": "Complete: Act 1",
        "description": "Applies A New Beginning plus Find the Fremen.",
        "nodes": ["DA_MQ_ANewBeginning", "DA_MQ_FindTheFremen"],
    },
    {
        "id": "vermillius_intro",
        "name": "Skip: Vermillius Gap Tutorials",
        "description": "Completes the Vermillius Gap tutorial roots.",
        "nodes": ["DA_SQ_VermiliusGap", "DA_Dunipedia_Landmarks.VermiliusGap"],
    },
    {
        "id": "deep_desert_intro",
        "name": "Skip: Deep Desert Intro",
        "description": "Completes the Deep Desert intro side-quest root.",
        "nodes": ["DA_SQ_DeepDesert"],
    },
    {
        "id": "taxation_intro",
        "name": "Skip: Taxation / Exchange Tutorial",
        "description": "Completes the exchange/travel tutorial root.",
        "nodes": ["DA_SQ_Taxation"],
    },
    {
        "id": "overland_intro",
        "name": "Skip: Overland Map Intro",
        "description": "Completes the overland map side-quest root.",
        "nodes": ["DA_SQ_OverlandMap"],
    },
    {
        "id": "unlock_all_lore",
        "name": "Unlock All Lore / Dunipedia",
        "description": "Reveals the broad Dunipedia lore roots.",
        "nodes": [
            "DA_Dunipedia_KnownUniverse",
            "DA_Dunipedia_Landmarks",
            "DA_Dunipedia_ManualOfTheFriendlyDesert",
            "DA_Dunipedia_WarForArrakis",
        ],
    },
]

DEFAULT_OVERREPAIR_DURABILITY = "1000"

# Default value for experimental vehicle module durability repair.
# This writes to dune.vehicle_modules stats JSON. Keep this sane until
# more exact per-module max durability values are confirmed.
DEFAULT_VEHICLE_REPAIR_DURABILITY = "3500"

# Live map configuration.
# Put your downloaded Hagga Basin / Arrakis image here:
#
#   ~/dune-admin-web/static/arrakis_hb.webp
#
# These bounds come from the working Dune dashboard calibration.
# The map image is expected to be 8000x8000 for cleanest alignment.
MAP_CONFIGS = {
    "HaggaBasin": {
        "key": "HaggaBasin",
        "label": "Arrakis - Hagga Basin",
        "image": "arrakis_hb.webp",
        "width": 8000,
        "height": 8000,
        "min_x": -456752.21,
        "max_x": 354547.46,
        "min_y": -450630.14,
        "max_y": 353821.95,
        "flip_y": False,
        # Confirmed from existing dashboard examples.
        "default_partition_id": 1,
    },
    "DeepDesert": {
        "key": "DeepDesert",
        "label": "The Deep Desert",
        "image": "deep_desert.webp",
        "width": 8000,
        "height": 8000,
        "min_x": -1268624.82,
        "max_x": 1163312.83,
        "min_y": -1266548.17,
        "max_y": 1162416.13,
        "flip_y": False,
        # Unknown on this server until tested. Leave blank in the UI
        # unless you confirm the correct partition id.
        "default_partition_id": "8",
    },
}

DEFAULT_MAP_KEY = "HaggaBasin"

# Vehicle relocation does not use MAP_CONFIGS default_partition_id
# because those map defaults are tuned for marker/teleport UI behavior and
# Hagga Basin's marker partition differs from the known safe gameplay partition.
# If your stack uses different vehicle partitions, adjust these two values.
ORNITHOPTER_PARTITION_DEFAULTS = {
    "HaggaBasin": 1,
    "DeepDesert": 8,
}

# Vehicle actor class patterns confirmed from exported dune.actors rows.
# Add newly discovered vehicle blueprint name fragments here before exposing
# them in the admin-only teleport UI. The SQL allow-list deliberately stays
# explicit so unrelated actors with transforms do not appear as movable vehicles.
TELEPORTABLE_VEHICLE_CLASS_PATTERNS = [
    "Ornithopter",
    "Sandbike",
    "Buggy",
    "TreadWheel",
    "SandCrawler",
]

# Emergency unstuck target.
# This should be a known-safe location in Hagga Basin. It is used by
# the emergency return button and bypasses click-selected coordinates.
SAFE_HAGGA_BASIN_RETURN = {
    "partition_id": 1,
    "x": 23404.83682414103,
    "y": 227266.60099261496,
    "z": 8552.14991713151,
}


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

# SocketIO powers the optional browser terminal. async_mode="threading"
# keeps setup simple and avoids forcing eventlet/gevent behavior.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# Active host shell sessions keyed by SocketIO session id.
SHELL_SESSIONS = {}

# In-process buyback sweep state. This deliberately lives in the webadmin
# daemon rather than cron so admins can start/stop it from the browser. It is
# reset when the webadmin process restarts.
MARKET_BUYBACK_STATE_LOCK = threading.Lock()
MARKET_BUYBACK_RUN_LOCK = threading.Lock()
MARKET_BUYBACK_STOP_EVENT = threading.Event()
MARKET_BUYBACK_THREAD = None
MARKET_BUYBACK_STATE = {
    "enabled": False,
    "price_multiplier": MARKET_PRICE_MULTIPLIER,
    "threshold_percent": MARKET_BUY_THRESHOLD_PERCENT,
    "max_buys": MARKET_BUY_MAX_PER_CLICK,
    "interval_minutes": MARKET_BUYBACK_INTERVAL_MINUTES,
    "last_run": "",
    "last_output": "",
    "last_error": "",
    "next_run": "",
    "runs": 0,
}


@app.context_processor
def inject_template_globals():
    return {
        "panel_version": PANEL_VERSION,
        "redblink_stack_version": REDBLINK_STACK_VERSION,
        "maps": MAPS,
        "restart_targets": RESTART_TARGETS,
        "scout_thopter_template": SCOUT_THOPTER_TEMPLATE,
        "medium_bundle": MEDIUM_THOPTER_BUNDLE,
        "lasgun_augment_bundle": LASGUN_AUGMENT_BUNDLE,
        "solaris_grant_amounts": SOLARIS_GRANT_AMOUNTS,
        "specialization_xp_tracks": SPECIALIZATION_XP_TRACKS,
        "specialization_max_xp": SPECIALIZATION_MAX_XP,
        "character_max_xp": CHARACTER_MAX_XP,
        "character_max_level": max(CHARACTER_LEVEL_XP),
        "progression_presets": PROGRESSION_PRESETS,
        "default_overrepair_durability": DEFAULT_OVERREPAIR_DURABILITY,
        "default_vehicle_repair_durability": DEFAULT_VEHICLE_REPAIR_DURABILITY,
        "enable_host_command_runner": ENABLE_HOST_COMMAND_RUNNER,
        "enable_host_shell": ENABLE_HOST_SHELL,
        "enable_stack_installer": ENABLE_STACK_INSTALLER,
        "redblink_repo_url": REDBLINK_REPO_URL,
        "redblink_install_dir": str(REDBLINK_INSTALL_DIR),
        "map_configs": MAP_CONFIGS,
        "default_map_key": DEFAULT_MAP_KEY,
        "market_bot_class": MARKET_BOT_CLASS,
        "market_price_multiplier": MARKET_PRICE_MULTIPLIER,
        "market_seed_exchange_id": MARKET_SEED_EXCHANGE_ID,
        "market_resource_stack_size": MARKET_RESOURCE_STACK_SIZE,
        "market_buy_threshold_percent": MARKET_BUY_THRESHOLD_PERCENT,
        "market_buy_max_per_click": MARKET_BUY_MAX_PER_CLICK,
        "market_buyback_interval_minutes": MARKET_BUYBACK_INTERVAL_MINUTES,
    }


# =========================================================
# DATABASE HELPERS
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            character_name TEXT DEFAULT ''
        )
        """
    )
    columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "character_name" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN character_name TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def user_count():
    conn = db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def list_users():
    conn = db()
    rows = conn.execute(
        """
        SELECT id, username, role, COALESCE(character_name, '') AS character_name
        FROM users
        ORDER BY username
        """
    ).fetchall()
    conn.close()
    return rows


def footer_online_users():
    """
    Return online game characters matched to local web accounts when possible.

    The web panel does not keep a persistent browser-presence table, so the
    footer uses in-game online characters and colors them by the linked web role
    when an admin has entered the exact character name on the user account.
    """
    users = [
        {
            "username": row["username"],
            "role": row["role"],
            "character_name": (row["character_name"] or "").casefold(),
        }
        for row in list_users()
    ]
    by_character = {
        user["character_name"]: user
        for user in users
        if user["character_name"]
    }

    footer_rows = []
    for character in get_characters(include_offline=False):
        character_name = character.get("character_name", "")
        linked = by_character.get(character_name.casefold())
        footer_rows.append(
            {
                "username": linked["username"] if linked else "",
                "role": linked["role"] if linked else "unlinked",
                "character_name": character_name,
                "online_status": character.get("online_status", ""),
            }
        )

    footer_rows.sort(key=lambda row: (row["role"] == "unlinked", row["username"] or row["character_name"]))
    return footer_rows


init_db()


# =========================================================
# AUTH HELPERS
# =========================================================

def logged_in():
    return "user" in session


def current_role():
    return session.get("role", "")


def is_admin():
    return current_role() == "admin"


def is_operator_or_admin():
    return current_role() in ("operator", "admin")


def is_vip():
    return current_role() == "vip"


def can_use_vip_tools():
    return current_role() in ("vip", "admin")


def require_login():
    if not logged_in():
        return redirect("/login")
    return None


# =========================================================
# LOGGING
# =========================================================

def log_action(user, action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ACTION_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {user}: {action}\n")


def recent_log_lines(limit=250):
    if not ACTION_LOG.exists():
        return []
    return ACTION_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


# =========================================================
# COMMAND / DATA HELPERS
# =========================================================

def run_command(cmd, timeout=60):
    """Run controlled command list. Never change this to shell=True."""
    proc = subprocess.run(
        cmd,
        cwd=str(DUNE_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    return (
        "$ " + " ".join(cmd)
        + "\n\nSTDOUT:\n" + proc.stdout
        + "\nSTDERR:\n" + proc.stderr
        + f"\nExit code: {proc.returncode}"
    )


def run_psql(sql, timeout=60):
    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    return run_command(cmd, timeout=timeout)


def run_psql_script(sql, timeout=180):
    """Run a multi-statement SQL script through psql stdin."""
    cmd = [
        "docker",
        "exec",
        "-i",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(DUNE_ROOT),
        input=sql,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    return (
        "$ " + " ".join(cmd)
        + "\n\nSTDOUT:\n" + proc.stdout
        + "\nSTDERR:\n" + proc.stderr
        + f"\nExit code: {proc.returncode}"
    )


def load_items():
    if not ITEMS_FILE.exists():
        return []
    with open(ITEMS_FILE, encoding="utf-8") as f:
        return json.load(f)


def search_items(query, limit=100):
    items = load_items()
    needle = query.casefold().strip()

    if not needle:
        return []

    results = []

    for item in items:
        fields = [
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("category", "")),
            str(item.get("source", "")),
        ]

        if any(needle in field.casefold() for field in fields):
            results.append(item)

    return results[:limit]


def market_price_multiplier_from_value(value):
    """
    Validate an admin-entered per-run market price multiplier.

    The environment default stays useful for unattended installs, while this
    helper lets admins tune one seed run from the browser without editing files.
    """
    raw_value = str(value if value not in (None, "") else MARKET_PRICE_MULTIPLIER).strip()
    try:
        multiplier = int(raw_value)
    except ValueError as exc:
        raise ValueError("price multiplier must be a whole number") from exc

    if multiplier < 1:
        raise ValueError("price multiplier must be at least 1")
    if multiplier > 10000:
        raise ValueError("price multiplier must be 10000 or lower")
    return multiplier


def market_buy_threshold_from_value(value):
    raw_value = str(value if value not in (None, "") else MARKET_BUY_THRESHOLD_PERCENT).strip()
    try:
        threshold = int(raw_value)
    except ValueError as exc:
        raise ValueError("buy threshold must be a whole percent") from exc

    if threshold < 1:
        raise ValueError("buy threshold must be at least 1%")
    if threshold > 100:
        raise ValueError("buy threshold must be 100% or lower")
    return threshold


def market_buy_max_from_value(value):
    raw_value = str(value if value not in (None, "") else MARKET_BUY_MAX_PER_CLICK).strip()
    try:
        max_buys = int(raw_value)
    except ValueError as exc:
        raise ValueError("max buys must be a whole number") from exc

    if max_buys < 1:
        raise ValueError("max buys must be at least 1")
    if max_buys > 5000:
        raise ValueError("max buys must be 5000 or lower")
    return max_buys


def market_buyback_interval_from_value(value):
    raw_value = str(value if value not in (None, "") else MARKET_BUYBACK_INTERVAL_MINUTES).strip()
    try:
        interval = int(raw_value)
    except ValueError as exc:
        raise ValueError("buyback interval must be whole minutes") from exc

    if interval < 1:
        raise ValueError("buyback interval must be at least 1 minute")
    if interval > 1440:
        raise ValueError("buyback interval must be 1440 minutes or lower")
    return interval


def market_exchange_id_from_value(value):
    raw_value = str(value if value is not None else MARKET_SEED_EXCHANGE_ID).strip()
    if not raw_value:
        return None
    try:
        exchange_id = int(raw_value)
    except ValueError as exc:
        raise ValueError("exchange id must be blank or a whole number") from exc

    if exchange_id < 1:
        raise ValueError("exchange id must be at least 1")
    return exchange_id


def build_market_seed_plan(price_multiplier=None):
    multiplier = market_price_multiplier_from_value(price_multiplier)
    return market_seed.build_seed_plan(
        MARKET_ITEM_DATA_FILE,
        multiplier,
        MARKET_EQUIPPABLE_LISTINGS,
        MARKET_SCHEMATIC_LISTINGS,
        MARKET_RESOURCE_STACK_SIZE,
        MARKET_SPECIAL_NAME_TERMS,
        MARKET_SPECIAL_NAME_LISTINGS,
        MARKET_REFINED_RESOURCE_PRICE_MULTIPLIER,
        MARKET_RAW_RESOURCE_PRICE_MULTIPLIER,
        MARKET_RAW_RESOURCE_PRICE_OVERRIDES,
    )


def market_seed_summary(price_multiplier=None):
    multiplier = market_price_multiplier_from_value(price_multiplier)
    plan = build_market_seed_plan(multiplier)
    return market_seed.summary(plan, multiplier)


def seed_market_preset(clear_existing=True, price_multiplier=None, exchange_id=None):
    multiplier = market_price_multiplier_from_value(price_multiplier)
    exchange_id_override = market_exchange_id_from_value(exchange_id)
    plan = build_market_seed_plan(multiplier)
    if not plan:
        raise ValueError(f"market item data not found or empty: {MARKET_ITEM_DATA_FILE}")
    sql = market_seed.build_seed_sql(
        plan,
        MARKET_BOT_CLASS,
        multiplier,
        clear_existing=clear_existing,
        exchange_id_override=exchange_id_override,
    )
    return run_psql_script(sql, timeout=300)


def buy_player_market_listings(price_multiplier=None, threshold_percent=None, max_buys=None):
    multiplier = market_price_multiplier_from_value(price_multiplier)
    threshold = market_buy_threshold_from_value(threshold_percent)
    buy_limit = market_buy_max_from_value(max_buys)
    plan = build_market_seed_plan(multiplier)
    if not plan:
        raise ValueError(f"market item data not found or empty: {MARKET_ITEM_DATA_FILE}")
    sql = market_seed.build_buy_player_listings_sql(
        plan,
        MARKET_BOT_CLASS,
        threshold_percent=threshold,
        max_buys=buy_limit,
    )
    return run_psql_script(sql, timeout=300)


def run_buyback_sweep(price_multiplier=None, threshold_percent=None, max_buys=None):
    """
    Run one buyback sweep with overlap protection.

    Manual buyback and timed buyback share this helper so two long database
    sweeps cannot run at the same time from different buttons/threads.
    """
    acquired = MARKET_BUYBACK_RUN_LOCK.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("buyback sweep already running")
    try:
        return buy_player_market_listings(
            price_multiplier=price_multiplier,
            threshold_percent=threshold_percent,
            max_buys=max_buys,
        )
    finally:
        MARKET_BUYBACK_RUN_LOCK.release()


def market_buyback_status():
    with MARKET_BUYBACK_STATE_LOCK:
        return dict(MARKET_BUYBACK_STATE)


def set_market_buyback_state(**updates):
    with MARKET_BUYBACK_STATE_LOCK:
        MARKET_BUYBACK_STATE.update(updates)
        return dict(MARKET_BUYBACK_STATE)


def market_buyback_loop():
    """
    Background timed buyback worker.

    Start runs one immediate sweep, then this loop handles later interval runs.
    """
    while True:
        status = market_buyback_status()
        interval_seconds = max(1, int(status["interval_minutes"])) * 60
        if MARKET_BUYBACK_STOP_EVENT.wait(interval_seconds):
            break

        status = market_buyback_status()
        if not status.get("enabled"):
            continue

        multiplier = status.get("price_multiplier") or MARKET_PRICE_MULTIPLIER
        threshold = status.get("threshold_percent") or MARKET_BUY_THRESHOLD_PERCENT
        max_buys = status.get("max_buys") or MARKET_BUY_MAX_PER_CLICK
        started = datetime.now()
        try:
            output = run_buyback_sweep(
                price_multiplier=multiplier,
                threshold_percent=threshold,
                max_buys=max_buys,
            )
            next_run = datetime.now() + timedelta(minutes=int(status["interval_minutes"]))
            set_market_buyback_state(
                last_run=started.strftime("%Y-%m-%d %H:%M:%S"),
                last_output=output[-4000:],
                last_error="",
                next_run=next_run.strftime("%Y-%m-%d %H:%M:%S"),
                runs=int(status.get("runs") or 0) + 1,
            )
            log_action(
                "system",
                f"automated {MARKET_BOT_CLASS} buyback sweep at {threshold}% threshold using {multiplier}x prices, max {max_buys}",
            )
        except Exception as exc:
            next_run = datetime.now() + timedelta(minutes=int(status["interval_minutes"]))
            set_market_buyback_state(
                last_run=started.strftime("%Y-%m-%d %H:%M:%S"),
                last_error=str(exc),
                next_run=next_run.strftime("%Y-%m-%d %H:%M:%S"),
            )
            log_action("system", f"automated buyback sweep failed: {exc}")


def start_market_buyback_sweep(
    price_multiplier=None,
    threshold_percent=None,
    max_buys=None,
    interval_minutes=None,
    run_now=True,
):
    global MARKET_BUYBACK_THREAD, MARKET_BUYBACK_STOP_EVENT

    multiplier = market_price_multiplier_from_value(price_multiplier)
    threshold = market_buy_threshold_from_value(threshold_percent)
    buy_limit = market_buy_max_from_value(max_buys)
    interval = market_buyback_interval_from_value(interval_minutes)
    next_run = datetime.now() + timedelta(minutes=interval)

    with MARKET_BUYBACK_STATE_LOCK:
        MARKET_BUYBACK_STATE.update(
            {
                "enabled": True,
                "price_multiplier": multiplier,
                "threshold_percent": threshold,
                "max_buys": buy_limit,
                "interval_minutes": interval,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": "",
            }
        )

    if MARKET_BUYBACK_THREAD is None or not MARKET_BUYBACK_THREAD.is_alive():
        MARKET_BUYBACK_STOP_EVENT = threading.Event()
        MARKET_BUYBACK_THREAD = threading.Thread(target=market_buyback_loop, daemon=True)
        MARKET_BUYBACK_THREAD.start()

    if run_now:
        started = datetime.now()
        try:
            output = run_buyback_sweep(
                price_multiplier=multiplier,
                threshold_percent=threshold,
                max_buys=buy_limit,
            )
            next_run = datetime.now() + timedelta(minutes=interval)
            set_market_buyback_state(
                last_run=started.strftime("%Y-%m-%d %H:%M:%S"),
                last_output=output[-4000:],
                last_error="",
                next_run=next_run.strftime("%Y-%m-%d %H:%M:%S"),
                runs=int(market_buyback_status().get("runs") or 0) + 1,
            )
            log_action(
                "system",
                f"started automated {MARKET_BOT_CLASS} buyback with immediate sweep at {threshold}% threshold using {multiplier}x prices, max {buy_limit}",
            )
        except Exception as exc:
            next_run = datetime.now() + timedelta(minutes=interval)
            set_market_buyback_state(
                last_run=started.strftime("%Y-%m-%d %H:%M:%S"),
                last_error=str(exc),
                next_run=next_run.strftime("%Y-%m-%d %H:%M:%S"),
            )
            raise

    return market_buyback_status()


def stop_market_buyback_sweep():
    MARKET_BUYBACK_STOP_EVENT.set()
    return set_market_buyback_state(enabled=False, next_run="")


def build_market_clear_npc_sql():
    """
    Remove only this market bot's NPC exchange listings and their backing items.

    Player listings are protected by both owner_id and is_npc_order = TRUE.
    This is useful while tuning presets because it clears the exchange without
    immediately creating replacement listings.
    """
    bot_class = market_seed.sql_literal(MARKET_BOT_CLASS)
    return f"""
DO $$
DECLARE
    v_owner_id BIGINT;
    v_item_ids BIGINT[];
BEGIN
    SELECT id INTO v_owner_id
    FROM dune.actors
    WHERE class = {bot_class}
    LIMIT 1;

    IF v_owner_id IS NULL THEN
        RAISE NOTICE 'No market bot actor found for class {MARKET_BOT_CLASS}. Nothing to clear.';
        RETURN;
    END IF;

    SELECT ARRAY_AGG(item_id) INTO v_item_ids
    FROM dune.dune_exchange_orders
    WHERE owner_id = v_owner_id
      AND is_npc_order = TRUE
      AND item_id IS NOT NULL;

    DELETE FROM dune.dune_exchange_sell_orders
    WHERE order_id IN (
        SELECT id
        FROM dune.dune_exchange_orders
        WHERE owner_id = v_owner_id
          AND is_npc_order = TRUE
    );

    DELETE FROM dune.dune_exchange_orders
    WHERE owner_id = v_owner_id
      AND is_npc_order = TRUE;

    IF v_item_ids IS NOT NULL THEN
        DELETE FROM dune.items
        WHERE id = ANY(v_item_ids);
    END IF;
END $$;
"""


def clear_market_npc_listings():
    return run_psql_script(build_market_clear_npc_sql(), timeout=120)


def get_characters(include_offline=True):
    """
    Return character rows with IDs needed by the panel.

    include_offline=True is important for overrepair, because overrepair
    should be run while the character is logged off.
    """
    where_clause = "" if include_offline else "WHERE ps.online_status <> 'Offline'"

    sql = f"""
    SELECT
        ps.character_name,
        ps.online_status,
        ps.life_state,
        ps.player_pawn_id,
        ps.player_controller_id,
        ps.player_state_id,
        inv.id,
        acc."user",
        acc.funcom_id
    FROM dune.player_state ps
    LEFT JOIN dune.accounts acc
        ON acc.id = ps.account_id
    LEFT JOIN LATERAL (
        SELECT id
        FROM dune.inventories
        WHERE actor_id = ps.player_pawn_id
        ORDER BY id
        LIMIT 1
    ) inv ON true
    {where_clause}
    ORDER BY
        CASE WHEN ps.online_status = 'Offline' THEN 0 ELSE 1 END,
        ps.character_name,
        inv.id;
    """

    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        rows = []

        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 9:
                continue

            rows.append(
                {
                    "character_name": parts[0],
                    "online_status": parts[1],
                    "life_state": parts[2],
                    "character_actor_id": parts[3],
                    "player_controller_id": parts[4],
                    "player_state_id": parts[5],
                    "inventory_id": parts[6],
                    "fls_id": parts[7],
                    "funcom_id": parts[8],
                }
            )

        return rows

    except Exception:
        return []


def get_user_character_name(username):
    """
    Return the exact in-game character name bound to a local web account.

    VIP self-service authorization depends on this local binding. Admins should
    enter the character name verbatim when creating/updating VIP accounts.
    """
    conn = db()
    row = conn.execute(
        "SELECT COALESCE(character_name, '') AS character_name FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return (row["character_name"] if row else "").strip()


def get_self_character_for_user(username):
    """
    Resolve a VIP account to its own character actor, FLS/account id, and
    primary character inventory.

    The character name comes from the local users table and is never accepted
    from the browser during VIP actions.
    """
    character_name = get_user_character_name(username)
    if not character_name:
        raise ValueError("No in-game character name is linked to this web account.")

    safe_name = character_name.replace("'", "''")
    sql = f"""
    SELECT
        ps.character_name,
        ps.online_status,
        ps.life_state,
        ps.player_pawn_id,
        inv.id,
        acc."user",
        acc.funcom_id
    FROM dune.player_state ps
    LEFT JOIN dune.accounts acc
        ON acc.id = ps.account_id
    LEFT JOIN LATERAL (
        SELECT id
        FROM dune.inventories
        WHERE actor_id = ps.player_pawn_id
        ORDER BY id
        LIMIT 1
    ) inv ON true
    WHERE ps.character_name = '{safe_name}'
    ORDER BY inv.id
    LIMIT 1;
    """

    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "failed to query linked character")

    line = proc.stdout.strip()
    if not line:
        raise ValueError(f"Linked character not found: {character_name}")

    parts = line.split("\t")
    if len(parts) < 7:
        raise ValueError("unexpected linked character query result")

    return {
        "character_name": parts[0],
        "online_status": parts[1],
        "life_state": parts[2],
        "character_actor_id": parts[3],
        "inventory_id": parts[4],
        "fls_id": parts[5],
        "funcom_id": parts[6],
    }



def get_vehicles():
    """
    Return vehicles that have module rows.

    In observed data, the vehicle actor id matches vehicle_modules.vehicle_id.
    This query intentionally joins actors to vehicle_modules so the selector
    only shows vehicles with repairable module data.
    """
    sql = r"""
    SELECT
        a.id AS vehicle_id,
        a.class AS vehicle_class,
        COUNT(vm.id) AS module_count,
        MIN((vm.stats #>> '{FVehicleModuleDurabilityStats,1,CurrentDurability}')::numeric) AS min_durability,
        MAX((vm.stats #>> '{FVehicleModuleDurabilityStats,1,CurrentDurability}')::numeric) AS max_durability
    FROM dune.actors a
    JOIN dune.vehicle_modules vm
        ON vm.vehicle_id = a.id
    WHERE a.class ILIKE '%Vehicle%'
       OR a.class ILIKE '%Ornithopter%'
       OR a.class ILIKE '%Sandbike%'
       OR a.class ILIKE '%Buggy%'
       OR a.class ILIKE '%TreadWheel%'
       OR a.class ILIKE '%SandCrawler%'
    GROUP BY a.id, a.class
    ORDER BY a.id;
    """

    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        vehicles = []

        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 5:
                continue

            vehicles.append(
                {
                    "vehicle_id": parts[0],
                    "vehicle_class": parts[1],
                    "module_count": parts[2],
                    "min_durability": parts[3],
                    "max_durability": parts[4],
                }
            )

        return vehicles

    except Exception:
        return []


def build_vehicle_repair_sql(vehicle_id, durability_value):
    """
    Build SQL to set durability for every module on one vehicle.

    This updates the observed vehicle module durability path:
        FVehicleModuleDurabilityStats -> 1 -> CurrentDurability

    It also writes:
        FVehicleModuleDurabilityStats -> 1 -> MaxDurability

    That second key may be created if absent. This is intentional for the
    overrepair behavior, but this remains an admin-only experimental tool.
    """
    veh_id = int(vehicle_id)
    durability = float(durability_value)

    return f"""
WITH settings AS (
    SELECT
        {veh_id}::bigint AS target_vehicle_id,
        {durability}::numeric AS durability_value
),
updated_modules AS (
    UPDATE dune.vehicle_modules vm
    SET stats =
        jsonb_set(
            jsonb_set(
                vm.stats,
                '{{FVehicleModuleDurabilityStats,1,CurrentDurability}}',
                to_jsonb(s.durability_value),
                true
            ),
            '{{FVehicleModuleDurabilityStats,1,MaxDurability}}',
            to_jsonb(s.durability_value),
            true
        )
    FROM settings s
    WHERE vm.vehicle_id = s.target_vehicle_id
      AND vm.stats #> '{{FVehicleModuleDurabilityStats,1,CurrentDurability}}' IS NOT NULL
    RETURNING
        vm.id AS module_id,
        vm.vehicle_id,
        vm.template_id,
        vm.stats #> '{{FVehicleModuleDurabilityStats,1,CurrentDurability}}'
            AS current_durability,
        vm.stats #> '{{FVehicleModuleDurabilityStats,1,MaxDurability}}'
            AS max_durability
)
SELECT
    module_id,
    vehicle_id,
    template_id,
    current_durability,
    max_durability
FROM updated_modules
ORDER BY module_id;
"""

def build_overrepair_sql(character_actor_id, inventory_id, durability_value):
    actor_id = int(character_actor_id)
    inv_id = int(inventory_id)
    durability = float(durability_value)

    return f"""
WITH settings AS (
    SELECT
        {actor_id}::bigint AS character_actor_id,
        {inv_id}::bigint AS target_inventory_id,
        {durability}::numeric AS durability_value
),
updated_items AS (
    UPDATE dune.items i
    SET stats =
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    i.stats,
                    '{{FItemStackAndDurabilityStats,1,CurrentDurability}}',
                    to_jsonb(s.durability_value),
                    true
                ),
                '{{FItemStackAndDurabilityStats,1,DecayedMaxDurability}}',
                to_jsonb(s.durability_value),
                true
            ),
            '{{FItemStackAndDurabilityStats,1,MaxDurability}}',
            to_jsonb(s.durability_value),
            true
        )
    FROM dune.inventories inv
    CROSS JOIN settings s
    WHERE i.inventory_id = inv.id
      AND inv.id = s.target_inventory_id
      AND inv.actor_id = s.character_actor_id
      AND i.stats #> '{{FItemStackAndDurabilityStats,1,CurrentDurability}}' IS NOT NULL
    RETURNING
        i.inventory_id,
        i.id AS item_id,
        i.template_id,
        i.position_index,
        i.quality_level,
        i.stats #> '{{FItemStackAndDurabilityStats,1,CurrentDurability}}'
            AS current_durability,
        i.stats #> '{{FItemStackAndDurabilityStats,1,DecayedMaxDurability}}'
            AS decayed_max_durability,
        i.stats #> '{{FItemStackAndDurabilityStats,1,MaxDurability}}'
            AS max_durability
)
SELECT
    inventory_id,
    item_id,
    template_id,
    position_index,
    quality_level,
    current_durability,
    decayed_max_durability,
    max_durability
FROM updated_items
ORDER BY inventory_id, position_index, item_id;
"""


def build_set_research_points_sql(character_actor_id, research_points):
    """
    Build admin-only SQL to set one character's available research points.

    This is intentionally a fresh implementation inspired by the provided
    reference query. The browser supplies only the character actor id and the
    desired point value; validation is done against dune.player_state before
    the actor JSON is updated.
    """
    actor_id = int(character_actor_id)
    points = int(research_points)

    if points < 0:
        raise ValueError("research points cannot be negative")

    return f"""
WITH settings AS (
    SELECT
        {actor_id}::bigint AS character_actor_id,
        {points}::integer AS research_points
),
selected_player AS (
    SELECT
        ps.character_name,
        ps.player_pawn_id AS character_actor_id,
        ps.online_status,
        ps.life_state
    FROM dune.player_state ps
    JOIN settings s
        ON s.character_actor_id = ps.player_pawn_id
),
original_value AS (
    SELECT
        a.id AS character_actor_id,
        a.class AS actor_class,
        a.properties #> '{{TechKnowledgePlayerComponent,m_TechKnowledgePoints}}'
            AS before_research_points
    FROM dune.actors a
    JOIN selected_player sp
        ON sp.character_actor_id = a.id
),
updated_actor AS (
    UPDATE dune.actors a
    SET properties = jsonb_set(
        a.properties,
        '{{TechKnowledgePlayerComponent,m_TechKnowledgePoints}}',
        to_jsonb(s.research_points),
        true
    )
    FROM settings s
    JOIN selected_player sp
        ON sp.character_actor_id = s.character_actor_id
    WHERE a.id = sp.character_actor_id
    RETURNING
        a.id AS character_actor_id,
        a.properties #> '{{TechKnowledgePlayerComponent,m_TechKnowledgePoints}}'
            AS after_research_points
)
SELECT
    sp.character_name,
    sp.character_actor_id,
    sp.online_status,
    sp.life_state,
    ov.actor_class,
    ov.before_research_points,
    ua.after_research_points
FROM selected_player sp
JOIN original_value ov
    ON ov.character_actor_id = sp.character_actor_id
JOIN updated_actor ua
    ON ua.character_actor_id = sp.character_actor_id;
"""


def build_give_specialization_xp_sql(player_controller_id, track_type, xp_amount):
    """
    Build admin-only SQL to add XP to one specialization track.

    This follows the table/function behavior observed in IceHunter's
    MIT-licensed dune-admin project, but keeps our implementation narrow:
    selected track only, additive XP only, and capped to SPECIALIZATION_MAX_XP.
    The player id here is the player controller id from dune.player_state.
    """
    controller_id = int(player_controller_id)
    amount = int(xp_amount)
    track = str(track_type).strip()

    if track not in SPECIALIZATION_XP_TRACKS:
        raise ValueError("unsupported XP track")
    if amount <= 0:
        raise ValueError("XP amount must be greater than zero")

    safe_track = track.replace("'", "''")

    return f"""
WITH settings AS (
    SELECT
        {controller_id}::bigint AS player_controller_id,
        '{safe_track}'::dune.specializationtracktype AS track_type,
        LEAST({amount}::integer, {SPECIALIZATION_MAX_XP}::integer) AS xp_delta,
        {SPECIALIZATION_MAX_XP}::integer AS max_xp
),
selected_player AS (
    SELECT
        ps.character_name,
        ps.player_controller_id,
        ps.online_status,
        ps.life_state
    FROM dune.player_state ps
    JOIN settings s
        ON s.player_controller_id = ps.player_controller_id
),
original_value AS (
    SELECT
        sp.character_name,
        sp.player_controller_id,
        sp.online_status,
        sp.life_state,
        s.track_type,
        COALESCE(st.xp_amount, 0) AS before_xp,
        COALESCE(st.level, 0) AS before_level
    FROM selected_player sp
    CROSS JOIN settings s
    LEFT JOIN dune.specialization_tracks st
        ON st.player_id = sp.player_controller_id
       AND st.track_type = s.track_type
),
upserted_track AS (
    INSERT INTO dune.specialization_tracks (player_id, track_type, xp_amount, level)
    SELECT
        s.player_controller_id,
        s.track_type,
        s.xp_delta,
        ov.before_level
    FROM settings s
    JOIN original_value ov
        ON ov.player_controller_id = s.player_controller_id
    ON CONFLICT (player_id, track_type)
    DO UPDATE SET xp_amount = GREATEST(LEAST(
        dune.specialization_tracks.xp_amount + EXCLUDED.xp_amount,
        (SELECT max_xp FROM settings)
    ), 0)
    RETURNING
        player_id,
        track_type,
        xp_amount AS after_xp,
        level AS after_level
)
SELECT
    ov.character_name,
    ov.player_controller_id,
    ov.online_status,
    ov.life_state,
    ov.track_type::text,
    ov.before_xp,
    ut.after_xp,
    (ut.after_xp - ov.before_xp) AS xp_added,
    ov.before_level,
    ut.after_level
FROM original_value ov
JOIN upserted_track ut
    ON ut.player_id = ov.player_controller_id
   AND ut.track_type = ov.track_type;
"""


def sql_literal(value):
    """Quote a local string for SQL generated from trusted panel controls."""
    return "'" + str(value).replace("'", "''") + "'"


def sql_text_array(values):
    """Build a PostgreSQL text[] literal from a trusted local list."""
    return "ARRAY[" + ", ".join(sql_literal(value) for value in values) + "]::text[]"


def progression_preset_by_id(preset_id):
    for preset in PROGRESSION_PRESETS:
        if preset["id"] == preset_id:
            return preset
    return None


def build_reset_specialization_sql(player_controller_id, track_type):
    """
    Build admin-only SQL to reset specialization state.

    Resetting one track deletes that track's XP row. Resetting "all" uses the
    game's own reset routines for tracks and purchased keystones, which is the
    closest practical rollback after experimenting with specialization unlocks.
    """
    controller_id = int(player_controller_id)
    track = str(track_type).strip()

    if track.lower() == "all":
        return f"""
BEGIN;
SELECT dune.reset_specialization_tracks({controller_id}::bigint);
SELECT dune.reset_specialization_keystones({controller_id}::bigint);
SELECT
    'reset_all' AS status,
    {controller_id}::bigint AS player_controller_id,
    'all tracks and keystones' AS reset_scope;
COMMIT;
"""

    if track not in SPECIALIZATION_XP_TRACKS:
        raise ValueError("unsupported XP track")

    safe_track = track.replace("'", "''")

    return f"""
WITH deleted AS (
    DELETE FROM dune.specialization_tracks
    WHERE player_id = {controller_id}::bigint
      AND track_type::text = '{safe_track}'
    RETURNING player_id, track_type::text AS track_type, xp_amount, level
)
SELECT
    {controller_id}::bigint AS player_controller_id,
    '{safe_track}' AS reset_scope,
    COUNT(*) AS rows_deleted
FROM deleted;
"""


def build_progression_preset_sql(fls_id, preset_id, action):
    """
    Build admin-only SQL to apply or reset a curated journey-node preset.

    This intentionally uses journey_story_node state only. IceHunter's richer
    tool also applies tag side effects from game-data catalogs; we do not ship
    that catalog here, so the UI labels this as experimental and reversible.
    """
    preset = progression_preset_by_id(preset_id)
    if not preset:
        raise ValueError("unknown progression preset")

    requested_action = str(action).strip().lower()
    if requested_action not in ("apply", "reset"):
        raise ValueError("unsupported progression action")

    safe_fls = sql_literal(str(fls_id).strip())
    nodes_sql = sql_text_array(preset["nodes"])
    safe_preset_id = sql_literal(preset["id"])
    safe_preset_name = sql_literal(preset["name"])

    if requested_action == "apply":
        # Complete root nodes plus existing child nodes one row at a time. A
        # single broad UPDATE can collide with journey_story_node triggers, and
        # the game's bulk routine only touches the root ids we pass in.
        return f"""
BEGIN;
DO $$
DECLARE
    v_fls_id text := {safe_fls}::text;
    v_root_nodes text[] := {nodes_sql};
    v_account_id bigint;
    v_node text;
    v_rows integer := 0;
BEGIN
    IF NOT dune.is_player_offline(v_fls_id) THEN
        RAISE EXCEPTION 'Cannot update progression because the player is online.';
    END IF;

    SELECT id INTO v_account_id
    FROM dune.accounts
    WHERE "user" = v_fls_id;

    IF v_account_id IS NULL THEN
        RAISE EXCEPTION 'No account found for FLS id %', v_fls_id;
    END IF;

    CREATE TEMP TABLE IF NOT EXISTS eda_progression_result (
        action text,
        preset_id text,
        preset_name text,
        root_nodes integer,
        touched_rows integer,
        note text
    ) ON COMMIT DROP;
    TRUNCATE eda_progression_result;

    FOR v_node IN
        SELECT DISTINCT node_id
        FROM (
            SELECT unnest(v_root_nodes) AS node_id
            UNION
            SELECT jsn.story_node_id AS node_id
            FROM dune.journey_story_node jsn
            WHERE jsn.account_id = v_account_id
              AND EXISTS (
                  SELECT 1
                  FROM unnest(v_root_nodes) AS root_node
                  WHERE jsn.story_node_id = root_node
                     OR jsn.story_node_id LIKE root_node || '.%'
              )
        ) target_nodes
        ORDER BY node_id
    LOOP
        UPDATE dune.journey_story_node
        SET
            complete_condition_state = 'true'::jsonb,
            reveal_condition_state = 'true'::jsonb
        WHERE account_id = v_account_id
          AND story_node_id = v_node;

        IF NOT FOUND THEN
            INSERT INTO dune.journey_story_node (
                account_id,
                story_node_id,
                override_reward_block,
                has_pending_reward,
                complete_condition_state,
                reveal_condition_state,
                fail_condition_state,
                metadata_state,
                reset_group
            )
            VALUES (
                v_account_id,
                v_node,
                false,
                false,
                'true'::jsonb,
                'true'::jsonb,
                '{{}}'::jsonb,
                '{{}}'::jsonb,
                'Default'::dune.JourneyStoryResetGroup
            )
            ON CONFLICT ON CONSTRAINT journey_story_node_pkey
            DO UPDATE SET
                complete_condition_state = EXCLUDED.complete_condition_state,
                reveal_condition_state = EXCLUDED.reveal_condition_state,
                fail_condition_state = EXCLUDED.fail_condition_state,
                metadata_state = EXCLUDED.metadata_state;
        END IF;

        v_rows := v_rows + 1;
    END LOOP;

    INSERT INTO eda_progression_result
    VALUES (
        'applied',
        {safe_preset_id}::text,
        {safe_preset_name}::text,
        array_length(v_root_nodes, 1),
        v_rows,
        'Completed root nodes plus existing child rows one at a time. Relog after applying.'
    );
END $$;
SELECT
    action,
    preset_id,
    preset_name,
    root_nodes,
    touched_rows,
    note
FROM eda_progression_result;
COMMIT;
"""

    return f"""
BEGIN;
DO $$
DECLARE
    v_fls_id text := {safe_fls}::text;
    v_root_nodes text[] := {nodes_sql};
    v_account_id bigint;
    v_node text;
    v_rows integer := 0;
BEGIN
    IF NOT dune.is_player_offline(v_fls_id) THEN
        RAISE EXCEPTION 'Cannot reset progression because the player is online.';
    END IF;

    SELECT id INTO v_account_id
    FROM dune.accounts
    WHERE "user" = v_fls_id;

    IF v_account_id IS NULL THEN
        RAISE EXCEPTION 'No account found for FLS id %', v_fls_id;
    END IF;

    CREATE TEMP TABLE IF NOT EXISTS eda_progression_result (
        action text,
        preset_id text,
        preset_name text,
        root_nodes integer,
        touched_rows integer,
        note text
    ) ON COMMIT DROP;
    TRUNCATE eda_progression_result;

    FOR v_node IN
        SELECT DISTINCT jsn.story_node_id
        FROM dune.journey_story_node jsn
        WHERE jsn.account_id = v_account_id
          AND EXISTS (
              SELECT 1
              FROM unnest(v_root_nodes) AS root_node
              WHERE jsn.story_node_id = root_node
                 OR jsn.story_node_id LIKE root_node || '.%'
          )
        ORDER BY jsn.story_node_id
    LOOP
        UPDATE dune.journey_story_node
        SET complete_condition_state = '{{}}'::jsonb
        WHERE account_id = v_account_id
          AND story_node_id = v_node;

        DELETE FROM dune.journey_story_node_cooldown
        WHERE account_id = v_account_id
          AND story_node_id = v_node;

        v_rows := v_rows + 1;
    END LOOP;

    INSERT INTO eda_progression_result
    VALUES (
        'reset',
        {safe_preset_id}::text,
        {safe_preset_name}::text,
        array_length(v_root_nodes, 1),
        v_rows,
        'Reset root nodes plus existing child rows one at a time. Relog after resetting.'
    );
END $$;
SELECT
    action,
    preset_id,
    preset_name,
    root_nodes,
    touched_rows,
    note
FROM eda_progression_result;
COMMIT;
"""


def build_give_character_xp_sql(character_actor_id, xp_amount):
    """
    Build admin-only SQL to add character-level XP.

    Character XP is the displayed level pool on FLevelComponent.TotalXPEarned.
    When XP changes, the related total/unspent skill-point fields and research
    point/intel value are recalculated to match the new level. The XP curve and
    formulas are adapted from IceHunter's MIT-licensed dune-admin research.
    """
    actor_id = int(character_actor_id)
    amount = int(xp_amount)

    if amount <= 0:
        raise ValueError("XP amount must be greater than zero")

    return f"""
WITH settings AS (
    SELECT
        {actor_id}::bigint AS character_actor_id,
        LEAST({amount}::bigint, {CHARACTER_MAX_XP}::bigint) AS xp_delta,
        {CHARACTER_MAX_XP}::bigint AS max_xp
),
selected_player AS (
    SELECT
        ps.character_name,
        ps.player_pawn_id AS character_actor_id,
        ps.player_controller_id,
        ps.online_status,
        ps.life_state
    FROM dune.player_state ps
    JOIN settings s
        ON s.character_actor_id = ps.player_pawn_id
),
current_state AS (
    SELECT
        sp.character_name,
        sp.character_actor_id,
        sp.player_controller_id,
        sp.online_status,
        sp.life_state,
        fe.entity_id,
        COALESCE((fe.components #>> '{{FLevelComponent,1,TotalXPEarned}}')::bigint, 0) AS before_xp,
        COALESCE((fe.components #>> '{{FLevelComponent,1,TotalSkillPoints}}')::bigint, 0) AS before_total_skill_points,
        COALESCE((fe.components #>> '{{FLevelComponent,1,UnspentSkillPoints}}')::bigint, 0) AS before_unspent_skill_points,
        COALESCE((
            SELECT SUM((v->>'SkillPointsSpent')::int)
            FROM jsonb_each(fe.components->'FLevelComponent'->1->'ModuleData') AS kv(k, v)
            WHERE k != format(
                '(TagName="%s")',
                fe.components->'FLevelComponent'->1->'StarterSkillTreeTag'->>'TagName'
            )
        ), 0) AS spent_skill_points
    FROM selected_player sp
    JOIN dune.actor_fgl_entities afe
        ON afe.actor_id = sp.character_actor_id
       AND afe.slot_name = 'DuneCharacter'
    JOIN dune.fgl_entities fe
        ON fe.entity_id = afe.entity_id
),
keystone_bonus AS (
    SELECT
        cs.character_actor_id,
        COALESCE(SUM(
            CASE
                WHEN psk.keystone_id IN (1,3,6,9,12,15,18,21,24,27) THEN 3
                WHEN psk.keystone_id = 30 THEN 5
                WHEN psk.keystone_id BETWEEN 1 AND 29 THEN 1
                ELSE 0
            END
        ), 0)::bigint AS bonus_skill_points
    FROM current_state cs
    LEFT JOIN dune.purchased_specialization_keystones psk
        ON psk.player_id = cs.player_controller_id
    GROUP BY cs.character_actor_id
),
computed AS (
    SELECT
        cs.*,
        kb.bonus_skill_points,
        LEAST(cs.before_xp + s.xp_delta, s.max_xp) AS after_xp
    FROM current_state cs
    JOIN settings s
        ON s.character_actor_id = cs.character_actor_id
    JOIN keystone_bonus kb
        ON kb.character_actor_id = cs.character_actor_id
),
leveled AS (
    SELECT
        c.*,
        COALESCE((
            SELECT MAX(level_value)
            FROM (VALUES
                (0,0),(1,40),(2,215),(3,440),(4,740),(5,1240),(6,1790),(7,2390),(8,2990),(9,3590),(10,4190),
                (11,4790),(12,5390),(13,5990),(14,6590),(15,7190),(16,7790),(17,8390),(18,8990),(19,9590),(20,10190),
                (21,10790),(22,11390),(23,11990),(24,12590),(25,13190),(26,13790),(27,14390),(28,14990),(29,15590),(30,16190),
                (31,16790),(32,17390),(33,17990),(34,18590),(35,19190),(36,19790),(37,20390),(38,20990),(39,21590),(40,22190),
                (41,22790),(42,23390),(43,23990),(44,24590),(45,25190),(46,25790),(47,26390),(48,26990),(49,27590),(50,28190),
                (51,28790),(52,29390),(53,29990),(54,30590),(55,31190),(56,31790),(57,32390),(58,32990),(59,33590),(60,34190),
                (61,34790),(62,35390),(63,35990),(64,36590),(65,37190),(66,37790),(67,38390),(68,38990),(69,39590),(70,40190),
                (71,40790),(72,41390),(73,41990),(74,42590),(75,43190),(76,43790),(77,44390),(78,44990),(79,45590),(80,46190),
                (81,46790),(82,47390),(83,47990),(84,48590),(85,49190),(86,49790),(87,50390),(88,50990),(89,51590),(90,52190),
                (91,52790),(92,53390),(93,53990),(94,54590),(95,55190),(96,55790),(97,56390),(98,56990),(99,57590),(100,58190),
                (101,58840),(102,59490),(103,60140),(104,60790),(105,61440),(106,62090),(107,62740),(108,63390),(109,64040),(110,64690),
                (111,65340),(112,65990),(113,66640),(114,67290),(115,67940),(116,68590),(117,69240),(118,69890),(119,70540),(120,71190),
                (121,71840),(122,72490),(123,73140),(124,73790),(125,74440),(126,75090),(127,75740),(128,76391),(129,77044),(130,77699),
                (131,78357),(132,79018),(133,79683),(134,80353),(135,81030),(136,81714),(137,82407),(138,83110),(139,83825),(140,84554),
                (141,85298),(142,86060),(143,86842),(144,87646),(145,88475),(146,89332),(147,90220),(148,91141),(149,92100),(150,93099),
                (151,94143),(152,95235),(153,96380),(154,97582),(155,98845),(156,100175),(157,101576),(158,103054),(159,104614),(160,106263),
                (161,108006),(162,109849),(163,111799),(164,113862),(165,116046),(166,118358),(167,120806),(168,123397),(169,126139),(170,129041),
                (171,132112),(172,135360),(173,138795),(174,142426),(175,146263),(176,150316),(177,154596),(178,159114),(179,163880),(180,168906),
                (181,174203),(182,179784),(183,185661),(184,191846),(185,198353),(186,205195),(187,212385),(188,219938),(189,227868),(190,236190),
                (191,244918),(192,254069),(193,263657),(194,273700),(195,284213),(196,295214),(197,306719),(198,318746),(199,331314),(200,344440)
            ) AS curve(level_value, xp_required)
            WHERE xp_required <= c.after_xp
        ), 0)::bigint AS after_level
    FROM computed c
),
final_values AS (
    SELECT
        l.*,
        (l.after_level + l.bonus_skill_points) AS after_total_skill_points,
        GREATEST((l.after_level + l.bonus_skill_points) - l.spent_skill_points - 1, 0)::bigint AS after_unspent_skill_points,
        CASE
            WHEN l.after_level <= 0 THEN 0
            WHEN l.after_level = 1 THEN 4
            WHEN l.after_level <= 3 THEN 4 + (l.after_level - 1) * 2
            WHEN l.after_level <= 15 THEN 8 + (l.after_level - 3) * 3
            WHEN l.after_level <= 30 THEN 44 + (l.after_level - 15) * 5
            WHEN l.after_level <= 50 THEN 119 + (l.after_level - 30) * 10
            WHEN l.after_level <= 69 THEN 319 + (l.after_level - 50) * 20
            WHEN l.after_level <= 85 THEN 699 + (l.after_level - 69) * 30
            WHEN l.after_level <= 125 THEN 1179 + (l.after_level - 85) * 40
            ELSE 2779
        END::bigint AS after_research_points
    FROM leveled l
),
updated_fgl AS (
    UPDATE dune.fgl_entities fe
    SET components = jsonb_set(
        jsonb_set(
            jsonb_set(
                fe.components,
                '{{FLevelComponent,1,TotalXPEarned}}',
                to_jsonb(fv.after_xp),
                true
            ),
            '{{FLevelComponent,1,TotalSkillPoints}}',
            to_jsonb(fv.after_total_skill_points),
            true
        ),
        '{{FLevelComponent,1,UnspentSkillPoints}}',
        to_jsonb(fv.after_unspent_skill_points),
        true
    )
    FROM final_values fv
    WHERE fe.entity_id = fv.entity_id
    RETURNING fe.entity_id
),
updated_actor AS (
    UPDATE dune.actors a
    SET properties = jsonb_set(
        a.properties,
        '{{TechKnowledgePlayerComponent,m_TechKnowledgePoints}}',
        to_jsonb(fv.after_research_points),
        true
    )
    FROM final_values fv
    WHERE a.id = fv.character_actor_id
    RETURNING a.id
)
SELECT
    fv.character_name,
    fv.character_actor_id,
    fv.online_status,
    fv.life_state,
    fv.before_xp,
    fv.after_xp,
    (fv.after_xp - fv.before_xp) AS xp_added,
    fv.after_level,
    fv.before_total_skill_points,
    fv.after_total_skill_points,
    fv.before_unspent_skill_points,
    fv.after_unspent_skill_points,
    fv.spent_skill_points,
    fv.bonus_skill_points,
    fv.after_research_points,
    CASE WHEN fv.after_xp >= (SELECT max_xp FROM settings) THEN true ELSE false END AS xp_capped
FROM final_values fv
JOIN updated_fgl uf
    ON uf.entity_id = fv.entity_id
JOIN updated_actor ua
    ON ua.id = fv.character_actor_id;
"""


def build_set_character_level_sql(character_actor_id, target_level):
    """
    Build admin-only SQL to set the displayed character level exactly.

    This reuses the character-XP recalculation SQL so skill points and research
    points stay aligned with the level curve. The resulting output still shows
    the before/after XP delta, which may be negative when lowering a level.
    """
    level = int(target_level)
    if level not in CHARACTER_LEVEL_XP or level <= 0:
        raise ValueError("target level must be between 1 and 200")

    target_xp = CHARACTER_LEVEL_XP[level]
    sql = build_give_character_xp_sql(character_actor_id, target_xp)

    return sql.replace(
        "LEAST(cs.before_xp + s.xp_delta, s.max_xp) AS after_xp",
        f"{target_xp}::bigint AS after_xp",
    )


def build_give_skill_points_sql(character_actor_id, skill_points):
    """
    Build admin-only SQL to add usable character skill points.

    Skill points live on the same DuneCharacter FGL entity as character XP.
    Adding to both TotalSkillPoints and UnspentSkillPoints gives the character
    new spendable points without disturbing points already spent in skill trees.
    """
    actor_id = int(character_actor_id)
    amount = int(skill_points)

    if amount <= 0:
        raise ValueError("skill point amount must be greater than zero")
    if amount > 1000:
        raise ValueError("skill point amount must be 1000 or lower")

    return f"""
WITH settings AS (
    SELECT
        {actor_id}::bigint AS character_actor_id,
        {amount}::bigint AS skill_points_delta
),
selected_player AS (
    SELECT
        ps.character_name,
        ps.player_pawn_id AS character_actor_id,
        ps.online_status,
        ps.life_state
    FROM dune.player_state ps
    JOIN settings s
        ON s.character_actor_id = ps.player_pawn_id
),
current_state AS (
    SELECT
        sp.character_name,
        sp.character_actor_id,
        sp.online_status,
        sp.life_state,
        fe.entity_id,
        COALESCE((fe.components #>> '{{FLevelComponent,1,TotalSkillPoints}}')::bigint, 0) AS before_total_skill_points,
        COALESCE((fe.components #>> '{{FLevelComponent,1,UnspentSkillPoints}}')::bigint, 0) AS before_unspent_skill_points
    FROM selected_player sp
    JOIN dune.actor_fgl_entities afe
        ON afe.actor_id = sp.character_actor_id
       AND afe.slot_name = 'DuneCharacter'
    JOIN dune.fgl_entities fe
        ON fe.entity_id = afe.entity_id
),
updated_fgl AS (
    UPDATE dune.fgl_entities fe
    SET components = jsonb_set(
        jsonb_set(
            fe.components,
            '{{FLevelComponent,1,TotalSkillPoints}}',
            to_jsonb(cs.before_total_skill_points + s.skill_points_delta),
            true
        ),
        '{{FLevelComponent,1,UnspentSkillPoints}}',
        to_jsonb(cs.before_unspent_skill_points + s.skill_points_delta),
        true
    )
    FROM current_state cs
    JOIN settings s
        ON s.character_actor_id = cs.character_actor_id
    WHERE fe.entity_id = cs.entity_id
    RETURNING fe.entity_id
)
SELECT
    cs.character_name,
    cs.character_actor_id,
    cs.online_status,
    cs.life_state,
    cs.before_total_skill_points,
    (cs.before_total_skill_points + s.skill_points_delta) AS after_total_skill_points,
    cs.before_unspent_skill_points,
    (cs.before_unspent_skill_points + s.skill_points_delta) AS after_unspent_skill_points,
    s.skill_points_delta AS skill_points_added
FROM current_state cs
JOIN settings s
    ON s.character_actor_id = cs.character_actor_id
JOIN updated_fgl uf
    ON uf.entity_id = cs.entity_id;
"""


def grant_item(player_id, item_id, quantity, durability="1.0"):
    cmd = [
        str(DUNE_SCRIPT),
        "admin",
        "grant-item-id",
        player_id,
        item_id,
        str(quantity),
        str(durability),
    ]
    return run_command(cmd, timeout=60)



# =========================================================
# LIVE MAP HELPERS
# =========================================================

def parse_transform(transform_value):
    """
    Parse Dune transform text.

    Observed format:
        ("(X,Y,Z)","(QX,QY,QZ,QW)")

    We only need X/Y/Z for map plotting.
    """
    if not transform_value:
        return None

    match = re.search(
        r'\(([0-9.eE+\-]+),([0-9.eE+\-]+),([0-9.eE+\-]+)\)',
        str(transform_value),
    )

    if not match:
        return None

    return {
        "x": float(match.group(1)),
        "y": float(match.group(2)),
        "z": float(match.group(3)),
    }


def parse_transform_rotation(transform_value):
    """
    Return the rotation tuple text from an actor transform.

    Observed format:
        ("(X,Y,Z)","(QX,QY,QZ,QW)")

    Vehicle relocation preserves rotation and only changes position.
    """
    if not transform_value:
        return None

    matches = re.findall(
        r'\(([0-9.eE+\-]+),([0-9.eE+\-]+),([0-9.eE+\-]+)(?:,([0-9.eE+\-]+))?\)',
        str(transform_value),
    )

    for match in matches:
        if match[3]:
            return f"({match[0]},{match[1]},{match[2]},{match[3]})"

    return None


def build_transform_literal(existing_transform, x, y, z):
    rotation = parse_transform_rotation(existing_transform)

    if not rotation:
        raise ValueError("could not parse existing actor rotation")

    return f'("({float(x)},{float(y)},{float(z)})","{rotation}")'


def teleportable_vehicle_class_where(column_name="class"):
    """
    Build the SQL allow-list for movable vehicle actor classes.

    column_name is kept as a small escape hatch because some queries use
    dune.actors directly while others alias it as "a". Only pass trusted local
    column names here; do not pass user input.
    """
    return " OR ".join(
        f"{column_name} ILIKE '%{pattern}%'"
        for pattern in TELEPORTABLE_VEHICLE_CLASS_PATTERNS
    )


def get_teleportable_vehicles():
    """
    Return confirmed vehicle actor rows for admin-only relocation.

    Ownership is not trusted yet. owner_account_id is exposed only to admins
    as a clue, not as an authorization boundary.
    """
    # The class allow-list is intentionally explicit. It currently covers the
    # confirmed actor classes for light/medium/transport ornithopters, sandbike,
    # buggy, treadwheel, and sandcrawler.
    vehicle_where = teleportable_vehicle_class_where("class")
    sql = f"""
    SELECT
        id,
        class,
        COALESCE(map, '') AS map,
        COALESCE(partition_id::text, '') AS partition_id,
        transform::text,
        COALESCE(owner_account_id::text, '') AS owner_account_id
    FROM dune.actors
    WHERE ({vehicle_where})
      AND transform IS NOT NULL
    ORDER BY id;
    """

    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        vehicles = []

        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                continue

            coords = parse_transform(parts[4]) or {}
            short_class = parts[1].split("/")[-1] if parts[1] else "Vehicle"

            vehicles.append(
                {
                    "actor_id": parts[0],
                    "class": parts[1],
                    "short_class": short_class,
                    "map": parts[2],
                    "partition_id": parts[3],
                    "transform": parts[4],
                    "owner_account_id": parts[5],
                    "x": coords.get("x", ""),
                    "y": coords.get("y", ""),
                    "z": coords.get("z", ""),
                }
            )

        return vehicles

    except Exception:
        return []


def get_teleportable_vehicle_actor(actor_id):
    actor_id = int(actor_id)
    vehicle_where = teleportable_vehicle_class_where("class")
    sql = f"""
    SELECT
        id,
        class,
        COALESCE(map, '') AS map,
        COALESCE(partition_id::text, '') AS partition_id,
        transform::text
    FROM dune.actors
    WHERE id = {actor_id}
      AND ({vehicle_where})
      AND transform IS NOT NULL
    LIMIT 1;
    """

    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "dune",
        "-d",
        "dune",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "failed to query vehicle actor")

    line = proc.stdout.strip()
    if not line:
        raise ValueError("vehicle actor not found")

    parts = line.split("\t")
    if len(parts) < 5:
        raise ValueError("unexpected vehicle actor query result")

    return {
        "actor_id": parts[0],
        "class": parts[1],
        "map": parts[2],
        "partition_id": parts[3],
        "transform": parts[4],
    }


def build_vehicle_teleport_sql(actor_id, existing_transform, map_key, partition_id, x, y, z):
    actor_id = int(actor_id)
    partition_id = int(partition_id)
    x = float(x)
    y = float(y)
    z = float(z)
    safe_map_key = str(map_key).replace("'", "''")
    # Preserve the actor's existing rotation quaternion and replace only the
    # position vector. This avoids turning the vehicle while relocating it.
    safe_transform = build_transform_literal(existing_transform, x, y, z).replace("'", "''")
    vehicle_where = teleportable_vehicle_class_where("class")

    return f"""
UPDATE dune.actors
SET
    map = '{safe_map_key}',
    partition_id = {partition_id},
    transform = '{safe_transform}'
WHERE id = {actor_id}
  AND ({vehicle_where})
  AND transform IS NOT NULL
RETURNING
    id,
    class,
    map,
    partition_id,
    transform::text;
"""


def world_to_map_pixels(x, y, map_cfg):
    """
    Convert world coordinates to image pixel coordinates using the
    calibrated Hagga Basin map bounds.

    Marker rendering uses percentages, so the display still scales
    correctly if the browser resizes the map image.
    """
    min_x = map_cfg["min_x"]
    max_x = map_cfg["max_x"]
    min_y = map_cfg["min_y"]
    max_y = map_cfg["max_y"]
    width = map_cfg["width"]
    height = map_cfg["height"]

    if max_x == min_x or max_y == min_y:
        return None

    px = ((x - min_x) / (max_x - min_x)) * width
    py = ((y - min_y) / (max_y - min_y)) * height

    if map_cfg.get("flip_y"):
        py = height - py

    return {
        "px": px,
        "py": py,
        "in_bounds": 0 <= px <= width and 0 <= py <= height,
    }


def get_map_markers(map_key=None):
    """
    Pull live actors with transform data for the selected map.

    Uses actor.transform, not actor.properties. This is the key field
    that carries live spatial coordinates.
    """
    map_key = map_key or DEFAULT_MAP_KEY
    map_cfg = MAP_CONFIGS.get(map_key, MAP_CONFIGS[DEFAULT_MAP_KEY])
    map_key = map_cfg["key"]

    players_sql = f"""
    SELECT
        a.id,
        COALESCE(NULLIF(ps.character_name, ''), 'Unknown') AS name,
        ps.online_status::text AS online_status,
        acc."user" AS fls_id,
        a.map,
        a.transform::text
    FROM dune.actors a
    JOIN dune.player_state ps
        ON a.id = ps.player_pawn_id
    LEFT JOIN dune.accounts acc
        ON ps.account_id = acc.id
    WHERE a.transform IS NOT NULL
      AND a.map = '{map_key}'
    ORDER BY ps.character_name;
    """

    vehicles_sql = f"""
    SELECT
        v.id,
        a.class,
        a.map,
        a.transform::text
    FROM dune.vehicles v
    JOIN dune.actors a
        ON v.id = a.id
    WHERE a.transform IS NOT NULL
      AND a.map = '{map_key}'
    ORDER BY a.class;
    """

    buildings_sql = f"""
    SELECT
        b.id,
        a.class,
        a.map,
        a.transform::text
    FROM dune.buildings b
    JOIN dune.actors a
        ON b.id = a.id
    WHERE a.transform IS NOT NULL
      AND a.map = '{map_key}'
    ORDER BY b.id
    LIMIT 500;
    """

    def run_tab_query(sql):
        cmd = [
            "docker", "exec", POSTGRES_CONTAINER,
            "psql", "-U", "dune", "-d", "dune",
            "-At", "-F", "\t", "-c", sql,
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        if proc.returncode != 0:
            return []

        return proc.stdout.strip().splitlines()

    markers = []

    # Players
    for line in run_tab_query(players_sql):
        parts = line.split("\t")
        if len(parts) < 6:
            continue

        coords = parse_transform(parts[5])
        if not coords:
            continue

        pixel = world_to_map_pixels(coords["x"], coords["y"], map_cfg)
        if not pixel:
            continue

        markers.append({
            "id": parts[0],
            "name": parts[1],
            "online_status": parts[2],
            "fls_id": parts[3],
            "map": parts[4],
            "type": "player",
            **coords,
            **pixel,
        })

    # Vehicles
    for line in run_tab_query(vehicles_sql):
        parts = line.split("\t")
        if len(parts) < 4:
            continue

        coords = parse_transform(parts[3])
        if not coords:
            continue

        pixel = world_to_map_pixels(coords["x"], coords["y"], map_cfg)
        if not pixel:
            continue

        short_class = parts[1].split("/")[-1] if parts[1] else "Vehicle"

        markers.append({
            "id": parts[0],
            "name": short_class,
            "map": parts[2],
            "type": "vehicle",
            **coords,
            **pixel,
        })

    # Bases/buildings. If the table is not present or the query fails,
    # run_tab_query returns no rows and the map still works.
    for line in run_tab_query(buildings_sql):
        parts = line.split("\t")
        if len(parts) < 4:
            continue

        coords = parse_transform(parts[3])
        if not coords:
            continue

        pixel = world_to_map_pixels(coords["x"], coords["y"], map_cfg)
        if not pixel:
            continue

        short_class = parts[1].split("/")[-1] if parts[1] else "Base"

        markers.append({
            "id": parts[0],
            "name": short_class,
            "map": parts[2],
            "type": "base",
            **coords,
            **pixel,
        })

    return markers


def teleport_offline_player(fls_id, partition_id, x, y, z):
    """
    Teleport an offline player through RedBlink/Funcom's DB function.

    IMPORTANT:
    This is intended for offline characters. Online teleporting may not
    apply cleanly because the live server owns the actor state.
    """
    safe_fls = str(fls_id).replace("'", "''")

    sql = f"""
    SELECT dune.admin_move_offline_player_to_partition(
        '{safe_fls}',
        {int(partition_id)},
        ROW({float(x)}, {float(y)}, {float(z)})::dune.vector
    );
    """

    return run_psql(sql, timeout=60)



def emergency_return_to_hagga_basin(fls_id):
    """
    Move an offline character to the configured safe Hagga Basin point.

    This is meant as an operator/admin unstuck tool.
    """
    cfg = SAFE_HAGGA_BASIN_RETURN

    return teleport_offline_player(
        fls_id,
        cfg["partition_id"],
        cfg["x"],
        cfg["y"],
        cfg["z"],
    )



# =========================================================
# INFRASTRUCTURE HELPERS
# =========================================================

def run_infra_command(cmd, timeout=60, cwd=None):
    """
    Run an infrastructure command from a fixed argument list.

    This is for predefined installer/diagnostic commands. It should not be
    used with raw user command text.
    """
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    return (
        "$ " + " ".join(cmd)
        + "\n\nSTDOUT:\n" + proc.stdout
        + "\nSTDERR:\n" + proc.stderr
        + f"\nExit code: {proc.returncode}"
    )


def prereq_report():
    """
    Build a simple prereq report for RedBlink's stack.

    This checks the obvious local host requirements without mutating anything.
    """
    checks = [
        ("OS / kernel", ["bash", "-lc", "uname -a"]),
        ("Memory", ["bash", "-lc", "free -h"]),
        ("Disk /", ["bash", "-lc", "df -h /"]),
        ("CPU AVX/AVX2", ["bash", "-lc", "lscpu | grep -i 'flags' | head -1 | grep -oE 'avx2|avx' | sort -u | tr '\\n' ' ' || true"]),
        ("Docker", ["bash", "-lc", "docker --version || true"]),
        ("Docker Compose", ["bash", "-lc", "docker compose version || true"]),
        ("Git", ["bash", "-lc", "git --version || true"]),
        ("Dune command", ["bash", "-lc", "command -v dune || true"]),
    ]

    output = []

    for label, cmd in checks:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            output.append(f"## {label}\n{proc.stdout.strip() or proc.stderr.strip() or '(no output)'}")
        except Exception as exc:
            output.append(f"## {label}\nERROR: {exc}")

    return "\n\n".join(output)


def installer_step_command(step):
    """
    Return a predefined installer command.

    The installer is intentionally step-based instead of one giant root script.
    That makes it easier to inspect, safer to demo, and easier to recover.
    """
    install_dir = shlex.quote(str(REDBLINK_INSTALL_DIR))
    parent_dir = shlex.quote(str(REDBLINK_INSTALL_DIR.parent))
    repo_url = shlex.quote(REDBLINK_REPO_URL)

    commands = {
        "prereq": {
            "cmd": None,
            "timeout": 30,
            "custom": prereq_report,
        },

        "install_base_packages": {
            "cmd": [
                "bash",
                "-lc",
                "sudo -n apt update && sudo -n apt install -y git curl ca-certificates apt-transport-https software-properties-common"
            ],
            "timeout": 300,
        },

        "install_docker": {
            "cmd": [
                "bash",
                "-lc",
                "curl -fsSL https://get.docker.com | sudo -n sh"
            ],
            "timeout": 900,
        },

        "install_docker_fallback": {
            "cmd": [
                "bash",
                "-lc",
                "sudo -n apt update && sudo -n apt install -y docker.io docker-compose-plugin && sudo -n systemctl enable --now docker"
            ],
            "timeout": 900,
        },

        "install_docker_compose_plugin": {
            "cmd": [
                "bash",
                "-lc",
                "sudo -n apt update && sudo -n apt install -y docker-compose-plugin"
            ],
            "timeout": 300,
        },

        "add_user_to_docker_group": {
            "cmd": [
                "bash",
                "-lc",
                "sudo -n usermod -aG docker $USER && echo 'User added to docker group. Logout/login or reboot may be required.'"
            ],
            "timeout": 60,
        },

        "enable_docker_service": {
            "cmd": [
                "bash",
                "-lc",
                "sudo -n systemctl enable --now docker && systemctl status docker --no-pager || true"
            ],
            "timeout": 60,
        },

        "clone_or_pull": {
            "cmd": [
                "bash",
                "-lc",
                f"mkdir -p {parent_dir} && if [ -d {install_dir}/.git ]; then cd {install_dir} && git pull; else git clone {repo_url} {install_dir}; fi"
            ],
            "timeout": 300,
        },

        "install_dune_command": {
            "cmd": [
                "bash",
                "-lc",
                f"cd {install_dir} && sudo -n runtime/scripts/install-command.sh"
            ],
            "timeout": 300,
        },

        "dune_init": {
            "cmd": [
                "bash",
                "-lc",
                f"cd {install_dir} && dune init"
            ],
            "timeout": 600,
        },

        "docker_ps": {
            "cmd": [
                "bash",
                "-lc",
                "docker ps"
            ],
            "timeout": 30,
        },
    }
    return commands.get(step)


def start_shell_session(sid):
    """
    Start a login shell attached to a pseudo-terminal.

    This is powerful. It is admin-only and disabled by default.
    """
    if sid in SHELL_SESSIONS:
        return

    shell = os.environ.get("SHELL", "/bin/bash")
    pid, fd = pty.fork()

    if pid == 0:
        os.execv(shell, [shell])

    SHELL_SESSIONS[sid] = {
        "pid": pid,
        "fd": fd,
    }

    def reader():
        while sid in SHELL_SESSIONS:
            try:
                ready, _, _ = select.select([fd], [], [], 0.1)
                if fd in ready:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    socketio.emit("shell_output", {"data": data.decode(errors="replace")}, to=sid)
            except OSError:
                break
            except Exception as exc:
                socketio.emit("shell_output", {"data": f"\n[terminal error: {exc}]\n"}, to=sid)
                break

        stop_shell_session(sid)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()


def stop_shell_session(sid):
    session_obj = SHELL_SESSIONS.pop(sid, None)

    if not session_obj:
        return

    try:
        os.close(session_obj["fd"])
    except Exception:
        pass

    try:
        os.kill(session_obj["pid"], signal.SIGHUP)
    except Exception:
        pass





# =========================================================
# DASHBOARD RESOURCE HELPERS
# =========================================================

_LAST_NET_SAMPLE = {
    "timestamp": None,
    "bytes_sent": None,
    "bytes_recv": None,
}

def bytes_to_human(value):
    try:
        value = float(value)
    except Exception:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0

    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1

    return f"{value:.1f} {units[idx]}"


def get_system_resource_summary():
    """
    Return host-level resource metrics for the dashboard.

    Network totals are reported since boot. RX/TX rates are estimated from
    the previous API sample and become meaningful after the second refresh.
    """
    global _LAST_NET_SAMPLE

    try:
        now = time.time()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()

        rx_rate = 0
        tx_rate = 0

        if (
            _LAST_NET_SAMPLE["timestamp"] is not None
            and _LAST_NET_SAMPLE["bytes_recv"] is not None
            and _LAST_NET_SAMPLE["bytes_sent"] is not None
        ):
            elapsed = max(now - _LAST_NET_SAMPLE["timestamp"], 0.001)
            rx_rate = max((net.bytes_recv - _LAST_NET_SAMPLE["bytes_recv"]) / elapsed, 0)
            tx_rate = max((net.bytes_sent - _LAST_NET_SAMPLE["bytes_sent"]) / elapsed, 0)

        _LAST_NET_SAMPLE = {
            "timestamp": now,
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        }

        return {
            "ok": True,
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used": bytes_to_human(memory.used),
            "memory_total": bytes_to_human(memory.total),
            "disk_percent": round(disk.percent, 1),
            "disk_used": bytes_to_human(disk.used),
            "disk_total": bytes_to_human(disk.total),
            "net_sent": bytes_to_human(net.bytes_sent),
            "net_recv": bytes_to_human(net.bytes_recv),
            "net_rx_rate": bytes_to_human(rx_rate) + "/s",
            "net_tx_rate": bytes_to_human(tx_rate) + "/s",
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }


def get_world_summary_counts():
    """
    Return basic world/server counts for the dashboard.

    Fails gracefully if the RedBlink stack/Postgres container is not running.
    """
    sql = r"""
    WITH player_counts AS (
        SELECT
            COUNT(*) AS total_players,
            COUNT(*) FILTER (WHERE online_status::text <> 'Offline') AS online_players
        FROM dune.player_state
    ),
    vehicle_counts AS (
        SELECT
            COUNT(*) FILTER (WHERE a.map = 'HaggaBasin') AS vehicles_hagga_basin,
            COUNT(*) FILTER (WHERE a.map = 'DeepDesert') AS vehicles_deep_desert,
            COUNT(*) AS total_vehicles
        FROM dune.vehicles v
        JOIN dune.actors a
            ON a.id = v.id
    ),
    base_counts AS (
        SELECT
            COUNT(*) FILTER (WHERE a.map = 'HaggaBasin') AS bases_hagga_basin,
            COUNT(*) FILTER (WHERE a.map = 'DeepDesert') AS bases_deep_desert
        FROM dune.buildings b
        JOIN dune.actors a
            ON a.id = b.id
    )
    SELECT
        pc.total_players,
        pc.online_players,
        vc.total_vehicles,
        vc.vehicles_hagga_basin,
        vc.vehicles_deep_desert,
        bc.bases_hagga_basin,
        bc.bases_deep_desert
    FROM player_counts pc
    CROSS JOIN vehicle_counts vc
    CROSS JOIN base_counts bc;
    """

    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", "dune", "-d", "dune",
        "-At", "-F", "\t", "-c", sql,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": proc.stderr.strip() or "world count query failed",
            }

        line = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
        parts = line.split("\t")

        if len(parts) < 7:
            return {
                "ok": False,
                "error": "unexpected world count output",
            }

        return {
            "ok": True,
            "total_players": parts[0],
            "online_players": parts[1],
            "total_vehicles": parts[2],
            "vehicles_hagga_basin": parts[3],
            "vehicles_deep_desert": parts[4],
            "bases_hagga_basin": parts[5],
            "bases_deep_desert": parts[6],
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }


def build_dashboard_metrics_payload():
    return {
        "ok": True,
        "system": get_system_resource_summary(),
        "world": get_world_summary_counts(),
    }
