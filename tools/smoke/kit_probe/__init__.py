"""Smoke-test probe for the GigaHA Starter Kit (used by tools/smoke_test.py only; never installed).

On startup it creates the three Local Calendars, waits for the seed automation, runs a
scripted scenario against the generated scripts/automations, dumps every state to
probe_results.json in the config dir, and stops Home Assistant.
"""
from __future__ import annotations

import asyncio
import json
import traceback
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN = "kit_probe"


async def async_setup(hass: HomeAssistant, config) -> bool:
    scenario = config.get(DOMAIN, {}).get("scenario", [])

    async def run(_event):
        out = {"steps": [], "errors": [], "calls": []}

        # Stand-ins for device actions the test server has no integration for: record the call instead
        async def fake(call):
            out["calls"].append({"action": f"{call.domain}.{call.service}", "data": dict(call.data)})
        for dom, svc in (("remote", "turn_off"), ("switch", "turn_off"), ("switch", "turn_on"),
                         ("media_player", "turn_off"), ("media_player", "media_pause"), ("number", "set_value")):
            if not hass.services.has_service(dom, svc):
                hass.services.async_register(dom, svc, fake)
        try:
            for name in ("Exercise Log", "Chore Log", "Bank History"):
                flow = await hass.config_entries.flow.async_init("local_calendar", context={"source": "user"})
                await hass.config_entries.flow.async_configure(flow["flow_id"], {"calendar_name": name})
            await asyncio.sleep(25)  # seed automation waits 15 s
            out["after_seed"] = snapshot(hass)
            for step in scenario:
                rec = {"step": step}
                try:
                    if step["do"] == "set":
                        domain = step["entity"].split(".")[0]
                        if domain == "input_select":
                            await hass.services.async_call(domain, "select_option", {"entity_id": step["entity"], "option": step["value"]}, blocking=True)
                        elif domain == "input_text":
                            await hass.services.async_call(domain, "set_value", {"entity_id": step["entity"], "value": step["value"]}, blocking=True)
                        else:
                            await hass.services.async_call(domain, "set_value", {"entity_id": step["entity"], "value": step["value"]}, blocking=True)
                    elif step["do"] == "state":
                        hass.states.async_set(step["entity"], step["value"], step.get("attributes", {}))
                    elif step["do"] == "calls_reset":
                        out["calls"].clear()
                    elif step["do"] == "call":
                        d, s = step["action"].split(".")
                        await hass.services.async_call(d, s, step.get("data", {}), blocking=True)
                    elif step["do"] == "automation":
                        ent = next(st.entity_id for st in hass.states.async_all("automation")
                                   if st.attributes.get("id") == step["id"])
                        await hass.services.async_call("automation", "trigger", {"entity_id": ent, "skip_condition": step.get("skip_condition", True)}, blocking=False)
                    await asyncio.sleep(step.get("wait", 2))
                    rec["ok"] = True
                except Exception as err:  # noqa: BLE001
                    rec["ok"] = False
                    rec["error"] = f"{type(err).__name__}: {err}"
                rec["states"] = {e: (hass.states.get(e).state if hass.states.get(e) else None) for e in step.get("expect", {})}
                rec["expect"] = step.get("expect", {})
                rec["calls"] = [c["action"] + " " + str(c["data"].get("entity_id")) for c in out["calls"]]
                out["steps"].append(rec)
            await asyncio.sleep(5)
            cal = await hass.services.async_call(
                "calendar", "get_events",
                {"entity_id": ["calendar.exercise_log", "calendar.chore_log", "calendar.bank_history"],
                 "start_date_time": (dt_util.now() - timedelta(days=3)).isoformat(),
                 "end_date_time": (dt_util.now() + timedelta(days=3)).isoformat()},
                blocking=True, return_response=True)
            out["calendars"] = {k: [e["summary"] for e in v["events"]] for k, v in cal.items()}
            out["final"] = snapshot(hass)
        except Exception:  # noqa: BLE001
            out["errors"].append(traceback.format_exc())
        await hass.async_add_executor_job(
            lambda: open(hass.config.path("probe_results.json"), "w").write(json.dumps(out, indent=1, default=str)))
        await hass.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, run)
    return True


def snapshot(hass):
    return {s.entity_id: {"state": s.state, "attributes": dict(s.attributes)} for s in hass.states.async_all()}
