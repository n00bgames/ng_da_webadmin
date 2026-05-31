# Changelog

All notable changes to Easy Dune Admin are documented here.

## 0.7.0-beta

### Changed

- Split the former `app.py` monolith into a small launcher, `eda_core.py` for shared configuration/helpers/services, and `eda_routes.py` for Flask and Socket.IO route registrations.
- Kept existing routes, templates, and admin workflows behavior-compatible while reducing future app.py bloat.
- Marked Specialization XP as WIP/unconfirmed in the Admin UI and documentation. The tool appears to create/update the expected database entries, but persistence and in-game behavior still need confirmation after reaching the required progression/faction access.
- Documented that progression edits may require relogging, restarting the affected map, or restarting the battlegroup. Restarts can appear slow, and login may briefly show an error before recovering.

### Planned

- `0.7.1` candidate: evaluate faction manipulation tools after faction membership and related database state can be captured and tested safely.

## 0.6.6-rc2

### Added

- Renamed project branding and repository references to Easy Dune Admin.
- Added VIP role tools for linked characters.
- Added admin-managed exact in-game character-name linking for VIP accounts.
- Added VIP self-only overrepair for the linked character inventory.
- Added VIP self-only offline teleport using the linked character account/FLS ID.
- Added VIP self-only Mk6 Scout and Mk6 Medium Ornithopter grants.
- Added admin-only Lightning Gun kit grant through the RedBlink item grant command.
- Added admin-only SolarisCoin grant with preset amount dropdown.
- Added admin-only research point setter for selected characters.
- Added admin-only character XP grant for the actual displayed character level.
- Added admin-only set character level tool using the same level XP curve.
- Added admin-only skill point grant that adds usable skill points without changing character level XP.
- Added WIP/unconfirmed admin-only specialization XP grant for Combat, Crafting, Gathering, Exploration, and Sabotage tracks.
- Added admin-only specialization reset for one track or all tracks plus keystones.
- Added experimental admin-only progression preset apply/reset tools for curated journey roots.
- Added admin-only preset market seeding.
- Added Seed Exchange ID override for servers whose visible player market is not the DB `Global` exchange id.
- Added per-run market price multiplier tuning, defaulting to 5x.
- Added 8-listing boost for market-seeded items/schematics named wing, track, or locomotion.
- Added 2.5x refined-resource category price multiplier.
- Added raw-resource category price tuning with special overrides for spice, titanium, stravidium, agave seeds, and basalt.
- Added clear-only NPC market listing cleanup for the market bot.
- Added market bot buyback for player listings priced at or below 60% of the current preset price.
- Added start/stop controls for automated 30-minute market buyback sweeps.
- Added Admin UI controls for buyback threshold, max buys per sweep, and sweep interval.
- Changed buyback sweep Start to run one sweep immediately before continuing on the interval.
- Added bundled IceHunter-derived market item data and third-party MIT notice.
- Added admin vehicle teleport support for Ornithopter, Sandbike, Buggy, TreadWheel, and SandCrawler actor families.
- Added zoomable/draggable admin vehicle map with marker selection and double-click coordinate targeting.
- Added `restart.sh` and `shutdown.sh` helpers for screen/headless daemon control.

### Changed

- Restricted operator access away from Infrastructure Services, Advanced Management, and logs.
- Updated viewer/VIP privacy handling so sensitive database IDs are not exposed to lower roles.
- Updated vehicle teleport warnings to document that loaded vehicle actors require an affected map/server restart.
- Updated live map mouse-wheel behavior so normal scrolling moves the page and Ctrl/Command+wheel zooms the map.
- Updated dashboard RedBlink stack display variable.
- Removed hard dependency on `dune.inventories.type` for character inventory lookup to support stacks without that column.

### Attribution

- Market tooling research, category mapping, bundled market item data, progression preset structure, specialization XP research, and character-level XP curve research are adapted from IceHunter / Ryan Wilson's MIT-licensed `dune-admin` project. See `THIRD_PARTY_NOTICES.md`.
- RedBlink's MIT license notice is included for the companion stack this panel targets and the wrapper/admin command workflows it uses. See `THIRD_PARTY_NOTICES.md`.
- Linked upstream repositories for RedBlink's `dune-awakening-selfhost-docker` and IceHunter / Ryan Wilson's `dune-admin` in the README and third-party notices.

## 0.6.5-rc1

### Added

- Updated RedBlink stack target to `v1.3.2`.
- Added RedBlink map runtime controls:
  - `dune maps list`
  - `dune maps mode`
  - `dune maps set <map> dynamic`
  - `dune maps set <map> always-on`
  - `dune maps reconcile`
- Added Deep Desert dual PvP/PvE controls.
- Added grouped restart services.
- Added DB health/status/list/backup controls.
- Added `.gitattributes` line-ending guard.
- Added `setup.sh`.
- Added runtime map and banner assets.
- Added GitHub README images under `images/`.

### Changed

- Hardened browser shell fitting.
- Improved `start.sh`.
- Updated release packaging and GPLv3 metadata.
