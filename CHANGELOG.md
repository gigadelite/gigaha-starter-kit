# Changelog

## 2026-11-21 (Saturday)

### 0.2.0: Xbox and PlayStation
- New screen types `xbox` (Xbox integration: counts any running game/app; pause + `remote.turn_off`
  when out) and `playstation` (PlayStation Network for counting; optional PS5-MQTT `power` switch for
  rest mode, otherwise a time's-up warning). Both support `exempt_apps`, dry run, the 15-minute warning,
  and skip quietly until their integration exists. Apple TV now shares the same code path.
- Nightly rollover notes "Went N min over" in Bank History when a screen ran past zero.
- Settings dashboard shows what each screen does when time runs out.
- `household.yaml` rejects unknown entity keys per screen type.
- Tests: new `consoles` household (live, every screen type); `family6` gained a PS5. The smoke test now
  fakes each console playing with no time left and checks counting, exempt apps and the exact off call
  (none in dry run, none when no off switch). All four households pass. No real Xbox/PlayStation yet.
- Apply: rebuild, copy `out/config/`, restart.

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
