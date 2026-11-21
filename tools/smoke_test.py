#!/usr/bin/env python3
"""Boot a real Home Assistant on generated configs and run the Motivator through a scenario.

    python3 tools/smoke_test.py --hass /path/to/venv/bin/hass [household files...]

Defaults to every file in tests/households/. For each one: build, add the test-only
kit_probe component, start HA (no network needed), log exercise/chores/tokens, quick-add,
run the rollover/streak/recap automations, and check the numbers. Exits non-zero on any
failure or on errors in the HA log that mention the kit's entities.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402


def scenario(cfg):
    people, screens = cfg["people"], cfg["screens"]
    a = people[0]
    k = next((p for p in people if p["tracking"] == "manual"), people[-1])
    s0 = screens[0]
    steps = media_steps(cfg) + [
        {"do": "set", "entity": "input_select.motivator_who", "value": a["name"]},
        {"do": "set", "entity": "input_select.motivator_exercise_type", "value": cfg["exercise_types"][0]},
        {"do": "set", "entity": "input_number.motivator_exercise_minutes", "value": 45},
        {"do": "call", "action": "script.motivator_log_exercise", "wait": 3,
         "expect": {f"sensor.{a['id']}_exercise_today": "45", f"sensor.{a['id']}_active_minutes_today": "45"}},
        {"do": "set", "entity": "input_select.motivator_chore", "value": cfg["chores"][0]["name"], "wait": 2,
         "expect": {"input_number.motivator_chore_minutes": f"{float(cfg['chores'][0]['minutes'])}"}},
        {"do": "call", "action": "script.motivator_log_chore",
         "data": {"who_id": k["id"], "chore": cfg["chores"][1]["name"], "minutes": 30}, "wait": 3,
         "expect": {f"sensor.{k['id']}_chores_daily": "30.0",
                    f"sensor.{k['id']}_earned_today": f"{30.0 + (45 if k is a else 0)}"}},
        {"do": "set", "entity": "input_select.motivator_who", "value": k["name"]},
        {"do": "set", "entity": "input_text.motivator_token_reason", "value": "Sick day"},
        {"do": "call", "action": "script.motivator_use_token", "wait": 2,
         "expect": {f"input_number.{k['id']}_tokens_used_week": "1.0"}},
        {"do": "set", "entity": "input_select.motivator_quick_screen", "value": s0["name"]},
        {"do": "set", "entity": "input_number.motivator_quick_minutes", "value": 15},
        {"do": "call", "action": "script.motivator_quick_add", "wait": 2,
         "expect": {f"input_number.{s0['id']}_extra_today": "15.0"}},
        {"do": "call", "action": "script.motivator_quick_remove", "wait": 2,
         "expect": {f"input_number.{s0['id']}_extra_today": "0.0"}},
        {"do": "automation", "id": "gigaha_motivator_active_days", "wait": 3,
         "expect": {f"input_number.{a['id']}_active_days_week": "1.0"}},
        {"do": "automation", "id": "gigaha_motivator_rollover", "wait": 5},
        {"do": "set", "entity": f"input_number.{a['id']}_active_days_week", "value": cfg["m"]["credits_per_week"]},
        {"do": "set", "entity": f"input_number.{a['bonus_to']}_bonus_bank", "value": 0},
        {"do": "automation", "id": "gigaha_motivator_streaks", "wait": 5,
         "expect": {f"counter.{a['id']}_streak_weeks": "1",
                    f"input_number.{a['bonus_to']}_bonus_bank": f"{float(cfg['m']['streak_bonus'][0])}"}},
        {"do": "automation", "id": "gigaha_motivator_recap", "wait": 3},
        {"do": "call", "action": "script.motivator_undo_last", "wait": 3,
         "expect": {f"sensor.{k['id']}_chores_daily": "0.0"}},
        {"do": "call", "action": "script.motivator_notify", "data": {"who": "all", "title": "t", "message": "m"}, "wait": 2},
    ] + ([{"do": "automation", "id": "gigaha_motivator_challenge", "wait": 3}] if cfg["challenge"] else []) + [
    ]
    for s in screens:
        if s["type"] == "nintendo_switch":
            # Dry run: force it to exercise the logbook path. Live: respect the "integration exists" guard.
            steps.append({"do": "automation", "id": f"gigaha_{s['id']}_gate_apply", "wait": 2,
                          "skip_condition": cfg["dry_run"]})
    return steps


def media_steps(cfg):
    """Fake each media screen playing with no time left; check counting, exemptions and the off action."""
    steps = []
    for s in cfg["screens"]:
        if not s["media"]:
            continue
        sid, mp = s["id"], s["entities"]["media_player"]
        attr = s["app_attrs"][-1]
        if s["off_entity"]:
            steps.append({"do": "state", "entity": s["off_entity"], "value": "on"})
        steps += [
            {"do": "call", "action": "input_boolean.turn_off", "data": {"entity_id": f"input_boolean.{sid}_free_enabled"},
             "wait": 2, "expect": {f"sensor.{sid}_minutes_left": "0"}},
            {"do": "calls_reset"},
            {"do": "state", "entity": mp, "value": "playing", "attributes": {attr: "Space Racer"}, "wait": 4,
             "expect": {f"sensor.{sid}_active_app": "Space Racer", f"binary_sensor.{sid}_counted_playing": "on"},
             "check_off": None if cfg["dry_run"] else s["off_entity"], "screen": sid},
        ]
        if s["exempt_apps"]:
            steps.append({"do": "state", "entity": mp, "value": "playing", "attributes": {attr: s["exempt_apps"][0] + " Live"},
                          "wait": 2, "expect": {f"binary_sensor.{sid}_counted_playing": "off"}})
        steps += [
            {"do": "state", "entity": mp, "value": "on", "attributes": {}, "wait": 2,
             "expect": {f"binary_sensor.{sid}_counted_playing": "off"}},
            {"do": "state", "entity": mp, "value": "off", "attributes": {}, "wait": 1},
            {"do": "call", "action": f"input_boolean.turn_{'on' if s['free_minutes'] > 0 else 'off'}",
             "data": {"entity_id": f"input_boolean.{sid}_free_enabled"}},
        ]
    return steps


def expected_screen_earned(cfg, earned):
    return {s["id"]: round(sum(earned.get(p["id"], 0) * p["earn_to"].get(s["id"], 0) / 100 for p in cfg["people"]), 1)
            for s in cfg["screens"]}


def run_one(hass: str, household: Path) -> list[str]:
    fails: list[str] = []
    cfg = build.load(household)
    work = Path(tempfile.mkdtemp(prefix="kit-smoke-"))
    build.build(build.load(household), work)
    shutil.copytree(ROOT / "tools/smoke/kit_probe", work / "custom_components/kit_probe")
    steps = scenario(cfg)
    with open(work / "configuration.yaml", "a") as f:
        f.write("\nkit_probe:\n  scenario: " + json.dumps(steps) + "\n")
    proc = subprocess.run([hass, "-c", str(work), "--skip-pip-packages", "none"],
                          capture_output=True, text=True, timeout=400)
    res_path = work / "probe_results.json"
    if not res_path.exists():
        return [f"{household.name}: HA didn't produce results (exit {proc.returncode}): {proc.stderr[-800:]}"]
    res = json.loads(res_path.read_text())
    fails += [f"{household.name}: probe error: {e}" for e in res["errors"]]
    for st in res["steps"]:
        label = st["step"].get("action") or st["step"].get("id") or st["step"].get("entity")
        if not st.get("ok"):
            fails.append(f"{household.name}: {label}: {st.get('error')}")
        if "check_off" in st["step"]:
            off = st["step"]["check_off"]
            offs = [c for c in st.get("calls", []) if c.split()[0] in ("remote.turn_off", "switch.turn_off", "media_player.turn_off")]
            if off and not any(off in c for c in offs):
                fails.append(f"{household.name}: {st['step']['screen']}: out of time but {off} wasn't turned off (calls: {st.get('calls')})")
            if not off and offs:
                fails.append(f"{household.name}: {st['step']['screen']}: turned something off without an off switch / in dry run: {offs}")
        for ent, want in st["expect"].items():
            got = st["states"].get(ent)
            if str(got) != str(want):
                fails.append(f"{household.name}: after {label}: {ent} = {got}, expected {want}")
    seed = res["after_seed"]
    for s in cfg["screens"]:
        got = seed.get(f"input_number.{s['id']}_free_minutes", {}).get("state")
        if got != f"{float(s['free_minutes'])}":
            fails.append(f"{household.name}: seed: {s['id']}_free_minutes = {got}, expected {s['free_minutes']}")
        if seed.get(f"input_boolean.{s['id']}_gate", {}).get("state") != "on":
            fails.append(f"{household.name}: seed: {s['id']}_gate not on")
    # unavailable kit entities after start = broken templates
    for eid, st in res["final"].items():
        obj = eid.split(".", 1)[1]
        mine = any(obj.startswith(p["id"] + "_") for p in cfg["people"]) or any(obj.startswith(s["id"] + "_") for s in cfg["screens"]) \
            or "motivator" in obj or obj.startswith(("household_", "chore_challenge", "bank_history"))
        if mine and st["state"] == "unavailable" and not eid.startswith(("automation.", "script.")):
            fails.append(f"{household.name}: {eid} is unavailable")
    cals = res.get("calendars", {})
    if not cals.get("calendar.bank_history"):
        fails.append(f"{household.name}: nothing written to Bank History")
    log = (work / "home-assistant.log").read_text()
    noise = ("kit_probe", "libturbojpeg", "alerts.home-assistant.io", "libpcap", "zlib_ng", "Skipping pip", "go2rtc", "cloud",
             "analytics", "Error fetching", "Cannot connect to host", "Error requesting")
    for line in log.splitlines():
        if re.search(r"\b(ERROR|WARNING)\b", line) and not any(n in line for n in noise):
            fails.append(f"{household.name}: log: {line[:300]}")
    (ROOT / "out").mkdir(exist_ok=True)
    shutil.copy(res_path, ROOT / "out" / f"smoke_{household.stem}.json")
    shutil.copy(work / "home-assistant.log", ROOT / "out" / f"smoke_{household.stem}.log")
    shutil.rmtree(work, ignore_errors=True)
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hass", required=True, help="path to the hass executable (pip install homeassistant)")
    ap.add_argument("households", nargs="*")
    a = ap.parse_args()
    files = [Path(h) for h in a.households] or sorted((ROOT / "tests/households").glob("*.yaml"))
    total = []
    for h in files:
        fails = run_one(a.hass, h)
        print(f"{'PASS' if not fails else 'FAIL'}  {h.name}")
        for f in fails:
            print("   ", f)
        total += fails
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
