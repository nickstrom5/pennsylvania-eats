"""Official Pennsylvania records -> data/raw/official/

Fetched here (robots.txt checked first with check_sources.py; one request at a time, an honest user agent):
- philly_licenses.csv   City of Philadelphia L&I "Business Licenses" (OpenDataPhilly; Carto table `business_licenses`, phl.carto.com
                        SQL API). Food license types only, every status (inactive and closed ones only flag closures). Columns:
                        trade name (`business_name`), address, license type/status and dates, point, OPA account. Never downloaded:
                        `legalname`, `legalfirstname`, `legallastname`, `opa_owner`, `ownercontact*` and `business_mailing_address`.
- pda_2018_2020.csv     PA Department of Agriculture "Public Food Inspections last 24 months County Agriculture" (data.pa.gov
                        etb6-jzdg, public domain), last updated 2020-03-31. Calibration only: never shown as a current result.
- carto_meta.json, socrata_meta.json   each feed's own refresh stamp (records-through dates come from these)

Downloaded by Nick in his browser (robots.txt fences these paths for every crawler, so the pipeline never fetches them):
- manual/achd_current.csv      WPRDC "Food Facility/Restaurant Inspections" (1c9cf8d8-..., /datastore/dump/), CC0
- manual/achd_history.csv      WPRDC "Food Facility/Restaurant Inspections (2014-2025)" (4ea730d8-...)
- manual/achd_violations.csv   WPRDC "Food Facility/Restaurant Inspection Violations (2014-2025)" (1a1329e2-...)
- manual/achd_facilities.csv   WPRDC "Geocoded Food Facilities (as of 2025)" (112a3821-...)
- manual/plcb_licenses.csv     PLCB+ "CSV Download of All Licenses" (plcbplus.pa.gov/pub/LicenseExport.aspx)
official.py reads them when they're there and says so when they're not.
"""
import os, io, csv, json, time, sys
import requests

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "official")
os.makedirs(f"{OUT}/manual", exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "pa-eats data pipeline (nick@eatsranked.com)"
ONLY = set(sys.argv[1:])
want = lambda n: not ONLY or n in ONLY
t = time.time()

FOOD_TYPES = ("Food Preparing and Serving", "Food Preparing and Serving (30+ SEATS)", "Food Caterer",
              "Food Establishment, Retail Permanent Location", "Food Establishment, Retail Perm Location (Large)",
              "Food Estab, Retail Non-Permanent Location (Annual)", "Food Establishment, Outdoor")
COLS = ("licensenum, licensetype, licensestatus, business_name, address, unit_type, unit_num, zip, initialissuedate, mostrecentissuedate, "
        "expirationdate, inactivedate, revenuecode, opa_account_num, parcel_id_num, council_district, censustract, "
        "ST_Y(the_geom) AS lat, ST_X(the_geom) AS lon")


def carto(q):
    for attempt in range(4):
        try:
            r = S.get("https://phl.carto.com/api/v2/sql", params={"q": q, "format": "csv"}, timeout=300)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == 3:
                raise
            print("  retry", e, flush=True); time.sleep(10 * (attempt + 1))


if want("philly"):
    types = ", ".join("'" + x.replace("'", "''") + "'" for x in FOOD_TYPES)
    txt = carto(f"SELECT {COLS} FROM business_licenses WHERE licensetype IN ({types}) "
                f"AND (licensestatus = 'Active' OR mostrecentissuedate >= '2022-01-01' OR inactivedate >= '2023-01-01') ORDER BY licensenum")
    open(f"{OUT}/philly_licenses.csv", "w").write(txt)
    rows = list(csv.DictReader(io.StringIO(txt)))
    time.sleep(1)
    # the table's own freshness: the newest issue date in it (Carto exposes no refresh stamp for the table)
    newest = carto("SELECT max(mostrecentissuedate) AS newest, max(initialissuedate) AS newest_initial FROM business_licenses WHERE mostrecentissuedate <= now() AND initialissuedate <= now()")
    m = list(csv.DictReader(io.StringIO(newest)))[0]
    json.dump({"business_licenses": {"fetched": time.strftime("%Y-%m-%d"), **m}}, open(f"{OUT}/carto_meta.json", "w"), indent=1)
    print(f"philly licenses: {len(rows):,} rows | newest issue {m} ({round(time.time() - t)} s)", flush=True)

if want("pda2020"):
    r = S.get("https://data.pa.gov/resource/etb6-jzdg.csv", params={"$limit": 200000, "$select": "organization_name,active_indicator,"
              "public_facility_name,program_group_type,address,city,county_name,zip_code,inspection_date,inspection_reason_type,"
              "overall_compliance,geocoded_column"}, timeout=300)
    r.raise_for_status()
    open(f"{OUT}/pda_2018_2020.csv", "w").write(r.text)
    time.sleep(1)
    meta = S.get("https://data.pa.gov/api/views/etb6-jzdg.json", timeout=60).json()
    json.dump({"etb6-jzdg": {"name": meta["name"], "rowsUpdatedAt": meta.get("rowsUpdatedAt")}}, open(f"{OUT}/socrata_meta.json", "w"), indent=1)
    print("pda 2018-2020:", r.text.count("\n") - 1, "rows", flush=True)

for f in ("achd_current", "achd_history", "achd_violations", "achd_facilities", "plcb_licenses"):
    p = f"{OUT}/manual/{f}.csv"
    print(f"manual/{f}.csv:", "present, " + time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))) if os.path.exists(p) else "MISSING (Nick downloads it)")
print("done", round(time.time() - t), "s")
