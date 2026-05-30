"""
Market preset seeding helpers.

This module is a Python-native, admin-only market seeding tool inspired by
IceHunter / Ryan Wilson's MIT-licensed dune-admin marketbot. We reuse the
confirmed market category mask mapping and exchange insert shape with
attribution, while keeping this implementation small and button-driven for
this webadmin.
"""

import json
from pathlib import Path


KNOWN_CODES = {
    1: {"garment": 0, "weapons": 1, "vehicles": 2, "utility": 3, "augment": 4, "misc": 5},
    2: {
        "lightarmor": 0, "heavyarmor": 1, "stillsuits": 2, "utilitywearables": 3,
        "socialwearables": 4, "pistol": 2, "heavypistol": 3, "heavyrifle": 4,
        "smg": 5, "spitdart": 6, "shotgun": 7, "battlerifle": 8,
        "heavyshotgun": 9, "missilelauncher": 10, "flamethrower": 11,
        "fireballer": 12, "lasgun": 13, "ammunition": 14, "sandbike": 0,
        "buggy": 1, "lightornithopter": 2, "mediumornithopter": 3,
        "transportornithopter": 4, "sandcrawler": 5, "buildingtools": 0,
        "hydrationtools": 2, "gatheringtools": 3, "cartographytools": 4,
        "utilitytools": 5, "consumables": 6, "armor": 0, "melee": 1,
        "ranged": 2, "fuel": 0, "refinedresources": 1, "components": 2,
        "rawresources": 3,
    },
}

DEPTH3_PARENT_CODES = {
    ("lightarmor", "head"): 0, ("lightarmor", "chest"): 1,
    ("lightarmor", "hands"): 2, ("lightarmor", "legs"): 3,
    ("lightarmor", "feet"): 4, ("heavyarmor", "head"): 0,
    ("heavyarmor", "chest"): 1, ("heavyarmor", "hands"): 2,
    ("heavyarmor", "legs"): 3, ("heavyarmor", "feet"): 4,
    ("stillsuits", "head"): 0, ("stillsuits", "chest"): 1,
    ("stillsuits", "hands"): 2, ("stillsuits", "legs"): 3,
    ("stillsuits", "feet"): 4, ("utilitywearables", "head"): 0,
    ("utilitywearables", "chest"): 1, ("utilitywearables", "hands"): 2,
    ("utilitywearables", "legs"): 3, ("utilitywearables", "feet"): 4,
    ("socialwearables", "head"): 0, ("socialwearables", "chest"): 1,
    ("socialwearables", "hands"): 2, ("socialwearables", "legs"): 3,
    ("socialwearables", "feet"): 4, ("sandbike", "chassis"): 0,
    ("sandbike", "engine"): 1, ("sandbike", "tread"): 2,
    ("sandbike", "utility"): 3, ("buggy", "chassis"): 0,
    ("buggy", "engine"): 1, ("buggy", "tread"): 2,
    ("buggy", "utility"): 3, ("lightornithopter", "chassis"): 0,
    ("lightornithopter", "engine"): 1, ("lightornithopter", "utility"): 2,
    ("mediumornithopter", "chassis"): 0, ("mediumornithopter", "engine"): 1,
    ("mediumornithopter", "utility"): 2, ("transportornithopter", "chassis"): 0,
    ("transportornithopter", "engine"): 1, ("transportornithopter", "utility"): 2,
    ("sandcrawler", "chassis"): 0, ("sandcrawler", "engine"): 1,
    ("sandcrawler", "utility"): 2, ("hydrationtools", "watertools"): 0,
    ("hydrationtools", "bloodtools"): 1, ("gatheringtools", "cutteray"): 0,
    ("gatheringtools", "miningtools"): 1, ("utilitytools", "powerpack"): 0,
    ("utilitytools", "scanner"): 1, ("utilitytools", "suspensor"): 2,
    ("utilitytools", "shields"): 3, ("utilitytools", "solido"): 4,
    ("consumables", "medical"): 0, ("consumables", "food"): 1,
    ("consumables", "drink"): 2,
}

WEAPON_REMAP = {"shortblades": (1, 0), "longblades": (1, 1)}

UNIQUE_SCHEMATIC_DEPTH2 = {"garment": 5, "weapons": 3, "vehicles": 6, "utility": 7, "augment": 4}
UNIQUE_SCHEMATIC_DEPTH3 = {
    "lightarmor": 0, "heavyarmor": 1, "stillsuits": 2, "utilitywearables": 3,
    "socialwearables": 4, "shortblades": 0, "longblades": 1, "pistol": 2,
    "heavypistol": 3, "heavyrifle": 4, "smg": 5, "spitdart": 6,
    "shotgun": 7, "battlerifle": 8, "heavyshotgun": 9, "missilelauncher": 10,
    "flamethrower": 11, "fireballer": 12, "lasgun": 13, "sandbike": 0,
    "buggy": 1, "lightornithopter": 2, "mediumornithopter": 3,
    "transportornithopter": 4, "sandcrawler": 5, "buildingtools": 0,
    "hydrationtools": 2, "gatheringtools": 3, "cartographytools": 4,
    "utilitytools": 5, "armor": 0, "melee": 1, "ranged": 2,
}


def load_item_data(path):
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("items", {})


def rarity_multiplier(rarity):
    return {"common": 1.0, "rare": 5.0, "unique": 5.0, "memento": 2.0}.get((rarity or "common").casefold(), 1.0)


def equipment_price(tier):
    return {1: 2000, 2: 8000, 3: 30000, 4: 100000, 5: 300000, 6: 750000}.get(int(tier or 0), 500)


def schematic_price(tier):
    return {1: 500, 2: 1500, 3: 4000, 4: 12000, 5: 30000, 6: 75000}.get(int(tier or 0), 500)


def material_unit_price(tier):
    return {1: 20, 2: 80, 3: 200, 4: 600, 5: 1500, 6: 4000}.get(int(tier or 0), 5)


def round_price(value):
    value = int(round(value))
    if value >= 1_000_000:
        step = 100_000
    elif value >= 100_000:
        step = 10_000
    elif value >= 10_000:
        step = 1_000
    elif value >= 1_000:
        step = 100
    else:
        step = 10
    return int(round(value / step) * step)


def base_price(item):
    tier = int(item.get("tier") or 0)
    rarity = item.get("rarity") or "common"
    stack_max = int(item.get("stack_max") or 1)
    vendor_price = int(item.get("vendor_price") or 0)
    material_cost = int(item.get("material_cost") or 0)
    is_schematic = bool(item.get("is_schematic"))

    if material_cost > 0 and stack_max <= 1 and not is_schematic and rarity.casefold() in ("unique", "memento"):
        return int(round(schematic_price(tier) * rarity_multiplier(rarity) + material_cost * 0.75))
    if vendor_price >= 10:
        return int(round(vendor_price * rarity_multiplier(rarity)))
    if stack_max <= 1:
        price = schematic_price(tier) if is_schematic else equipment_price(tier)
        return int(round(price * rarity_multiplier(rarity)))
    return max(1, int(round(material_unit_price(tier) * rarity_multiplier(rarity))))


def category_price_multiplier(
    item,
    template_id,
    refined_resource_multiplier=1.0,
    raw_resource_multiplier=1.0,
    raw_resource_overrides=None,
):
    category = item.get("category") or ""
    if category == "items/misc/rawresources":
        overrides = raw_resource_overrides or {}
        return float(overrides.get(template_id, raw_resource_multiplier))
    if category == "items/misc/refinedresources":
        return float(refined_resource_multiplier)
    return 1.0


def list_price(
    item,
    template_id,
    price_multiplier,
    refined_resource_multiplier=1.0,
    raw_resource_multiplier=1.0,
    raw_resource_overrides=None,
):
    price = round_price(base_price(item))
    min_price = int(item.get("min_price") or 0)
    max_price = int(item.get("max_price") or 0)
    if min_price and price < min_price:
        price = min_price
    if max_price and price > max_price:
        price = max_price
    category_multiplier = category_price_multiplier(
        item,
        template_id,
        refined_resource_multiplier,
        raw_resource_multiplier,
        raw_resource_overrides,
    )
    return max(1, round_price(price * int(price_multiplier) * category_multiplier))


def segment_index(items):
    index = {1: [], 2: [], 3: []}
    for item in items.values():
        parts = (item.get("category") or "").split("/")
        for depth in range(1, min(len(parts), 4)):
            if parts[depth] not in index[depth]:
                index[depth].append(parts[depth])
    for values in index.values():
        values.sort()
    return index


def unique_schematic_mask(category):
    parts = (category or "").split("/")
    if len(parts) < 3 or parts[0] != "items":
        return 0, 0, False
    d1_code = KNOWN_CODES[1].get(parts[1])
    d2_code = UNIQUE_SCHEMATIC_DEPTH2.get(parts[1])
    d3_code = UNIQUE_SCHEMATIC_DEPTH3.get(parts[2])
    if d3_code is None and len(parts) >= 4:
        d3_code = UNIQUE_SCHEMATIC_DEPTH3.get(parts[3])
    if d1_code is None or d2_code is None or d3_code is None:
        return 0, 0, False
    return (d1_code << 24) | (d2_code << 16) | (d3_code << 8), 3, True


def category_mask(category, index):
    parts = (category or "").split("/")[:4]
    if not parts or not parts[0]:
        return 0, 0
    if len(parts) >= 3 and parts[1] == "weapons" and parts[2] in WEAPON_REMAP:
        d2_code, d3_code = WEAPON_REMAP[parts[2]]
        return (KNOWN_CODES[1]["weapons"] << 24) | (d2_code << 16) | (d3_code << 8), 3

    mask = 0
    for depth in range(1, len(parts)):
        segment = parts[depth]
        code = None
        if depth == 3 and len(parts) >= 3:
            code = DEPTH3_PARENT_CODES.get((parts[2], segment))
        if code is None:
            code = KNOWN_CODES.get(depth, {}).get(segment)
        if code is None:
            code = index.get(depth, []).index(segment) + 1 if segment in index.get(depth, []) else 0
        mask |= int(code) << ((4 - depth) * 8)
    return mask, max(0, len(parts) - 1)


def tradeable(item):
    category = item.get("category") or ""
    return not (
        item.get("tradeable") is False
        or not category
        or category.startswith("items/customization/")
        or category.startswith("items/construction/")
    )


def preset_kind(item):
    category = item.get("category") or ""
    stack_max = int(item.get("stack_max") or 1)
    if item.get("is_schematic"):
        return "schematic"
    if stack_max > 1 and category.startswith("items/misc/"):
        return "resource"
    if stack_max <= 1 and category.startswith(("items/garment/", "items/weapons/", "items/vehicles/", "items/utility/", "items/augment/")):
        return "equippable"
    return ""


def matches_special_name(item, template_id, special_name_terms):
    haystack = f"{template_id} {item.get('name') or ''}".casefold()
    return any(term and term in haystack for term in special_name_terms or [])


def build_seed_plan(
    item_data_path,
    price_multiplier,
    equippable_listings,
    schematic_listings,
    resource_stack_size,
    special_name_terms=None,
    special_name_listings=8,
    refined_resource_multiplier=1.0,
    raw_resource_multiplier=1.0,
    raw_resource_overrides=None,
):
    items = load_item_data(item_data_path)
    index = segment_index(items)
    plan = []
    for template_id, item in items.items():
        if template_id.startswith("Emote_") or not tradeable(item):
            continue
        kind = preset_kind(item)
        if not kind:
            continue

        category = item.get("category") or ""
        if item.get("is_schematic"):
            mask, depth, ok = unique_schematic_mask(category)
            if not ok:
                mask, depth = category_mask(category, index)
            listings = schematic_listings
            stack_size = 1
        elif kind == "resource":
            mask, depth = category_mask(category, index)
            listings = 1
            stack_size = resource_stack_size
        else:
            mask, depth = category_mask(category, index)
            listings = equippable_listings
            stack_size = 1

        special_boost = kind != "resource" and matches_special_name(item, template_id, special_name_terms)
        if special_boost:
            listings = max(int(listings), int(special_name_listings))

        for _ in range(max(1, int(listings))):
            plan.append({
                "template_id": template_id,
                "display_name": item.get("name") or template_id,
                "kind": kind,
                "special_boost": special_boost,
                "stack_size": int(stack_size),
                "price": list_price(
                    item,
                    template_id,
                    price_multiplier,
                    refined_resource_multiplier,
                    raw_resource_multiplier,
                    raw_resource_overrides,
                ),
                "category_mask": int(mask),
                "category_depth": int(depth),
                "quality_level": int(item.get("min_quality_level") or 0),
            })
    plan.sort(key=lambda row: (row["kind"], row["display_name"].casefold(), row["template_id"]))
    return plan


def summary(plan, price_multiplier):
    result = {
        "listings": len(plan),
        "equippable_listings": 0,
        "schematic_listings": 0,
        "resource_listings": 0,
        "resource_units": 0,
        "special_boosted_listings": 0,
        "price_multiplier": int(price_multiplier),
    }
    for row in plan:
        result[f"{row['kind']}_listings"] += 1
        if row.get("special_boost"):
            result["special_boosted_listings"] += 1
        if row["kind"] == "resource":
            result["resource_units"] += row["stack_size"]
    return result


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def build_seed_sql(plan, bot_class, price_multiplier, clear_existing=True, exchange_id_override=None):
    values = []
    for row in plan:
        values.append("(" + ",".join([
            sql_literal(row["template_id"]),
            str(row["stack_size"]),
            str(row["price"]),
            str(row["category_mask"]),
            str(row["category_depth"]),
            str(row["quality_level"]),
            sql_literal(row["kind"]),
        ]) + ")")
    values_sql = ",\n".join(values)

    clear_sql = ""
    if clear_existing:
        clear_sql = f"""
DO $$
DECLARE
    v_owner_id BIGINT;
    v_item_ids BIGINT[];
BEGIN
    SELECT id INTO v_owner_id FROM dune.actors WHERE class = {sql_literal(bot_class)} LIMIT 1;
    IF v_owner_id IS NOT NULL THEN
        SELECT ARRAY_AGG(item_id) INTO v_item_ids
        FROM dune.dune_exchange_orders
        WHERE owner_id = v_owner_id AND is_npc_order = TRUE AND item_id IS NOT NULL;

        DELETE FROM dune.dune_exchange_sell_orders
        WHERE order_id IN (
            SELECT id FROM dune.dune_exchange_orders
            WHERE owner_id = v_owner_id AND is_npc_order = TRUE
        );

        DELETE FROM dune.dune_exchange_orders
        WHERE owner_id = v_owner_id AND is_npc_order = TRUE;

        IF v_item_ids IS NOT NULL THEN
            DELETE FROM dune.items WHERE id = ANY(v_item_ids);
        END IF;
    END IF;
END $$;
"""

    if exchange_id_override:
        exchange_sql = f"v_exchange_id := {int(exchange_id_override)};"
    else:
        exchange_sql = "SELECT dune.get_dune_exchange_id('Global') INTO v_exchange_id;"

    return f"""
BEGIN;

CREATE TEMP TABLE market_seed_plan (
    template_id TEXT NOT NULL,
    stack_size BIGINT NOT NULL,
    item_price BIGINT NOT NULL,
    category_mask INTEGER NOT NULL,
    category_depth SMALLINT NOT NULL,
    quality_level BIGINT NOT NULL,
    seed_kind TEXT NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE market_seed_result (
    status TEXT NOT NULL,
    exchange_id BIGINT NOT NULL,
    access_point_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    inventory_id BIGINT NOT NULL
) ON COMMIT DROP;

INSERT INTO market_seed_plan
    (template_id, stack_size, item_price, category_mask, category_depth, quality_level, seed_kind)
VALUES
{values_sql};

{clear_sql}

DO $$
DECLARE
    v_exchange_id BIGINT;
    v_access_point_id BIGINT;
    v_inventory_id BIGINT;
    v_owner_id BIGINT;
    v_user_id BIGINT;
    v_partition_id BIGINT;
    v_next_position BIGINT;
    v_expiration_time BIGINT;
    v_item_id BIGINT;
    v_order_id BIGINT;
    rec RECORD;
BEGIN
    -- Most stacks use the game's Global exchange function. Some self-hosted
    -- stacks expose the player-visible exchange under another id; the admin UI
    -- can pass an explicit override for those servers.
    {exchange_sql}

    SELECT COALESCE(
        (SELECT access_point_id FROM dune.dune_exchange_orders WHERE exchange_id = v_exchange_id LIMIT 1),
        1
    ) INTO v_access_point_id;

    SELECT dune.get_exchange_inventory_id(v_exchange_id) INTO v_inventory_id;

    SELECT id INTO v_owner_id FROM dune.actors WHERE class = {sql_literal(bot_class)} LIMIT 1;
    IF v_owner_id IS NULL THEN
        SELECT partition_id INTO v_partition_id FROM dune.world_partition ORDER BY partition_id LIMIT 1;
        INSERT INTO dune.actors (class, serial, gas_attributes, properties, dimension_index, partition_id)
        VALUES ({sql_literal(bot_class)}, 0, '{{}}', '{{}}', 0, v_partition_id)
        RETURNING id INTO v_owner_id;
    END IF;

    SELECT dune.dune_exchange_get_user_id(v_owner_id) INTO v_user_id;
    PERFORM dune.dune_exchange_modify_user_solari_balance(
        v_owner_id,
        GREATEST(0, 9000000000000 - COALESCE(dune.dune_exchange_retrieve_solari_balance(v_owner_id), 0))
    );

    INSERT INTO dune.dune_exchange_categories_hash (id, hash)
    VALUES (1, 0)
    ON CONFLICT (id) DO UPDATE SET hash = 0;

    SELECT COALESCE(MAX(position_index), -1) + 1 INTO v_next_position
    FROM dune.items
    WHERE inventory_id = v_inventory_id;

    SELECT COALESCE(MAX(expiration_time) + 604800, 999999999) INTO v_expiration_time
    FROM dune.dune_exchange_orders;

    FOR rec IN SELECT * FROM market_seed_plan ORDER BY seed_kind, template_id LOOP
        INSERT INTO dune.items (inventory_id, stack_size, position_index, template_id, quality_level, stats)
        VALUES (v_inventory_id, rec.stack_size, v_next_position, rec.template_id, rec.quality_level, '{{}}')
        RETURNING id INTO v_item_id;

        v_next_position := v_next_position + 1;

        INSERT INTO dune.dune_exchange_orders
            (exchange_id, access_point_id, owner_id, is_npc_order, expiration_time,
             template_id, durability_cur, durability_max, category_mask, category_depth,
             item_price, quality_level, item_id)
        VALUES
            (v_exchange_id, v_access_point_id, v_owner_id, TRUE, v_expiration_time,
             rec.template_id, 1.0, 1.0, rec.category_mask, rec.category_depth,
             rec.item_price, rec.quality_level, v_item_id)
        RETURNING id INTO v_order_id;

        INSERT INTO dune.dune_exchange_sell_orders (order_id, initial_stack_size, wear_normalized_price)
        VALUES (v_order_id, rec.stack_size, rec.item_price);
    END LOOP;

    INSERT INTO market_seed_result
        (status, exchange_id, access_point_id, owner_id, inventory_id)
    VALUES
        ('seeded', v_exchange_id, v_access_point_id, v_owner_id, v_inventory_id);
END $$;

SELECT
    r.status,
    r.exchange_id,
    r.access_point_id,
    r.owner_id,
    r.inventory_id,
    COUNT(*) AS listing_count,
    COUNT(*) FILTER (WHERE seed_kind = 'equippable') AS equippable_listings,
    COUNT(*) FILTER (WHERE seed_kind = 'schematic') AS schematic_listings,
    COUNT(*) FILTER (WHERE seed_kind = 'resource') AS resource_listings,
    SUM(CASE WHEN seed_kind = 'resource' THEN stack_size ELSE 0 END) AS resource_units,
    {int(price_multiplier)} AS price_multiplier
FROM market_seed_plan
CROSS JOIN market_seed_result r
GROUP BY r.status, r.exchange_id, r.access_point_id, r.owner_id, r.inventory_id;

COMMIT;
"""


def build_buy_player_listings_sql(plan, bot_class, threshold_percent=60, max_buys=500):
    price_by_template = {}
    for row in plan:
        template_id = row["template_id"]
        price_by_template[template_id] = max(price_by_template.get(template_id, 0), int(row["price"]))

    threshold = max(1, min(100, int(threshold_percent)))
    values = []
    for template_id, list_price_value in sorted(price_by_template.items()):
        # Buyback thresholds must be exact. Do not use round_price() here:
        # cosmetic market rounding can turn 60% of 170,000 into 100,000,
        # causing legitimate 101,999 listings to be skipped.
        max_buy_price = max(1, (int(list_price_value) * threshold + 99) // 100)
        values.append("(" + ",".join([
            sql_literal(template_id),
            str(int(max_buy_price)),
        ]) + ")")
    values_sql = ",\n".join(values)

    return f"""
BEGIN;

CREATE TEMP TABLE market_buy_plan (
    template_id TEXT PRIMARY KEY,
    max_unit_price BIGINT NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE market_buy_result (
    purchased INTEGER NOT NULL,
    total_units BIGINT NOT NULL,
    total_solari BIGINT NOT NULL,
    threshold_percent INTEGER NOT NULL,
    max_buys INTEGER NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE market_buy_diagnostics (
    player_sell_orders BIGINT NOT NULL,
    known_player_sell_orders BIGINT NOT NULL,
    eligible_player_sell_orders BIGINT NOT NULL,
    above_threshold_sell_orders BIGINT NOT NULL,
    unknown_template_sell_orders BIGINT NOT NULL
) ON COMMIT DROP;

INSERT INTO market_buy_plan (template_id, max_unit_price)
VALUES
{values_sql};

DO $$
DECLARE
    v_owner_id BIGINT;
    v_user_id BIGINT;
    v_partition_id BIGINT;
    v_expiration_time BIGINT;
    v_log_order_id BIGINT;
    v_purchased INTEGER := 0;
    v_units BIGINT := 0;
    v_solari BIGINT := 0;
    rec RECORD;
BEGIN
    SELECT id INTO v_owner_id FROM dune.actors WHERE class = {sql_literal(bot_class)} LIMIT 1;
    IF v_owner_id IS NULL THEN
        SELECT partition_id INTO v_partition_id FROM dune.world_partition ORDER BY partition_id LIMIT 1;
        INSERT INTO dune.actors (class, serial, gas_attributes, properties, dimension_index, partition_id)
        VALUES ({sql_literal(bot_class)}, 0, '{{}}', '{{}}', 0, v_partition_id)
        RETURNING id INTO v_owner_id;
    END IF;

    SELECT dune.dune_exchange_get_user_id(v_owner_id) INTO v_user_id;
    PERFORM dune.dune_exchange_modify_user_solari_balance(
        v_owner_id,
        GREATEST(0, 9000000000000 - COALESCE(dune.dune_exchange_retrieve_solari_balance(v_owner_id), 0))
    );

    SELECT COALESCE(MAX(expiration_time) + 604800, 999999999) INTO v_expiration_time
    FROM dune.dune_exchange_orders;

    INSERT INTO market_buy_diagnostics
    SELECT
        COUNT(*) AS player_sell_orders,
        COUNT(*) FILTER (WHERE p.template_id IS NOT NULL) AS known_player_sell_orders,
        COUNT(*) FILTER (WHERE p.template_id IS NOT NULL AND o.item_price <= p.max_unit_price) AS eligible_player_sell_orders,
        COUNT(*) FILTER (WHERE p.template_id IS NOT NULL AND o.item_price > p.max_unit_price) AS above_threshold_sell_orders,
        COUNT(*) FILTER (WHERE p.template_id IS NULL) AS unknown_template_sell_orders
    FROM dune.dune_exchange_orders o
    JOIN dune.dune_exchange_sell_orders s
        ON s.order_id = o.id
    LEFT JOIN market_buy_plan p
        ON p.template_id = o.template_id
    WHERE o.is_npc_order = FALSE
      AND o.owner_id <> v_owner_id;

    FOR rec IN
        SELECT
            o.id AS order_id,
            o.exchange_id,
            o.access_point_id,
            o.owner_id AS seller_actor_id,
            o.template_id,
            o.item_price,
            o.item_id,
            COALESCE(i.stack_size, s.initial_stack_size, 1) AS actual_stack,
            p.max_unit_price
        FROM dune.dune_exchange_orders o
        JOIN dune.dune_exchange_sell_orders s
            ON s.order_id = o.id
        JOIN market_buy_plan p
            ON p.template_id = o.template_id
        LEFT JOIN dune.items i
            ON i.id = o.item_id
        WHERE o.is_npc_order = FALSE
          AND o.owner_id <> v_owner_id
          AND o.item_price <= p.max_unit_price
        ORDER BY o.item_price ASC, o.id ASC
        LIMIT {int(max_buys)}
    LOOP
        INSERT INTO dune.dune_exchange_orders
            (exchange_id, access_point_id, owner_id, template_id, expiration_time,
             durability_cur, durability_max, item_price, category_mask, category_depth, is_npc_order)
        VALUES
            (rec.exchange_id, rec.access_point_id, rec.seller_actor_id, rec.template_id, v_expiration_time,
             1.0, 1.0, rec.item_price, 0, 0, FALSE)
        RETURNING id INTO v_log_order_id;

        INSERT INTO dune.dune_exchange_fulfilled_orders
            (order_id, source_order_id, completion_type, stack_size, original_order_id)
        VALUES
            (v_log_order_id, NULL, 4, rec.actual_stack, rec.order_id);

        UPDATE dune.dune_exchange_users
        SET solari_balance = solari_balance - (rec.item_price * rec.actual_stack)
        WHERE owner_id = v_owner_id;

        DELETE FROM dune.dune_exchange_sell_orders WHERE order_id = rec.order_id;
        DELETE FROM dune.dune_exchange_orders WHERE id = rec.order_id;

        IF rec.item_id IS NOT NULL THEN
            DELETE FROM dune.items WHERE id = rec.item_id;
        END IF;

        v_purchased := v_purchased + 1;
        v_units := v_units + rec.actual_stack;
        v_solari := v_solari + (rec.item_price * rec.actual_stack);
    END LOOP;

    INSERT INTO market_buy_result
        (purchased, total_units, total_solari, threshold_percent, max_buys)
    VALUES
        (v_purchased, v_units, v_solari, {threshold}, {int(max_buys)});
END $$;

SELECT
    purchased,
    total_units,
    total_solari,
    threshold_percent,
    max_buys
FROM market_buy_result;

SELECT
    player_sell_orders,
    known_player_sell_orders,
    eligible_player_sell_orders,
    above_threshold_sell_orders,
    unknown_template_sell_orders
FROM market_buy_diagnostics;

SELECT
    o.id AS order_id,
    o.template_id,
    o.item_price,
    p.max_unit_price,
    CASE
        WHEN p.template_id IS NULL THEN 'unknown_template'
        WHEN o.item_price > p.max_unit_price THEN 'above_threshold'
        ELSE 'eligible'
    END AS buyback_status,
    COALESCE(i.stack_size, s.initial_stack_size, 1) AS stack_size
FROM dune.dune_exchange_orders o
JOIN dune.dune_exchange_sell_orders s
    ON s.order_id = o.id
LEFT JOIN market_buy_plan p
    ON p.template_id = o.template_id
LEFT JOIN dune.items i
    ON i.id = o.item_id
WHERE o.is_npc_order = FALSE
ORDER BY
    CASE
        WHEN p.template_id IS NULL THEN 0
        WHEN o.item_price > p.max_unit_price THEN 1
        ELSE 2
    END,
    o.id
LIMIT 20;

COMMIT;
"""
