# GigaHA Starter Kit — instructions for Claude sessions

A generator for a shareable Home Assistant setup. `household.yaml` → `build.py` → `out/config/`.
It's a depersonalized rebuild of a private, single-household HA config; nothing from that
household may appear here.

## Rules
- **No personal data, ever.** No real names, phones, entity IDs, domains, IPs, addresses or
  pets from the source household. Examples use Alex/Sam/Riley and `example.com`. `tools/leakscan.py`
  must pass before every push (it checks hashes in `tools/leak_hashes.txt`; never write the words).
  Private IPs only as `192.168.1.x` placeholders.
- **Templates:** build-time Jinja uses `<< >>`, `<% %>`, `<# #>`; `{{ }}` / `{% %}` pass through to HA.
  Inline `<% if %>` at the end of a line eats the newline (trim_blocks): put block tags on their own lines.
- **Entity IDs come from `household.yaml` ids**, not names: template entities set `default_entity_id`,
  `unique_id` is `gigaha_<...>`, automation ids are `gigaha_<...>`. Never change an existing id scheme
  (it would orphan users' history).
- **Generated files carry a GENERATED header.** Users edit `household.yaml`, not output.
- **Core cards only** in dashboards until a module ships its own card JS (then: `www/<module>/`,
  version constant + `?v=`).
- **Every device action respects dry run** (`dry_run` → `logbook.log` instead of acting) and guards
  against the integration not being set up yet. Calendar writes go through
  `script.motivator_calendar_event`; notifications through `script.motivator_notify`.
- **Validate before pushing:** `tools/check.sh` (build all test households, `hass --script check_config`,
  leak scan). For logic changes also `python3 tools/smoke_test.py --hass <hass>` (boots HA, runs the
  scenario). Say plainly what hasn't been tested on a real server or in a browser.
- Every change gets a `CHANGELOG.md` entry under today's date (`## YYYY-MM-DD (Weekday)`); bump
  `KIT_VERSION` in build.py for releases. Update README/SETUP when behavior or layout changes.
- Small commits straight to `main`.
