# Pennsylvania sources, coverage and calibration (checked 2026-10-19)

Every host was robots-checked with `pipeline/check_sources.py` (RFC 9309 matcher, agents ClaudeBot / Claude-User / anthropic-ai)
before the first request. Pipeline user agent: `pa-eats data pipeline (nick@eatsranked.com)`.

## Official records

| Source | What | Access | Terms | Cadence | Used for |
|---|---|---|---|---|---|
| City of Philadelphia L&I "Business Licenses" (OpenDataPhilly; Carto table `business_licenses` via `phl.carto.com/api/v2/sql`) | 15,015 food-type license rows (active + inactive since 2022/23). Active "Food Preparing and Serving" 4,322 + "(30+ SEATS)" 2,662 = 6,984 restaurant licenses; retail 1,471; carts 733; caterers 233 | robots.txt fences `/api/` only for Googlebot, Slurp, Yandex, msnbot, baiduspider; no `*` group: usable | City of Philadelphia open data | daily on paper; newest issue date 2026-10-18 (the old 2026-08-17 stall is over) | existence (tier "official"), add places the map lacks, closure flags |
| Allegheny County Health Department via WPRDC, package `allegheny-county-restaurant-food-facility-inspection-violations` (CC0) | current inspections `1c9cf8d8-…` (9,501 rows, 2025-08-11 to 2026-07-28; last ETL 2026-08-05; wiped each ETL), history `4ea730d8-…` (124,674 rows, 2014–Jul 2025), violations `1a1329e2-…` (stops 2025), facilities `112a3821-…` (32,245) | **robots.txt disallows `/api/` and `/datastore/dump/` for `*`** (the only download links). Never fetched by the pipeline. Before the robots read on 2026-10-19 this session made 4 metadata/sample requests to `/api/` (package_show + 3 one-row datastore_search); none since. | CC0 | "monthly" per WPRDC; actually stalled since 2026-08-05 | Allegheny placards, **waiting for Nick's hand download** into `data/raw/official/manual/achd_*.csv` |
| PLCB+ "CSV Download of All Licenses" (`plcbplus.pa.gov/pub/LicenseExport.aspx`) | 60,763 rows on 2026-09-27 per the prompt | **robots.txt disallows the export for our agents.** Never fetched. | PLCB | — | liquor licenses statewide, **waiting for Nick's hand download** into `data/raw/official/manual/plcb_licenses.csv` |
| PDA "Public Food Inspections last 24 months County Agriculture" (data.pa.gov `etb6-jzdg`, public domain) | 112,061 rows, 2018-03-01 to 2020-12-16 (rowsUpdatedAt 2020-03-31), no coordinates | Socrata API | public domain | dead since 2020 | calibration only, never shown |
| PA Food Safety Inspection Search (pafoodsafety.pa.gov) | PDA + ~100 local agencies incl. Philadelphia, Chester/Delaware/Erie county HDs, Allentown, Bethlehem, Easton, Harrisburg, Lancaster City | search-only (robots allows; we never scrape) | — | — | link only, with PDA's disclosure quoted verbatim |
| Philadelphia DPH (philadelphia-pa.healthinspections.us/philadelphia/), Bucks (bucks-pa.healthinspections.us), Montgomery (pa.healthinspections.us/montgomery/) | Tyler search portals | search-only; never scraped | — | — | link only |
| ACHD restaurant finder (webapps.achd.net/Restaurant/) | search | never scraped | — | — | link only |

PDA's disclosure, verbatim (pafoodsafety.pa.gov, fetched 2026-10-19): "Please remember that any inspection is a 'snapshot' of the day and time
of the inspection. An inspection conducted on any given day may not be representative of the overall, long-term cleanliness of an
establishment. Also, at the time of the inspection, violations are recorded but are often corrected on site prior to the inspector leaving
the establishment."

Philadelphia's `business_name` is usually "LEGAL ENTITY LLC (TRADE NAME)" and sometimes a person's name with the trade name in parentheses
("SHIYING LIU (PANDA HOUSE)"). `official._trade` shows only the parenthesized trade name; the outside part (legal or personal) is used for
matching only. `legalname`, `legalfirstname`, `legallastname`, `opa_owner`, `ownercontact*` and `business_mailing_address` are never
downloaded.

BLS QCEW: data.bls.gov's robots.txt disallows our agents, so QCEW isn't re-fetched; the prompt's numbers stand (26,686 private NAICS 722
establishments, 2025 average; Philadelphia 3,894, Allegheny 3,027, Montgomery 1,938, Bucks 1,368).

## Map listings

Overture Maps places 2026-09-23.1 (latest release on 2026-10-19), `addresses[1].region = 'PA'`: 645,413 places, 56,280 eating/drinking
categories. Google 2021 (UCSD Google Local `meta-Pennsylvania.json.gz`, web leaderboard only): 37,313 food listings, 27,393 matched.
Census cartographic boundaries 2025: 67 counties, 2,571 municipalities (963 boroughs, 1,545 townships, 56 cities, 6 "municipality",
1 town), 2,003 Census places.

## Calibration (data/pa/calibration.json)

Match = same name nearby, or same street address with a distinctive name word, or the only listing at the address of a license filed
under a legal or personal name.

Philadelphia active restaurant licenses (6,714 businesses), app grouping:

| Listing kind | Listings | Matched |
|---|---|---|
| Meta, confidence 0.95+ | 3,338 | 58.6% |
| Meta, 0.90–0.95 | 615 | 29.1% |
| Meta, below 0.90 | 844 | 19.2% |
| BrightQuery 0.95+ | 729 | 32.6% |
| Chain feeds (AllThePlaces/DAC) | 59 | 28.8% |
| other sources (Foursquare, Microsoft, low BrightQuery) | 3,067 | 14.4% |
| Overture says closed | 172 | 11.0% |

The map listings hold 42.3% of the licenses. The license list also holds schools, daycares, churches and corner stores (a Philadelphia
corner store with hot food holds "Food Preparing and Serving"), so these are floors, lower than NYC's 82% against DOHMH. PDA 2018–20
(statewide, stale) is reported for comparison: Meta 0.95+ 37%.

Keep rules (same as New York): app = official record or hand-checked or Meta ≥ 0.95 or a chain's own feed; web = Meta / chain feeds /
official / hand-checked, minus places Google showed closed in 2021 unless an official list confirms them.

## Build result (2026-10-19, web)

35,496 places, 34,255 restaurants (non-restaurants hidden by default: 528 stores, 425 venues, 7 betting, 191 members' clubs, 43
convenience counters). Regions: Philadelphia 5,969, Philly Suburbs 6,074, Pittsburgh Region 6,639, South Central 5,493, Northeast &
Poconos 3,470, Central 2,407, Lehigh Valley 1,769, Northwest 1,718, Northern Tier 716. 3,749 on an official list (Philadelphia only, until
the ACHD and PLCB files arrive), 985 of them added from the license list.

## Honors

- MICHELIN (Northeast Cities, Philadelphia's first selection 2025-11-18): guide.michelin.com answers robots.txt with an empty 202 (AWS
  WAF challenge), so it is never fetched (`check_sources.py` now treats that as a bot check). Stars + Green Star from MICHELIN's press
  release (michelinmedia.com); Bib Gourmands from a 2025-11-26 report; both agree with the prompt's Sept 27, 2026 list. 3 stars, 10 Bibs,
  Pietramala (Green Star). Recommended places in `data/research/app/LEADS.md`. Refresh after 2026-12-14.
- James Beard: Kalaya (2026 Outstanding Restaurant), Jesse Ito / Royal Sushi & Izakaya (2026 Best Chef: Mid-Atlantic), Oyster House (2026
  America's Classic; Sansom St since 1976), Phila Lorn / Mawn (2025 Emerging Chef).
- Hosts that block us (never cite): guide.michelin.com, pennlive.com, lancasteronline.com, 6abc.com, nbcphiladelphia.com,
  data.bls.gov; philadelphia.eater.com unreachable.
