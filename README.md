# GigaHA Starter Kit

A Home Assistant setup you generate from one file. Describe your household in `household.yaml`
(people, phones, consoles and TVs, house rules), run `build.py`, and you get a complete
`/config`: packages, dashboards and themes, with nobody's personal details baked in.

The first module is **The Motivator**: screen time has to be earned. Exercise, chores and
steps earn minutes into a bank for each screen (a Nintendo Switch, an Apple TV), and Home
Assistant spends from it: it sets the Switch's daily limit and puts the Apple TV to sleep when time
runs out.

> **Status: 0.1, beta.** The Motivator core is built and tested on a real (headless) Home Assistant
> 2026.2 with 1-, 3- and 6-person households. The dashboards use only built-in cards and haven't been
> looked at in a browser yet. Start with `dry_run: true`.

## How it works

```
household.yaml ──► build.py ──► out/config/
                                 ├─ configuration.yaml
                                 ├─ packages/motivator_household.yaml
                                 ├─ packages/motivator_person_<id>.yaml   (one per person)
                                 ├─ packages/motivator_screen_<id>.yaml   (one per screen)
                                 ├─ dashboards/*.yaml                     (YAML-mode dashboards)
                                 └─ themes/
```

- **Any number of people.** Each is an `admin`, `member` or `child`, and tracks with a `phone`
  (Apple Health steps and exercise minutes from the HA companion app) or `manual` (logs by hand,
  e.g. a kid whose Apple Watch is on Family Setup).
- **Any number of screens.** Each has its own bank, free daily time, bank cap and on/off gate.
- **Each person splits their earnings** across screens (`earn_to: {switch: 70, tv: 30}`), and has
  a screen for their streak bonuses.
- **Notifications are routed:** to the person's phone, and for children without a phone (or with
  `notify_parents: true`) to the admins too. A phone that isn't set up yet is skipped quietly.
- **Dry run:** everything is calculated and logged to the logbook ("would set the Switch limit to
  95 min"), nothing is applied. Use it while you get comfortable, and on any test server that shares
  devices with a real one.
- **Rebuild any time.** The build only replaces files it wrote last time (`.gigaha_manifest.json`),
  so your own packages, automations and UI dashboards are left alone. Don't edit generated files;
  change `household.yaml` and rebuild.

## The Motivator rules (defaults; all in `household.yaml › motivator`)

| | |
|---|---|
| Earning | Exercise 1:1, chores 1:1, steps 1 min per 200 |
| Active day | 30+ min of your own exercise + chores (steps don't count) |
| Successful week | 5 credits (active days + tokens). 1 free token a week, plus any won |
| Streak bonus | Weeks 1–4: 30/60/90/120 min, then 60 a week, 120 every 4th week |
| Chore Challenge | Most chore minutes Sun–Sat wins (2+ people). Winner picks from their phone: 60 min bonus, last place does a chore, or an extra token |
| Banks | Unused minutes roll over nightly; bonus minutes are never capped, regular ones up to the cap |
| Work hours | Optional per person: Apple Health exercise during work hours doesn't count (with a switch to count it anyway) |

Schedule: 11:58 PM active days counted · 11:59 PM banks roll over · Saturday 11:59:30 PM streaks
settled · Sunday 12:01 AM new week · Sunday noon Chore Challenge · Sunday 12:05 PM recap to everyone.

## Dashboards

| Dashboard | Who | What |
|---|---|---|
| Motivator (`/the-motivator`) | everyone | Home: each screen's time left, bank, earned and used; everyone's earned today; Chore Challenge; bank history. One page per person: today, this week, streak, tokens, where their minutes go |
| Log Activity (`/log-activity`) | everyone | Log exercise, log a chore (default minutes fill in), use a token, undo the last entry |
| Motivator Settings (`/motivator-settings`) | admins only | Per screen: gate, free time, cap, banks. Add/remove time today, work-hours switches, tokens, reset banks |

## Quick start

See **[SETUP.md](SETUP.md)**. In short: copy `household.example.yaml` to `household.yaml`, edit it,
`python3 build.py`, copy `out/config/` to a fresh Home Assistant, create three Local Calendars,
restart.

## Repo layout

```
household.example.yaml     # start here (copy to household.yaml, which git ignores)
build.py                   # the generator
kit/templates/             # package templates (build-time tags are << >> and <% %>; {{ }} is left for HA)
kit/dashboards.py          # dashboard builders (core cards only)
kit/themes/                # Copper Canyon, Ironworks
tests/households/          # 1-, 3- and 6-person test households
tools/check.sh             # build every test household, run HA's config check, scan for leaks
tools/smoke_test.py        # boot real HA on each test household and run the Motivator through a scenario
tools/leakscan.py          # fails if anything personal leaks in (names are stored only as hashes)
```

## Roadmap

1. **Motivator core** ✅ (this release)
2. **Home + ops:** Main Dash hub, Lights (builds itself from Areas), Maintenance (GitHub pull/backup, inventory, security, speed test), to-do inbox
3. **Media:** TV guide, Switch hub, Music (Music Assistant), screen-time stats
4. **Life admin:** Foodie (Mealie), Money (SimpleFIN), Community calendars, Lockbox, chores planner
5. **Infrastructure profiles:** `ha_only` (add-ons) or `homelab` (Proxmox containers, reverse proxy, Pocket ID SSO)
6. **Advanced:** NanoMDM for supervised family iPhones (web clips to dashboards, Wi-Fi, restrictions)
7. **Private add-on modules** for things that only make sense for one household, switched on from that household's `household.yaml`

## Testing

```
pip install pyyaml jinja2 homeassistant==2026.2.3   # homeassistant only for the checks
tools/check.sh                                     # fast: build + HA config check + leak scan
python3 tools/smoke_test.py --hass $(which hass)   # slow: boots HA for each test household
```
