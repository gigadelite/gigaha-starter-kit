"""Dashboard builders for the GigaHA Starter Kit.

Each builder returns a Lovelace config (dict) built only from core cards, so a fresh
Home Assistant needs no HACS or custom resources. build_all() returns
[{"meta": {...}, "config": {...}}] for build.py to write as YAML dashboards.
"""
from __future__ import annotations

THEME = "Copper Canyon"
ADMIN_THEME = "Ironworks"

URL_MOTIVATOR = "the-motivator"
URL_LOG = "log-activity"
URL_SETTINGS = "motivator-settings"


def _heading(text, icon=None):
    h = {"type": "heading", "heading": text}
    if icon:
        h["icon"] = icon
    return h


def _tile(entity, name=None, icon=None, color=None, **extra):
    t = {"type": "tile", "entity": entity}
    if name:
        t["name"] = name
    if icon:
        t["icon"] = icon
    if color:
        t["color"] = color
    t.update(extra)
    return t


def _button(name, icon, script, confirm=None, data=None):
    action = {"action": "perform-action", "perform_action": script}
    if data:
        action["data"] = data
    if confirm:
        action["confirmation"] = {"text": confirm}
    return {"type": "button", "name": name, "icon": icon, "show_state": False,
            "tap_action": action, "grid_options": {"columns": 6, "rows": 2}}


def _dry_run_banner():
    return {
        "type": "markdown",
        "content": "**Dry run is on.** Banks and limits are calculated but never applied to your devices. "
                   "Set `dry_run: false` in household.yaml and rebuild when you're ready.",
        "visibility": [{"condition": "state", "entity": "binary_sensor.motivator_dry_run", "state": "on"}],
    }


def _section(*cards, column_span=None):
    s = {"type": "grid", "cards": [c for c in cards if c]}
    if column_span:
        s["column_span"] = column_span
    return s


def _bank_history_md():
    return {
        "type": "markdown",
        "title": "Bank history (7 days)",
        "content": (
            "{% set ev = state_attr('sensor.bank_history_recent', 'events') or [] %}"
            "{% if not ev %}Nothing yet. Needs the **Bank History** Local Calendar.{% endif %}"
            "{% for e in ev %}**{{ as_timestamp(e.date) | timestamp_custom('%a %-m/%-d') }}** · {{ e.summary }}\n"
            "{% endfor %}"
        ),
    }


def motivator(cfg):
    people, screens, m = cfg["people"], cfg["screens"], cfg["m"]
    home_sections = []
    for s in screens:
        cards = [
            _heading(s["name"], s["icon"]),
            _tile(f"sensor.{s['id']}_minutes_left", "Time left today", "mdi:timer-outline", "deep-orange"),
            _tile(f"sensor.{s['id']}_banked", "Banked", "mdi:piggy-bank", "amber"),
            _tile(f"sensor.{s['id']}_earned_today", "Earned today", "mdi:heart-plus", "green"),
            _tile(f"sensor.{s['id']}_used_today", "Used today", s["icon"], "blue"),
        ]
        home_sections.append(_section(*cards))
    who = [_heading("Today", "mdi:account-group")]
    for p in people:
        who.append(_tile(f"sensor.{p['id']}_earned_today", p["name"], "mdi:account-heart", "deep-orange",
                         tap_action={"action": "navigate", "navigation_path": f"/{URL_MOTIVATOR}/{p['id']}"}))
    home_sections.append(_section(*who))
    extra = [_heading("This week", "mdi:trophy")]
    if cfg["challenge"]:
        extra.append({
            "type": "markdown",
            "title": "Chore Challenge",
            "content": (
                "{% set rows = state_attr('sensor.chore_challenge_leader', 'standings') or [] %}"
                "Leader: **{{ states('sensor.chore_challenge_leader') }}**\n\n"
                "{% for r in rows %}{{ loop.index }}. {{ r.name }} · {{ r.min }} min\n{% endfor %}"
                "\nMost chore minutes Sunday–Saturday wins. Exercise and steps don't count."
            ),
        })
    extra.append({
        "type": "markdown",
        "content": "{% set s = states('sensor.motivator_chore_owed') %}"
                   "{% if s not in ['None', 'unknown', 'unavailable'] %}🧹 **{{ s }}**{% endif %}",
        "visibility": [{"condition": "state", "entity": "sensor.motivator_chore_owed", "state_not": "None"}],
    })
    extra.append(_bank_history_md())
    home_sections.append(_section(*extra))

    views = [{
        "title": "Home",
        "path": "home",
        "icon": "mdi:home-heart",
        "type": "sections",
        "max_columns": 4,
        "theme": THEME,
        "badges": [],
        "header": {"card": _dry_run_banner()},
        "sections": home_sections,
    }]

    for p in people:
        pid = p["id"]
        today = [
            _heading(f"{p['name']} today", "mdi:calendar-today"),
            _tile(f"sensor.{pid}_earned_today", "Earned", "mdi:account-heart", "deep-orange"),
            _tile(f"sensor.{pid}_exercise_today", "Exercise", "mdi:run", "green"),
            _tile(f"sensor.{pid}_chores_daily", "Chores", "mdi:broom", "amber"),
        ]
        if p["tracking"] == "phone":
            today.append({
                "type": "markdown",
                "content": "{% set st = states('sensor." + pid + "_steps_today') | int(0) %}"
                           "{% set em = states('sensor." + pid + "_steps_earned_today') | int(0) %}"
                           "👟 **{{ (em // 60) ~ 'h ' if em >= 60 else '' }}{{ em % 60 }}m · {{ '{:,}'.format(st) }} steps**"
                           f"  \n<small>1 min per {m['steps_per_minute']} steps</small>",
            })
        today.append(_tile(f"sensor.{pid}_active_minutes_today", f"Active (needs {m['active_day_minutes']})",
                           "mdi:account-check", "teal"))
        week = [
            _heading("This week", "mdi:calendar-week"),
            _tile(f"sensor.{pid}_week_credits", f"Credits (need {m['credits_per_week']})", "mdi:calendar-check", "green"),
            _tile(f"counter.{pid}_streak_weeks", "Streak", "mdi:fire", "deep-orange"),
            _tile(f"sensor.{pid}_tokens_available", "Tokens", "mdi:ticket", "purple"),
            _tile(f"input_number.{pid}_best_streak_weeks", "Best streak", "mdi:trophy-outline", "amber"),
            _tile(f"sensor.{pid}_earned_week", "Earned this week", "mdi:sigma", "blue"),
            {"type": "markdown", "title": "Last week",
             "content": "{{ states('input_text." + pid + "_last_week') if states('input_text." + pid
                        + "_last_week') not in ['', 'unknown'] else 'Your first recap arrives Sunday at noon.' }}"},
        ]
        goes = ", ".join(f"{cfg['screens_by_id'][sid]['name']} {pct}%" for sid, pct in p["earn_to"].items())
        where = [
            _heading("Where it goes", "mdi:call-split"),
            {"type": "markdown",
             "content": f"Earned minutes go to **{goes}**. Streak bonuses go to "
                        f"**{cfg['screens_by_id'][p['bonus_to']]['name']}**."},
        ] + [_tile(f"sensor.{sid}_minutes_left", f"{cfg['screens_by_id'][sid]['name']} left today",
                   cfg["screens_by_id"][sid]["icon"], "deep-orange") for sid in p["earn_to"]]
        graph = _section({
            "type": "history-graph",
            "title": "Earned per day",
            "hours_to_show": 168,
            "entities": [{"entity": f"sensor.{pid}_earned_today", "name": "Earned"}],
        }, column_span=2)
        views.append({
            "title": p["name"],
            "path": pid,
            "icon": "mdi:account",
            "type": "sections",
            "max_columns": 4,
            "theme": THEME,
            "badges": [],
            "header": {"card": _dry_run_banner()},
            "sections": [_section(*today), _section(*week), _section(*where), graph],
        })
    return {"title": "Motivator", "views": views}


def log_activity(cfg):
    people = cfg["people"]
    exercise = _section(
        _heading("Log exercise", "mdi:run"),
        {"type": "entities", "entities": [
            "input_select.motivator_who", "input_select.motivator_exercise_type",
            "input_number.motivator_exercise_minutes", "input_text.motivator_note"]},
        _button("Add exercise", "mdi:plus-circle", "script.motivator_log_exercise"),
    )
    chores = _section(
        _heading("Log a chore", "mdi:broom"),
        {"type": "entities", "entities": [
            "input_select.motivator_who", "input_select.motivator_chore",
            "input_number.motivator_chore_minutes", "input_text.motivator_note"]},
        _button("Add chore", "mdi:plus-circle", "script.motivator_log_chore"),
    )
    tokens = _section(
        _heading("Use a token", "mdi:ticket"),
        {"type": "markdown", "content":
            f"A token counts as an active day. {cfg['m']['weekly_tokens']} free per week (use it or lose it) plus any you've won."},
        {"type": "entities", "entities": ["input_select.motivator_who", "input_text.motivator_token_reason"]},
        *[_tile(f"sensor.{p['id']}_tokens_available", p["name"], "mdi:ticket", "purple") for p in people],
        _button("Use token", "mdi:ticket-confirmation", "script.motivator_use_token",
                confirm="Use a token for the selected person?"),
    )
    fix = _section(
        _heading("Fix a mistake", "mdi:undo"),
        _tile("input_text.motivator_last_entry", "Last entry", "mdi:history"),
        _button("Undo last entry", "mdi:undo", "script.motivator_undo_last", confirm="Undo the last logged entry?"),
        {"type": "markdown",
         "content": "{% set s = states('sensor.motivator_chore_owed') %}{% if s != 'None' %}🧹 **{{ s }}**{% endif %}",
         "visibility": [{"condition": "state", "entity": "sensor.motivator_chore_owed", "state_not": "None"}]},
        dict(_button("Owed chore done", "mdi:check", "script.motivator_clear_chore_owed"),
             visibility=[{"condition": "state", "entity": "sensor.motivator_chore_owed", "state_not": "None"}]),
    )
    return {"title": "Log Activity", "views": [{
        "title": "Log", "path": "log", "icon": "mdi:pencil-plus", "type": "sections", "max_columns": 4,
        "theme": THEME, "badges": [], "header": {"card": _dry_run_banner()},
        "sections": [exercise, chores, tokens, fix],
    }]}


def settings(cfg):
    sections = []
    for s in cfg["screens"]:
        sid = s["id"]
        ents = [f"input_boolean.{sid}_gate", f"input_boolean.{sid}_free_enabled", f"input_number.{sid}_free_minutes",
                f"input_number.{sid}_bank_cap", f"input_number.{sid}_bank", f"input_number.{sid}_bonus_bank"]
        cards = [_heading(s["name"], s["icon"]), {"type": "entities", "entities": ents}]
        if s["type"] == "nintendo_switch":
            cards.append(_tile(f"sensor.{sid}_play_limit", "Limit HA sends", "mdi:timer-lock"))
            cards.append(_tile(s["entities"]["limit"], "Limit on the console", "mdi:nintendo-switch"))
        else:
            cards.append(_tile(f"sensor.{sid}_active_app", "Active app", "mdi:television-play"))
            cards.append(_button("Reconnect", "mdi:refresh", f"script.{sid}_reconnect"))
        sections.append(_section(*cards))
    sections.append(_section(
        _heading("Add or remove time", "mdi:timer-plus-outline"),
        {"type": "entities", "entities": ["input_select.motivator_quick_screen", "input_number.motivator_quick_minutes"]},
        _button("Add for today", "mdi:plus", "script.motivator_quick_add"),
        _button("Remove", "mdi:minus", "script.motivator_quick_remove", confirm="Remove time from this screen?"),
    ))
    house = [_heading("Household", "mdi:home-account"),
             _tile("binary_sensor.motivator_dry_run", "Dry run", "mdi:test-tube")]
    wh = [f"input_boolean.{p['id']}_count_work_hours" for p in cfg["people"] if p["work_hours"]]
    if wh:
        house.append({"type": "entities", "title": "Count exercise during work hours", "entities": wh})
    house.append({"type": "entities", "title": "Tokens and streaks", "entities": [
        e for p in cfg["people"] for e in (f"input_number.{p['id']}_extra_tokens", f"counter.{p['id']}_streak_weeks")]})
    house.append(_tile("input_datetime.motivator_last_rollover", "Last rollover", "mdi:calendar-check"))
    house.append(_button("Reset all banks", "mdi:piggy-bank-outline", "script.motivator_reset_banks",
                         confirm="Set every bank and bonus bank to 0?"))
    sections.append(_section(*house))
    return {"title": "Motivator Settings", "views": [{
        "title": "Settings", "path": "settings", "icon": "mdi:cog", "type": "sections", "max_columns": 4,
        "theme": ADMIN_THEME, "badges": [], "header": {"card": _dry_run_banner()}, "sections": sections,
    }]}


def build_all(cfg):
    out = []
    if cfg["modules"].get("motivator", True):
        out += [
            {"meta": {"url": URL_MOTIVATOR, "file": "motivator.yaml", "title": "Motivator", "icon": "mdi:trophy", "admin": False},
             "config": motivator(cfg)},
            {"meta": {"url": URL_LOG, "file": "log_activity.yaml", "title": "Log Activity", "icon": "mdi:pencil-plus", "admin": False},
             "config": log_activity(cfg)},
            {"meta": {"url": URL_SETTINGS, "file": "motivator_settings.yaml", "title": "Motivator Settings", "icon": "mdi:cog", "admin": True},
             "config": settings(cfg)},
        ]
    return out
