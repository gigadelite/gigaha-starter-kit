#!/usr/bin/env python3
"""GigaHA Starter Kit generator.

Reads household.yaml (or the file given with -c) and writes a complete Home Assistant
config to out/config/ (or -o). Copy that folder's contents into /config, check the
configuration, and restart.

    python3 build.py                       # household.yaml -> out/config
    python3 build.py -c tests/households/family6.yaml -o out/family6
    python3 build.py --check               # validate household.yaml only

Needs Python 3.10+ with PyYAML and Jinja2 (pip install pyyaml jinja2).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "kit"
sys.path.insert(0, str(KIT))
import dashboards  # noqa: E402  (kit/dashboards.py)

KIT_VERSION = "0.2.0"
UID = "gigaha"  # prefix for every unique_id / automation id the kit creates

ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# type: (required entities, optional entities)
SCREEN_TYPES = {
    "nintendo_switch": (["limit", "suspend", "used"], []),
    "apple_tv": (["media_player"], []),
    "xbox": (["media_player"], ["remote"]),
    "playstation": (["media_player"], ["power"]),
}
MEDIA = {  # how media-player screens are read and turned off
    "apple_tv": {"icon": "mdi:television", "on_states": ["playing", "paused", "idle", "on"], "app_attrs": ["app_name"],
                 "off_key": "media_player", "off_how": "pause and put the Apple TV to sleep"},
    "xbox": {"icon": "mdi:microsoft-xbox", "on_states": ["playing", "paused", "idle", "on"],
             "app_attrs": ["app_name", "media_title"], "off_key": "remote", "off_how": "pause and turn the Xbox off"},
    "playstation": {"icon": "mdi:sony-playstation", "on_states": ["playing", "paused", "on"],
                    "app_attrs": ["app_name", "media_title"], "off_key": "power", "off_how": "put the PlayStation in rest mode"},
}
ROLES = ("admin", "member", "child")

DEFAULTS = {
    "household": {"name": "Our House", "dry_run": True},
    "motivator": {
        "steps_per_minute": 200,
        "active_day_minutes": 30,
        "credits_per_week": 5,
        "weekly_tokens": 1,
        "streak_bonus": [30, 60, 90, 120],
        "streak_bonus_after": 60,
        "streak_bonus_every_4th": 120,
        "challenge_prize_minutes": 60,
        "challenge_pick_hours": 20,
    },
    "chores": [{"name": n, "minutes": mins} for n, mins in [
        ("Dishes", 15), ("Clean kitchen", 30), ("Clean bathroom", 30), ("Sweep / vacuum", 20), ("Mop floors", 20),
        ("Laundry (wash/dry)", 15), ("Fold / put away laundry", 15), ("Tidy / declutter", 15),
        ("Dust / wipe surfaces", 15), ("Change bed sheets", 10), ("Trash / recycling", 5), ("Cook a meal", 30),
        ("Meal prep", 45), ("Grocery shopping", 45), ("Mow lawn", 45), ("Yard work / weeding", 30),
        ("Feed / walk pets", 15), ("Homework help", 30), ("Errands", 30), ("Other", 15)]],
    "exercise_types": ["Walk", "Bike", "Run", "Swim", "Strength / Workout", "Yoga / Stretch", "Sports / Play", "Other"],
    "modules": {"motivator": True},
}


class ConfigError(Exception):
    pass


def _hhmm(value, where):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value))
    if not m or int(m[1]) > 24 or int(m[2]) > 59:
        raise ConfigError(f"{where}: time must look like 09:00, got {value!r}")
    return int(m[1]) * 60 + int(m[2])


def load(path: Path) -> dict:
    """Load household.yaml, apply defaults, validate, and derive everything templates need."""
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        raise ConfigError(f"{path} not found. Copy household.example.yaml to household.yaml first.")
    errors: list[str] = []
    cfg = copy.deepcopy(DEFAULTS)
    for key, val in raw.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    hh = cfg["household"]
    hh["dry_run"] = bool(hh.get("dry_run", True))
    m = cfg["motivator"]

    # ---- screens ----
    screens = cfg.get("screens") or []
    if not screens:
        errors.append("screens: add at least one screen (a Switch or an Apple TV)")
    seen: set[str] = set()
    for i, s in enumerate(screens):
        where = f"screens[{i}]"
        sid = s.get("id", "")
        if not ID_RE.match(str(sid)):
            errors.append(f"{where}: id must be lowercase letters/numbers/_ (got {sid!r})")
        if sid in seen:
            errors.append(f"{where}: duplicate id {sid!r}")
        seen.add(sid)
        s.setdefault("name", str(sid).replace("_", " ").title())
        if s.get("type") not in SCREEN_TYPES:
            errors.append(f"{where}: type must be one of {', '.join(SCREEN_TYPES)}")
            continue
        media = MEDIA.get(s["type"])
        s.setdefault("icon", media["icon"] if media else "mdi:nintendo-switch")
        ents = s.get("entities") or {}
        required, optional = SCREEN_TYPES[s["type"]]
        for k in required:
            if not ents.get(k):
                errors.append(f"{where}.entities: {k} is required for {s['type']}")
        for k in ents:
            if k not in required + optional:
                errors.append(f"{where}.entities: {k!r} isn't used by {s['type']} (use {', '.join(required + optional)})")
        s["entities"] = ents
        s["media"] = bool(media)
        if media:
            s["on_states"] = media["on_states"]
            s["app_attrs"] = media["app_attrs"]
            s["off_entity"] = ents.get(media["off_key"])
            s["off_how"] = media["off_how"]
        else:
            s["off_entity"] = ents.get("suspend")
            s["off_how"] = "lower the console's daily limit"
        s["exempt_apps"] = [str(a) for a in (s.get("exempt_apps") or [])]
        s["free_minutes"] = int(s.get("free_minutes", 0))
        s["bank_cap"] = int(s.get("bank_cap", 180))
        if not 30 <= s["bank_cap"] <= 600:
            errors.append(f"{where}: bank_cap must be 30-600 minutes")
        if not 0 <= s["free_minutes"] <= 240:
            errors.append(f"{where}: free_minutes must be 0-240")
    screens_by_id = {s.get("id"): s for s in screens}

    # ---- people ----
    people = cfg.get("people") or []
    if not people:
        errors.append("people: add at least one person")
    pseen: set[str] = set()
    for i, p in enumerate(people):
        where = f"people[{i}]"
        pid = p.get("id", "")
        if not ID_RE.match(str(pid)):
            errors.append(f"{where}: id must be lowercase letters/numbers/_ (got {pid!r})")
        if pid in pseen or pid in screens_by_id:
            errors.append(f"{where}: id {pid!r} is already used by another person or screen")
        if pid in ("household", "motivator", "chore", "bank"):
            errors.append(f"{where}: id {pid!r} is reserved; pick another")
        pseen.add(pid)
        p.setdefault("name", str(pid).title())
        p["role"] = p.get("role", "member")
        if p["role"] not in ROLES:
            errors.append(f"{where}: role must be admin, member or child")
        p["tracking"] = p.get("tracking", "phone" if p.get("phone") else "manual")
        if p["tracking"] not in ("phone", "manual"):
            errors.append(f"{where}: tracking must be phone or manual")
        if p["tracking"] == "phone" and not p.get("phone"):
            errors.append(f"{where}: tracking: phone needs phone: <companion app device name>")
        phone = p.get("phone")
        hs = p.get("health_sensors") or {}
        p["health"] = {
            "steps": hs.get("steps", f"sensor.{phone}_health_steps"),
            "exercise": hs.get("exercise", f"sensor.{phone}_exercise_time"),
        }
        earn = {str(k): float(v) for k, v in (p.get("earn_to") or {}).items()}
        if not earn and len(screens) == 1:
            earn = {screens[0].get("id"): 100.0}
        if not earn:
            errors.append(f"{where}: earn_to is required when there's more than one screen")
        for k in earn:
            if k not in screens_by_id:
                errors.append(f"{where}.earn_to: {k!r} isn't a screen id ({', '.join(screens_by_id)})")
        if earn and abs(sum(earn.values()) - 100) > 0.01:
            errors.append(f"{where}.earn_to: shares add up to {sum(earn.values()):g}, need 100")
        p["earn_to"] = {k: (int(v) if v == int(v) else v) for k, v in earn.items() if v > 0}
        p["bonus_to"] = p.get("bonus_to") or (max(p["earn_to"], key=p["earn_to"].get) if p["earn_to"] else None)
        if p["bonus_to"] and p["bonus_to"] not in screens_by_id:
            errors.append(f"{where}: bonus_to {p['bonus_to']!r} isn't a screen id")
        p["notify_parents"] = bool(p.get("notify_parents", p["role"] == "child" and not phone))
        wh = p.get("work_hours")
        if wh:
            if p["tracking"] != "phone":
                errors.append(f"{where}: work_hours only applies to tracking: phone")
            days = [str(d).lower()[:3] for d in wh.get("days", DAYS[:5])]
            bad = [d for d in days if d not in DAYS]
            if bad:
                errors.append(f"{where}.work_hours.days: unknown day(s) {bad}")
            try:
                start = _hhmm(wh.get("start", "09:00"), f"{where}.work_hours.start")
                end = _hhmm(wh.get("end", "17:00"), f"{where}.work_hours.end")
                if end <= start:
                    errors.append(f"{where}.work_hours: end must be after start")
            except ConfigError as e:
                errors.append(str(e))
                start, end = 540, 1020
            p["work_hours"] = {"days": days, "start": wh.get("start", "09:00"), "end": wh.get("end", "17:00"),
                               "day_nums": [DAYS.index(d) for d in days if d in DAYS], "start_min": start, "end_min": end}
        else:
            p["work_hours"] = None
    if people and not any(p.get("role") == "admin" for p in people):
        errors.append("people: at least one person needs role: admin")
    names = [p.get("name") for p in people]
    if len(set(names)) != len(names):
        errors.append("people: names must be unique (they're used in the Who picker)")

    # ---- motivator / chores ----
    for k in ("steps_per_minute", "active_day_minutes", "credits_per_week", "weekly_tokens",
              "streak_bonus_after", "streak_bonus_every_4th", "challenge_prize_minutes", "challenge_pick_hours"):
        try:
            m[k] = int(m[k])
        except (TypeError, ValueError):
            errors.append(f"motivator.{k} must be a whole number")
    if not 1 <= m.get("credits_per_week", 5) <= 7:
        errors.append("motivator.credits_per_week must be 1-7")
    if not 1 <= m.get("challenge_pick_hours", 20) <= 99:
        errors.append("motivator.challenge_pick_hours must be 1-99")
    m["streak_bonus"] = [int(x) for x in m["streak_bonus"]] or [30]
    chores = cfg.get("chores") or []
    if not chores:
        errors.append("chores: add at least one chore")
    for c in chores:
        c["minutes"] = int(c.get("minutes", 15))
    if len({c["name"] for c in chores}) != len(chores):
        errors.append("chores: names must be unique")

    if errors:
        raise ConfigError("household.yaml has problems:\n  - " + "\n  - ".join(errors))

    # ---- derived ----
    admins = [p for p in people if p["role"] == "admin"]
    admin_svcs = [f"notify.mobile_app_{p['phone']}" for p in admins if p.get("phone")]
    routes = {}
    for p in people:
        svcs = [f"notify.mobile_app_{p['phone']}"] if p.get("phone") else []
        if p["notify_parents"]:
            svcs += [s for s in admin_svcs if s not in svcs]
        routes[p["id"]] = svcs
    for s in screens:
        s["earners"] = [p for p in people if s["id"] in p["earn_to"]]
        s["earner_ids"] = [p["id"] for p in s["earners"]] or [p["id"] for p in admins]

    cfg.update(
        people=people,
        screens=screens,
        screens_by_id=screens_by_id,
        chores=chores,
        m=m,
        dry_run=hh["dry_run"],
        uid=UID,
        kit_version=KIT_VERSION,
        routes=routes,
        admin_ids=[p["id"] for p in admins],
        people_ids=[p["id"] for p in people],
        name_to_id={p["name"]: p["id"] for p in people},
        id_to_name={p["id"]: p["name"] for p in people},
        screen_name_to_id={s["name"]: s["id"] for s in screens},
        chore_defaults={c["name"]: c["minutes"] for c in chores},
        challenge=len(people) >= 2,
        streak_items=[{"p": p["id"], "name": p["name"], "screen": p["bonus_to"],
                       "screen_name": screens_by_id[p["bonus_to"]]["name"]} for p in people],
        recap_items=[{"p": p["id"], "name": p["name"], "steps": p["tracking"] == "phone"} for p in people],
    )
    return cfg


def work_expr(p: dict) -> str:
    wh = p.get("work_hours")
    if not wh:
        return "false"
    return (f"is_state('input_boolean.{p['id']}_count_work_hours', 'off') and now().weekday() in {wh['day_nums']}"
            f" and {wh['start_min']} <= now().hour * 60 + now().minute < {wh['end_min']}")


def env() -> Environment:
    e = Environment(
        loader=FileSystemLoader(str(KIT / "templates")),
        block_start_string="<%", block_end_string="%>",
        variable_start_string="<<", variable_end_string=">>",
        comment_start_string="<#", comment_end_string="#>",
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    e.globals["work_expr"] = work_expr
    e.policies["json.dumps_kwargs"] = {"sort_keys": False, "ensure_ascii": False}
    return e


class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_rep)


def dump_yaml(obj) -> str:
    return yaml.dump(obj, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=200)


def build(cfg: dict, out: Path) -> list[Path]:
    # Remove only files the previous build wrote (listed in the manifest); never touch anything else,
    # so it's safe to build straight into a /config that has your own packages and dashboards.
    manifest = out / ".gigaha_manifest.json"
    if manifest.exists():
        for rel in json.loads(manifest.read_text()).get("files", []):
            (out / rel).unlink(missing_ok=True)
    elif (out / "configuration.yaml").exists():
        raise SystemExit(f"{out} already has a configuration.yaml the kit didn't write. Build into an empty folder "
                         "(or a /config the kit created) so nothing of yours gets overwritten.")
    (out / "packages").mkdir(parents=True, exist_ok=True)
    (out / "dashboards").mkdir(exist_ok=True)
    (out / "themes").mkdir(exist_ok=True)
    e = env()
    written: list[Path] = []

    def write(rel: str, text: str):
        path = out / rel
        path.write_text(text)
        written.append(path)

    dash = dashboards.build_all(cfg)
    cfg["dashboards"] = [d["meta"] for d in dash]
    write("configuration.yaml", e.get_template("configuration.yaml.j2").render(**cfg))
    for f in ("automations.yaml", "scripts.yaml", "scenes.yaml"):
        if not (out / f).exists():
            write(f, "[]\n" if f == "automations.yaml" else "")
    if cfg["modules"].get("motivator", True):
        write("packages/motivator_household.yaml", e.get_template("packages/motivator_household.yaml.j2").render(**cfg))
        for p in cfg["people"]:
            write(f"packages/motivator_person_{p['id']}.yaml",
                  e.get_template("packages/motivator_person.yaml.j2").render(**cfg, p=p))
        for s in cfg["screens"]:
            write(f"packages/motivator_screen_{s['id']}.yaml",
                  e.get_template("packages/motivator_screen.yaml.j2").render(**cfg, s=s))
    header = f"# GENERATED by the GigaHA Starter Kit {KIT_VERSION} from household.yaml. Rebuild instead of editing.\n"
    for d in dash:
        write(f"dashboards/{d['meta']['file']}", header + dump_yaml(d["config"]))
    for t in sorted((KIT / "themes").glob("*.yaml")):
        shutil.copy(t, out / "themes" / t.name)
        written.append(out / "themes" / t.name)
    manifest.write_text(json.dumps({"kit_version": KIT_VERSION,
                                    "files": sorted(str(p.relative_to(out)) for p in written
                                                    if p.name not in ("automations.yaml", "scripts.yaml", "scenes.yaml"))},
                                   indent=1))
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default="household.yaml", help="household file (default household.yaml)")
    ap.add_argument("-o", "--out", default="out/config", help="output folder (default out/config)")
    ap.add_argument("--check", action="store_true", help="validate the household file and stop")
    a = ap.parse_args()
    try:
        cfg = load(Path(a.config))
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    if a.check:
        print(f"{a.config}: OK ({len(cfg['people'])} people, {len(cfg['screens'])} screens)")
        return 0
    written = build(cfg, Path(a.out))
    mode = "DRY RUN (limits logged, not applied)" if cfg["dry_run"] else "LIVE (limits applied)"
    print(f"Built {len(written)} files in {a.out}: {len(cfg['people'])} people, {len(cfg['screens'])} screens, {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
