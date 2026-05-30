# Changelog

All notable changes to Easy Dune Admin are documented here.

## 0.6.6-rc2

### Added

- Renamed project branding and repository references to Easy Dune Admin.
- Added VIP role tools for linked characters.
- Added admin-managed exact in-game character-name linking for VIP accounts.
- Added VIP self-only overrepair for the linked character inventory.
- Added VIP self-only offline teleport using the linked character account/FLS ID.
- Added VIP self-only Mk6 Scout and Mk6 Medium Ornithopter grants.
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

- Market tooling research, category mapping, and bundled market item data are adapted from IceHunter / Ryan Wilson's MIT-licensed `dune-admin` project. See `THIRD_PARTY_NOTICES.md`.

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
