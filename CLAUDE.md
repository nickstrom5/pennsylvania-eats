# Pennsylvania Eats (pa-eats): notes for Claude Code sessions

Started 2026-10-19 from `../state-prompts/PENNSYLVANIA_PROMPT.md`. Read `../STATE_EATS_PLAYBOOK.md`, that prompt and
`playbook/12-sources.md` first. Never modify other state folders. The pipeline is ported from `../ny-eats/`; the leaderboard page is
generated from `../ny-eats/site/index.html` (read-only) by `scripts/make-leaderboard.py`.

- **Web leaderboard** (`site/`): private artifact link in `LOCAL.md` (untracked). Uses Google 2021 ratings; the app never will.

## Data rules
- Official records stay in their jurisdiction: ACHD placards (Allegheny only, shown as official with the date, no computed grade);
  Philadelphia L&I licenses (existence only). PDA, Philadelphia DPH, Bucks and Montgomery portals are search-only: link, never scrape.
- WPRDC `/datastore/dump/` + `/api/` and the PLCB export are robots-blocked: Nick downloads them by hand into
  `data/raw/official/manual/` (`achd_current.csv`, `achd_history.csv`, `achd_violations.csv`, `achd_facilities.csv`, `plcb_licenses.csv`).
  `official._plcb` must be written against the export's real columns (show Premises only; never Licensee, Owner, Manager).
- Philadelphia `business_name` = "LEGAL (TRADE)": only the trade name is shown (`official._trade`).
- Members' clubs (VFW, Legion, fire company socials, ACHD "Social Club-Bar Only") and Wawa/Sheetz-type counters are flagged
  (`members`, `counter`) and hidden with the non-restaurants until Nick decides.
- guide.michelin.com is behind a bot challenge: never fetched. Research sources must pass `pipeline/check_sources.py`.

## Rebuild
```bash
cd pipeline
../.venv/bin/python fetch_official.py      # Philadelphia licenses, PDA 2018-20; reports which manual files are present
../.venv/bin/python fetch_overture.py      # Overture 2026-09-23.1 -> data/pa/overture_pa.parquet
../.venv/bin/python fetch_geo.py           # Census counties, municipalities, places
../.venv/bin/python official.py && ../.venv/bin/python listings.py && ../.venv/bin/python calibrate.py
../.venv/bin/python pennsylvania.py        # web leaderboard data -> site/pa-*.json   (PA_APP=1 for the app data)
../.venv/bin/python check_sources.py       # must report 0 unusable
cd .. && .venv/bin/python scripts/make-leaderboard.py
```
Preview: the `pa-eats-leaderboard` entry in `../.claude/launch.json` (port 8871).

## Outward actions need Nick's explicit yes, every time
Repos, pushes, Pages, App Store Connect, uploads, emails, data requests to agencies. Never submit for review. Support: nick@eatsranked.com.
