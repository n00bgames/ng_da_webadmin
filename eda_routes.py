"""
Easy Dune Admin route registrations.

Importing this module attaches all Flask routes and Socket.IO handlers to the
shared app/socketio objects from eda_core. Keep route handlers here and shared
business logic in eda_core or future service modules.
"""

from eda_core import *  # noqa: F401,F403 - route module intentionally shares app context

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

    metrics = build_dashboard_metrics_payload()

    return render_template(
        "dashboard.html",
        system_summary=metrics["system"],
        world_summary=metrics["world"],
    )


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
    if not is_operator_or_admin():
        return "Forbidden", 403
    return render_template("grants.html")


@app.route("/server")
def server_page():
    if not logged_in():
        return redirect("/login")
    if not is_operator_or_admin():
        return "Forbidden", 403
    return render_template("server.html")


@app.route("/vip")
def vip_page():
    if not logged_in():
        return redirect("/login")
    if not can_use_vip_tools():
        return "Forbidden", 403
    return render_template("vip.html")


@app.route("/admin")
def admin_page():
    if not logged_in():
        return redirect("/login")
    if not is_admin():
        return "Forbidden", 403
    return render_template("admin.html")


@app.route("/infrastructure")
def infrastructure_page():
    if not logged_in():
        return redirect("/login")
    if not is_admin():
        return "Forbidden", 403
    return render_template("infrastructure.html")


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
    if not is_admin():
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
    character_name = request.form.get("character_name", "").strip()

    if role not in ("viewer", "vip", "operator", "admin"):
        role = "viewer"

    if username and password:
        conn = db()
        conn.execute(
            "INSERT INTO users (username, password, role, character_name) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, character_name),
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

    if role not in ("viewer", "vip", "operator", "admin"):
        role = "viewer"

    conn = db()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()

    log_action(session["user"], f"changed user id {user_id} role to {role}")
    return redirect("/users")


@app.route("/users/character", methods=["POST"])
def change_user_character():
    if not logged_in() or not is_admin():
        return "Forbidden", 403

    user_id = request.form.get("user_id", "").strip()
    character_name = request.form.get("character_name", "").strip()

    conn = db()
    conn.execute(
        "UPDATE users SET character_name = ? WHERE id = ?",
        (character_name, user_id),
    )
    conn.commit()
    conn.close()

    log_action(session["user"], f"changed user id {user_id} character link to {character_name}")
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

    # Viewer/VIP privacy: broad character APIs do not expose IDs to lower roles.
    # VIP self-service receives its own IDs through /api/vip-character only.
    if current_role() in ("viewer", "vip"):
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

    if current_role() in ("viewer", "vip"):
        players = [
            {
                "character_name": p.get("character_name", ""),
                "online_status": p.get("online_status", ""),
                "life_state": p.get("life_state", ""),
            }
            for p in players
        ]

    return jsonify({"ok": True, "players": players})


@app.route("/api/footer-online-users")
def api_footer_online_users():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    return jsonify({"ok": True, "users": footer_online_users()})


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

    # Viewer/VIP privacy: map markers may show names/dots, but not FLS IDs.
    if current_role() in ("viewer", "vip"):
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
    partition_default = ORNITHOPTER_PARTITION_DEFAULTS.get(map_cfg["key"], "")
    partition_id = request.form.get("partition_id", str(partition_default)).strip()
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


@app.route("/api/vip-character")
def api_vip_character():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not can_use_vip_tools():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        character = get_self_character_for_user(session["user"])
        # This endpoint is self-only. It intentionally returns the user's own
        # actor/inventory/FLS IDs so the VIP page can display useful diagnostics.
        return jsonify({"ok": True, "character": character})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404


@app.route("/api/vip-overrepair", methods=["POST"])
def api_vip_overrepair():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not can_use_vip_tools():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    durability = request.form.get("durability", DEFAULT_OVERREPAIR_DURABILITY).strip()

    try:
        character = get_self_character_for_user(session["user"])
        if not character.get("character_actor_id") or not character.get("inventory_id"):
            return jsonify({"ok": False, "error": "linked character actor/inventory not found"}), 400

        sql = build_overrepair_sql(
            character["character_actor_id"],
            character["inventory_id"],
            durability,
        )
        output = run_psql(sql, timeout=60)

        log_action(
            session["user"],
            f"vip overrepair own character {character['character_name']} durability {durability}",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"VIP overrepair failed: {exc}"}), 500


@app.route("/api/vip-teleport-offline", methods=["POST"])
def api_vip_teleport_offline():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not can_use_vip_tools():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    map_key = request.form.get("map_key", DEFAULT_MAP_KEY).strip()
    map_cfg = MAP_CONFIGS.get(map_key, MAP_CONFIGS[DEFAULT_MAP_KEY])
    partition_default = ORNITHOPTER_PARTITION_DEFAULTS.get(map_cfg["key"], "")
    partition_id = request.form.get("partition_id", str(partition_default)).strip()
    x = request.form.get("x", "0").strip()
    y = request.form.get("y", "0").strip()
    z = request.form.get("z", "1000").strip()

    if not partition_id:
        return jsonify({"ok": False, "error": "missing partition ID for selected map"}), 400

    try:
        character = get_self_character_for_user(session["user"])
        if not character.get("fls_id"):
            return jsonify({"ok": False, "error": "linked character FLS/account ID not found"}), 400

        output = teleport_offline_player(character["fls_id"], partition_id, x, y, z)

        log_action(
            session["user"],
            f"vip teleport own character {character['character_name']} partition {partition_id} to ({x}, {y}, {z})",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"VIP teleport failed: {exc}"}), 500


@app.route("/api/vip-give-scout-thopter", methods=["POST"])
def api_vip_give_scout_thopter():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not can_use_vip_tools():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        character = get_self_character_for_user(session["user"])
        if not character.get("fls_id"):
            return jsonify({"ok": False, "error": "linked character FLS/account ID not found"}), 400

        cmd = [
            str(DUNE_SCRIPT),
            "admin",
            "grant-template",
            character["fls_id"],
            SCOUT_THOPTER_TEMPLATE,
        ]
        output = run_command(cmd, timeout=60)

        log_action(
            session["user"],
            f"vip grant template {SCOUT_THOPTER_TEMPLATE} to own character {character['character_name']}",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"VIP scout thopter grant failed: {exc}"}), 500


@app.route("/api/vip-give-medium-thopter", methods=["POST"])
def api_vip_give_medium_thopter():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not can_use_vip_tools():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        character = get_self_character_for_user(session["user"])
        if not character.get("fls_id"):
            return jsonify({"ok": False, "error": "linked character FLS/account ID not found"}), 400

        outputs = []
        for item_id, qty in MEDIUM_THOPTER_BUNDLE:
            outputs.append(grant_item(character["fls_id"], item_id, qty, "1.0"))

        log_action(
            session["user"],
            f"vip grant Mk6 Medium thopter bundle to own character {character['character_name']}",
        )

        return jsonify({"ok": True, "output": "\n\n---\n\n".join(outputs)})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"VIP medium thopter grant failed: {exc}"}), 500


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


@app.route("/api/market-preset-preview")
def api_market_preset_preview():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        summary = market_seed_summary(request.args.get("price_multiplier"))
        return jsonify({"ok": True, "summary": summary})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market preset preview failed: {exc}"}), 500


@app.route("/api/market-seed-preset", methods=["POST"])
def api_market_seed_preset():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    clear_existing = request.form.get("clear_existing", "0") == "1"
    price_multiplier = market_price_multiplier_from_value(request.form.get("price_multiplier"))
    exchange_id = market_exchange_id_from_value(request.form.get("exchange_id"))

    try:
        output = seed_market_preset(
            clear_existing=clear_existing,
            price_multiplier=price_multiplier,
            exchange_id=exchange_id,
        )
        log_action(
            session["user"],
            f"seeded market preset with {price_multiplier}x prices exchange_id={exchange_id or 'Global'} clear_existing={clear_existing}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market preset seed failed: {exc}"}), 500


@app.route("/api/market-clear-npc", methods=["POST"])
def api_market_clear_npc():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        output = clear_market_npc_listings()
        log_action(session["user"], f"cleared {MARKET_BOT_CLASS} NPC market listings")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market NPC clear failed: {exc}"}), 500


@app.route("/api/market-buy-player-listings", methods=["POST"])
def api_market_buy_player_listings():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    price_multiplier = market_price_multiplier_from_value(request.form.get("price_multiplier"))
    threshold_percent = market_buy_threshold_from_value(request.form.get("threshold_percent"))
    max_buys = market_buy_max_from_value(request.form.get("max_buys"))

    try:
        output = run_buyback_sweep(
            price_multiplier=price_multiplier,
            threshold_percent=threshold_percent,
            max_buys=max_buys,
        )
        log_action(
            session["user"],
            f"{MARKET_BOT_CLASS} bought player listings at {threshold_percent}% threshold using {price_multiplier}x prices, max {max_buys}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market buy failed: {exc}"}), 500


@app.route("/api/market-buyback-status")
def api_market_buyback_status():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    return jsonify({"ok": True, "status": market_buyback_status()})


@app.route("/api/market-buyback-start", methods=["POST"])
def api_market_buyback_start():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    price_multiplier = market_price_multiplier_from_value(request.form.get("price_multiplier"))
    threshold_percent = market_buy_threshold_from_value(request.form.get("threshold_percent"))
    max_buys = market_buy_max_from_value(request.form.get("max_buys"))
    interval_minutes = market_buyback_interval_from_value(request.form.get("interval_minutes"))

    try:
        status = start_market_buyback_sweep(
            price_multiplier=price_multiplier,
            threshold_percent=threshold_percent,
            max_buys=max_buys,
            interval_minutes=interval_minutes,
        )
        log_action(
            session["user"],
            f"started automated {MARKET_BOT_CLASS} buyback every {status['interval_minutes']} minutes at {threshold_percent}% using {price_multiplier}x prices, max {max_buys}",
        )
        return jsonify({"ok": True, "status": status, "output": "Automated buyback sweep started."})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market buyback start failed: {exc}"}), 500


@app.route("/api/market-buyback-stop", methods=["POST"])
def api_market_buyback_stop():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        status = stop_market_buyback_sweep()
        log_action(session["user"], f"stopped automated {MARKET_BOT_CLASS} buyback")
        return jsonify({"ok": True, "status": status, "output": "Automated buyback sweep stopped."})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Market buyback stop failed: {exc}"}), 500



@app.route("/api/infra-command", methods=["POST"])
def api_infra_command():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    if not ENABLE_HOST_COMMAND_RUNNER:
        return jsonify({"ok": False, "error": "host command runner disabled; set ENABLE_HOST_COMMAND_RUNNER=1"}), 403

    command_key = request.form.get("command", "").strip()
    entry = ALLOWED_INFRA_COMMANDS.get(command_key)

    if not entry:
        return jsonify({"ok": False, "error": "unknown command"}), 400

    try:
        output = run_infra_command(entry["cmd"], timeout=entry.get("timeout", 60))
        log_action(session["user"], f"ran infra command {command_key}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Command failed: {exc}"}), 500


@app.route("/api/installer-step", methods=["POST"])
def api_installer_step():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    if not ENABLE_STACK_INSTALLER:
        return jsonify({"ok": False, "error": "stack installer disabled; set ENABLE_STACK_INSTALLER=1"}), 403

    step = request.form.get("step", "").strip()
    entry = installer_step_command(step)

    if not entry:
        return jsonify({"ok": False, "error": "unknown installer step"}), 400

    try:
        if entry.get("custom"):
            output = entry["custom"]()
        else:
            output = run_infra_command(entry["cmd"], timeout=entry.get("timeout", 60))

        log_action(session["user"], f"ran installer step {step}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Installer step failed: {exc}"}), 500




@app.route("/api/dashboard-metrics")
def api_dashboard_metrics():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    return jsonify(build_dashboard_metrics_payload())


@app.route("/api/logs")
def api_logs():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
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


@app.route("/api/grant-lasgun-augment-bundle", methods=["POST"])
def api_grant_lasgun_augment_bundle():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_id = request.form.get("player_id", "").strip()
    if not player_id:
        return jsonify({"ok": False, "error": "missing player/FLS id"}), 400

    outputs = []
    try:
        for item_id, qty in LASGUN_AUGMENT_BUNDLE:
            outputs.append(grant_item(player_id, item_id, qty, "1.0"))

        log_action(session["user"], f"grant lasgun augment bundle to {player_id}")
        return jsonify({"ok": True, "output": "\n\n---\n\n".join(outputs)})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Lasgun bundle grant failed: {exc}"}), 500


@app.route("/api/grant-solari", methods=["POST"])
def api_grant_solari():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_id = request.form.get("player_id", "").strip()
    amount_text = request.form.get("amount", "").strip()

    if not player_id:
        return jsonify({"ok": False, "error": "missing player/FLS id"}), 400

    try:
        amount = int(amount_text)
        if amount not in SOLARIS_GRANT_AMOUNTS:
            return jsonify({"ok": False, "error": "unsupported Solari amount"}), 400

        output = grant_item(player_id, SOLARIS_COIN_ITEM_ID, amount, "1.0")
        log_action(session["user"], f"grant {amount} SolarisCoin to {player_id}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Solari grant failed: {exc}"}), 500


@app.route("/api/set-research-points", methods=["POST"])
def api_set_research_points():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    character_actor_id = request.form.get("character_actor_id", "").strip()
    research_points = request.form.get("research_points", "").strip()

    try:
        sql = build_set_research_points_sql(character_actor_id, research_points)
        output = run_psql(sql, timeout=60)
        log_action(
            session["user"],
            f"set research points actor {character_actor_id} to {research_points}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Research point update failed: {exc}"}), 500


@app.route("/api/give-specialization-xp", methods=["POST"])
def api_give_specialization_xp():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_controller_id = request.form.get("player_controller_id", "").strip()
    track_type = request.form.get("track_type", "").strip()
    xp_amount = request.form.get("xp_amount", "").strip()

    try:
        sql = build_give_specialization_xp_sql(player_controller_id, track_type, xp_amount)
        output = run_psql(sql, timeout=60)
        log_action(
            session["user"],
            f"give {xp_amount} {track_type} XP to controller {player_controller_id}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"XP grant failed: {exc}"}), 500


@app.route("/api/reset-specialization", methods=["POST"])
def api_reset_specialization():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    player_controller_id = request.form.get("player_controller_id", "").strip()
    track_type = request.form.get("track_type", "").strip()

    try:
        sql = build_reset_specialization_sql(player_controller_id, track_type)
        output = run_psql_script(sql, timeout=60)
        log_action(
            session["user"],
            f"reset specialization {track_type} for controller {player_controller_id}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Specialization reset failed: {exc}"}), 500


@app.route("/api/give-character-xp", methods=["POST"])
def api_give_character_xp():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    character_actor_id = request.form.get("character_actor_id", "").strip()
    xp_amount = request.form.get("xp_amount", "").strip()

    try:
        sql = build_give_character_xp_sql(character_actor_id, xp_amount)
        output = run_psql(sql, timeout=60)
        log_action(
            session["user"],
            f"give {xp_amount} character XP to actor {character_actor_id}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Character XP grant failed: {exc}"}), 500


@app.route("/api/set-character-level", methods=["POST"])
def api_set_character_level():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    character_actor_id = request.form.get("character_actor_id", "").strip()
    target_level = request.form.get("target_level", "").strip()

    try:
        sql = build_set_character_level_sql(character_actor_id, target_level)
        output = run_psql(sql, timeout=60)
        log_action(
            session["user"],
            f"set character level actor {character_actor_id} to {target_level}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Character level update failed: {exc}"}), 500


@app.route("/api/progression-preset", methods=["POST"])
def api_progression_preset():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    fls_id = request.form.get("fls_id", "").strip()
    preset_id = request.form.get("preset_id", "").strip()
    action = request.form.get("action", "").strip()

    if not fls_id:
        return jsonify({"ok": False, "error": "missing player/FLS id"}), 400

    try:
        sql = build_progression_preset_sql(fls_id, preset_id, action)
        output = run_psql_script(sql, timeout=90)
        log_action(
            session["user"],
            f"{action} progression preset {preset_id} for {fls_id}",
        )
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Progression preset failed: {exc}"}), 500


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


@app.route("/api/teleportable-vehicles")
def api_teleportable_vehicles():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    return jsonify({"ok": True, "vehicles": get_teleportable_vehicles()})


@app.route("/api/ornithopters")
def api_ornithopters():
    """
    Backward-compatible alias for browsers that still have older admin JS cached.
    New code should use /api/teleportable-vehicles.
    """
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    vehicles = get_teleportable_vehicles()
    return jsonify({"ok": True, "ornithopters": vehicles, "vehicles": vehicles})


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



@app.route("/api/teleport-vehicle", methods=["POST"])
def api_teleport_vehicle():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401

    # Vehicle ownership is not confirmed in the current schema. Even though
    # dune.actors has owner_account_id, observed vehicle rows may be null,
    # so this tool remains admin-only and must not be exposed to operators/VIPs.
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    actor_id = request.form.get("actor_id", "").strip()
    map_key = request.form.get("map_key", DEFAULT_MAP_KEY).strip()
    map_cfg = MAP_CONFIGS.get(map_key, MAP_CONFIGS[DEFAULT_MAP_KEY])
    partition_id = request.form.get("partition_id", str(map_cfg.get("default_partition_id", ""))).strip()
    x = request.form.get("x", "0").strip()
    y = request.form.get("y", "0").strip()
    z = request.form.get("z", "1000").strip()

    if not actor_id:
        return jsonify({"ok": False, "error": "missing vehicle actor ID"}), 400

    if not partition_id:
        return jsonify({"ok": False, "error": "missing partition ID"}), 400

    try:
        actor = get_teleportable_vehicle_actor(actor_id)
        sql = build_vehicle_teleport_sql(
            actor_id,
            actor["transform"],
            map_cfg["key"],
            partition_id,
            x,
            y,
            z,
        )
        output = run_psql(sql, timeout=60)

        log_action(
            session["user"],
            f"teleport vehicle actor {actor_id} map {map_cfg['key']} partition {partition_id} to ({x}, {y}, {z})",
        )

        return jsonify({"ok": True, "output": output})

    except Exception as exc:
        return jsonify({"ok": False, "error": f"Vehicle teleport failed: {exc}"}), 500


@app.route("/api/teleport-ornithopter", methods=["POST"])
def api_teleport_ornithopter():
    """
    Backward-compatible alias for cached admin pages from the thopter-only build.
    New code should use /api/teleport-vehicle.
    """
    return api_teleport_vehicle()


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

    if target in INFRASTRUCTURE_RESTART_TARGETS and not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        output = run_command([str(DUNE_SCRIPT), "restart", target], timeout=180)
        log_action(session["user"], f"restart target {target}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Restart failed: {exc}"}), 500



@app.route("/api/restart-map", methods=["POST"])
def api_restart_map():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    map_name = request.form.get("map_name", "").strip()
    allowed_maps = {"DeepDesert_1", "SH_Arrakeen", "SH_HarkoVillage"}

    if map_name not in allowed_maps:
        return jsonify({"ok": False, "error": "map restart not allowed"}), 400

    try:
        stop_output = run_command([str(DUNE_SCRIPT), "despawn", map_name, "--force"], timeout=180)
        start_output = run_command([str(DUNE_SCRIPT), "spawn", map_name], timeout=300)
        log_action(session["user"], f"restart map {map_name}")
        return jsonify({
            "ok": True,
            "output": "DESPAWN OUTPUT:\\n" + stop_output + "\\n\\nSPAWN OUTPUT:\\n" + start_output
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Map restart failed: {exc}"}), 500


@app.route("/api/db-command", methods=["POST"])
def api_db_command():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    action = request.form.get("action", "").strip()

    allowed = {
        "health": [str(DUNE_SCRIPT), "db", "health"],
        "status": [str(DUNE_SCRIPT), "db", "status"],
        "list": [str(DUNE_SCRIPT), "db", "list"],
        "backup": [str(DUNE_SCRIPT), "db", "backup"],
    }

    cmd = allowed.get(action)
    if not cmd:
        return jsonify({"ok": False, "error": "invalid database action"}), 400

    try:
        output = run_command(cmd, timeout=600)
        log_action(session["user"], f"dune db {action}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Database command failed: {exc}"}), 500



@app.route("/api/maps-list", methods=["POST"])
def api_maps_list():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        output = run_command([str(DUNE_SCRIPT), "maps", "list"], timeout=60)
        log_action(session["user"], "dune maps list")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Map list failed: {exc}"}), 500


@app.route("/api/maps-mode", methods=["POST"])
def api_maps_mode():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    map_name = request.form.get("map_name", "").strip()

    try:
        cmd = [str(DUNE_SCRIPT), "maps", "mode"]
        if map_name:
            cmd.append(map_name)
        output = run_command(cmd, timeout=60)
        log_action(session["user"], f"dune maps mode {map_name or 'all'}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Map mode failed: {exc}"}), 500


@app.route("/api/maps-set-mode", methods=["POST"])
def api_maps_set_mode():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    map_name = request.form.get("map_name", "").strip()
    mode = request.form.get("mode", "").strip()

    if not map_name:
        return jsonify({"ok": False, "error": "missing map name"}), 400

    if mode not in ("dynamic", "always-on"):
        return jsonify({"ok": False, "error": "invalid map mode"}), 400

    try:
        output = run_command([str(DUNE_SCRIPT), "maps", "set", map_name, mode], timeout=120)
        log_action(session["user"], f"dune maps set {map_name} {mode}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Map set failed: {exc}"}), 500


@app.route("/api/maps-reconcile", methods=["POST"])
def api_maps_reconcile():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    try:
        output = run_command([str(DUNE_SCRIPT), "maps", "reconcile"], timeout=180)
        log_action(session["user"], "dune maps reconcile")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Map reconcile failed: {exc}"}), 500


@app.route("/api/deepdesert-dual", methods=["POST"])
def api_deepdesert_dual():
    if not logged_in():
        return jsonify({"ok": False, "error": "not logged in"}), 401
    if not is_operator_or_admin():
        return jsonify({"ok": False, "error": "permission denied"}), 403

    action = request.form.get("action", "").strip()

    allowed = {
        "status": [str(DUNE_SCRIPT), "deepdesert", "dual", "status"],
        "enable": [str(DUNE_SCRIPT), "deepdesert", "dual", "enable", "--yes"],
        "disable": [str(DUNE_SCRIPT), "deepdesert", "dual", "disable", "--yes"],
        "disable_force": [str(DUNE_SCRIPT), "deepdesert", "dual", "disable", "--force", "--yes"],
        "bootstrap": [str(DUNE_SCRIPT), "deepdesert", "dual", "bootstrap", "--yes"],
        "repair": [str(DUNE_SCRIPT), "deepdesert", "dual", "repair"],
    }

    cmd = allowed.get(action)
    if not cmd:
        return jsonify({"ok": False, "error": "invalid Deep Desert dual action"}), 400

    try:
        output = run_command(cmd, timeout=300)
        log_action(session["user"], f"dune deepdesert dual {action}")
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Deep Desert dual command failed: {exc}"}), 500




# =========================================================
# SOCKET.IO HOST SHELL
# =========================================================

@socketio.on("connect")
def socket_connect():
    if not logged_in() or not is_admin() or not ENABLE_HOST_SHELL:
        disconnect()
        return False

    emit("shell_output", {"data": "[connected to host shell]\n"})


@socketio.on("shell_start")
def socket_shell_start():
    if not logged_in() or not is_admin() or not ENABLE_HOST_SHELL:
        disconnect()
        return

    log_action(session.get("user", "unknown"), "started host shell session")
    start_shell_session(request.sid)


@socketio.on("shell_input")
def socket_shell_input(message):
    if not logged_in() or not is_admin() or not ENABLE_HOST_SHELL:
        disconnect()
        return

    session_obj = SHELL_SESSIONS.get(request.sid)
    if not session_obj:
        return

    data = message.get("data", "")
    os.write(session_obj["fd"], data.encode())


@socketio.on("shell_resize")
def socket_shell_resize(message):
    if not logged_in() or not is_admin() or not ENABLE_HOST_SHELL:
        disconnect()
        return

    session_obj = SHELL_SESSIONS.get(request.sid)
    if not session_obj:
        return

    try:
        rows = int(message.get("rows", 24))
        cols = int(message.get("cols", 80))
        rows = max(10, min(rows, 200))
        cols = max(40, min(cols, 400))

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(session_obj["fd"], termios.TIOCSWINSZ, winsize)
    except Exception:
        return


@socketio.on("disconnect")
def socket_disconnect():
    stop_shell_session(request.sid)
