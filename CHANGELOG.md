# Changelog

## 2026-11-21 (Saturday)

### 0.1.0: Motivator core
- `household.yaml` schema: any number of people (admin/member/child; phone or manual tracking;
  per-screen earning split; bonus screen; optional work-hours exclusion; notify-parents routing),
  any number of screens (Nintendo Switch, Apple TV), rules, chores, exercise types, dry run.
- `build.py`: validates the household file with plain-English errors, renders packages per person
  and per screen plus household rules, YAML-mode dashboards (Motivator, Log Activity, admin-only
  Motivator Settings), and themes. Rebuilds only replace files from the previous build (manifest);
  refuses to write into a `/config` it didn't create.
- Motivator: earning from Apple Health steps/exercise and logged exercise/chores; per-screen banks
  with free time, caps, bonus banks, nightly rollover and missed-rollover flag; Switch limit push and
  Apple TV sleep (both dry-run aware and skipped until the integration exists); tokens; streaks and
  bonuses; Chore Challenge for 2+ people with phone prize pick; Sunday recap; undo; quick add/remove.
- Safe plumbing: calendar writes skip missing Local Calendars; each phone notification runs on its
  own, so a phone that isn't set up can't stop an automation.
- Tooling: `tools/check.sh` (build + HA config check + leak scan), `tools/smoke_test.py` (boots
  HA 2026.2.3 on 1-, 3- and 6-person households and runs a full scenario; all pass), `tools/leakscan.py`.
- Not yet checked in a browser: the three dashboards (core cards only).
