let latestCharacters = [];

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function showOutput(text) {
    const output = document.getElementById("actionOutput");
    if (!output) return;
    output.style.display = "block";
    output.textContent = text;
}

async function postForm(endpoint, form) {
    const data = new FormData(form);

    const response = await fetch(endpoint, {
        method: "POST",
        body: data
    });

    const json = await response.json();

    if (!json.ok) {
        showOutput(json.error || "Action failed.");
        return;
    }

    showOutput(json.output || "Action completed.");
}

function wireAjaxForms() {
    document.querySelectorAll(".ajaxForm").forEach(form => {
        form.addEventListener("submit", async function(event) {
            event.preventDefault();
            await postForm(form.dataset.endpoint, form);
        });
    });
}

async function refreshLogs() {
    const panel = document.getElementById("logOutput");
    if (!panel) return;

    const response = await fetch("/api/logs");
    const data = await response.json();

    if (!data.ok) {
        panel.textContent = data.error || "Unable to refresh logs.";
        return;
    }

    panel.textContent = data.lines.join("\n");
}

async function fetchCharacters(includeOffline = true) {
    const response = await fetch(`/api/characters?include_offline=${includeOffline ? "1" : "0"}`);
    const data = await response.json();
    latestCharacters = data.characters || [];
    return latestCharacters;
}

function characterLabel(c, includeIds = true) {
    const status = c.online_status || "Unknown";
    const name = c.character_name || "Unknown";
    if (!includeIds || !c.fls_id) {
        return `[${status}] ${name}`;
    }
    return `[${status}] ${name} | FLS ${c.fls_id} | Actor ${c.character_actor_id || ""} | Inv ${c.inventory_id || ""}`;
}

function fillCharacterSelect(selectId, characters, includeIds = true) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = `<option value="">Select a character...</option>`;

    characters.forEach((c, index) => {
        const opt = document.createElement("option");
        opt.value = String(index);
        opt.textContent = characterLabel(c, includeIds);
        select.appendChild(opt);
    });
}

async function refreshOnlinePlayers() {
    const panel = document.getElementById("onlinePlayers");
    if (!panel) return;

    try {
        const response = await fetch("/api/online-players");
        const data = await response.json();

        const players = data.players || [];

        if (players.length === 0) {
            panel.innerHTML = "No players online.";
            return;
        }

        panel.innerHTML = players.map(player => {
            const idBlock =
                (player.fls_id || player.funcom_id)
                ? `
                    <br>
                    FLS: ${escapeHtml(player.fls_id || "")}
                    <br>
                    Funcom: ${escapeHtml(player.funcom_id || "")}
                    <br>
                    Actor: ${escapeHtml(player.character_actor_id || "")}
                    <br>
                    Inventory: ${escapeHtml(player.inventory_id || "")}
                  `
                : "";

            return `
                <div class="player">
                    <b>${escapeHtml(player.character_name || "")}</b><br>
                    Status:
                    ${escapeHtml(player.online_status || "")}
                    /
                    ${escapeHtml(player.life_state || "")}
                    ${idBlock}
                </div>
            `;
        }).join("");

    } catch (err) {
        panel.innerHTML =
            `<span class="status-bad">Failed to refresh online players.</span>`;
    }
}

async function loadCharactersForGrantPage() {
    const chars = await fetchCharacters(true);

    fillCharacterSelect("grantCharacterSelect", chars);
    fillCharacterSelect("scoutCharacterSelect", chars);
    fillCharacterSelect("mediumCharacterSelect", chars);
}

async function loadCharactersForAdminPage() {
    const chars = await fetchCharacters(true);
    fillCharacterSelect("overrepairCharacterSelect", chars);
    fillCharacterSelect("lasgunCharacterSelect", chars);
    fillCharacterSelect("researchCharacterSelect", chars);
    fillCharacterSelect("characterXpCharacterSelect", chars);
    fillCharacterSelect("characterLevelCharacterSelect", chars);
    fillCharacterSelect("xpCharacterSelect", chars);
    fillCharacterSelect("specializationResetCharacterSelect", chars);
    fillCharacterSelect("progressionCharacterSelect", chars);
    fillCharacterSelect("solariCharacterSelect", chars);
}

function fillGrantPlayerId() {
    const sel = document.getElementById("grantCharacterSelect");
    const input = document.getElementById("grantPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

function fillScoutPlayerId() {
    const sel = document.getElementById("scoutCharacterSelect");
    const input = document.getElementById("scoutPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

function fillMediumPlayerId() {
    const sel = document.getElementById("mediumCharacterSelect");
    const input = document.getElementById("mediumPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

function fillOverrepairFields() {
    const sel = document.getElementById("overrepairCharacterSelect");
    const c = latestCharacters[Number(sel.value)];
    if (!c) return;

    const actorInput = document.getElementById("overrepairActorId");
    const inventoryInput = document.getElementById("overrepairInventoryId");

    if (actorInput) actorInput.value = c.character_actor_id || "";
    if (inventoryInput) inventoryInput.value = c.inventory_id || "";
}

function fillLasgunPlayerId() {
    const sel = document.getElementById("lasgunCharacterSelect");
    const input = document.getElementById("lasgunPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

function fillResearchActorId() {
    const sel = document.getElementById("researchCharacterSelect");
    const input = document.getElementById("researchActorId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.character_actor_id || "";
}

function fillCharacterXpActorId() {
    const sel = document.getElementById("characterXpCharacterSelect");
    const input = document.getElementById("characterXpActorId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.character_actor_id || "";
}

function fillCharacterLevelActorId() {
    const sel = document.getElementById("characterLevelCharacterSelect");
    const input = document.getElementById("characterLevelActorId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.character_actor_id || "";
}

function fillXpControllerId() {
    const sel = document.getElementById("xpCharacterSelect");
    const input = document.getElementById("xpControllerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.player_controller_id || "";
}

function fillSpecializationResetControllerId() {
    const sel = document.getElementById("specializationResetCharacterSelect");
    const input = document.getElementById("specializationResetControllerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.player_controller_id || "";
}

function fillProgressionPlayerId() {
    const sel = document.getElementById("progressionCharacterSelect");
    const input = document.getElementById("progressionPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

function fillSolariPlayerId() {
    const sel = document.getElementById("solariCharacterSelect");
    const input = document.getElementById("solariPlayerId");
    const c = latestCharacters[Number(sel.value)];
    if (input && c) input.value = c.fls_id || "";
}

async function searchItems() {
    const query = document.getElementById("itemSearchQuery").value || "";
    const resultsPanel = document.getElementById("itemSearchResults");

    const response = await fetch(`/api/item-search?q=${encodeURIComponent(query)}`);
    const data = await response.json();

    const items = data.items || [];

    if (items.length === 0) {
        resultsPanel.innerHTML = "No items found.";
        return;
    }

    resultsPanel.innerHTML = items.map(item => {
        const id = item.id || "";
        const name = item.name || id;
        const cat = item.category || "";
        const source = item.source || "";

        return `
            <div class="item">
                <b>${escapeHtml(name)}</b><br>
                ID:
                <a href="#" onclick="selectItem('${escapeHtml(id)}'); return false;">
                    ${escapeHtml(id)}
                </a><br>
                Category: ${escapeHtml(cat)}<br>
                Source: ${escapeHtml(source)}
            </div>
        `;
    }).join("");
}

function selectItem(itemId) {
    const input = document.getElementById("grantItemId");
    if (input) input.value = itemId;

    const selected = document.getElementById("selectedItemNotice");
    if (selected) {
        selected.textContent = `Selected Item: ${itemId}`;
        selected.style.display = "block";
    }
}


async function loadMarketPresetPreview() {
    const panel = document.getElementById("marketPresetPreview");
    if (!panel) return;

    try {
        const multiplierInput = document.getElementById("marketPriceMultiplier");
        const multiplier = multiplierInput ? multiplierInput.value || "1" : "1";
        const response = await fetch(`/api/market-preset-preview?price_multiplier=${encodeURIComponent(multiplier)}`);
        const data = await response.json();

        if (!data.ok) {
            panel.textContent = data.error || "Unable to load market seed preview.";
            return;
        }

        const summary = data.summary || {};
        panel.textContent =
            `Listings: ${summary.listings || 0}\n`
            + `Equippable listings: ${summary.equippable_listings || 0}\n`
            + `Schematic listings: ${summary.schematic_listings || 0}\n`
            + `Resource listings: ${summary.resource_listings || 0}\n`
            + `Resource units: ${summary.resource_units || 0}\n`
            + `Boosted wing/track/locomotion listings: ${summary.special_boosted_listings || 0}\n`
            + `Price multiplier: ${summary.price_multiplier || 1}x`;
    } catch (err) {
        panel.textContent = "Unable to load market seed preview.";
    }
}


async function refreshMarketBuybackStatus() {
    const panel = document.getElementById("marketBuybackStatus");
    if (!panel) return;

    try {
        const response = await fetch("/api/market-buyback-status");
        const data = await response.json();

        if (!data.ok) {
            panel.textContent = data.error || "Unable to load buyback automation status.";
            return;
        }

        const status = data.status || {};
        panel.textContent =
            `Automated buyback: ${status.enabled ? "Running" : "Stopped"}\n`
            + `Interval: ${status.interval_minutes || 30} minutes\n`
            + `Price multiplier: ${status.price_multiplier || 1}x\n`
            + `Buy threshold: ${status.threshold_percent || 60}%\n`
            + `Max buys: ${status.max_buys || 500}\n`
            + `Next run: ${status.next_run || "Not scheduled"}\n`
            + `Last run: ${status.last_run || "Never"}\n`
            + `Runs completed: ${status.runs || 0}\n`
            + `Last error: ${status.last_error || "None"}`;
    } catch (err) {
        panel.textContent = "Unable to load buyback automation status.";
    }
}


// =========================================================
// Vehicle repair helpers
// =========================================================

let latestVehicles = [];
let latestOrnithopters = [];
let ornithopterAdminMapZoom = 0.10;
let ornithopterAdminMapControlsWired = false;
let ornithopterAdminMapDragging = false;
let ornithopterAdminMapDragStartX = 0;
let ornithopterAdminMapDragStartY = 0;
let ornithopterAdminMapDragScrollLeft = 0;
let ornithopterAdminMapDragScrollTop = 0;

async function fetchVehicles() {
    const response = await fetch("/api/vehicles");
    const data = await response.json();
    latestVehicles = data.vehicles || [];
    return latestVehicles;
}

function vehicleLabel(v) {
    const id = v.vehicle_id || "";
    const klass = v.vehicle_class || "Unknown vehicle";
    const shortClass = klass.split("/").pop() || klass;
    return `Vehicle ${id} | ${shortClass} | modules ${v.module_count || "?"} | durability ${v.min_durability || "?"}-${v.max_durability || "?"}`;
}

function fillVehicleSelect(selectId, vehicles) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = `<option value="">Select a vehicle...</option>`;

    vehicles.forEach((v, index) => {
        const opt = document.createElement("option");
        opt.value = String(index);
        opt.textContent = vehicleLabel(v);
        select.appendChild(opt);
    });
}

async function loadVehiclesForAdminPage() {
    const vehicles = await fetchVehicles();
    fillVehicleSelect("vehicleSelect", vehicles);
}

function fillVehicleRepairFields() {
    const sel = document.getElementById("vehicleSelect");
    const input = document.getElementById("vehicleRepairId");
    const v = latestVehicles[Number(sel.value)];
    if (input && v) input.value = v.vehicle_id || "";
}


// =========================================================
// Vehicle teleport helpers
// =========================================================

async function fetchOrnithopters() {
    const response = await fetch("/api/teleportable-vehicles");
    const data = await response.json();
    latestOrnithopters = data.vehicles || [];
    return latestOrnithopters;
}

function ornithopterLabel(t) {
    const id = t.actor_id || "";
    const shortClass = t.short_class || "Vehicle";
    const map = t.map || "Unknown map";
    const partition = t.partition_id || "?";
    const x = Number(t.x || 0).toFixed(0);
    const y = Number(t.y || 0).toFixed(0);
    const z = Number(t.z || 0).toFixed(0);
    const owner = t.owner_account_id ? ` | owner ${t.owner_account_id}` : "";
    return `Actor ${id} | ${shortClass} | ${map} partition ${partition} | X ${x} Y ${y} Z ${z}${owner}`;
}

function fillOrnithopterSelect(selectId, ornithopters) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = `<option value="">Select a vehicle...</option>`;

    ornithopters.forEach((t, index) => {
        const opt = document.createElement("option");
        opt.value = String(index);
        opt.textContent = ornithopterLabel(t);
        select.appendChild(opt);
    });
}

async function loadOrnithoptersForAdminPage() {
    const ornithopters = await fetchOrnithopters();
    fillOrnithopterSelect("ornithopterSelect", ornithopters);
    syncOrnithopterAdminMapZoomSlider();
    renderOrnithopterAdminMap();
}

function ornithopterPartitionForMap(mapKey) {
    // These are the known gameplay partition IDs for vehicle relocation.
    // Change them here if your RedBlink stack/database uses different IDs.
    if (mapKey === "DeepDesert") return "8";
    return "1";
}

function fillOrnithopterPartitionDefault() {
    const mapSelect = document.getElementById("ornithopterMapKey");
    const partitionInput = document.getElementById("ornithopterPartitionId");

    if (mapSelect && partitionInput) {
        partitionInput.value = ornithopterPartitionForMap(mapSelect.value);
    }
}

function ornithopterMapKeyForActor(t, fallbackMapKey) {
    // Some actor rows have a blank/nonstandard map field. For form safety, only
    // put map keys into the dropdown that the backend route accepts.
    if (typeof adminMapConfigs !== "undefined" && t.map && adminMapConfigs[t.map]) {
        return t.map;
    }
    if (String(t.partition_id || "") === ornithopterPartitionForMap("DeepDesert")) {
        return "DeepDesert";
    }
    if (String(t.partition_id || "") === ornithopterPartitionForMap("HaggaBasin")) {
        return "HaggaBasin";
    }
    return fallbackMapKey || "HaggaBasin";
}

function fillOrnithopterTeleportFields() {
    const sel = document.getElementById("ornithopterSelect");
    const t = latestOrnithopters[Number(sel.value)];
    if (!t) return;

    const actorInput = document.getElementById("ornithopterActorId");
    const mapSelect = document.getElementById("ornithopterMapKey");
    const partitionInput = document.getElementById("ornithopterPartitionId");
    const xInput = document.getElementById("ornithopterX");
    const yInput = document.getElementById("ornithopterY");
    const zInput = document.getElementById("ornithopterZ");

    const mapKey = ornithopterMapKeyForActor(t, mapSelect ? mapSelect.value : "HaggaBasin");

    if (actorInput) actorInput.value = t.actor_id || "";
    if (mapSelect) mapSelect.value = mapKey;
    if (partitionInput) partitionInput.value = t.partition_id || ornithopterPartitionForMap(mapKey);
    if (xInput) xInput.value = t.x || "";
    if (yInput) yInput.value = t.y || "";
    if (zInput) zInput.value = t.z || "";
}

function adminWorldToMapPixels(x, y, mapConfig) {
    const minX = mapConfig.min_x;
    const maxX = mapConfig.max_x;
    const minY = mapConfig.min_y;
    const maxY = mapConfig.max_y;

    if (maxX === minX || maxY === minY) return null;

    const px = ((x - minX) / (maxX - minX)) * mapConfig.width;
    let py = ((y - minY) / (maxY - minY)) * mapConfig.height;

    if (mapConfig.flip_y) {
        py = mapConfig.height - py;
    }

    return {
        px,
        py,
        inBounds: px >= 0 && px <= mapConfig.width && py >= 0 && py <= mapConfig.height
    };
}

function adminMapPixelsToWorld(px, py, mapConfig) {
    const minX = mapConfig.min_x;
    const maxX = mapConfig.max_x;
    const minY = mapConfig.min_y;
    const maxY = mapConfig.max_y;

    if (mapConfig.width === 0 || mapConfig.height === 0) return null;

    let normalizedY = py / mapConfig.height;
    if (mapConfig.flip_y) {
        normalizedY = 1 - normalizedY;
    }

    return {
        x: minX + (px / mapConfig.width) * (maxX - minX),
        y: minY + normalizedY * (maxY - minY)
    };
}

function ornithopterBelongsOnMap(t, mapKey) {
    // Prefer exact actor map matches, but still allow the known partition IDs.
    // Some actor rows can have empty or nonstandard map labels while their
    // partition/transform still place them on the expected map.
    const partitionMatches =
        String(t.partition_id || "") === ornithopterPartitionForMap(mapKey);

    return t.map === mapKey || partitionMatches;
}

function fillOrnithopterTeleportFromActor(t) {
    const actorInput = document.getElementById("ornithopterActorId");
    const mapSelect = document.getElementById("ornithopterMapKey");
    const partitionInput = document.getElementById("ornithopterPartitionId");
    const xInput = document.getElementById("ornithopterX");
    const yInput = document.getElementById("ornithopterY");
    const zInput = document.getElementById("ornithopterZ");

    const mapKey = ornithopterMapKeyForActor(t, document.getElementById("ornithopterMapView")?.value || "HaggaBasin");

    if (actorInput) actorInput.value = t.actor_id || "";
    if (mapSelect) mapSelect.value = mapKey;
    if (partitionInput) partitionInput.value = t.partition_id || ornithopterPartitionForMap(mapKey);
    if (xInput) xInput.value = t.x || "";
    if (yInput) yInput.value = t.y || "";
    if (zInput) zInput.value = t.z || "";
}

function fillOrnithopterTargetFromAdminMapClick(event) {
    if (typeof adminMapConfigs === "undefined") return;
    if (event.target.closest(".ornithopter-marker")) return;

    event.preventDefault();

    const mapSelect = document.getElementById("ornithopterMapView");
    const formMapSelect = document.getElementById("ornithopterMapKey");
    const partitionInput = document.getElementById("ornithopterPartitionId");
    const xInput = document.getElementById("ornithopterX");
    const yInput = document.getElementById("ornithopterY");
    const zInput = document.getElementById("ornithopterZ");
    const frame = document.getElementById("ornithopterMapFrame");
    const canvas = document.getElementById("ornithopterMapCanvas");
    const summary = document.getElementById("ornithopterMapSummary");

    if (!mapSelect || !frame || !canvas || !xInput || !yInput) return;

    const mapKey = mapSelect.value || "HaggaBasin";
    const mapConfig = adminMapConfigs[mapKey] || adminMapConfigs.HaggaBasin;
    const canvasRect = canvas.getBoundingClientRect();

    // Convert the double-click location back into source map image pixels.
    // Keep this formula paired with adminWorldToMapPixels/adminMapPixelsToWorld
    // if you ever recalibrate the map bounds in app.py.
    const px = (event.clientX - canvasRect.left) / ornithopterAdminMapZoom;
    const py = (event.clientY - canvasRect.top) / ornithopterAdminMapZoom;

    if (px < 0 || px > mapConfig.width || py < 0 || py > mapConfig.height) return;

    const world = adminMapPixelsToWorld(px, py, mapConfig);
    if (!world) return;

    if (formMapSelect) formMapSelect.value = mapKey;
    if (partitionInput) partitionInput.value = ornithopterPartitionForMap(mapKey);
    xInput.value = world.x.toFixed(3);
    yInput.value = world.y.toFixed(3);

    // Z is intentionally not derived from the flat map. If a vehicle has been
    // selected, leave its current altitude as the starting point; otherwise use
    // a conservative above-ground starter value the admin can adjust.
    if (zInput && !zInput.value) {
        zInput.value = "1500";
    }

    if (summary) {
        summary.textContent =
            `${mapConfig.label}: target set to X ${world.x.toFixed(0)} Y ${world.y.toFixed(0)}`;
    }
}

function syncOrnithopterAdminMapZoomSlider() {
    const slider = document.getElementById("ornithopterMapZoom");
    const readout = document.getElementById("ornithopterMapZoomReadout");
    const percent = Math.round(ornithopterAdminMapZoom * 100);

    if (slider) slider.value = String(percent);
    if (readout) readout.textContent = `${percent}%`;
}

function setOrnithopterAdminMapZoom(newZoom) {
    ornithopterAdminMapZoom = Math.max(0.05, Math.min(1.00, newZoom));
    syncOrnithopterAdminMapZoomSlider();
    renderOrnithopterAdminMap();
}

function setOrnithopterAdminMapZoomFromSlider() {
    const slider = document.getElementById("ornithopterMapZoom");
    if (!slider) return;
    setOrnithopterAdminMapZoom(Number(slider.value || 10) / 100);
}

function setOrnithopterAdminMapZoomAroundPoint(newZoom, clientX, clientY) {
    const frame = document.getElementById("ornithopterMapFrame");
    if (!frame) {
        setOrnithopterAdminMapZoom(newZoom);
        return;
    }

    const oldZoom = ornithopterAdminMapZoom;
    const nextZoom = Math.max(0.05, Math.min(1.00, newZoom));
    const rect = frame.getBoundingClientRect();
    const sourceX = (frame.scrollLeft + clientX - rect.left) / oldZoom;
    const sourceY = (frame.scrollTop + clientY - rect.top) / oldZoom;

    ornithopterAdminMapZoom = nextZoom;
    syncOrnithopterAdminMapZoomSlider();
    renderOrnithopterAdminMap();

    frame.scrollLeft = (sourceX * nextZoom) - (clientX - rect.left);
    frame.scrollTop = (sourceY * nextZoom) - (clientY - rect.top);
}

function wireOrnithopterAdminMapControls() {
    const frame = document.getElementById("ornithopterMapFrame");
    const canvas = document.getElementById("ornithopterMapCanvas");

    if (!frame || !canvas || ornithopterAdminMapControlsWired) return;
    ornithopterAdminMapControlsWired = true;

    frame.addEventListener("dblclick", fillOrnithopterTargetFromAdminMapClick);

    frame.addEventListener("pointerdown", function(event) {
        if (event.button !== 0 || event.target.closest(".ornithopter-marker")) return;

        ornithopterAdminMapDragging = true;
        ornithopterAdminMapDragStartX = event.clientX;
        ornithopterAdminMapDragStartY = event.clientY;
        ornithopterAdminMapDragScrollLeft = frame.scrollLeft;
        ornithopterAdminMapDragScrollTop = frame.scrollTop;
        frame.classList.add("is-dragging");
        frame.setPointerCapture(event.pointerId);
    });

    frame.addEventListener("pointermove", function(event) {
        if (!ornithopterAdminMapDragging) return;

        event.preventDefault();
        frame.scrollLeft = ornithopterAdminMapDragScrollLeft - (event.clientX - ornithopterAdminMapDragStartX);
        frame.scrollTop = ornithopterAdminMapDragScrollTop - (event.clientY - ornithopterAdminMapDragStartY);
    });

    frame.addEventListener("pointerup", function(event) {
        if (!ornithopterAdminMapDragging) return;

        ornithopterAdminMapDragging = false;
        frame.classList.remove("is-dragging");
        if (frame.hasPointerCapture(event.pointerId)) {
            frame.releasePointerCapture(event.pointerId);
        }
    });

    frame.addEventListener("pointercancel", function(event) {
        ornithopterAdminMapDragging = false;
        frame.classList.remove("is-dragging");
        if (frame.hasPointerCapture(event.pointerId)) {
            frame.releasePointerCapture(event.pointerId);
        }
    });

    frame.addEventListener("wheel", function(event) {
        if (!event.ctrlKey && !event.metaKey) {
            event.preventDefault();
            window.scrollBy({
                top: event.deltaY,
                left: event.deltaX,
                behavior: "auto"
            });
            return;
        }

        event.preventDefault();
        const zoomStep = event.deltaY < 0 ? 1.12 : 0.88;
        setOrnithopterAdminMapZoomAroundPoint(
            ornithopterAdminMapZoom * zoomStep,
            event.clientX,
            event.clientY
        );
    }, { passive: false });
}

function renderOrnithopterAdminMap() {
    if (typeof adminMapConfigs === "undefined") return;

    const mapSelect = document.getElementById("ornithopterMapView");
    const canvas = document.getElementById("ornithopterMapCanvas");
    const image = document.getElementById("ornithopterMapImage");
    const layer = document.getElementById("ornithopterMarkerLayer");
    const summary = document.getElementById("ornithopterMapSummary");

    if (!mapSelect || !canvas || !image || !layer || !summary) return;

    const mapKey = mapSelect.value || "HaggaBasin";
    const mapConfig = adminMapConfigs[mapKey] || adminMapConfigs.HaggaBasin;
    const zoom = ornithopterAdminMapZoom;

    image.src = `/static/${mapConfig.image}`;
    image.alt = mapConfig.label;

    const width = mapConfig.width * zoom;
    const height = mapConfig.height * zoom;

    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    image.style.width = `${width}px`;
    image.style.height = `${height}px`;
    layer.style.width = `${width}px`;
    layer.style.height = `${height}px`;
    layer.innerHTML = "";

    const visible = latestOrnithopters
        .filter(t => ornithopterBelongsOnMap(t, mapKey))
        .map(t => {
            const pixel = adminWorldToMapPixels(Number(t.x), Number(t.y), mapConfig);
            return { ...t, pixel };
        })
        .filter(t => t.pixel && t.pixel.inBounds);

    summary.textContent = `${mapConfig.label}: ${visible.length} vehicle actor(s) in bounds`;

    visible.forEach(t => {
        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = "ornithopter-marker";
        marker.style.left = `${t.pixel.px * zoom}px`;
        marker.style.top = `${t.pixel.py * zoom}px`;
        marker.title = ornithopterLabel(t);
        marker.addEventListener("click", event => {
            event.stopPropagation();
            fillOrnithopterTeleportFromActor(t);
        });
        marker.addEventListener("dblclick", event => {
            event.stopPropagation();
        });
        layer.appendChild(marker);
    });
}
