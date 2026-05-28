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


// =========================================================
// Vehicle repair helpers
// =========================================================

let latestVehicles = [];

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
