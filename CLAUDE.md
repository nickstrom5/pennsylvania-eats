# Pennsylvania Eats (pa-eats): notes for Claude Code sessions

Started 2026-10-19 from `../state-prompts/PENNSYLVANIA_PROMPT.md`. Read `../STATE_EATS_PLAYBOOK.md`, that prompt and
`playbook/12-sources.md` first. Never modify other state folders. The pipeline is ported from `../ny-eats/`; the leaderboard page is
generated from `../ny-eats/site/index.html` (read-only) by `scripts/make-leaderboard.py`.

- **Web leaderboard** (`site/`): private artifact link in `LOCAL.md` (untracked). Uses Google 2021 ratings; the app never will.
- **App**: "Pennsylvania Eats: Restaurants", subtitle "Cheesesteaks to Pierogies", Home Screen "PA Eats"; site pennsylvania.eatsranked.com.

## Nick's decisions (2026-10-19, `playbook/05-naming.md`)
- Name above; icon = salted soft pretzel in gold on hemlock (`scripts/icon-concepts.swift` concept A, passes the shared style check).
- Palette = Penn's Woods: hemlock #2E4E3F, barn red #A23B2A, cream #F6F1E7, gold #E8A33D only as a fill under near-black text.
- Members' clubs and convenience counters (Wawa, Sheetz...) stay hidden with the non-restaurants.

## Data rules
- Official records stay in their jurisdiction: ACHD placards (Allegheny only, shown as official with the date, no computed grade);
  Philadelphia L&I licenses (existence only). PDA, Philadelphia DPH, Bucks and Montgomery portals are search-only: link, never scrape.
- WPRDC `/datastore/dump/` + `/api/` and the PLCB export are robots-blocked: Nick downloads them by hand into
  `data/raw/official/manual/` (`achd_current.csv`, `achd_history.csv`, `achd_violations.csv`, `achd_facilities.csv`, `plcb_licenses.csv`).
  `official._plcb` must be written against the export's real columns (show Premises only; never Licensee, Owner, Manager).
- Philadelphia `business_name` = "LEGAL (TRADE)": only the trade name is shown (`official._trade`).
- Members' clubs (VFW, Legion, fire company socials, ACHD "Social Club-Bar Only") and Wawa/Sheetz-type counters are flagged
  (`members`, `counter`) and hidden with the non-restaurants (Nick's call, 2026-10-19).
- guide.michelin.com is behind a bot challenge: never fetched. Research sources must pass `pipeline/check_sources.py`.
- Hijacked pages: `check_websites.py` runs `pipeline/injection.py` (identical to `../wi-eats/pipeline/injection.py`; `test_injection.py`
  must pass). `--recheck-ok` re-fetches every passing page before a release, `--retry-transient` the 429s and connection errors;
  `CHECK_WORKERS=4` slows a run. Saves are atomic; still back up `data/pa/website_check.json` before stopping a run.
  `pipeline/website_blocklist.json` drops known-bad links from the app, leaderboard and website.

## Waiting on Nick's hand-downloaded files (`data/raw/official/manual/`)
Everything below stays empty or hidden until the WPRDC ACHD CSVs and the PLCB export are there; then rerun from `official.py` down.
- ACHD placards in the app, website (`HAS_ACHD` in `scripts/make-site.py` turns the Allegheny copy on) and leaderboard.
- `official._plcb`: write it against the export's real columns (Premises only), then liquor licenses everywhere.
- Allegheny calibration (`calibrate.py`) and the leaderboard's Allegheny board.
- ACHD's "records through" date (`official.records_through`, from the files' own dates).

## Rebuild
```bash
cd pipeline
../.venv/bin/python fetch_official.py      # Philadelphia licenses, PDA 2018-20; reports which manual files are present
../.venv/bin/python fetch_overture.py      # Overture 2026-09-23.1 -> data/pa/overture_pa.parquet
../.venv/bin/python fetch_geo.py           # Census counties, municipalities, places
../.venv/bin/python official.py && ../.venv/bin/python listings.py && ../.venv/bin/python calibrate.py
../.venv/bin/python pennsylvania.py        # web leaderboard data -> site/pa-*.json   (PA_APP=1 for the app data)
../.venv/bin/python check_sources.py       # must report 0 unusable
../.venv/bin/python check_websites.py --recheck-ok   # every candidate link (hours); then rerun PA_APP=1 pennsylvania.py
cd .. && .venv/bin/python scripts/make-leaderboard.py
rm PennsylvaniaEats/Resources/Data/places-*.json && cp data/app/index.json data/app/places-*.json PennsylvaniaEats/Resources/Data/
.venv/bin/python scripts/export-glyphs.py         # the app's food glyphs -> scripts/glyphs.json (site icons)
.venv/bin/python scripts/make-site.py && .venv/bin/python scripts/qa-site.py   # website + web app in docs/, then headless QA
```
`make-site.py` gives a guide a page and a Home card only with 4+ hand-checked places (pierogies, pretzels and diners are short), and
the oldest-restaurants page only with 3+ dated places. `CUSTOM_DOMAIN` stays "" until Nick's `pennsylvania` CNAME exists.
Preview: the `pa-eats-leaderboard` entry in `../.claude/launch.json` (port 8871).

## Outward actions need Nick's explicit yes, every time
Repos, pushes, Pages, App Store Connect, uploads, emails, data requests to agencies. Never submit for review. Support: nick@eatsranked.com.
