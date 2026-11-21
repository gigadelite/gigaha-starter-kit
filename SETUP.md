# Setup

For a **fresh** Home Assistant (a new HA OS VM or a spare machine). Installing onto an existing,
lived-in server comes later; the build refuses to write into a `/config` it didn't create.

## 1. Before you build

1. Install Home Assistant OS and finish onboarding. Create a login for each adult; kids who'll use
   the dashboards get their own login without admin rights.
2. Install the **Home Assistant companion app** on every phone that will track steps and exercise.
   In the app: Settings › Companion App › Sensors › turn on the Health sensors (steps, exercise time).
   Note each phone's **device name** (Settings › Devices & services › Mobile App). That's the
   `phone:` value: `notify.mobile_app_<phone>`.
   *Don't log out and back in later:* that can rename the device and break notifications and the Health sensors.
3. Add the device integrations (Settings › Devices & services › Add integration):
   - **Nintendo Switch Parental Controls** for each Switch. Note the entity IDs of its
     *max screen time today* number, *suspend software* switch and *used screen time* sensor.
   - **Apple TV** for each Apple TV. Note the media player entity ID.
   - **Xbox** for each Xbox. On the console first: Settings › Devices & connections › Remote features
     › on. Note the media player and remote entity IDs. (If they don't appear, reload the integration.)
   - **PlayStation Network** for each PlayStation (sign in with an NPSSO token, ideally from a private
     browser window). **Don't log out of playstation.com afterwards:** that cancels the token and HA
     loses the console within a week. Note the console's media player entity ID.
     To let HA put a PS5 or PS4 in rest mode, also install the **PS5-MQTT** add-on (needs MQTT) and note
     its power switch. Without it, a PlayStation gets a time's-up warning instead.

## 2. Build

On any computer with Python 3.10+:

```
git clone <this repo> && cd gigaha-starter-kit
pip install pyyaml jinja2
cp household.example.yaml household.yaml
# edit household.yaml: people, phones, screens and their entity IDs, rules
python3 build.py --check          # finds mistakes without writing anything
python3 build.py                  # writes out/config/
```

Keep `dry_run: true` for now.

## 3. Install

1. Copy everything in `out/config/` (including the hidden `.gigaha_manifest.json`) into Home Assistant's
   `/config`, e.g. with the Samba share or Studio Code Server add-on. Replace the default `configuration.yaml`.
2. Developer Tools › YAML › **Check configuration**, then **Restart**.
3. Create three **Local Calendars** (Settings › Devices & services › Add integration › Local Calendar),
   named exactly: `Exercise Log`, `Chore Log`, `Bank History`. (Everything works without them; you
   just don't get the history.)
4. Open **Motivator**, **Log Activity** and **Motivator Settings** in the sidebar. The defaults from
   `household.yaml` (free time, caps, gates on) are applied once on the first start; after that the
   Settings dashboard owns them.

## 4. Go live

Watch it for a few days in dry run. Settings › System › Logs › Logbook shows what it *would* have done.
When the numbers look right: set `dry_run: false`, rebuild, copy, restart.

## Changing things later

Edit `household.yaml`, rebuild, copy `out/config/` over again, restart. The build only replaces files
it made last time. Keep a person's or screen's `id` the same forever: it's in every entity ID, and
changing it starts that person over.

| Change | After copying |
|---|---|
| Rules, chores, people, screens | Restart |
| Dashboards only | Refresh the browser |

## Known limits (0.1)

- Apple Health data needs the person's own iPhone with the companion app. A Family Setup Apple Watch
  (no iPhone) shares its data to the parent's Health app, which HA can't read as far as we know, so those kids log by hand.
- Anyone can log for anyone in Log Activity; the calendars are the audit trail.
- Week runs Sunday–Saturday (not configurable yet).
- The Switch limit is pushed every 5 minutes, so a game can run up to 5 minutes past a top-up being removed.
- Xbox and PlayStation are enforced by turning the console off (rest mode on PlayStation), not by
  their own family limits. A game may not save first, so the 15-minute warning matters.
- PlayStation time is polled every 30 seconds, so it can be up to a minute off.
- On every media screen, the home screen with nothing running doesn't count.
