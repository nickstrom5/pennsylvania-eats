"""Official Pennsylvania records -> one table of food businesses (data/pa/official.pkl)

Jurisdictions (`jur`), each kept to its own area and never blended:
- philly   City of Philadelphia L&I business licenses (food types). "Food Preparing and Serving" (and "30+ SEATS") is a restaurant
           license; retail food licenses (stores) and non-permanent ones (trucks, carts) only flag counters and carts. Active
           licenses are current; revoked, closed, expired and inactive ones only flag closures. No inspection result: DPH's reports
           are search-only (philadelphia-pa.healthinspections.us), so nothing here is a grade or score.
- achd     Allegheny County Health Department (WPRDC, CC0; Nick's manual download). The latest placard per facility (green
           "Inspected & Permitted", yellow "Consumer Alert", red "Closed") and its date, shown as official. No computed grade.
- plcb     PLCB+ "CSV Download of All Licenses" (Nick's manual download). Active and parked licenses; trade name (Premises) only.
- pda2020  PDA "Public Food Inspections last 24 months" (data.pa.gov etb6-jzdg, through 2020-03-31): calibration only, never shown.

Only trade names are ever kept. Legal names, owners and managers are never downloaded or read (fetch_official.py).
"""
import os, re, json
import numpy as np, pandas as pd
from common import norm_name, RAW, PA, canon_city, name_sim, _stems, GENERIC

OFF = os.path.join(RAW, "official")
MAN = os.path.join(OFF, "manual")
DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
TYPES = set("""ST STREET AVE AV AVENUE BLVD BOULEVARD RD ROAD DR DRIVE LN LANE CT COURT PL PLACE PKWY PARKWAY TER TERRACE TRL TRAIL WAY
HWY HIGHWAY CIR CIRCLE PLZ PLAZA SQ SQUARE MALL BND PASS XING RUN ROW WALK RDG TPKE TPK TURNPIKE PIKE EXT EXTENSION GRN GREEN CRES
COMMONS CMNS LNDG LANDING EXPY EXPRESSWAY ALY ALLEY""".split())
ORD = {"FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5", "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8", "NINTH": "9",
       "TENTH": "10", "ELEVENTH": "11", "TWELFTH": "12"}
PHILLY_KIND = {"Food Preparing and Serving": "restaurant", "Food Preparing and Serving (30+ SEATS)": "restaurant", "Food Caterer": "caterer",
               "Food Establishment, Retail Permanent Location": "store", "Food Establishment, Retail Perm Location (Large)": "store",
               "Food Estab, Retail Non-Permanent Location (Annual)": "cart", "Food Establishment, Outdoor": "cart"}
ON_PREMISE = {"restaurant", "tavern", "bar", "hotel", "brewery"}   # the licenses a restaurant or bar holds
ENTITY_RX = re.compile(r"\b(?:INC|LLC|L\.L\.C|CORP|CORPORATION|LTD|CO|ENTERPRISES?|HOLDINGS?|GROUP|ASSOCIATES|PARTNERS|MANAGEMENT)\b\.?", re.I)


def road(a):
    """One spelling for numbered roads: 'ROUTE 30' = 'RT 30' = 'PA-30' = 'SR 30' = 'US ROUTE 30' = 'US-30'."""
    a = re.sub(r"(\d)\s*&\s*(\d)", r"\1-\2", a.upper())
    a = re.sub(r"\b(?:U\.?\s?S\.?|PA|P\.A\.|STATE|SR|S\.R\.|COUNTY|CO|T)[-\s]+(?:ROUTE|RTE|RT|HIGHWAY|HWY|ROAD|RD)?\s*-?\s*(\d+[A-Z]?)\b", r"RT \1", a)
    a = re.sub(r"\b(?:ROUTE|RTE|RT)\.?\s*#?\s*(\d+[A-Z]?)\b", r"RT \1", a)
    a = re.sub(r"\bTPKE\b|\bTPK\b", "TURNPIKE", a)
    a = re.sub(r"\bST\.?\s+(?=MARYS|JAMES|JOHNS|PAULS|DAVIDS|CLAIR|LAWRENCE|VINCENT)", "SAINT ", a)
    return re.sub(r"\bHIGHWAY\b", "HWY", a)


def _ordinal(w):
    w = ORD.get(w, w)
    m = re.fullmatch(r"(\d+)(?:ST|ND|RD|TH)", w)
    return m.group(1) if m else w


def street_key(a):
    """'2505 Main St' -> ('2505', 'MAIN'); '134 ROUTE 30' -> ('134', 'RT 30'); 'S 9TH ST' and 'South 9th Street' -> '9'."""
    if not isinstance(a, str):
        return None, None
    a = re.sub(r"[.,#]", " ", road(a))
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s+(.*)$", a)
    if not m:
        return None, None
    num = m.group(1)
    words = [w for w in m.group(3).split() if w]
    while len(words) > 1 and words[0] in DIRS:
        words = words[1:]
    core = []
    for w in words:
        if w in TYPES and core:
            break
        core.append(_ordinal(w))
    return num, " ".join(core[:3]) or None


def street_nums(a):
    """'157-159 W Main St' -> {'157', '159'}; '2505 Main St' -> {'2505'}."""
    if not isinstance(a, str):
        return set()
    a = road(a)
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s", a.upper() + " ")
    if not m:
        return set()
    lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:   # "1500-02"
        hi = int(str(lo)[: len(str(lo)) - len(m.group(2))] + m.group(2)) if m.group(2) else lo
    return {str(x) for x in range(lo, hi + 1, 2 if (hi - lo) % 2 == 0 else 1)} if 0 <= hi - lo <= 12 else {str(lo)}


def _names(*vals):
    out = []
    for v in vals:
        if not isinstance(v, str):
            continue
        for part in re.split(r"\s*/\s*|\s+\bdba\b\s+|\s+&\s+(?=[A-Z][a-z])|\s*\(\s*|\s*\)\s*", v, flags=re.I):
            k = norm_name(re.sub(r"\b(?:LLC|INC|CORP|CORPORATION|LTD|CO)\b\.?", "", part, flags=re.I))
            if k and k not in out:
                out.append(k)
    return out


def _ok(la, lo):
    return la == la and lo == lo and 39.6 < la < 42.4 and -80.7 < lo < -74.6


def records_through():
    """Publication lag: count only records at least 7 days before each feed's own newest stamp (data meta), never hard-coded."""
    out = {}
    cm = json.load(open(f"{OFF}/carto_meta.json"))["business_licenses"]
    out["philly"] = (pd.Timestamp(cm["newest"][:10]) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    if os.path.exists(f"{MAN}/achd_current.csv"):
        d = pd.read_csv(f"{MAN}/achd_current.csv", dtype=str, usecols=["inspect_dt"])
        out["achd"] = (pd.to_datetime(d.inspect_dt).max() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    return out


# Philadelphia's `business_name` is mostly "LEGAL ENTITY LLC (TRADE NAME)", sometimes a person's name with the trade name in
# parentheses ("SHIYING LIU (PANDA HOUSE)"), sometimes the legal entity alone ("MICHAELS FAMILY RESTAURANT VIII INC"). The trade name
# is shown; the part outside the parentheses is used only to match records, never shown (it can be a person).
PAREN = re.compile(r"^(.*?)\s*\(\s*(.+?)\s*\)\s*$")
PERSON = re.compile(r"^[A-Z][A-Za-z'-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z'-]+){1,2}$")


def _trade(n):
    """-> (shown trade name or None, every name usable for matching)."""
    if not isinstance(n, str) or not n.strip():
        return None, []
    n = re.sub(r"\s+", " ", n).strip()
    m = PAREN.match(n)
    if m and m.group(2) and not ENTITY_RX.search(m.group(2)):
        return m.group(2), [m.group(2), ENTITY_RX.sub(" ", m.group(1))]
    bare = ENTITY_RX.sub(" ", n).strip(" ,.")
    if ENTITY_RX.search(n) or PERSON.match(n if not n.isupper() else n.title()):
        return None, [bare]   # a legal entity or a person: match on it, never show it
    return n, [n]


def _philly(through):
    d = pd.read_csv(f"{OFF}/philly_licenses.csv", dtype=str).fillna("")
    rows = []
    for r in d.itertuples(index=False):
        la, lo = pd.to_numeric(r.lat, errors="coerce"), pd.to_numeric(r.lon, errors="coerce")
        name, match = _trade(r.business_name)
        issued = r.initialissuedate[:10] or None
        if issued and issued > through:
            continue
        rows.append({"jur": "philly", "lic": "PHL-" + r.licensenum, "name": name, "keys": _names(*match), "addr": r.address,
                     "city": "Philadelphia", "county": "Philadelphia", "zip": r.zip[:5], "kind": PHILLY_KIND[r.licensetype],
                     "cred": r.licensetype, "status": r.licensestatus, "active": r.licensestatus == "Active", "since": issued,
                     "expires": r.expirationdate[:10] or None, "inactive": r.inactivedate[:10] or None, "opa": r.opa_account_num or None,
                     "lat": la if _ok(la, lo) else np.nan, "lon": lo if _ok(la, lo) else np.nan})
    return rows


# ACHD placards (Alerts, Closures and Enforcements page). Values are mapped from the table as published; unknown values stay as given.
ACHD_PLACARD = {"Inspected & Permitted": "green", "Consumer Alert": "yellow"}


def _achd(through):
    if not os.path.exists(f"{MAN}/achd_current.csv"):
        print("!! ACHD files missing (data/raw/official/manual/achd_*.csv): Allegheny has no inspection records this build")
        return []
    cur = pd.read_csv(f"{MAN}/achd_current.csv", dtype=str).fillna("")
    hist = pd.read_csv(f"{MAN}/achd_history.csv", dtype=str).fillna("") if os.path.exists(f"{MAN}/achd_history.csv") else pd.DataFrame()
    fac = pd.read_csv(f"{MAN}/achd_facilities.csv", dtype=str).fillna("") if os.path.exists(f"{MAN}/achd_facilities.csv") else pd.DataFrame()
    cur = cur[cur.inspect_dt <= through]
    rows = []
    last = cur.sort_values("inspect_dt").groupby(["facility_name", "num", "street", "zip_code"], as_index=False).tail(1)
    geo = {}
    if len(fac):
        for r in fac.itertuples(index=False):
            k = (norm_name(getattr(r, "facility_name", "")), str(getattr(r, "num", "")).strip(), str(getattr(r, "zip", ""))[:5])
            la, lo = pd.to_numeric(getattr(r, "latitude", None), errors="coerce"), pd.to_numeric(getattr(r, "longitude", None), errors="coerce")
            if _ok(la, lo):
                geo[k] = (la, lo)
    for r in last.itertuples(index=False):
        la, lo = geo.get((norm_name(r.facility_name), r.num.strip(), r.zip_code[:5]), (np.nan, np.nan))
        rows.append({"jur": "achd", "lic": f"ACHD-{r.inspection_id}", "name": r.facility_name, "keys": _names(r.facility_name),
                     "addr": f"{r.num} {r.street}".strip(), "city": canon_city(r.city), "municipality": canon_city(r.municipal),
                     "county": "Allegheny", "zip": r.zip_code[:5], "kind": "food", "cred": r.category, "active": r.permit_status == "Active",
                     "since": r.bus_st_date or None, "lat": la, "lon": lo, "placard": r.placard_desc,
                     "placard_color": ACHD_PLACARD.get(r.placard_desc), "last_insp": r.inspect_dt, "insp_purpose": r.inspection_purpose,
                     "nonprofit": r.nonprofit == "Yes"})
    return rows


def _plcb():
    if not os.path.exists(f"{MAN}/plcb_licenses.csv"):
        print("!! PLCB export missing (data/raw/official/manual/plcb_licenses.csv): no liquor licenses this build")
        return []
    raise NotImplementedError("read the PLCB export's columns first")


def _pda2020():
    d = pd.read_csv(f"{OFF}/pda_2018_2020.csv", dtype=str).fillna("")
    d = d.sort_values("inspection_date").drop_duplicates(["public_facility_name", "address", "zip_code"], keep="last")
    return [{"jur": "pda2020", "lic": f"PDA20-{i}", "name": r.public_facility_name, "keys": _names(r.public_facility_name), "addr": r.address,
             "city": canon_city(r.city), "county": r.county_name.title().replace("Mckean", "McKean"), "zip": r.zip_code[:5], "kind": "food",
             "cred": r.organization_name, "active": r.active_indicator == "Yes", "since": None, "lat": np.nan, "lon": np.nan,
             "last_insp": r.inspection_date[:10]} for i, r in enumerate(d.itertuples(index=False))]


def load(cache=True):
    path = f"{PA}/official.pkl"
    srcs = [f for f in (f"{OFF}/philly_licenses.csv", f"{OFF}/pda_2018_2020.csv", f"{MAN}/achd_current.csv", f"{MAN}/plcb_licenses.csv")
            if os.path.exists(f)]
    if cache and os.path.exists(path) and os.path.getmtime(path) > max([os.path.getmtime(f) for f in srcs] + [os.path.getmtime(__file__)]):
        return pd.read_pickle(path)
    thr = records_through()
    df = pd.DataFrame(_philly(thr["philly"]) + _achd(thr.get("achd", "9999")) + _plcb() + _pda2020())
    df["num"], df["street"] = zip(*[street_key(a) if isinstance(a, str) and re.match(r"\s*\d", a) else (None, None) for a in df.addr])
    # one business can hold several records (a food license and a liquor license, a renewal under a new number): same address, a name in common
    parent = list(range(len(df)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    key_town = (df.county.fillna("") + "|" + df.zip.fillna("")).tolist()
    keys = df["keys"].tolist()
    groups = {}
    for i, (kt, num, st) in enumerate(zip(key_town, df.num, df.street)):
        if num and st:
            groups.setdefault((kt, num, st), []).append(i)
    for idx in groups.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                ka, kb = keys[idx[a]], keys[idx[b]]
                if any(name_sim(x, y) >= 85 or ((_stems(x) - GENERIC) & (_stems(y) - GENERIC)) for x in ka for y in kb):
                    ra, rb = find(idx[a]), find(idx[b])
                    if ra != rb:
                        parent[rb] = ra
    df["biz"] = [find(i) for i in range(len(df))]
    df.attrs["through"] = thr
    df.to_pickle(path)
    json.dump(thr, open(f"{PA}/records_through.json", "w"))
    return df


if __name__ == "__main__":
    df = load(cache=False)
    print("records through:", df.attrs.get("through"))
    a = df[df.active]
    print("records:", len(df), "| active:", len(a), "| with coordinates:", f"{a.lat.notna().mean():.1%}", "| with a name:", f"{a.name.notna().mean():.1%}")
    print(a.groupby(["jur", "kind"]).agg(n=("lic", "size"), placed=("lat", lambda s: round(s.notna().mean(), 3))).to_string())
