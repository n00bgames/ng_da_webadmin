#!/usr/bin/env python3
"""
n00bGame's Dune Awakening Web-Admin
Panel version: 0.5.8-alpha
RedBlink stack compatibility target: v1.3.1

0.5.8-alpha public demonstration build:
- Updates navigation links into polished Dune-themed buttons.
- Updates Mk6 Medium Ornithopter kit RocketAmmo from 100 to 250.
- Adds emergency return configuration and endpoint.
- Vehicle module repair now attempts to update CurrentDurability and MaxDurability.
- README now includes alpha/demo guidance, security notes, tested features, known risks, and required assets.

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
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash


# =========================================================
# CONFIGURABLE VALUES
# =========================================================

PANEL_VERSION = "0.5.8-alpha"
REDBLINK_STACK_VERSION = "v1.3.1"

# RedBlink stack path. Change this if your install lives elsewhere.
DUNE_ROOT = Path(
    os.environ.get(
        "DUNE_ROOT",
        "/home/steihl/dune-awakening-selfhost-docker",
    )
)

# Official RedBlink wrapper script.
DUNE_SCRIPT = DUNE_ROOT / "runtime/scripts/dune"

# RedBlink item catalog.
ITEMS_FILE = DUNE_ROOT / "runtime/data/admin-items.json"

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "users.db"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
ACTION_LOG = LOG_DIR / "actions.log"

POSTGRES_CONTAINER = "dune-postgres"

# Change with:
# export DUNE_SECRET_KEY='long-random-string'
SECRET_KEY = os.environ.get("DUNE_SECRET_KEY", "change-this-secret-before-sharing")

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
        "default_partition_id": 250100,
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
        "default_partition_id": "",
    },
}

DEFAULT_MAP_KEY = "HaggaBasin"

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


@app.context_processor
def inject_template_globals():
    return {
        "panel_version": PANEL_VERSION,
        "redblink_stack_version": REDBLINK_STACK_VERSION,
        "maps": MAPS,
        "restart_targets": RESTART_TARGETS,
        "scout_thopter_template": SCOUT_THOPTER_TEMPLATE,
        "medium_bundle": MEDIUM_THOPTER_BUNDLE,
        "default_overrepair_durability": DEFAULT_OVERREPAIR_DURABILITY,
        "default_vehicle_repair_durability": DEFAULT_VEHICLE_REPAIR_DURABILITY,
        "map_configs": MAP_CONFIGS,
        "default_map_key": DEFAULT_MAP_KEY,
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
            role TEXT NOT NULL
        )
        """
    )
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
        SELECT id, username, role
        FROM users
        ORDER BY username
        """
    ).fetchall()
    conn.close()
    return rows


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
# SETUP / LOGIN / ACCOUNT
# =========================================================

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if user_count() > 0:
        return redirect("/login")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username and password:
            conn = db()
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), "admin"),
            )
            conn.commit()
            conn.close()

            log_action(username, "created first admin account")
            return redirect("/login")

    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if user_count() == 0:
        return redirect("/setup")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if row and check_password_hash(row["password"], password):
            session["user"] = row["username"]
            session["role"] = row["role"]
            log_action(username, "logged in")
            return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_action(session["user"], "logged out")
    session.clear()
    return redirect("/login")


@app.route("/account", methods=["GET", "POST"])
def account():
    if not logged_in():
        return redirect("/login")

    message = ""

    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "").strip()

        conn = db()

        if new_username:
            conn.execute(
                "UPDATE users SET username = ? WHERE username = ?",
                (new_username, session["user"]),
            )
            log_action(session["user"], f"changed username to {new_username}")
            session["user"] = new_username
            message = "Username updated."

        if new_password:
            conn.execute(
                "UPDATE users SET password = ? WHERE username = ?",
                (generate_password_hash(new_password), session["user"]),
            )
            log_action(session["user"], "changed own password")
            message = "Password updated."

        conn.commit()
        conn.close()

    return render_template("account.html", message=message)


# =========================================================
# PAGES
# =========================================================

@app.route("/")
def dashboard():
    if not logged_in():
        return redirect("/login")
    return render_template("dashboard.html")


@app.route("/online")
def online_page():
    if not logged_in():
        return redirect("/login")
    return render_template("online.html")


@app.route("/map")
def map_page():
    if not logged_in():
        return redirect("/login")
    return render_template("map.html")


@app.route("/grants")
def grants_page():
    if not logged_in():
        return redirect("/login")
    if current_role() == "viewer":
        return "Forbidden", 403
    return render_template("grants.html")


@app.route("/server")
def server_page():
    if not logged_in():
        return redirect("/login")
    if current_role() == "viewer":
        return "Forbidden", 403
    return render_template("server.html")


@app.route("/admin")
def admin_page():
    if not logged_in():
        return redirect("/login")
    if not is_admin():
        return "Forbidden", 403
    return render_template("admin.html")


@app.route("/users")
def users_page():
    if not logged_in():
        return redirect("/login")
    if not is_admin():
        return "Forbidden", 403
    return render_template("users.html", users=list_users())


@app.route("/logs")
def logs_page():
    if not logged_in():
        return redirect("/login")
    if current_role() == "viewer":
        return "Forbidden", 403
    return render_template("logs.html", lines=recent_log_lines())


# =========================================================
# USER MANAGEMENT ROUTES
# =========================================================

@app.route("/users/add", methods=["POST"])
def add_user():
    if not logged_in() or not is_admin():
        return "Forbidden", 403

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "viewer").strip()

    if role not in ("viewer", "operator", "admin"):
        role = "viewer"

    if username and password:
        conn = db()
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )
        conn.commit()
        conn.close()
        log_action(session["user"], f"created user {username} ({role})")

    return redirect("/users")


@app.route("/users/role", methods=["POST"])
def change_user_role():
    if not logged_in() or not is_admin():
        return "Forbidden", 403

    user_id = request.form.get("user_id", "").strip()
    role = request.form.get("role", "viewer").strip()

    if role not in ("viewer", "operator", "admin"):
        role = "viewer"

    conn = db()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()

    log_action(session["user"], f"changed user id {user_id} role to {role}")
    return redirect("/users")


@app.route("/users/password", methods=["POST"])
def reset_user_password():
    if not logged_in() or not is_admin():
        return "Forbidden", 403

    user_id = request.form.get("user_id", "").strip()
    password = request.form.get("password", "").strip()

    if password:
        conn = db()
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
        conn.commit()
        conn.close()
        log_action(session["user"], f"reset password for user id {user_id}")

    return redirect("/users")


@app.route("/users/delete", methods=["POST"])
def delete_user():
    if not logged_in() or not is_admin():
        return "Forbidden", 403

    user_id = request.form.get("user_id", "").strip()

    conn = db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_action(session["user"], f"deleted user id {user_id}")
    return redirect("/users")


# =========================================================
# AJAX API ROUTES
# =========================================================

@app.route("/api/characters")
def api_characters():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    include_offline = request.args.get("include_offline", "1") != "0"
    chars = get_characters(include_offline=include_offline)

    # Viewer privacy: viewers do not receive IDs.
    if current_role() == "viewer":
        chars = [
            {
                "character_name": c.get("character_name", ""),
                "online_status": c.get("online_status", ""),
                "life_state": c.get("life_state", ""),
            }
            for c in chars
        ]

    return jsonify({"ok": True, "characters": chars})


@app.route("/api/online-players")
def api_online_players():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    players = get_characters(include_offline=False)

    if current_role() == "viewer":
        players = [
            {
                "character_name": p.get("character_name", ""),
                "online_status": p.get("online_status", ""),
                "life_state": p.get("life_state", ""),
            }
            for p in players
        ]

    return jsonify({"ok": True, "players": players})


@app.route("/api/item-search")
def api_item_search():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    query = request.args.get("q", "").strip()
    return jsonify({"ok": True, "items": search_items(query)})


@app.route("/api/map-markers")
def api_map_markers():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    requested_map = request.args.get("map", DEFAULT_MAP_KEY).strip()
    map_cfg = MAP_CONFIGS.get(requested_map, MAP_CONFIGS[DEFAULT_MAP_KEY])
    markers = get_map_markers(map_cfg["key"])

    # Viewer privacy: viewers may see names and dots, but not FLS IDs.
    if current_role() == "viewer":
        for marker in markers:
            marker.pop("fls_id", None)

    return jsonify({
        "ok": True,
        "map": map_cfg,
        "maps": MAP_CONFIGS,
        "default_map": DEFAULT_MAP_KEY,
        "markers": markers,
    })


@app.route("/api/teleport-offline", methods=["POST"])
def api_teleport_offline():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    fls_id = request.form.get("fls_id", "").strip()
    map_key = request.form.get("map_key", DEFAULT_MAP_KEY).strip()
    map_cfg = MAP_CONFIGS.get(map_key, MAP_CONFIGS[DEFAULT_MAP_KEY])
    partition_id = request.form.get("partition_id", str(map_cfg.get("default_partition_id", ""))).strip()
    x = request.form.get("x", "0").strip()
    y = request.form.get("y", "0").strip()
    z = request.form.get("z", "0").strip()

    if not fls_id:
        return jsonify({"ok": False, "error": "missing FLS ID"}), 400

    if not partition_id:
        return jsonify({"ok": False, "error": "missing partition ID for selected map"}), 400

    try:
        output = teleport_offline_player(fls_id, partition_id, x, y, z)

        log_action(
            session["user"],
            f"teleport offline fls {fls_id} partition {partition_id} to ({x}, {y}, {z})",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"Teleport failed: {exc}"}), 500


@app.route("/api/emergency-return", methods=["POST"])
def api_emergency_return():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    fls_id = request.form.get("fls_id", "").strip()

    if not fls_id:
        return jsonify({"ok": False, "error": "missing FLS ID"}), 400

    try:
        output = emergency_return_to_hagga_basin(fls_id)

        log_action(
            session["user"],
            f"emergency return to Hagga Basin safe point for {fls_id}",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"Emergency return failed: {exc}"}), 500


@app.route("/api/logs")
def api_logs():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if current_role() == "viewer":
        return jsonify({"ok": False, "error": "permission denied"}), 403
    return jsonify({"ok": True, "lines": recent_log_lines()})


@app.route("/api/grant", methods=["POST"])
def api_grant():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_id = request.form.get("player_id", "").strip()
    item_id = request.form.get("item_id", "").strip()
    quantity = request.form.get("quantity", "1").strip()
    durability = request.form.get("durability", "1.0").strip()

    try:
        output = grant_item(player_id, item_id, quantity, durability)
        log_action(session["user"], f"grant {item_id} x{quantity} to {player_id}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Grant failed: {exc}"}), 500


@app.route("/api/give-scout-thopter", methods=["POST"])
def api_give_scout_thopter():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_id = request.form.get("player_id", "").strip()

    cmd = [
        str(DUNE_SCRIPT),
        "admin",
        "grant-template",
        player_id,
        SCOUT_THOPTER_TEMPLATE,
    ]

    try:
        output = run_command(cmd, timeout=60)
        log_action(session["user"], f"grant template {SCOUT_THOPTER_TEMPLATE} to {player_id}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Scout thopter grant failed: {exc}"}), 500


@app.route("/api/give-medium-thopter", methods=["POST"])
def api_give_medium_thopter():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_id = request.form.get("player_id", "").strip()

    outputs = []
    try:
        for item_id, qty in MEDIUM_THOPTER_BUNDLE:
            outputs.append(grant_item(player_id, item_id, qty, "1.0"))

        log_action(session["user"], f"grant Mk6 Medium thopter bundle to {player_id}")
        return jsonify({"ok": True, "output": "\n\n---\n\n".join(outputs)})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Medium thopter grant failed: {exc}"}), 500



@app.route("/api/vehicles")
def api_vehicles():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    return jsonify({"ok": True, "vehicles": get_vehicles()})


@app.route("/api/repair-vehicle", methods=["POST"])
def api_repair_vehicle():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    # Direct vehicle module SQL mutation is admin-only.
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    vehicle_id = request.form.get("vehicle_id", "").strip()
    durability = request.form.get("durability", DEFAULT_VEHICLE_REPAIR_DURABILITY).strip()

    try:
        sql = build_vehicle_repair_sql(vehicle_id, durability)
        output = run_psql(sql, timeout=60)

        log_action(
            session["user"],
            f"repair vehicle {vehicle_id} module durability {durability}",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"Vehicle repair failed: {exc}"}), 500



@app.route("/api/overrepair", methods=["POST"])
def api_overrepair():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    character_actor_id = request.form.get("character_actor_id", "").strip()
    inventory_id = request.form.get("inventory_id", "").strip()
    durability = request.form.get("durability", DEFAULT_OVERREPAIR_DURABILITY).strip()

    try:
        sql = build_overrepair_sql(character_actor_id, inventory_id, durability)
        output = run_psql(sql, timeout=60)
        log_action(
            session["user"],
            f"overrepair actor {character_actor_id} inventory {inventory_id} durability {durability}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Overrepair failed: {exc}"}), 500


@app.route("/api/spawn-map", methods=["POST"])
def api_spawn_map():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    map_name = request.form.get("map_name", "").strip()
    if map_name not in MAPS:
        return jsonify({"ok": False, "error": "unknown map"}), 400

    try:
        output = run_command([str(DUNE_SCRIPT), "spawn", map_name], timeout=120)
        log_action(session["user"], f"spawn map {map_name}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Spawn failed: {exc}"}), 500


@app.route("/api/restart-target", methods=["POST"])
def api_restart_target():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    target = request.form.get("target", "").strip()
    if target not in RESTART_TARGETS:
        return jsonify({"ok": False, "error": "unknown restart target"}), 400

    try:
        output = run_command([str(DUNE_SCRIPT), "restart", target], timeout=180)
        log_action(session["user"], f"restart target {target}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Restart failed: {exc}"}), 500


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8088)
