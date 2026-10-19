"""Stage 2: the Pennsylvania list -> site/ (web leaderboard) or, with PA_APP=1, data/app/ (the app). Both are split by region.

Statewide base: Overture Maps listings (stage1.pkl), each placed in a county (and region) and a municipality, kept by the rule
calibrate.py measured against Philadelphia's restaurant licenses (and ACHD's facility list and PLCB's licenses when present).
Official records: every listing is matched against the jurisdiction's own list; places on an official list that the map data
doesn't have are added from it (trade names only). Results stay with their jurisdiction and are never blended:
- Allegheny County: ACHD's placard (green "Inspected & Permitted", yellow "Consumer Alert", red closure) and its date, official.
- Philadelphia: an active L&I food license (existence only; DPH's inspection reports are search-only and linked, never scraped).
- Everywhere else: PDA's PA Food Safety Inspection Search is search-only and linked, never scraped.
Web leaderboard only: ratings, reviews and price level from Google's Sep 2021 snapshot (UCSD Google Local). PA_APP=1 drops all of
that (the App Store build ships no Google-derived data).
"""
import os, re, sys, json, math, glob, hashlib, unicodedata, collections, urllib.parse
import numpy as np, pandas as pd
import shapely
from shapely.geometry import shape
from rapidfuzz import fuzz
from common import (norm_name, nice, name_sim, cuisine, FOOD_COST, MARGIN, MARGIN_CUISINE, SPEND, GENERIC, _stems, DATA, PA, ROOT, RAW,
                    canon_city, CUISINE_RULES)
from brands import brand_of
import official
from official import street_key, street_nums, ON_PREMISE
from listings_util import official_match, _close_words
from check_websites import bad_host

APP = os.environ.get("PA_APP") == "1"
SITE = os.environ.get("PA_SITE") or (os.path.join(ROOT, "data", "app") if APP else os.path.join(ROOT, "site"))
GENERATED = "2026-10-19"
OVERTURE = "2026-09-23.1"
GOOD_SOURCES = {"meta", "AllThePlaces", "DAC"}
BASE = {1: 600_000, 2: 1_000_000, 3: 2_200_000, 4: 3_500_000}   # typical yearly sales by price tier (same as Chicago)
B_FIT = 0.764
REGIONS = ["Philadelphia", "Philly Suburbs", "Lehigh Valley", "South Central", "Northeast & Poconos", "Central", "Pittsburgh Region",
           "Northwest", "Northern Tier"]
SLUG = {r: re.sub(r"[^a-z]+", "-", r.lower()).strip("-") for r in REGIONS}
TAX_CUISINE = {
    "pizza_restaurant": "Pizza", "mexican_restaurant": "Mexican", "taco_restaurant": "Mexican", "texmex_restaurant": "Mexican",
    "sandwich_shop": "Sandwiches & Deli", "delicatessen": "Sandwiches & Deli", "bakery": "Bakery & Sweets", "donut_shop": "Bakery & Sweets",
    "dessert_shop": "Bakery & Sweets", "ice_cream_shop": "Bakery & Sweets", "bagel_shop": "Bagels", "cupcake_shop": "Bakery & Sweets",
    "frozen_yogurt_shop": "Bakery & Sweets", "chocolatier": "Bakery & Sweets", "popcorn_shop": "Bakery & Sweets",
    "bar_and_grill_restaurant": "Bar & Pub", "gastropub": "Bar & Pub", "bar": "Bar & Pub", "brewery": "Bar & Pub", "pub": "Bar & Pub",
    "sports_bar": "Bar & Pub", "cocktail_bar": "Bar & Pub", "wine_bar": "Bar & Pub", "dive_bar": "Bar & Pub", "beer_bar": "Bar & Pub",
    "irish_pub": "Bar & Pub", "tiki_bar": "Bar & Pub", "speakeasy": "Bar & Pub", "hookah_bar": "Bar & Pub", "gay_bar": "Bar & Pub",
    "chinese_restaurant": "Chinese", "italian_restaurant": "Italian", "burger_restaurant": "Burgers",
    "breakfast_and_brunch_restaurant": "Breakfast & Diner", "diner": "Breakfast & Diner", "barbecue_restaurant": "BBQ",
    "chicken_restaurant": "Chicken & Wings", "chicken_wings_restaurant": "Chicken & Wings", "sushi_restaurant": "Japanese & Sushi",
    "japanese_restaurant": "Japanese & Sushi", "ramen_restaurant": "Japanese & Sushi", "seafood_restaurant": "Seafood", "poke_restaurant": "Seafood",
    "steakhouse": "Steakhouse", "indian_restaurant": "South Asian", "pakistani_restaurant": "South Asian", "thai_restaurant": "Thai",
    "hot_dog_restaurant": "Hot Dogs", "mediterranean_restaurant": "Mediterranean & Middle Eastern",
    "greek_restaurant": "Mediterranean & Middle Eastern", "middle_eastern_restaurant": "Mediterranean & Middle Eastern",
    "korean_restaurant": "Korean", "vietnamese_restaurant": "Vietnamese", "salad_bar": "Healthy & Vegan", "vegan_restaurant": "Healthy & Vegan",
    "vegetarian_restaurant": "Healthy & Vegan", "health_food_restaurant": "Healthy & Vegan", "coffee_shop": "Coffee & Café", "cafe": "Coffee & Café",
    "coffee_roastery": "Coffee & Café", "smoothie_juice_bar": "Healthy & Vegan", "juice_bar": "Healthy & Vegan", "bubble_tea_shop": "Coffee & Café",
    "tea_room": "Coffee & Café", "soul_food": "Soul & Southern", "southern_american_restaurant": "Soul & Southern",
    "cajun_and_creole_restaurant": "Seafood", "caribbean_restaurant": "Latin & Caribbean", "jamaican_restaurant": "Latin & Caribbean",
    "latin_american_restaurant": "Latin & Caribbean", "cuban_restaurant": "Latin & Caribbean", "puerto_rican_restaurant": "Latin & Caribbean",
    "peruvian_restaurant": "Latin & Caribbean", "brazilian_restaurant": "Latin & Caribbean", "colombian_restaurant": "Latin & Caribbean",
    "dominican_restaurant": "Latin & Caribbean", "salvadoran_restaurant": "Latin & Caribbean", "african_restaurant": "African",
    "ethiopian_restaurant": "African", "french_restaurant": "European", "german_restaurant": "European", "polish_restaurant": "European",
    "portuguese_restaurant": "European", "spanish_restaurant": "European", "tapas_bar": "European", "noodles_restaurant": "Chinese",
    "belgian_restaurant": "European", "russian_restaurant": "European", "fondue_restaurant": "European", "irish_restaurant": "European",
    "scandinavian_restaurant": "European", "european_restaurant": "European", "eastern_european_restaurant": "European",
    "hungarian_restaurant": "European", "british_restaurant": "European", "dutch_restaurant": "European", "ukrainian_restaurant": "European",
    "kosher_restaurant": "Jewish & Kosher", "jewish_restaurant": "Jewish & Kosher", "dim_sum_restaurant": "Chinese", "cantonese_restaurant": "Chinese",
    "szechuan_restaurant": "Chinese", "dumpling_restaurant": "Chinese",
}
DOHMH_CUISINE = {}
KINDS = ["cheesesteak", "roast pork", "hoagie", "tomato pie", "old forge", "pierogi", "pittsburgh sandwich", "pa dutch", "pretzel", "diner",
         "oldest"]
TAGS = ["steak", "pie", "pierogi", "dutch", "pretzel", "diner", "oldest"]   # bit order in the data files
TAG_KINDS = {"steak": ["cheesesteak", "roast pork", "hoagie"], "pie": ["tomato pie", "old forge"], "pierogi": ["pierogi", "pittsburgh sandwich"],
             "dutch": ["pa dutch"], "pretzel": ["pretzel"], "diner": ["diner"], "oldest": ["oldest"]}


def pct(s):
    return (s.rank(pct=True) * 100).round(1)


def km(la1, lo1, la2, lo2):
    return math.hypot((la1 - la2) * 111, (lo1 - lo2) * 83)


def curated_matcher(frame):
    """A researched place -> row of frame: same street number and street with a similar name; else a near-exact name in the same city
    (municipality or mailing name) at a compatible street number; else a near-exact name unique statewide when no number is given."""
    by_key, by_num = {}, {}
    for i, a in enumerate(frame.street):
        sk = street_key(a)[1]
        for n in street_nums(a):
            if sk:
                by_key.setdefault((n, sk), []).append(i)
                by_num.setdefault(n, []).append((sk, i))
    cities = [{(c or "").lower() for c in cs if isinstance(c, str)} for cs in zip(frame.city, frame.get("place", frame.city), frame.get("muni", frame.city))]
    row_nums = [street_nums(a) for a in frame.street]
    ks = list(frame.k.fillna(""))
    zips = [str(z)[:5] if isinstance(z, str) else "" for z in frame.get("zip", pd.Series([None] * len(frame)))]

    def match(c):
        keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
        keys.discard("")
        if not keys:   # a name made only of stop words ("The Restaurant"): fall back to the lowercased name itself
            keys = {re.sub(r"[^A-Z0-9 ]", "", c["name"].upper()).strip()} - {""}
            if not keys:
                return None
        _, sk = street_key(c.get("address") or "")
        cands = set()
        for n in street_nums(c.get("address") or ""):
            cands.update(by_key.get((n, sk), []))
            if sk:
                cands.update(i for sk2, i in by_num.get(n, []) if sk2 != sk and fuzz.ratio(sk, sk2) >= 85)
        ccity = {(c.get(k) or "").lower() for k in ("city", "municipality", "place")} - {""}
        czip = (c.get("zip") or "")[:5]
        # every borough has a 100 Main St: the same address counts only in the record's own town or ZIP code
        elsewhere = lambda i: bool(ccity and cities[i] and not (cities[i] & ccity) and not (czip and zips[i] == czip))
        best, bs = None, 0
        for i in cands:
            if elsewhere(i):
                continue
            s_ = max((fuzz.token_set_ratio(m, ks[i]) for m in keys), default=0)
            if s_ >= 60 and s_ > bs:
                best, bs = i, s_
        if best is None and not c.get("chain"):
            cnums = street_nums(c.get("address") or "")
            ok = lambda i: not (cnums and row_nums[i] and not (cnums & row_nums[i]))
            sim = [max(fuzz.ratio(m, k) for m in keys) if k else 0 for k in ks]
            hits = [i for i, s_ in enumerate(sim) if s_ >= 90 and (cities[i] & ccity) and ok(i)] \
                or ([i for i, s_ in enumerate(sim) if s_ >= 95 and ok(i)] if not cnums else [])
            if len(hits) == 1:
                best = hits[0]
        return best
    return match


def load_curated():
    """MICHELIN Guide (Philadelphia) and James Beard honors -> entries (facts only, each with sources)."""
    out, by = [], {}

    def entry(e):
        city = e.get("city")
        key = (norm_name(e["name"]), (city or "").lower(), street_key(e.get("address") or "")[0] or "")
        if key not in by:
            by[key] = {"name": e["name"], "address": e.get("address"), "city": city, "municipality": e.get("municipality"),
                       "zip": e.get("zip"), "county": e.get("county"), "chain": False, "match_names": [e["name"].upper()], "james_beard": [],
                       "tags": [], "open": True, "rsources": [], "dishes": []}
            out.append(by[key])
        return by[key]
    mpath = f"{DATA}/research/michelin.json"
    if os.path.exists(mpath):
        for r in json.load(open(mpath)).get("restaurants", []):
            if r.get("open") is False:
                continue
            c = entry(r)
            c["match_names"] += [m for m in r.get("match_names") or [] if m not in c["match_names"]]
            c["michelin"] = r.get("distinction")
            if r.get("green_star"):
                c["green"] = True
            c["verified"] = True   # in the current selection; closures since are listed separately and skipped above
            c["rsources"] += [u for u in r.get("sources") or [] if not source_blocked(u)]
    jpath = f"{DATA}/research/jbf.json"
    if os.path.exists(jpath):
        for r in json.load(open(jpath)):
            if r.get("open") is False or not r.get("name"):
                continue
            c = entry(r)
            c["match_names"] += [m for m in r.get("match_names") or [] if m not in c["match_names"]]
            if r.get("open") is True:
                c["verified"] = True
            elif not c.get("michelin"):
                c["no_add"] = True   # an honoree with no 2025-26 evidence of being open: annotate its listing, never add it on its own
            c["james_beard"] += [h for h in (r.get("james_beard") or r.get("honors") or []) if h not in c["james_beard"]]
            c["rsources"] += [u for u in r.get("sources") or [] if not source_blocked(u)]
            c["chef"] = c.get("chef") or r.get("chef")
            if isinstance(r.get("founded"), int) and not c.get("founded"):
                c["founded"] = r["founded"]
            c["founded_note"] = c.get("founded_note") or r.get("founded_note")
    return out, by


SOURCE_HOSTS = json.load(open(f"{DATA}/research/source_hosts.json")) if os.path.exists(f"{DATA}/research/source_hosts.json") else {}
# websites never linked, whatever the link check said: hacked (hidden casino or pharmacy links), expired, or another business's page.
# The same list and rules as scripts/make-site.py `blocked()`: "domain" covers it and every subdomain, "url" one page on a shared host.
WEB_BLOCKLIST = json.load(open(f"{ROOT}/pipeline/website_blocklist.json", encoding="utf-8"))


def _host_path(u):
    s = urllib.parse.urlsplit(u.strip() if re.match(r"^[a-z][a-z0-9+.-]*://", u.strip(), re.I) else "//" + u.strip())
    return (s.hostname or "").lower().rstrip(".").removeprefix("www."), s.path.rstrip("/").lower()


def link_blocked(u):
    if not u:
        return False
    host, path = _host_path(u)
    for b in WEB_BLOCKLIST:
        if b.get("match", "domain") == "url":
            if (host, path) == _host_path(b["url"]):
                return True
        else:
            d = _host_path(b["domain"])[0]
            if host == d or host.endswith("." + d):
                return True
    return False


def source_blocked(u):
    from check_sources import why_not, host, API_HOSTS
    h = host(u)
    if h in API_HOSTS:
        return False
    if h not in SOURCE_HOSTS:
        print("!! source host never checked (run check_sources.py):", h); return False
    return why_not(SOURCE_HOSTS, u) is not None


def load_research(CUR, by):
    """data/research/app/*.json: the hand-checked guides. A place already in CUR (an honoree) gets its kinds and notes there."""
    for f in sorted(glob.glob(f"{DATA}/research/app/*.json")):
        try:
            entries = json.load(open(f))
        except json.JSONDecodeError as e:
            print("!! research file doesn't parse, skipped:", f, e); continue
        for e in entries:
            # a source on a host that blocks us (robots.txt, bot check: check_sources.py) never ships; a record waiting to be
            # re-sourced ("recheck") isn't hand-checked until it is
            e["sources"] = [u for u in e.get("sources") or [] if not source_blocked(u)]
            if e.get("open") is False or not e.get("name") or not e.get("sources") or e.get("recheck"):
                continue
            city = e.get("city")
            key = (norm_name(e["name"]), (city or "").lower(), street_key(e.get("address") or "")[0] or "")
            c = by.get(key)
            if c is None:
                c = {"name": e["name"], "address": e.get("address"), "city": city, "municipality": e.get("municipality"), "zip": e.get("zip"),
                     "county": e.get("county"), "chain": False, "match_names": [e["name"].upper()], "founded": None, "open": True, "tags": [],
                     "dishes": [], "james_beard": [], "rsources": [], "research_only": True}
                by[key] = c; CUR.append(c)
            c.pop("no_add", None)   # the guide research confirmed it open
            c["verified"] = True
            c["tags"] = list(dict.fromkeys(c["tags"] + [k.lower() for k in (e.get("kinds") or [])]))
            c["dishes"] = list(dict.fromkeys(c["dishes"] + (e.get("dishes") or [])))
            c["rsources"] = list(dict.fromkeys(c["rsources"] + (e.get("sources") or [])))
            for k in ("note", "website", "season", "branch_of", "founded_note", "evidence_date", "neighborhood"):
                c[k] = c.get(k) or e.get(k)
            c["seasonal"] = bool(c.get("seasonal") or e.get("seasonal"))
            if not c.get("founded") and isinstance(e.get("founded"), int):
                c["founded"] = e["founded"]
    return CUR


o = pd.read_pickle(f"{PA}/stage1.pkl")
G = pd.read_pickle(f"{PA}/google21.pkl")
if APP:   # the App Store build ignores every Google 2021 match
    o["in21"] = False; o["closed21"] = False; o["gi"] = np.nan
calib = json.load(open(f"{PA}/calibration.json"))
TOWNWORDS = frozenset(w for t in pd.concat([o.place.dropna(), o.muni.dropna()]).unique() for w in norm_name(t).split())
THROUGH = json.load(open(f"{PA}/records_through.json"))
CARTO_META = json.load(open(f"{RAW}/official/carto_meta.json"))

# ---------------------------------------------------------------- official records, matched within each jurisdiction
F = official.load()
F = F[F.active & F.jur.ne("pda2020") & (F.name.notna() | F.addr.notna() | F["keys"].map(bool))].reset_index(drop=True)
AREA = {"philly": o.county.eq("Philadelphia"), "achd": o.county.eq("Allegheny"), "plcb": o.county.notna()}
for jur, sel in AREA.items():
    R = F[(F.jur == jur) & (F.kind.isin(ON_PREMISE | {"club", "caterer", "maker", "venue"}) if jur == "plcb" else
                            (F.kind.isin(["restaurant", "caterer", "store"]) if jur == "philly" else True))]
    if not len(R):
        o["off_" + jur] = np.nan
        print(f"no {jur} records this build", flush=True); continue
    idx = o.index[sel]
    m = official_match(o.loc[idx].reset_index(drop=True), R.reset_index(drop=True), town_words=TOWNWORDS)
    o["off_" + jur] = np.nan
    for i, j in m.items():
        o.at[idx[i], "off_" + jur] = R.index[j]
    print(f"listings matched to {jur}:", len(m), flush=True)
JURS = ["philly", "achd", "plcb"]
o["off"] = np.nan
for jur in JURS:   # the local record first: it's the place's own license or permit
    o["off"] = o.off.where(o.off.notna(), o["off_" + jur])
o["official"] = o.off.notna()

# ---------------------------------------------------------------- map listings geocoded onto the same street in another town
# Map sources sometimes geocode an address onto a same-named street in another town (every borough has a Main Street). A listing without an official record is dropped
# when it's farther from every official record in its own ZIP code than that ZIP's records spread (90th percentile, at least 3 km), and
# either the ZIP belongs to another county (90%+ of its records) or the gap is over 15 km.
def zip_far(o, F, KX=79.0, KY=111.0):
    G = F[F.zip.notna() & F.lat.notna() & F.county.notna()].assign(z5=lambda d: d.zip.astype(str).str[:5])
    zcounty = {}
    for z, g in G.groupby("z5"):
        vc = g.county.value_counts()
        if len(g) >= 5 and vc.iloc[0] / len(g) >= 0.9:
            zcounty[z] = vc.index[0]
    REC = {z: g[["lon", "lat"]].to_numpy() * [KX, KY] for z, g in G.groupby("z5") if len(g) >= 3}
    z5 = o.zip.fillna("").astype(str).str[:5]
    far = pd.Series(False, index=o.index)
    for z, g in o[o.lat.notna() & ~o.official].groupby(z5):
        R = REC.get(z)
        if R is None:
            continue
        c = R.mean(0)
        thr = max(3.0, float(np.percentile(np.hypot(*(R - c).T), 90)))
        L = g[["lon", "lat"]].to_numpy() * [KX, KY]
        dmin = np.sqrt(((L[:, None, :] - R[None, :, :]) ** 2).sum(-1)).min(1)
        other = (g.county.notna() & (g.county != zcounty.get(z, g.county))).to_numpy() if z in zcounty else np.zeros(len(g), bool)
        far.loc[g.index] = (dmin > thr) & (other | (dmin > 15))
    return far
o["j_zipfar"] = zip_far(o, F) & ~o.src.eq("research")
print("map listings far from their own ZIP code, dropped:", int(o.j_zipfar.sum()),
      o.loc[o.j_zipfar, ["name", "zip", "county"]].head(8).values.tolist(), flush=True)

# ---------------------------------------------------------------- keep rule (calibrate.py / calibration.json)
base_ok = ~o.j_junk & ~o.j_closedname & ~o.j_outside & ~o.j_far & ~o.j_zipfar & ~o.ov_closed & ~(o.nowhere & ~o.in21) & o.county.notna()
CUR, CUR_BY = load_curated()
CUR = load_research(CUR, CUR_BY)
print("honors + hand-checked research entries:", len(CUR), flush=True)
_m = curated_matcher(o[base_ok].reset_index())
_bo = o.index[base_ok]
verified = pd.Series(False, index=o.index)
for c in CUR:
    j = _m(c)
    if j is not None:
        verified[_bo[j]] = True
keep = base_ok & (~o.closed21 | o.official | verified) & (o.src.isin(GOOD_SOURCES) | o.official | verified)
if APP:
    # measured against Philadelphia's active restaurant licenses (calibration.json): Meta listings with Overture confidence >= 0.95
    # matched one 59% of the time (the license list also holds schools, daycares and corner stores, and many licenses are filed under a
    # legal or personal name), Meta 0.90-0.95 29% and below 0.90 19%, BrightQuery 0.95+ 33%, other sources 14%; so only Meta 0.95+ and
    # the chains' own feeds ship on their own, everything else only when an official list or our research confirms it
    conf = o.confidence.fillna(0)
    keep = base_ok & (o.official | verified | ((o.src == "meta") & (conf >= 0.95)) | o.src.isin(["AllThePlaces", "DAC"]))
print("kept listings:", int(keep.sum()), "of", len(o), "| dropped single-source (Foursquare/BrightQuery/Microsoft):",
      int((base_ok & ~o.src.isin(GOOD_SOURCES) & ~o.official & ~verified).sum()), "| closed per Google 2021:",
      int((base_ok & o.closed21 & ~o.official).sum()), flush=True)
o = o[keep].reset_index(drop=True)

# ---------------------------------------------------------------- duplicate listings of one place
o["biz"] = o.off.map(lambda j: F.biz.iat[int(j)] if j == j else np.nan)
o["rank"] = o.official.astype(int) * 8 + o.in21.astype(int) * 4 + o.src.isin(GOOD_SOURCES).astype(int) * 2 + o.confidence.fillna(0)
o = o.sort_values("rank", ascending=False).reset_index(drop=True)
cell, drop = {}, set()
LA, LO, K, BZ, ST, BN = o.lat.to_numpy(), o.lon.to_numpy(), o.k.tolist(), o.biz.to_numpy(), o.st.tolist(), o.brand_n.tolist()
for i in range(len(o)):
    key = (round(LA[i] / 0.001), round(LO[i] / 0.0013))
    dup_ = False
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in cell.get((key[0] + dy, key[1] + dx), []):
                d_ = math.hypot((LA[j] - LA[i]) * 111000, (LO[j] - LO[i]) * 83000)
                same_biz = BZ[i] == BZ[i] and BZ[i] == BZ[j] and name_sim(K[i], K[j]) >= 80
                if same_biz or (d_ < 80 and (K[i] == K[j] or (fuzz.token_set_ratio(K[i], K[j]) >= 92 and ST[i] & ST[j]))) or (
                        d_ < 150 and isinstance(BN[i], str) and BN[i] == BN[j]):
                    dup_ = True; break
            if dup_: break
        if dup_: break
    if dup_:
        drop.add(i)
    else:
        cell.setdefault(key, []).append(i)
o = o.drop(index=list(drop)).reset_index(drop=True)
akey = [(b if isinstance(b, str) else k, n, c) if n and isinstance(c, str) else None for b, k, n, c in zip(o.brand_n, o.k, o.num, o.city)]
seen, dup = set(), []
for a in akey:
    dup.append(a is not None and a in seen)
    if a is not None:
        seen.add(a)
has_addr = o.num.notna()
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    with_a, without = grp[has_addr[grp.index]], grp[~has_addr[grp.index]]
    for i, r in without.iterrows():
        if len(with_a) and (np.hypot((with_a.lat - r.lat) * 111, (with_a.lon - r.lon) * 83) < 1.5).any():
            dup[i] = True
o = o[~np.array(dup)].reset_index(drop=True)
near_dup = set()
for (k, c), grp in o[o.brand_n.isna() & o.k.fillna("").str.len().ge(4) & o.city.notna()].groupby(["k", "city"]):
    if len(grp) < 2 or not (_stems(k) - GENERIC):
        continue
    idx = list(grp.index)
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if idx[b] in near_dup or idx[a] in near_dup:
                continue
            lim = 250 if o.city[idx[a]] in ("Philadelphia", "Pittsburgh") else 500   # city blocks are short: two same-name places 400 m apart can be two branches
            if math.hypot((o.lat[idx[a]] - o.lat[idx[b]]) * 111000, (o.lon[idx[a]] - o.lon[idx[b]]) * 83000) < lim and not (o.official[idx[a]] and o.official[idx[b]]):
                near_dup.add(idx[b])
o = o.drop(index=list(near_dup)).reset_index(drop=True)
print("after merging duplicate listings:", len(o), "(dropped", len(drop) + sum(dup) + len(near_dup), ")", flush=True)
confirmed = ((o.src == "meta") & (o.confidence.fillna(0) >= 0.95)) if APP else o.in21
o["tier"] = np.where(o.official, "official", np.where(confirmed, "both", "listing"))

# ---------------------------------------------------------------- places on an official list that the map listings don't have
FOODWORD = re.compile(r"\b(?:PIZZA|PIZZERIA|RESTAURANT|GRILL|KITCHEN|CAFE|BAKERY|BAKE SHOP|DELI|DINER|BAR|PUB|TAVERN|TACOS?|TAQUERIA|BURGERS?|"
                      r"WINGS|CHICKEN|SUSHI|THAI|CHINA|CHINESE|JERK|PATTY|PATTIES|SEAFOOD|FISH|COFFEE|ESPRESSO|TEA|BISTRO|EATERY|BBQ|BAGELS?|DONUTS?|"
                      r"DUNKIN|SUBWAY|WENDYS|MCDONALDS|BURGER KING|TACO BELL|POPEYES|KFC|DOMINOS|STARBUCKS|PHO|RAMEN|HALAL|GYRO|KEBAB|EMPANADAS?|"
                      r"LOUNGE|CANTINA|TRATTORIA|STEAK|SOUL|CUISINE|FOOD|NOODLES?|DUMPLINGS?|DIM SUM|BUFFET|CREAMERY|ICE CREAM|HOTS)\b")
NOT_REST = re.compile(r"\b(?:SCHOOL|ACADEMY|ELEMENTARY|MIDDLE|HIGH|COLLEGE|UNIVERSITY|CHURCH|MINISTR\w*|SHELTER|SOUP KITCHEN|PANTRY|HEAD START|"
                      r"CHILD|DAYCARE|NURSING|HOSPITAL|MEDICAL|MARKET|GROCERY|SUPERMARKET|PHARMACY|CVS|WALGREENS|DOLLAR|WALMART|TARGET|"
                      r"STADIUM|CONCESSIONS?|THEATRE|THEATER|SALVATION ARMY|YMCA|COMMUNITY|SOCIETY|CORRECTIONAL|DISTRIBUT\w*|CAFETERIA|"
                      r"DINING HALL|COMMISSARY|EMPLOYEE|CORPORATE|SENIOR|ADULT DAY|CAMP|SPORTSMEN|GOLF|COUNTRY CLUB)\b")
found = set(o.biz.dropna())
# Philadelphia's restaurant licenses (every food business in the city that cooks or serves holds one) and ACHD's facilities are full
# lists: add them (minus institutions). PLCB licenses: only names that say food (a license can belong to a hall or a club).
# Records whose only name is a legal entity or a person are never added (they'd have no name to show).
add = F[~F.biz.isin(found) & F.lat.notna() & F.name.notna() & (((F.jur == "philly") & (F.kind == "restaurant")) | (F.jur == "achd")
                                                                | ((F.jur == "plcb") & F.kind.isin(ON_PREMISE)))].copy()
add["pri"] = add.jur.map({"philly": 0, "achd": 1, "plcb": 2})
add = add.sort_values("pri").drop_duplicates("biz")
kname = add.name.map(norm_name)
needs_food = add.jur.isin(["plcb"])
add = add[~add.name.str.upper().str.contains(NOT_REST) & (~needs_food | kname.str.contains(FOODWORD) | add.kind.isin(["restaurant", "tavern", "bar"]))]
ENTITY = re.compile(r"\b(?:LLC|L\.L\.C|INC|CORP|CORPORATION|LTD|LIMITED|LLP|ENTERPRISES?|HOLDINGS?|GROUP|MANAGEMENT|PARTNERS|ASSOCIATES)\b\.?", re.I)
ent = add.name.str.contains(ENTITY) & ~add.name.map(lambda n: norm_name(ENTITY.sub(" ", n))).str.contains(FOODWORD)
print("license-only records left out because the trade name is a legal entity:", int(ent.sum()), add.name[ent].head(6).tolist())
add = add[~ent]
OTHER_BIZ = re.compile(r"\b(?:REMODEL\w*|CONSTRUCTION|CONTRACTING|CONTRACTORS?|PLUMBING|ROOFING|LANDSCAP\w*|AUTOMOTIVE|AUTO (?:BODY|REPAIR|SALES)|"
                       r"TIRES?|INSURANCE|REALTY|REAL ESTATE|HAIR|SALON|BARBER\w*|NAILS|CLEANERS|CLEANING|MOVERS|STORAGE|PROPERTIES)\b")
add = add[~add.name.map(norm_name).str.contains(OTHER_BIZ)]
print("official places not in the map listings:", len(add), add.jur.value_counts().to_dict(), flush=True)


DBA = re.compile(r"\bD\.?\s*/?\s*B\.?\s*/?\s*A\b\.?/?\s*[:\-]?\s*", re.I)


def after_dba(n):
    """'Development Authority Dba: Castle Cafe' -> 'Castle Cafe'; 'Saigon Project Dba' -> 'Saigon Project'; an SBA loan note
    ('E N Restaurant Dba-sba Small 7a Term') is not a trade name."""
    n = re.sub(r"\s*\bD/?B/?A\b[-\s]*SBA\b.*$", "", n or "", flags=re.I)
    parts = DBA.split(n)
    if len(parts) < 2 or not parts[0].strip():   # no DBA, or the name itself starts with it (the bar called d.b.a.)
        return n
    return parts[-1].strip(" .-:") or parts[0].strip(" .-:")


def clean_official(n):
    n = re.split(r"\s*;\s*", n or "")[0]
    n = after_dba(n)
    n = re.sub(r"\s*#\s*\d+\w*.*$|\s*\(#?[A-Z]?\d+\)|\s+\d{3,}\s*$", "", n)
    n = ENTITY.sub("", n)
    n = re.split(r"\s*/\s*", n)[0] if "/" in n else n
    n = re.sub(r"\s+", " ", n).strip(" -,&/.")
    return nice(n) if n.isupper() or n.islower() else n


A = pd.DataFrame({"id": add.lic.values, "name": add.name.map(clean_official).values, "street": add.addr.values, "place": add.city.values,
                  "zip": add.zip.values, "lat": add.lat.values, "lon": add.lon.values,
                  "cat": np.where(add.kind.isin(["tavern", "bar"]), "bar", "restaurant"), "tax": None, "confidence": np.nan, "brand": None,
                  "src": "official", "official": True, "off": add.index.values, "biz": add.biz.values, "tier": "official", "in21": False,
                  "closed21": False, "dom": None, "web": None, "phone": add.get("phone", pd.Series(None, index=add.index)).values})
for jur in JURS:
    A["off_" + jur] = np.where(add.jur.values == jur, add.index.values, np.nan)
A = A[A.name.str.len() >= 2].reset_index(drop=True)
A["k"] = A.name.map(norm_name)
A["st"] = A.k.map(lambda k: _stems(k) - GENERIC if k else set())
A["num"] = A.street.map(lambda a: street_key(a)[0])
A["brand_n"] = A.k.map(brand_of)
# Google 2021 listings for the added rows (web only; the ones no map listing took)
taken = set(o.gi.dropna().astype(int))
grid = {}
for i, (la, lo) in enumerate(zip(G.latitude, G.longitude)):
    grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(i)
GK_, GC_, GLA_, GLO_, GN_, GS_, GS2_ = (G[c].tolist() for c in ("k", "closed21", "latitude", "longitude", "num", "st", "st2"))
pairs = []
for ai, (k, la, lo, num, st) in ([] if APP else enumerate(zip(A.k, A.lat, A.lon, A.num, A.st))):
    if not k:
        continue
    gy, gx = round(la / 0.0015), round(lo / 0.002)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for gi in grid.get((gy + dy, gx + dx), []):
                if gi in taken or not GK_[gi] or GC_[gi]:
                    continue
                dist = math.hypot((GLA_[gi] - la) * 111000, (GLO_[gi] - lo) * 83000)
                if dist > 200:
                    continue
                s = name_sim(k, GK_[gi])
                same_num = num is not None and GN_[gi] == num
                if same_num and st & GS_[gi]:
                    s = max(s, 80)
                if s < 95 and not st & GS2_[gi]:
                    continue
                if (s >= 88 and dist < 150) or (s >= 75 and same_num):
                    pairs.append((s + (10 if same_num else 0) - dist / 25, ai, gi))
A["gi"] = np.nan
ta, tg = set(), set()
for sc, ai, gi in sorted(pairs, key=lambda t: -t[0]):
    if ai in ta or gi in tg:
        continue
    ta.add(ai); tg.add(gi); A.at[ai, "gi"] = gi
A["in21"] = A.gi.notna()
# a licensed place the address match missed can sit on top of its own map listing under a slightly different name: merge it into that
# listing, unless the listing already matched a record of its own (two neighbors are two places)
kgrid = {}
for j, (la, lo) in enumerate(zip(o.lat, o.lon)):
    kgrid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
merge, same_lic = {}, set()
OK_, OOFF, OLA_, OLO_, OST_ = o.k.tolist(), o.official.to_numpy(), o.lat.tolist(), o.lon.tolist(), o.st.tolist()
for ai, (k, la, lo, st) in enumerate(zip(A.k, A.lat, A.lon, A.st)):
    if not k:
        continue
    best, bs = None, -1
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in kgrid.get((round(la / 0.0015) + dy, round(lo / 0.002) + dx), []):
                if j in merge.values():
                    continue
                dist = math.hypot((OLA_[j] - la) * 111000, (OLO_[j] - lo) * 83000)
                if dist > 80:
                    continue
                s = name_sim(k, OK_[j]) if OK_[j] else 0
                if OOFF[j]:
                    if dist <= 80 and s >= 95:
                        same_lic.add(ai)
                    continue
                shared = bool(st & OST_[j]) or _close_words(st, OST_[j])
                nested = len(k.split()) >= 2 and OK_[j] and (set(k.split()) <= set(OK_[j].split()) or set(OK_[j].split()) <= set(k.split()))
                if (dist <= 60 and (s >= 88 or (shared and s >= 60) or nested)) or (dist <= 25 and s >= 75):
                    if s - dist / 10 > bs:
                        best, bs = j, s - dist / 10
    if best is not None:
        merge[ai] = best
for ai, j in merge.items():
    for c in ["official", "off", "biz", "tier"] + ["off_" + x for x in JURS]:
        v = A.at[ai, c]
        if c.startswith("off_") and v != v:
            continue
        o.at[o.index[j], c] = v
A = A.drop(index=list(set(merge) | same_lic)).reset_index(drop=True)
print("official rows merged into a map listing on the second pass:", len(merge), "| second records:", len(same_lic - set(merge)),
      "| official rows added:", len(A), flush=True)
o = pd.concat([o, A], ignore_index=True)

# ---------------------------------------------------------------- hand-checked places the map listings and lists don't have
import duckdb
OV = duckdb.connect().execute(f"SELECT name, street, city, zip, lat, lon, cat FROM '{PA}/overture_pa.parquet' WHERE name IS NOT NULL").df()
OV["k"] = OV.name.map(norm_name)
_m = curated_matcher(o)
missing = [c for c in CUR if not c.get("chain") and not c.get("no_add") and _m(c) is None]
FO = F[F.lat.notna()]
added, not_placed, geo_todo = [], [], []
for c in missing:
    keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
    spot = None
    nums, sk = street_nums(c.get("address") or ""), street_key(c.get("address") or "")[1]
    # an official record at the same address (any jurisdiction, any name): a bakery or retail counter not listed as a place to eat
    if nums and sk:
        cand = FO[FO.num.isin(nums) & (FO.street == sk)]
        if c.get("zip"):
            cand = cand[cand.zip.fillna("").astype(str).str[:5].isin([c["zip"][:5], ""])]
        else:   # no ZIP: the record's own town or county (every town has a 100 Main St)
            towns = {(c.get(k) or "").lower() for k in ("city", "municipality")} - {""}
            towns |= {"manhattan", "new york"} if towns & {"manhattan", "new york"} else set()
            cand = cand[cand.city.fillna("").str.lower().isin(towns) | (cand.county.eq(c.get("county")) if c.get("county") else False)]
        if len(cand):
            sims = [max((name_sim(m, k) for m in keys for k in ks), default=0) for ks in cand["keys"]]
            if max(sims) >= 60:
                h = cand.iloc[int(np.argmax(sims))]
                spot = (h.lat, h.lon)
    if spot is None:   # Overture's own listing of the place (any category: an inn, a bakery, a market) in the same city, by name
        town_l = {(c.get(k) or "").lower() for k in ("city", "municipality")} - {""}
        if "manhattan" in town_l:
            town_l.add("new york")
        cand = OV[OV.city.fillna("").str.lower().isin(town_l)]
        sims = [max(fuzz.ratio(m, k) for m in keys) if isinstance(k, str) and k else 0 for k in cand.k]
        if len(sims) and max(sims) >= 88:
            h = cand.iloc[int(np.argmax(sims))]
            hn = street_nums(h.street or "")
            if not (nums and hn and not (nums & hn)):
                spot = (h.lat, h.lon)
    if spot is None:
        gc = json.load(open(f"{DATA}/research/geocode_census.json")) if os.path.exists(f"{DATA}/research/geocode_census.json") else {}
        q = f"{c.get('address')}, {c.get('city')}, PA {c.get('zip') or ''}".strip()
        if q in gc:
            spot = (gc[q]["lat"], gc[q]["lon"])
        elif c.get("address"):
            geo_todo.append(q)
    if spot is None:
        not_placed.append(c["name"]); continue
    added.append({"id": "research-" + c["name"], "name": c["name"], "street": c.get("address"), "place": c.get("city"), "zip": c.get("zip"),
                  "lat": spot[0], "lon": spot[1], "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None, "src": "research",
                  "official": False, "off": np.nan, "biz": np.nan, "tier": "both", "in21": False, "closed21": False, "dom": None, "gi": np.nan,
                  "k": norm_name(c["name"]), "st": _stems(norm_name(c["name"])) - GENERIC, "num": street_key(c.get("address") or "")[0],
                  "brand_n": None, "web": c.get("website")})
if added:
    o = pd.concat([o, pd.DataFrame(added)], ignore_index=True)
os.makedirs(f"{DATA}/research", exist_ok=True)
json.dump(sorted(set(geo_todo)), open(f"{DATA}/research/geocode_todo.json", "w"), indent=1)
print("hand-checked places added (not in the map listings or lists):", len(added), "| not placed yet (see geocode_todo.json):", not_placed, flush=True)

# ---------------------------------------------------------------- placement for the added rows (county, region, municipality)
need = o.county.isna() | o.region.isna()
if need.any():
    pts = shapely.points(o.loc[need, "lon"].to_numpy(), o.loc[need, "lat"].to_numpy())

    def locate(path, props, max_deg=0.015):
        feats = json.load(open(path))["features"]
        tree = shapely.STRtree([shape(f["geometry"]) for f in feats])
        pi, gi = tree.query(pts, predicate="within")
        out = [None] * len(pts)
        for p, g in zip(pi, gi):
            if out[p] is None:
                out[p] = g
        left = [i for i, v in enumerate(out) if v is None]
        if left:
            near, dist = tree.query_nearest(pts[left], return_distance=True, all_matches=False)
            for (k, g), d_ in zip(near.T, dist):
                if d_ < max_deg:
                    out[left[k]] = g
        return [None if g is None else tuple(feats[g]["properties"].get(p) for p in props) for g in out]
    cty = locate(f"{PA}/pa_counties.geojson", ("county", "region"))
    sub = locate(f"{PA}/pa_cousub.geojson", ("name", "kind"))
    o.loc[need, "county"] = [c[0] if c else None for c in cty]
    o.loc[need, "region"] = [c[1] if c else None for c in cty]
    o.loc[need, "muni"] = [s[0] if s else None for s in sub]
    o.loc[need, "place"] = [canon_city(p) if isinstance(p, str) else None for p in o.loc[need, "place"]]
    o.loc[need, "city"] = ["Philadelphia" if co == "Philadelphia" else (p if isinstance(p, str) else m) for co, p, m in
                           zip(o.loc[need, "county"], o.loc[need, "place"], o.loc[need, "muni"])]
o = o[o.county.notna()].reset_index(drop=True)

o["street"] = [None if isinstance(a, str) and re.search(r"https?://|goo\.gl|maps\.app", a) else a for a in o.street]
o["place"] = [None if isinstance(p_, str) and (not p_.strip() or re.search(r"\d|\b(?:Ave|Avenue|St|Street|Rd|Road|Blvd)\b\.?", p_)) else p_ for p_ in o.place]
bad_city = o.city.fillna("").str.match(r"(?i)^(?:suite|ste|unit|apt|fl|floor|room|bldg)\b|^\d")
o.loc[bad_city, "city"] = [m if isinstance(m, str) else None for m in o.loc[bad_city, "muni"]]

# ---------------------------------------------------------------- fields
gi = [int(v) if v == v and v is not None else None for v in o.gi]
o["rating"] = [G.avg_rating.iat[i] if i is not None else np.nan for i in gi]
o["reviews"] = [G.num_of_reviews.iat[i] if i is not None else np.nan for i in gi]
o["gprice"] = [len(G.price.iat[i]) if i is not None and isinstance(G.price.iat[i], str) else np.nan for i in gi]
o["gcats"] = ["|".join(G.category.iat[i] or []) if i is not None else "" for i in gi]
o["gmap_id"] = [G.gmap_id.iat[i] if i is not None else None for i in gi]
o["name_out"] = [b if isinstance(b, str) and fuzz.ratio(norm_name(n), norm_name(b)) >= 88 else nice(n) if n.isupper() or n.islower() else n
                 for n, b in zip(o.name, o.brand_n)]
ofx = lambda j, col: F[col].iat[int(j)] if j == j and j is not None else None
o["dohmh_cuisine"] = None


def pick_cuisine(tax, k, gcats, raw, dc):
    for c, pat in CUISINE_RULES[:-1]:
        if pat.search(k or ""):
            return c
    if isinstance(tax, str) and tax in TAX_CUISINE:
        return TAX_CUISINE[tax]
    if isinstance(dc, str) and dc in DOHMH_CUISINE:
        return DOHMH_CUISINE[dc]
    return cuisine(k, gcats, raw)


o["cuisine"] = [pick_cuisine(t, k, gc, n, dc) for t, k, gc, n, dc in zip(o.tax, o.k, o.gcats, o.name, o.dohmh_cuisine)]
nk_ = o.k.fillna("")
o.loc[nk_.str.contains(r"\bBAGELS?\b"), "cuisine"] = "Bagels"
o.loc[nk_.str.contains(r"\bKOSHER\b|\bKNISH") & ~o.cuisine.isin(["Pizza", "Bagels"]), "cuisine"] = "Jewish & Kosher"
o.loc[nk_.str.contains(r"\bPIEROG|\bHALUSKI|\bKIELBASA\b|\bGOLABKI|\bPOLISH\b|\bUKRAINIAN\b"), "cuisine"] = "European"
o.loc[o.cat.isin(["bar", "brewery"]) & (o.cuisine == "American & Other"), "cuisine"] = "Bar & Pub"
o.loc[o.cat.isin(["coffee_shop", "cafe"]) & (o.cuisine == "American & Other"), "cuisine"] = "Coffee & Café"
o.loc[o.cuisine.eq("Asian & Other"), "cuisine"] = "American & Other"


def mode(x):
    return x.mode().iat[0]


bdom = {}
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    d = grp.dom.dropna()
    if len(d) >= 3:
        top, n = collections.Counter(d).most_common(1)[0]
        if n >= 0.5 * len(d):
            bdom[b] = top
FAMILY = {"Chicken & Wings": "quick", "Burgers": "quick", "Hot Dogs": "quick", "Sandwiches & Deli": "cafe", "Pizza": "pizza", "Bagels": "cafe",
          "Mexican": "mex", "Latin & Caribbean": "mex", "Coffee & Café": "cafe", "Bakery & Sweets": "cafe", "Jewish & Kosher": "cafe",
          "Breakfast & Diner": "cafe", "Healthy & Vegan": "cafe", "Steakhouse": "sitdown", "Seafood": "sea",
          "Bar & Pub": "bar", "Italian": "italian", "Chinese": "asian", "Japanese & Sushi": "asian", "Thai": "asian", "Korean": "asian",
          "Vietnamese": "asian", "South Asian": "sasian", "Mediterranean & Middle Eastern": "med", "European": "sitdown", "BBQ": "bbq",
          "Soul & Southern": "soul", "African": "african"}
brand_cuisine = o[o.brand_n.notna()].groupby("brand_n").cuisine.agg(mode)


def core(k):
    w = [x for x in k.split() if x not in GENERIC and x not in ("RESTAURANT", "RESTAURANTS", "CAFE", "STORE")]
    return " ".join(w) or k


def brand_ok(b, dm, cu, tax, obrand, name, src):
    if not isinstance(b, str):
        return None
    dm = dm if isinstance(dm, str) else None
    nk, bk = norm_name(name), norm_name(b)
    if src not in ("AllThePlaces", "DAC") and brand_of(nk) != b:
        return None
    ob = norm_name(obrand) if isinstance(obrand, str) else ""
    brand_feed = src in ("AllThePlaces", "DAC")
    label = bool(ob) and fuzz.token_set_ratio(ob, bk) >= 80
    related = brand_feed or fuzz.partial_ratio(bk, nk) >= 60 or (label and fuzz.partial_ratio(ob, nk) >= 60)
    if not related:
        return None
    squashed = re.sub(r"[^a-z]", "", b.lower())
    own_site = dm and (bdom.get(b) == dm or dm.split(".")[0].replace("-", "") in (squashed, squashed + "s"))
    exact = fuzz.ratio(core(nk), core(bk)) >= 90 or (label and fuzz.ratio(core(nk), core(ob)) >= 90) \
        or (len(bk) >= 6 and (nk == bk or nk.startswith(bk + " ")))
    if exact or own_site or (label and brand_feed):
        return b
    if dm and b in bdom and src != "BrightQuery":
        return None
    want = brand_cuisine.get(b)
    if isinstance(tax, str) and tax in TAX_CUISINE and want and FAMILY.get(cu) and FAMILY.get(want) and FAMILY[cu] != FAMILY[want]:
        return None
    return b


old_brand = o.brand_n.copy()
o["brand_n"] = [brand_ok(b, dm, cu, t, ob, n, sr) for b, dm, cu, t, ob, n, sr in zip(o.brand_n, o.dom, o.cuisine, o.tax, o.brand, o.name, o.src)]
rej = o[old_brand.notna() & o.brand_n.isna()]
print("brand matches rejected:", len(rej), collections.Counter(old_brand[rej.index]).most_common(8), flush=True)
o.loc[o.brand_n.notna(), "name_out"] = [b if fuzz.ratio(norm_name(n), norm_name(b)) >= 80 or len(norm_name(n)) <= len(norm_name(b)) + 2 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]


def chain_mode(x):
    real = x[x != "American & Other"]
    return (real if len(real) else x).mode().iat[0]


CHAIN_CUISINE = {"Dunkin'": "Coffee & Café", "Starbucks": "Coffee & Café", "Tim Hortons": "Coffee & Café", "Dairy Queen": "Bakery & Sweets",
                 "Cold Stone Creamery": "Bakery & Sweets", "Baskin-Robbins": "Bakery & Sweets", "Rita's Italian Ice": "Bakery & Sweets",
                 "Panera Bread": "Sandwiches & Deli", "Einstein Bros. Bagels": "Bagels", "Bruegger's": "Bagels", "Manhattan Bagel": "Bagels",
                 "Texas Roadhouse": "Steakhouse", "Tropical Smoothie Cafe": "Healthy & Vegan", "Smoothie King": "Healthy & Vegan",
                 "Saladworks": "Healthy & Vegan", "Honeygrow": "Healthy & Vegan", "Playa Bowls": "Healthy & Vegan", "Five Guys": "Burgers",
                 "Shake Shack": "Burgers", "Primanti Bros.": "Sandwiches & Deli", "Primo Hoagies": "Sandwiches & Deli", "Capriotti's": "Sandwiches & Deli",
                 "Philly Pretzel Factory": "Bakery & Sweets", "Auntie Anne's": "Bakery & Sweets", "Federal Donuts": "Bakery & Sweets",
                 "Duck Donuts": "Bakery & Sweets", "Chickie's & Pete's": "Bar & Pub", "Iron Hill Brewery": "Bar & Pub", "Eat'n Park": "Breakfast & Diner",
                 "Bob Evans": "Breakfast & Diner", "Friendly's": "American & Other", "Applebee's": "American & Other", "Hoss's": "Steakhouse",
                 "Fox's Pizza Den": "Pizza", "Vocelli Pizza": "Pizza", "Bonchon": "Chicken & Wings", "Wawa": "Sandwiches & Deli", "Sheetz": "Sandwiches & Deli",
                 "Isaly's": "Sandwiches & Deli", "Mister Softee": "Bakery & Sweets"}
allc = o.loc[o.brand_n.notna(), ["brand_n", "cuisine"]]
all_brand_cuisine = allc.groupby("brand_n").cuisine.agg(chain_mode)
o.loc[o.brand_n.notna(), "cuisine"] = o.loc[o.brand_n.notna(), "brand_n"].map(lambda b: CHAIN_CUISINE.get(b) or all_brand_cuisine.get(b))

o["price"] = o.gprice
o["price_est"] = o.price.isna().astype(int)
bp = o[o.gprice.notna()].groupby("brand_n").gprice.median()
o.loc[o.price.isna() & o.brand_n.notna(), "price"] = o.brand_n.map(bp)
cp = o[o.gprice.notna()].groupby("cuisine").gprice.median()
o.loc[o.price.isna(), "price"] = o.cuisine.map(cp)
o["price"] = o.price.fillna(2).round().clip(1, 4).astype(int)

bc = o.brand_n.value_counts()
o["chain_n"] = o.brand_n.map(lambda b: int(bc.get(b, 0)) if isinstance(b, str) else 1)
STORE_DOMS_ALL = {"wawa.com", "sheetz.com", "getgocafe.com", "gogetgo.com", "rutters.com", "turkeyhill.com", "royalfarms.com", "wegmans.com",
                  "shoprite.com", "walmart.com", "target.com", "costco.com", "bjs.com", "wholefoodsmarket.com", "traderjoes.com", "7-eleven.com",
                  "cvs.com", "walgreens.com", "speedway.com", "sunoco.com", "giantfoodstores.com", "giantfood.com", "gianteagle.com", "weismarkets.com",
                  "acmemarkets.com", "redners.com", "karnsfoods.com", "riteaid.com", "aldi.us", "lidl.com", "freshgrocer.com", "marketdistrict.com"}
first_stem = o.k.fillna("").map(lambda k: next((w for w in k.split() if w not in GENERIC and len(w) >= 3), None))
grpkey = pd.Series([(d, s) if isinstance(d, str) and isinstance(s, str) and not isinstance(b, str) and d not in STORE_DOMS_ALL else None
                    for d, s, b in zip(o.dom, first_stem, o.brand_n)], index=o.index)
gsize = grpkey.dropna().value_counts()
member = [g is not None and gsize.get(g, 0) >= 2 for g in grpkey]
o.loc[member, "chain_n"] = [int(gsize[g]) for g, m in zip(grpkey, member) if m]
o["ckey"] = grpkey.map(lambda g: "|".join(g) if g else None)
grp_cuisine = o[member].groupby("ckey").cuisine.agg(chain_mode)
o.loc[member, "cuisine"] = [grp_cuisine.get(k) for k in o.loc[member, "ckey"]]
sib = o.gprice.notna()
for key, sel in (("brand_n", o.brand_n.notna()), ("ckey", pd.Series(member, index=o.index))):
    med = o[sel & sib].groupby(key).gprice.median()
    fill = sel & (o.price_est == 1) & o[key].isin(med.index)
    o.loc[fill, "price"] = o.loc[fill, key].map(med).round().clip(1, 4).astype(int)

o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")
o["name_out"] = o.name_out.map(lambda n: re.sub(r"\b(?:Tcby|Ihop|Bj's|Bjs)\b", lambda m: {"tcby": "TCBY", "ihop": "IHOP"}.get(m.group(0).lower(), "BJ's"), n))
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
CJK = r"[぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]"
TAILWORDS = re.compile(r"^(?:best|award|voted|magazine|official|order|delivery|takeout|take out|catering|now open|open|to go|curbside|franchise|inside .*|"
                       r"(?:(?:ice cream|chocolates?|fudge|coffee|cafe|café|restaurant|bar|grill|pizza|shawarma|hookah lounge|seafood|"
                       r"bakery|deli|sandwiches|bagels?|tacos|gifts?|shopping|treats|sweets|full bar|food|game room|drinks|spirits|live music|events|patio|"
                       r"lodging|rooms|resort|motel|cocktails|beer|wine|burgers|wings|craft beer|sports bar|and|&|,|-|\s)+))$", re.I)


def tidy(n, brand):
    n = after_dba(unicodedata.normalize("NFKC", n))
    if re.search(r"[ÃÂâð][\u0080-¿ŒœŠšŸŽžƒˆ˜–-›€™]", n):
        for enc in ("cp1252", "latin-1"):
            try:
                n = n.encode(enc).decode("utf-8"); break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    n = re.sub(r"[®™©]", "", EMOJI.sub("", n))
    if re.search(r"[A-Za-z]{3,}", re.sub(CJK, "", n)):
        n = re.sub(r"\s*\([^()]*" + CJK + r"[^()]*\)", "", n)
    latin = re.sub(CJK + "+", " ", n)
    if re.search(r"[A-Za-z]{3,}", latin) and re.search(CJK, n):
        n = re.sub(r"\(\s*\)", "", latin)
    m = re.match(r"^(.*?)[,\s]+(?:LLC|Inc)\.?\s*-{1,2}\s*(.+)$", n, flags=re.I)
    if m:
        n = m.group(2) if len(m.group(2).split()) >= 2 and len(m.group(1).split()) <= 2 else m.group(1)
    n = re.sub(r"[,\s]+(?:LLC|L\.L\.C|LLP|L\.L\.P|Inc|Corp)\.?(?=\s|$|,)", "", n, flags=re.I)
    n = re.sub(r"\s*\([^()]*\)\s*$", "", n) if re.sub(r"\s*\([^()]*\)\s*$", "", n).strip() else n
    n = re.sub(r",?\s+(?:PA|Pa\.|Penna\.?)\s*$", "", n)
    parts = re.split(r"\s+[-–]{1,2}\s+|--", n)
    if len(parts) > 1:
        tail = " ".join(parts[1:])
        if TAILWORDS.match(tail.strip()) or re.search(r"\b(?:Best|Award|Magazine|Voted|20\d\d)\b", tail):
            n = parts[0]
    if isinstance(brand, str):
        n = re.sub(r"\s*#\s*\d+\s*$", "", n)
    n = re.sub(r"\s+[-–]\s+\d+[A-Za-z]?\s+[A-Za-z][\w.' ]*$", "", n)   # "Afrim Sports - 636 Albany Shaker Rd", "A&S Fine Foods - 361 Ave X"
    n = re.sub(r"^(.+?),\s*(the)$", lambda m: ("THE " if m.group(2).isupper() else "The ") + m.group(1), n, flags=re.I)   # "LOUNGE, THE" -> "THE LOUNGE"
    n = re.sub(r"^(?:Inc|LLC|Corp)\.?\s+", "", n, flags=re.I)                    # "Inc Star Luna"
    n = re.sub(r"^[^\w(]+", "", n)                                                # "?tea"
    n = re.sub(r"\s*(?:\.\s*){2,}$", "", n)                                       # "... . . ."
    n = re.sub(r"\s+", " ", n).strip(" -–,") or n
    return nice(n) if n.isupper() and len(n) > 4 else n


o["name_out"] = [tidy(n, b) for n, b in zip(o.name_out, o.brand_n)]
o.loc[o.brand_n.notna(), "name_out"] = [b if norm_name(n).startswith(norm_name(b)) and len(norm_name(b)) >= 3 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]
o["spell"] = o.name_out.map(lambda n: re.sub(r"[^a-z0-9]", "", n.lower()))
o["name_out"] = o.groupby("spell").name_out.transform(lambda s: s.mode().iat[0] if len(s) > 1 else s.iat[0])
towns_l = set(o.city.dropna().str.lower()) | set(o.place.dropna().str.lower()) | set(o.muni.dropna().str.lower())
nm = o.name_out.fillna("")
junk = (nm.str.match(r"(?i)^\d+(?:-\d+)?\s+(?:[NSEW]\.?\s+)?[\w.' ]+?\b(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Blvd|Ln|Lane|Way|Ct|Pl|Hwy|Pkwy|Trl|Tpke|Turnpike|Broadway)\b\.?(?:\s*#\s*\w+)?(?:\s*,.*)?$")
        | nm.str.contains(r"(?i)(?:\bclosed|\bretired)\s*\)?\s*$") | (nm.str.lower().str.strip().isin(towns_l) & o.brand_n.isna())
        | nm.str.match(r"(?i)^(?:city|town|village|borough) of ") | nm.str.strip().str.lower().isin(["kitchen", "bar", "pub", "tavern", "grill", "deli", "pizza", "bakery", "coffee", "diner", "restaurant", "cafe", "café", "d.b.a.", "dba", "d/b/a", "inc", "llc", "the"])
        | nm.str.match(r"^\(.*\)\W*$") | nm.str.fullmatch(r"(?i)[a-z]?\d+[a-z]?(?:\s+\d+)?")
        | ~nm.str.contains(r"[A-Za-z]"))
ENT_ONLY = nm.str.contains(r"\b(?:LLC|Inc|Corp|Corporation|Enterprises?|Holdings?|Associates|Partners|Management|Ventures)\b\.?$", case=False, regex=True) \
    & ~nm.map(lambda n: norm_name(ENTITY.sub(" ", n))).str.contains(FOODWORD)
junk |= ENT_ONLY & ~o.get("hc", pd.Series(False, index=o.index)).fillna(False).astype(bool)
print("junk names dropped:", int(junk.sum()), nm[junk].head(10).tolist(), "| legal-entity names:", int(ENT_ONLY.sum()), nm[ENT_ONLY].head(6).tolist(), flush=True)
o = o[~junk].reset_index(drop=True)

# ---------------------------------------------------------------- not restaurants (hidden unless "include non-restaurants" is on)
STORE = re.compile(r"^(?:SUNOCO|MOBIL|SHELL|GULF|CITGO|VALERO|BP|EXXON|SPEEDWAY|UNI MART|UNIMART|COUNTRY FAIR|FUEL ?ONE|"
                   r"WEGMANS|SHOPRITE|SHOP RITE|ACME(?: MARKETS?)?|GIANT(?: FOOD STORES?| EAGLE| MARKET)?|MARKET DISTRICT|WEIS(?: MARKETS?)?|REDNERS(?: MARKETS?)?|"
                   r"KARNS(?: FOODS?)?|BOYERS(?: FOOD MARKETS?)?|SAVE A LOT|FRESH GROCER|WALMART\b.*|COSTCO\b.*|TARGET|BJS WHOLESALE.*|WHOLE FOODS(?: MARKET)?|"
                   r"TRADER JOES|ALDI|LIDL|CVS|WALGREENS|RITE AID|DOLLAR \w+|DASHMART|GOPUFF)$|"
                   r"\b(?:GAS STATION|TRAVEL (?:CENTER|PLAZA)|TRUCK STOP|SERVICE (?:PLAZA|AREA)|LIQUORS? (?:STORE|SHOPPE?|OUTLET)|FINE WINE AND GOOD SPIRITS|"
                   r"WINE (?:MERCHANTS?|SHOP|STORE|OUTLET)|WINE AND (?:LIQUOR|SPIRITS)|AND SPIRITS$|BEER DISTRIBUTOR|BEVERAGE DISTRIBUTOR|VENDING|COMMISSARY|"
                   r"FOOD PANTRY|MEAT MARKET|BUTCHER|MINI ?MART|MINI MARKET|CONVENIENCE|SMOKE SHOP|GROCERY|SUPERMARKET|FOOD MARKET|GHOST KITCHEN|"
                   r"VIRTUAL KITCHEN|MRBEAST|MR BEAST|ITS JUST WINGS|WOW BAO|GENTLEM[AE]NS CLUB|TRAMPOLINE|INDOOR PLAYGROUND|LINDT|"
                   r"ROCKY MOUNTAIN CHOCOLATE|JELLY BELLY|GODIVA)\b")
# Pennsylvania's convenience chains with made-to-order food counters (Wawa hoagies, Sheetz MTO): flagged on their own so Nick can decide
COUNTER_BRANDS = ["Wawa", "Sheetz", "GetGo", "Rutter's", "Turkey Hill", "Royal Farms", "7-Eleven"]
REALFOOD = re.compile(r"\b(?:RESTAURANT|GRILL|BAR|PUB|TAVERN|PIZZA|PIZZERIA|CAFE|KITCHEN|STEAK|BISTRO|DINER|BREWING|BREWERY|TAP|SALOON|"
                      r"TAPROOM|LOUNGE|INN|EATERY|BURGERS?|BBQ|TACOS?|DRIVE IN|DELI|COFFEE|ICE CREAM|CREAMERY|BAKERY|SEAFOOD|DONUTS?|BAGELS?|HOTS|WINGS)\b")
CANDY = re.compile(r"\b(?:CANDY|CANDIES|FUDGE|POPCORN|CONFECTION\w*|CHOCOLATES?|CHOCOLATIER|TRUFFLES?|SWEETS? SHOPPE?|KETTLE CORN|NUTRITION)\b")
HARD = re.compile(r"\b(?:AIRPORT|TERMINAL [A-Z0-9]|CONCOURSE|GATE [A-Z]?\d+|PHL|LINCOLN FINANCIAL FIELD|CITIZENS BANK PARK|WELLS FARGO CENTER|"
                  r"XFINITY MOBILE ARENA|PNC PARK|ACRISURE STADIUM|PPG PAINTS ARENA|BEAVER STADIUM|LEVY|SODEXO|ARAMARK|DELAWARE NORTH|CENTERPLATE|COMPASS GROUP|"
                  r"CHARTWELLS|BON APPETIT|HMSHOST|EUREST|GUCKENHEIMER|SSP AMERICA|OTG|DELTA SKY CLUB|COMMISSARY|DINING HALL|UNIVERSITY DINING|"
                  r"CORRECTIONAL|PRISON|CAREERS|TRUCK ENTRANCE)\b")
SOFT = re.compile(r"\b(?:STADIUM|ARENA|FESTIVAL|CONCESSIONS?|FOOD ?SERVICES?|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|ELEMENTARY|STUDENT|CAMPUS|"
                  r"HOSPITAL|MEDICAL CENTER|CLINIC|HEALTH CENTER|SENIOR|RETIREMENT|ASSISTED LIVING|NURSING|CARE CENTER|REHAB|CHURCH|PARISH|"
                  r"CONGREGATION|TEMPLE|SYNAGOGUE|MOSQUE|MINISTR(?:Y|IES)|VFW|AMERICAN LEGION|AMVETS|FRATERNAL ORDER|ELKS LODGE|"
                  r"MOOSE LODGE|KNIGHTS OF COLUMBUS|COUNTRY CLUB|GOLF CLUB|GOLF COURSE|YACHT CLUB|ATHLETIC CLUB|SOCIAL CLUB|BEACH CLUB|"
                  r"SPORTSMEN'?S CLUB|ROD AND GUN|FISH AND GAME|CATERING|CATERERS?|BANQUETS?|BANQUET HALL|EVENT (?:CENTER|VENUE|SPACE)|"
                  r"CONVENTION CENTER|CONFERENCE CENTER|MUSEUM|ZOO|AQUARIUM|THEATER|THEATRE|CINEMAS?|BOWLING|LANES|"
                  r"HOTEL|MOTEL|INN AND SUITES|SUITES|MARRIOTT|HILTON|HYATT|SHERATON|WESTIN|HOLIDAY INN|HAMPTON INN|FAIRFIELD INN|RESIDENCE INN|"
                  r"COURTYARD|SPRINGHILL|RADISSON|BEST WESTERN|COMFORT INN|SUPER 8|RED ROOF|DAYS INN|"
                  r"CORPORATE|EMPLOYEE|CAFETERIA|MOBILE|FOOD TRUCK|FOOD CART|KIOSK|GYM|FITNESS|YMCA|YWCA|BOYS AND GIRLS CLUB|DAYCARE|DAY CARE|CHILD CARE|"
                  r"CHILDCARE|LEARNING CENTER|JAIL|MILITARY|NATIONAL GUARD|BUILDING)\b")
kd = o.name_out.map(norm_name).fillna("")
k_ = o.k.fillna("")
busy = o.reviews.fillna(0) >= 200
gfirst = o.gcats.fillna("").str.split("|").str[0]
plainly_food = kd.str.contains(REALFOOD) | o.cat.isin(["bar", "brewery", "coffee_shop", "cafe"]) \
    | gfirst.str.contains(r"\b(?:Bar|Pub|Restaurant|Cafe|Café|Coffee|Tavern|Grill|Brewery|Diner|Bakery)\b", regex=True)
brand_store = o.brand_n.isin(["Wegmans", "ShopRite", "Whole Foods Market", "Trader Joe's", "Sunoco", "Speedway", "Valero", "Rite Aid"])
counter = o.brand_n.isin(COUNTER_BRANDS) | o.k.fillna("").str.match(r"^(?:WAWA|SHEETZ|GETGO|RUTTERS|TURKEY HILL|ROYAL FARMS|7 ELEVEN)\b")
store = kd.str.contains(STORE) | brand_store | (o.dom.isin(STORE_DOMS_ALL) & ~plainly_food) | (kd.str.contains(CANDY) & ~kd.str.contains(REALFOOD) & ~busy)
venue = kd.str.contains(HARD) | k_.str.contains(HARD) | o.name.fillna("").str.upper().str.contains(r"\(T-?\d|\bGATE [A-Z]?\d", regex=True) \
    | (kd.str.contains(SOFT) & ~(busy | plainly_food))
LICENSE_ONLY_NONREST = re.compile(r"\b(?:APARTMENTS?|POOLS?|SWIM|AQUATIC|SPORTSM[AE]NS?|GUN CLUB|ASSOCIATION|ATTN|C O|EVENTS?|STUDIOS?|"
                                  r"BOATS|SPORTS CENTER|HOSPITALITY GROUP|KNIGHTS|HEALTH|CONDOMINIUMS?|HOMEOWNERS|NEIGHBORHOOD|COMMUNITY|"
                                  r"PARKS AND REC|RECREATION|CAMP|BIBLE|FOUNDATION|SOCIETY|COUNCIL|LEAGUE|UNION|INSTITUTE|CENTER$|FARMS?|AMUSEMENT|"
                                  r"ENTERTAINMENT|CORPORATION|HOLDINGS|MANAGEMENT|VENTURES|FIELD|PERFORMING ARTS|VINEYARDS?|WINERY|CATERERS?|CATERING)\b")
lic_only = o.src.eq("official")
club = kd.str.contains(r"\bCLUB\b") & ~kd.str.contains(r"NIGHT ?CLUB|CLUB CAR|CLUB SANDWICH|SUPPER CLUB|BOCCE CLUB")
venue |= lic_only & (kd.str.contains(LICENSE_ONLY_NONREST) | club) & ~busy
for la, lo, r_ in ((39.8744, -75.2424, 1.6), (40.4915, -80.2329, 1.2), (40.6524, -75.4404, 0.5), (40.1935, -76.7634, 0.5), (41.3385, -75.7234, 0.4),
                   (42.0831, -80.1739, 0.3)):   # PHL, PIT, Lehigh Valley, Harrisburg, Wilkes-Barre/Scranton and Erie airports
    venue |= (np.hypot((o.lat - la) * 111, (o.lon - lo) * 83) < r_) & ~busy
GAMING = re.compile(r"\b(?:SPORTSBOOK|SPORTS BOOK|OFF TRACK|OTB|BETTING|SLOT|SLOTS|GAMING|VGT|SKILL GAMES?)\b")
MEMBERS = re.compile(r"\b(?:ELKS|MOOSE|LODGE NO|HOSE CO(?:MPANY)?|FIRE (?:COMPANY|DEPARTMENT|DEPT)|VOLUNTEER FIRE|VFW|AMERICAN LEGION|"
                     r"KNIGHTS OF COLUMBUS|SONS OF ITALY|AMVETS|ORDER OF EAGLES|EAGLES AERIE|POLISH FALCONS|ROD AND GUN|FISH AND GAME|"
                     r"SPORTSM[AE]NS|YACHT CLUB|COUNTRY CLUB|GOLF CLUB|BEACH CLUB|SOCIAL CLUB|ATHLETIC CLUB|SWIM CLUB|TENNIS CLUB|"
                     r"FRATERNAL ORDER OF POLICE|FOP LODGE|LIEDERKRANZ|MAENNERCHOR|TURNVEREIN|SLOVAK CLUB|POLISH CLUB|ITALIAN AMERICAN CLUB|"
                     r"FIREMENS|FIREMEN'S|AMBULANCE ASSOCIATION|LEGION POST|VFW POST|ROD AND GUN CLUB)\b")
gaming, members = kd.str.contains(GAMING), kd.str.contains(MEMBERS)
# a diner or restaurant named for a club or a moose ("Country Club Diner", "Minced Moose") is a restaurant; a lone MOOSE needs LODGE
members &= ~kd.str.contains(r"\b(?:DINER|RESTAURANT|GRILLE?|CAFE|PIZZA|PIZZERIA|BISTRO|KITCHEN|EATERY)\b") | kd.str.contains(r"\bLODGE NO\b|\bPOST \d")
members &= ~(kd.str.contains(r"\bMOOSE\b") & ~kd.str.contains(r"\bLOYAL ORDER OF MOOSE\b|\bMOOSE (?:LODGE|FAMILY CENTER|CLUB)\b"))
# ACHD's "Social Club-Bar Only" category is a members' club (decision pending with Nick: flagged, hidden by default)
members |= pd.Series([isinstance(j, float) and j == j and "Social Club" in str(F.cred.iat[int(j)]) for j in o.off_achd], index=o.index)
o["counter"] = counter
o["members"] = members
o["venue"] = store | venue | gaming | members | counter
print("non-restaurants flagged:", int(o.venue.sum()), "| stores:", int(store.sum()), "| venues:", int((venue & ~store).sum()),
      "| betting:", int(gaming.sum()), "| member clubs:", int(members.sum()), "| convenience counters:", int(counter.sum()), flush=True)

# ---------------------------------------------------------------- guides: name-based tags (web and app), hand-checked kinds added below
nkey = o.name_out.map(norm_name).fillna("")
o["t_steak"] = (nkey.str.contains(r"\bCHEESE ?STEAKS?\b|\bSTEAKS?\b.*\bHOAGIES?\b|\bHOAGIES?\b|\bROAST PORK\b|\bKING OF STEAKS\b|\bSTEAKS?$") & ~o.cuisine.eq("Steakhouse") & ~nkey.str.contains(r"\bSTEAK ?HOUSE\b|\bCHOP ?HOUSE\b|\bGRILLE?\b.*\bSTEAKS$|\bSEAFOOD\b|\bTEXAS ROADHOUSE\b"))
o["t_pie"] = nkey.str.contains(r"\bTOMATO PIE\b|\bOLD FORGE\b.*\bPIZZA|\bPIZZA\b.*\bOLD FORGE\b")
o["t_pierogi"] = nkey.str.contains(r"\bPIEROG|\bPYROH|\bPEROGI")
o["t_dutch"] = nkey.str.contains(r"\bDUTCH\b|\bAMISH\b|\bSMORGASBORD\b|\bPA DUTCH\b") & ~nkey.str.contains(r"\bDUTCH BROS\b")
o["t_pretzel"] = nkey.str.contains(r"\bPRETZELS?\b") & ~o.brand_n.isin(["Auntie Anne's"])
o["t_diner"] = nkey.str.contains(r"\bDINER\b") | o.tax.eq("diner")
o["t_oldest"] = False
if APP:   # in the app the guides list hand-checked places only; name tags still help search
    for t_ in TAGS:
        o["n_" + t_] = o["t_" + t_]

# ---------------------------------------------------------------- the hand-checked research and honors
for col in ("jbf", "michelin", "founded", "founded_note", "cur_tags", "dishes", "season", "branch", "rnote", "rsite", "chef", "rsrc", "evidence"):
    o[col] = None
o["seasonal"] = False
match_curated = curated_matcher(o)
o["hc"] = False
matched_cur, unmatched = 0, []
for c in CUR:
    best = match_curated(c)
    if best is None:
        unmatched.append(c["name"] + " (" + (c.get("city") or "") + ")")
        continue
    matched_cur += 1
    i = o.index[best]
    if c.get("verified"):   # hand-checked = a 2025-26 source shows it open; an honor alone doesn't
        o.at[i, "hc"] = True
    for col, vals in (("jbf", c.get("james_beard")), ("cur_tags", c.get("tags")), ("dishes", c.get("dishes"))):
        if vals:
            have = [x for x in (o.at[i, col] or "").split("; ") if x]
            o.at[i, col] = "; ".join(have + [v for v in dict.fromkeys(vals) if v not in have])
    for col, v in (("michelin", c.get("michelin")), ("founded", c.get("founded")), ("founded_note", c.get("founded_note")),
                   ("season", c.get("season")), ("branch", c.get("branch_of")), ("rnote", c.get("note")), ("rsite", c.get("website")),
                   ("chef", c.get("chef")), ("rsrc", (c.get("rsources") or [None])[0]), ("evidence", c.get("evidence_date"))):
        if v and not o.at[i, col]:
            o.at[i, col] = v
    if c.get("seasonal"):
        o.at[i, "seasonal"] = True
print(f"research entries matched: {matched_cur}/{len(CUR)}; unmatched ({len(unmatched)}): {unmatched[:25]}", flush=True)
closed_v = []
for f in sorted(glob.glob(f"{DATA}/research/closed*.json")):
    try:
        closed_v += json.load(open(f))
    except json.JSONDecodeError as e:
        print("!! closed file doesn't parse, skipped:", f, e)
closed_v = [c for c in closed_v if c.get("name")]
# a closure removes the place only when the listing carries the closed place's own name: a new shop at the same address
# (2788 Bagels where Absolute Bagels was) is another business
def closed_match(c):
    b = match_curated(c)
    if b is None:
        return None
    return b if name_sim(norm_name(c["name"]), norm_name(o.name_out.iat[b]) or "") >= 85 or fuzz.ratio(norm_name(c["name"]), norm_name(o.name_out.iat[b])) >= 85 else None


gone = [(c["name"], o.name_out.iat[b]) for c in closed_v for b in [closed_match(c)] if b is not None]
drop_closed = {o.index[b] for c in closed_v for b in [closed_match(c)] if b is not None}
o = o.drop(index=list(drop_closed)).reset_index(drop=True)
print("verified closed, removed:", len(drop_closed), gone[:20], flush=True)
tags_c = o.cur_tags.fillna("").str.lower()
for t_, kinds in TAG_KINDS.items():
    has = tags_c.map(lambda s: any(k in s.split("; ") for k in kinds))
    o["t_" + t_] = (o["t_" + t_] & ~APP) | has if APP else (o["t_" + t_] | has)
KIND_CUISINE = [("cheesesteak", "Sandwiches & Deli"), ("roast pork", "Sandwiches & Deli"), ("hoagie", "Sandwiches & Deli"),
                ("tomato pie", "Pizza"), ("old forge", "Pizza"), ("pierogi", "European"), ("pittsburgh sandwich", "Sandwiches & Deli"),
                ("pa dutch", "American & Other"), ("pretzel", "Bakery & Sweets"), ("diner", "Breakfast & Diner")]
generic = o.hc & o.cuisine.eq("American & Other")
o.loc[generic, "cuisine"] = [next((c for k, c in KIND_CUISINE if k in t.split("; ")), "American & Other") for t in tags_c[generic]]
o["honored"] = o.jbf.notna() | o.michelin.notna() | o.t_oldest
o.loc[o.hc | o.honored, "venue"] = False   # an honored or hand-checked place is a restaurant, whatever its name says
o.loc[o.michelin.notna() & o.cuisine.eq("Bar & Pub"), "cuisine"] = "American & Other"
o.loc[o.michelin.isin(["1 Star", "2 Stars", "3 Stars"]) & o.price_est.eq(1), "price"] = 4
o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")

# ---------------------------------------------------------------- inspections (each jurisdiction's own, never blended) and licenses


def rec(col, j):
    return F[col].iat[int(j)] if j == j and j is not None else None


for c in ("placard", "placard_color", "last_insp", "insp_purpose", "cred"):
    o["ac_" + c] = [rec(c, j) for j in o.off_achd]
AC_COLS = [c for c in o.columns if c.startswith("ac_")]
bad = o.county.ne("Allegheny") & o.ac_last_insp.notna()
if bad.any():
    print("ACHD records outside Allegheny County, dropped from those places:", int(bad.sum()), o.name_out[bad].head(5).tolist(), flush=True)
o.loc[o.county.ne("Allegheny"), AC_COLS] = None
o["phl_lic"] = [rec("cred", j) for j in o.off_philly]
o["phl_since"] = [rec("since", j) for j in o.off_philly]
o.loc[o.county.ne("Philadelphia"), ["phl_lic", "phl_since"]] = None
o["liq"] = [rec("cred", j) for j in o.off_plcb]
o["liq_since"] = [rec("since", j) for j in o.off_plcb]
o["plcb_lic"] = [rec("lic", j) for j in o.off_plcb]
print("Allegheny places with an ACHD placard:", int(o.ac_placard.notna().sum()), o.ac_placard.value_counts().to_dict(),
      "| Philadelphia licensed:", int(o.phl_lic.notna().sum()), "| liquor licensed:", int(o.liq.notna().sum()), flush=True)

# ---------------------------------------------------------------- sales / profit: the Chicago model (web leaderboard only)
auv = {a["brand"]: a for a in json.load(open(f"{DATA}/chain_auv.json")) if a.get("auv_usd")}
med_rev = o[o.reviews.notna() & (o.chain_n < 5)].groupby("price").reviews.median()
rel = (o.reviews + 10) / (o.price.map(med_rev) + 10)
bump = np.where(o.bar, 1.15, 1.0)
o["rev"] = (o.price.map(BASE) * bump * rel.fillna(0.6) ** B_FIT).clip(100_000, 40_000_000)
o["rev_src"] = np.where(o.reviews.notna(), "model", "model-low")
n_auv = 0
for b, a in auv.items():
    sel = o.brand_n == b
    if not sel.any():
        continue
    n_auv += 1
    med = o.loc[sel, "reviews"].median()
    r_ = (o.loc[sel, "reviews"] / med) ** 0.35 if med == med else pd.Series(np.nan, index=o.index[sel])
    o.loc[sel, "rev"] = a["auv_usd"] * r_.fillna(0.85).clip(0.6, 1.5)
    o.loc[sel, "rev_src"] = "chain"
o.loc[o.venue & o.rev_src.isin(["model", "model-low"]), "rev_src"] = "venue"
m_rat = o.rating.mean() if o.rating.notna().any() else 4.2
o["bayes"] = (o.reviews * o.rating + 40 * m_rat) / (o.reviews + 40)
margin = o.price.map(MARGIN)
margin = o.cuisine.map(MARGIN_CUISINE).fillna(margin) * (0.8 + 0.4 * pct(o.bayes).fillna(40) / 100)
o["margin"] = margin.round(4)
o["profit"] = o.rev * o.margin
o["food_cost"] = o.cuisine.map(FOOD_COST).fillna(30)
o["value_raw"] = o.bayes - 0.18 * (o.price - 1)


def own_jbf(jb):
    """James Beard lines about the restaurant or its chef; an Outstanding Restaurateur honor belongs to the owners' whole group."""
    return "; ".join(h for h in (jb or "").split("; ") if "Restaurateur" not in h)


jb = o.jbf.map(lambda v: own_jbf(v) if isinstance(v, str) else "")
MI_PTS = {"3 Stars": 70, "2 Stars": 62, "1 Star": 52, "Bib Gourmand": 36, "Recommended": 22}
acc = (jb.str.contains("America's Classic") * 40 + jb.str.contains(r"\bwinner\b", case=False) * 26
       + (jb.str.contains(r"(?<!semi)finalist|nominee", case=False) & ~jb.str.contains(r"\bwinner\b", case=False)) * 14
       + (jb.str.contains("semifinalist", case=False) & ~jb.str.contains(r"(?<!semi)finalist|nominee|\bwinner\b", case=False)) * 6
       + o.michelin.map(MI_PTS).fillna(0) + o.t_oldest * 16).clip(upper=70)
years = (2026 - pd.to_numeric(o.founded, errors="coerce")).clip(lower=0)
o["s_icon"] = np.where(o.honored, (acc + years.fillna(0).clip(upper=100) / 100 * 20 + pct(np.log1p(o.reviews)).fillna(0) / 100 * 10).clip(upper=100), np.nan)


def r(x, n=0):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return int(round(float(x))) if n == 0 else round(float(x), n)


def clean(v):
    """NaN (pandas' missing value) -> None, all the way down, so json.dump(allow_nan=False) never trips."""
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        return clean(v.item())
    return v


def sval(v):
    return v if isinstance(v, str) and v else None


def hon_flags(x):
    jb_ = own_jbf(x.jbf)
    return ((1 if "America's Classic" in jb_ else 0) | (2 if re.search(r"\bwinner\b", jb_, re.I) else 0)
            | (4 if re.search(r"(?<!semi)finalist|nominee", jb_, re.I) else 0) | (8 if re.search("semifinalist", jb_, re.I) else 0)
            | (16 if x.t_oldest else 0))


def clean_url(u):
    base, _, q = u.partition("?")
    keep_ = [kv for kv in q.split("&") if kv and not re.match(r"(rwg_token|utm_[a-z]+|fbclid|gclid|y_source|cmpid|ref)=", kv)]
    return base + ("?" + "&".join(keep_) if keep_ else "")


MI_LEVEL = {"Recommended": 1, "Bib Gourmand": 2, "1 Star": 3, "2 Stars": 4, "3 Stars": 5}
o = o[o.lat.notna()].reset_index(drop=True)
o["street"] = o.street.map(lambda a: a if isinstance(a, str) and re.match(r"\s*\d", a) else (a if isinstance(a, str) and not re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+$", a) else None))

# ---------------------------------------------------------------- the same place twice: same name at the same street address, or (not a
# chain) the same name in one city within 300 m (NYC) / 400 m. The official record wins, then a hand-checked one, then more facts;
# the kept copy inherits what the dropped one knew (a license record can't take a hand-checked slice shop off its guide).
rank = o.tier.map({"official": 2, "both": 1, "listing": 0}).fillna(0) * 10 + o.hc.astype(int) * 5 + o.web.notna().astype(int)
keyname = o.name_out.map(lambda n: norm_name(n) or re.sub(r"[^a-z0-9]", "", str(n).lower()))
keyaddr = ["|".join(k) if all(k := street_key(s_)) else None for s_ in o.street]
drop2, merged, seen = set(), [], {}
for pos, i in enumerate(o.index):
    if keyaddr[pos] and keyname[i]:
        k = (keyname[i], keyaddr[pos], o.county[i])
        if k in seen:
            j = seen[k]
            lose = i if rank[i] <= rank[j] else j
            drop2.add(lose); seen[k] = j if lose == i else i
            merged.append((seen[k], lose))
        else:
            seen[k] = i
single = o[(o.chain_n.fillna(1) < 2) & ~o.index.isin(drop2)]
for (nm_, town), g in single.groupby([keyname[single.index], single.city]):
    if len(g) < 2 or not nm_:
        continue
    idx = list(g.index)
    for a_ in range(len(idx)):
        for b_ in range(a_ + 1, len(idx)):
            i, j = idx[a_], idx[b_]
            if i in drop2 or j in drop2:
                continue
            if km(o.at[i, "lat"], o.at[i, "lon"], o.at[j, "lat"], o.at[j, "lon"]) < (0.3 if o.at[i, "city"] in ("Philadelphia", "Pittsburgh") else 0.4):
                lose = i if rank[i] <= rank[j] else j
                drop2.add(lose); merged.append((j if lose == i else i, lose))
INHERIT = ["dishes", "season", "branch", "rnote", "rsite", "rsrc", "web", "phone", "founded", "founded_note", "jbf", "michelin", "chef", "s_icon",
           "cur_tags", "evidence", "liq", "liq_since", "plcb_lic", "phl_lic", "phl_since", "rating", "reviews", "gmap_id"] + \
          [c for c in o.columns if c.startswith("ac_")]
for keep_i, lose in merged:
    if o.at[keep_i, "cuisine"] == "American & Other" and o.at[lose, "cuisine"] != "American & Other":
        o.at[keep_i, "cuisine"] = o.at[lose, "cuisine"]
    for col in [c for c in o.columns if c.startswith("t_")] + ["hc", "honored", "seasonal"]:
        if bool(o.at[lose, col]) and not bool(o.at[keep_i, col]):
            o.at[keep_i, col] = o.at[lose, col]
    for col in INHERIT:
        a_, b_ = o.at[keep_i, col], o.at[lose, col]
        if (a_ is None or (isinstance(a_, float) and a_ != a_)) and not (b_ is None or (isinstance(b_, float) and b_ != b_)):
            o.at[keep_i, col] = b_
print("duplicates removed:", len(drop2), [o.at[i, "name_out"] for i in list(drop2)[:8]], flush=True)
o = o.drop(index=list(drop2))
fixes = json.load(open(f"{DATA}/research/name_fixes.json")) if os.path.exists(f"{DATA}/research/name_fixes.json") else []
for fx in fixes:
    hit = (o.name_out.str.upper() == fx["name"].upper()) & (o.city == fx["city"]) & o.street.fillna("").str.startswith(fx["street_number"] + " ")
    o.loc[hit, "name_out"] = fx["fixed"]
webs = o.web.fillna("").astype(str) + " " + o.rsite.fillna("").astype(str)
adult = (o.name_out.str.contains(r"gentlem[ae]n'?s club|exotic dancer|strip club|adult entertainment|go-?go bar|\bdelilah'?s\b|penthouse club|"
                                  r"club risqu|christie'?s cabaret|cheerleaders\b|\bdiamonds club|\bblush\b.*\bclub", case=False, regex=True)
         | (o.name_out.str.contains(r"\bcabaret\b", case=False, regex=True) & ~o.name_out.str.contains(r"theat|dinner|jazz|comedy", case=False, regex=True))) \
    | webs.str.contains(r"delilahs|penthouseclub|clubrisque|christiescabaret|cheerleadersphilly|gentlemensclub|gentlemens-club|stripclub", case=False, regex=True)
# Overture's own adult-entertainment listings: a listing with a shared distinctive word within 150 m is the same club under a plain name
import duckdb as _ddb
_AD = _ddb.connect().execute(f"SELECT name, lat, lon FROM '{PA}/overture_pa.parquet' WHERE (cat = 'adult_entertainment_venue' OR tax = 'strip_club') AND NOT regexp_matches(name, '(?i)living|skill games|literacy|institute')").df()
for n_, la_, lo_ in zip(_AD.name, _AD.lat, _AD.lon):
    st_ = _stems(norm_name(n_)) - GENERIC - TOWNWORDS
    if not st_:
        continue
    d_ = np.hypot((o.lat - la_) * 111000, (o.lon - lo_) * 84000)
    k_ = norm_name(n_)
    adult |= ~o.hc & (((d_ < 150) & o.name_out.map(lambda m: name_sim(k_, norm_name(m)) >= 85))
                      | ((d_ < 60) & o.name_out.map(lambda m: len(st_ & (_stems(norm_name(m)) - GENERIC)) >= 1 and len(st_) <= 2)))
print("adult clubs removed:", int(adult.sum()), o.name_out[adult].tolist()[:10], flush=True)
o = o[~adult]
smoke = o.name_out.str.contains(r"\bvape\b|smoke shop|\btobacco\b|cigar|\bcbd\b|dispensary|cannabis|head shop|hookah lounge", case=False, regex=True) & ~o.hc
o.loc[smoke, "venue"] = True
o = o.sort_values(["region", "county", "city", "name_out"], key=lambda s: s.map(REGIONS.index) if s.name == "region" else s).reset_index(drop=True)
nv = o[~o.venue]
COUNTIES = sorted(o.county.dropna().unique().tolist())
CITIES = sorted(o.city.dropna().unique().tolist()); CUIS = sorted(o.cuisine.unique().tolist()); BRANDS = sorted(o.brand_n.dropna().unique().tolist())
PLACES = sorted(o.place.dropna().unique().tolist()); HOODS = sorted(o.hood.dropna().unique().tolist()); MUNIS = sorted(o.muni.dropna().unique().tolist())
LIQT = [None] + sorted(o.liq.dropna().unique().tolist())
SRCS = ["official", "meta", "AllThePlaces", "DAC", "research", "BrightQuery", "Foursquare", "Microsoft"]
JURN = {"philly": 1, "achd": 2, "plcb": 3}
o["jur_n"] = [JURN.get(F.jur.iat[int(j)], 0) if j == j else 0 for j in o.off]
PLACARDS = sorted(o.ac_placard.dropna().unique().tolist())
COUNTY_REGION = {f["properties"]["county"]: f["properties"]["region"] for f in json.load(open(f"{PA}/pa_counties.geojson"))["features"]}
meta_common = {"generated": GENERATED, "overture_release": OVERTURE, "regions": REGIONS, "slugs": [SLUG[r_] for r_ in REGIONS],
               "counties": COUNTIES, "county_region": [REGIONS.index(COUNTY_REGION[c]) for c in COUNTIES], "tags": TAGS, "kinds": KINDS,
               "srcs": SRCS, "placards": PLACARDS, "liqt": LIQT, "records_through": THROUGH,
               "feeds": {"philly": CARTO_META["business_licenses"]["newest"][:10]}}
by_region = {r_: o.index[o.region == r_] for r_ in REGIONS}

if APP:
    def app_part(x):
        return (x.region, None)
    PARTS = [(r_, None) for r_ in REGIONS]
    PART_FILE = {(r_, b): f"places-{SLUG[r_]}{'-' + re.sub(r'[^a-z]+', '-', b.lower()) if b else ''}.json" for r_, b in PARTS}
    places_by = {}
    seen_ids = set()
    LINKS = json.load(open(f"{PA}/website_check.json")) if os.path.exists(f"{PA}/website_check.json") else None
    link_drops, link_cands = collections.Counter(), {}
    ci, cu, br, cy, pl, hd, mu = ({c: i for i, c in enumerate(L)} for L in (CITIES, CUIS, BRANDS, COUNTIES, PLACES, HOODS, MUNIS))
    TIER = {"listing": 0, "both": 1, "official": 2}
    KBIT = {k: 1 << i for i, k in enumerate(KINDS)}
    for i, x in o.iterrows():
        # a stable id from the source record (Overture's GERS id, the permit number, or the researched name + city), so saved places
        # survive a data refresh; never from a name and rounded coordinates
        idsrc = str(x.id) if isinstance(x.id, str) and x.id else f"{norm_name(x.name_out)}|{x.city}"
        p = {"id": hashlib.md5(idsrc.encode()).hexdigest()[:12], "n": x.name_out, "c": ci.get(x.city), "co": cy[x.county],
             "cu": cu[x.cuisine], "t": TIER[x.tier], "s": SRCS.index(x.src) if x.src in SRCS else 1}
        if isinstance(x.place, str) and x.place != x.city: p["pl"] = pl[x.place]
        if isinstance(x.hood, str): p["hd"] = hd[x.hood]
        if isinstance(x.muni, str) and x.muni not in (x.city, x.place): p["mu"] = mu[x.muni]
        if isinstance(x.street, str): p["a"] = nice(x.street, addr=True)
        if isinstance(x.zip, str) and re.match(r"^1[5-9]\d{3}", x.zip): p["z"] = x.zip[:5]
        p["la"], p["lo"] = round(float(x.lat), 5), round(float(x.lon), 5)
        if isinstance(x.brand_n, str): p["b"] = br[x.brand_n]
        if x.chain_n and int(x.chain_n) > 1: p["ch"] = int(x.chain_n)
        if x.jur_n: p["j"] = int(x.jur_n)
        if x.venue: p["v"] = 1
        if x.bar: p["bar"] = 1
        tg = sum(1 << bi for bi, t_ in enumerate(TAGS) if bool(x["t_" + t_]))
        if tg: p["g"] = tg
        if isinstance(x.liq, str): p["lq"] = LIQT.index(x.liq)
        if isinstance(x.ac_placard, str):
            p["ac"] = {"p": x.ac_placard, "d": sval(x.ac_last_insp)}
        if isinstance(x.phl_lic, str): p["phl"] = 1
        if x.counter: p["cc"] = 1
        if x.members: p["mc"] = 1
        if x.hc:
            p["hc"] = 1
            kinds = [k for k in (x.cur_tags or "").split("; ") if k in KBIT]
            if kinds: p["k"] = sum(KBIT[k] for k in kinds)
            for k, v in (("note", x.rnote), ("dish", x.dishes), ("sea", x.season), ("br", x.branch), ("src", x.rsrc), ("fn", x.founded_note)):
                if isinstance(v, str) and v:
                    p[k] = v
            if x.seasonal: p["seas"] = 1
        if x.honored or x.hc:   # honors are facts about the place, shown wherever it's listed
            for k, v in (("jbf", x.jbf), ("chef", x.chef)):
                if isinstance(v, str) and v:
                    p[k] = v
            if isinstance(x.michelin, str): p["mi"] = MI_LEVEL.get(x.michelin, 0)
            if x.s_icon == x.s_icon and x.s_icon is not None: p["ip"] = round(float(x.s_icon), 1)   # honors + verified years only: no review data in the app
            if isinstance(x.jbf, str) and x.jbf: p["h"] = hon_flags(x)
        if x.founded == x.founded and x.founded is not None: p["f"] = int(float(x.founded))
        web = x.rsite if isinstance(x.rsite, str) else (x.web if isinstance(x.web, str) else None)
        if web:
            w_ = clean_url(web)
            link_cands[w_] = x.brand_n if isinstance(x.brand_n, str) else x.name_out
            # fail closed: no check file, no links; and today's directory rules apply to links checked before they were added
            if link_blocked(w_):
                link_drops["on the website blocklist"] += 1
            elif LINKS is not None and LINKS.get(w_, {}).get("ok") and not bad_host(w_ if w_.startswith("http") else "https://" + w_):
                p["w"] = w_
            else:
                link_drops[LINKS.get(w_, {}).get("why", "not checked yet") if LINKS is not None else "no check file"] += 1
        digits = re.sub(r"\D", "", x.phone) if isinstance(x.phone, str) else ""
        digits = digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
        if len(digits) == 10 and digits[0] in "23456789": p["ph"] = "+1" + digits   # +1 and ten digits, or no phone at all
        while p["id"] in seen_ids:
            p["id"] = p["id"] + "x"
        seen_ids.add(p["id"])
        # one file per region so the app decodes them in parallel at launch
        places_by.setdefault(app_part(x), []).append(p)
    print("website links dropped:", sum(link_drops.values()), link_drops.most_common(8))
    json.dump(link_cands, open(f"{PA}/website_candidates.json", "w"), indent=0, ensure_ascii=False)
    os.makedirs(SITE, exist_ok=True)
    index = {"v": 1, **meta_common, "cities": CITIES, "mailing": PLACES, "hoods": HOODS, "munis": MUNIS, "cuisines": CUIS, "brands": BRANDS,
             "count": int(len(o)), "count_restaurants": int(len(nv)), "calibration": calib.get("app", {}),
             "files": [{"region": r_, "file": PART_FILE[(r_, b)], "count": len(places_by[(r_, b)]),
                        "count_restaurants": sum(1 for p in places_by[(r_, b)] if not p.get("v"))} for r_, b in PARTS if places_by.get((r_, b))]}
    assert sum(f["count"] for f in index["files"]) == len(o) and sum(f["count_restaurants"] for f in index["files"]) == len(nv), "file counts"
    assert not any(link_blocked(p.get("w")) for ps in places_by.values() for p in ps), "a website on pipeline/website_blocklist.json"
    for old_f in glob.glob(f"{SITE}/places-*.json"):
        os.remove(old_f)
    json.dump(clean(index), open(f"{SITE}/index.json", "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)
    for f in index["files"]:
        part = next(k for k, v in PART_FILE.items() if v == f["file"])
        json.dump(clean({"region": f["region"], "places": places_by[part]}), open(f"{SITE}/{f['file']}", "w"), separators=(",", ":"),
                  ensure_ascii=False, allow_nan=False, default=str)
    sizes = {f["file"][7:-5]: os.path.getsize(f"{SITE}/{f['file']}") // 1024 for f in index["files"]}
    print("APP: wrote", len(o), "places (", len(nv), "restaurants ) | KB by region:", sizes, "| total KB:", sum(sizes.values()),
          "| tiers:", nv.tier.value_counts().to_dict(), "| tags:", {t_: int(nv["t_" + t_].sum()) for t_ in TAGS}, "| hand-checked:", int(nv.hc.sum()))
    sys.exit(0)

# ---------------------------------------------------------------- web leaderboard export (columnar, one file per region; Google 2021 labeled)
ci, cu, br, cy, pl, hd = ({c: i for i, c in enumerate(L)} for L in (CITIES, CUIS, BRANDS, COUNTIES, PLACES, HOODS))
SRC = {"model": 0, "model-low": 1, "chain": 2, "reported": 3, "venue": 4}
TIER = {"listing": 0, "both": 1, "official": 2}
SCALE = {"lat": 10000, "lon": 10000, "rating": 10, "margin": 1000, "value_raw": 1000}
COLS = ["name", "addr", "city", "county", "place", "hood", "zip", "lat", "lon", "cuisine", "brand", "chain_n", "rating", "reviews", "price", "price_est",
        "rev_k", "rev_src", "margin", "value_raw", "tier", "jur", "bar", "venue", "tags", "src", "liq", "hc", "flag"]
os.makedirs(SITE, exist_ok=True)
files = []
for r_ in REGIONS:
    C = collections.OrderedDict((c, []) for c in COLS)
    SP = {"hon": [], "ac": []}
    extra = {}
    sub = o.loc[by_region[r_]]
    start = int(by_region[r_][0]) if len(by_region[r_]) else 0
    for i, x in sub.iterrows():
        tg = sum(1 << b for b, t_ in enumerate(TAGS) if bool(x["t_" + t_]))
        z = int(x.zip[:5]) if isinstance(x.zip, str) and re.match(r"^1[5-9]\d{3}", x.zip) else None
        vals = {"name": x.name_out, "addr": nice(x.street, addr=True) if isinstance(x.street, str) else None, "city": ci.get(x.city),
                "county": cy.get(x.county), "place": pl.get(x.place) if isinstance(x.place, str) and x.place != x.city else None,
                "hood": hd.get(x.hood) if isinstance(x.hood, str) else None, "zip": z, "lat": x.lat, "lon": x.lon, "cuisine": cu[x.cuisine],
                "brand": br.get(x.brand_n) if isinstance(x.brand_n, str) else None, "chain_n": int(x.chain_n), "rating": x.rating, "reviews": r(x.reviews),
                "price": int(x.price), "price_est": int(x.price_est), "rev_k": int(round(x.rev / 1000)), "rev_src": SRC[x.rev_src], "margin": x.margin,
                "value_raw": x.value_raw, "tier": TIER[x.tier], "jur": int(x.jur_n), "bar": int(bool(x.bar)), "venue": int(bool(x.venue)), "tags": tg,
                "src": SRCS.index(x.src) if x.src in SRCS else 1, "liq": LIQT.index(x.liq) if isinstance(x.liq, str) else 0, "hc": int(bool(x.hc)),
                "flag": int(bool(x.counter)) | int(bool(x.members)) << 1 | int(isinstance(x.phl_lic, str)) << 2}
        if x.honored:
            SP["hon"].append([i, int(round(x.s_icon * 10)), hon_flags(x), MI_LEVEL.get(x.michelin, 0) if isinstance(x.michelin, str) else 0])
        if isinstance(x.ac_placard, str):
            SP["ac"].append([i, x.ac_placard, sval(x.ac_last_insp), sval(x.ac_cred) or ""])
        for c, v in vals.items():
            if c in SCALE:
                v = None if v is None or v != v else int(round(float(v) * SCALE[c]))
            elif isinstance(v, float):
                v = None if v != v else v
            C[c].append(v.item() if hasattr(v, "item") else v)
        e = {k: v for k, v in (("jbf", x.jbf), ("michelin", x.michelin), ("founded", r(x.founded) if x.founded == x.founded and x.founded is not None else None),
                               ("founded_note", x.founded_note), ("note", x.rnote), ("dishes", x.dishes), ("season", x.season),
                               ("web", x.rsite if isinstance(x.rsite, str) and not link_blocked(x.rsite) else None), ("kinds", x.cur_tags), ("src", x.rsrc), ("chef", x.chef),
                               ("lic", x.plcb_lic), ("liq_since", x.liq_since), ("phl_lic", x.phl_lic), ("phl_since", x.phl_since),
                               ("muni", x.muni if x.muni != x.city else None))
             if isinstance(v, (str, int)) and v != ""}
        if e:
            extra[i] = e
    for _k, _v in list(C.items()) + list(SP.items()):
        _bad = [j for j, x in enumerate(_v) if (isinstance(x, float) and x != x) or (isinstance(x, list) and any(isinstance(y, float) and y != y for y in x))]
        if _bad: print("NaN in", r_, _k, len(_bad), _v[_bad[0]])
    fn, dn = f"pa-{SLUG[r_]}.json", f"pa-{SLUG[r_]}-detail.json"
    json.dump(clean({"region": r_, "start": start, "n": len(sub), "cols": C, "sparse": SP}), open(f"{SITE}/{fn}", "w"), separators=(",", ":"), allow_nan=False, default=str)
    json.dump(clean({"region": r_, "extra": {str(k): v for k, v in extra.items()}}), open(f"{SITE}/{dn}", "w"), separators=(",", ":"), allow_nan=False, default=str)
    files.append({"region": r_, "file": fn, "detail": dn, "start": start, "n": int(len(sub)), "restaurants": int((~sub.venue).sum())})
meta = {**meta_common, "cities": CITIES, "places": PLACES, "hoods": HOODS, "cuisines": CUIS, "brands": BRANDS, "src": list(SRC), "tiers": list(TIER),
        "food_cost": dict(FOOD_COST), "spend": SPEND, "count": len(o), "count_restaurants": int(len(nv)),
        "count_official": int(nv.official.sum()), "count_both": int((nv.tier == "both").sum()), "count_listing": int((nv.tier == "listing").sum()),
        "n_cities": int(nv.city.nunique()), "rating_mean": round(float(m_rat), 3), "model": {"b": B_FIT, "n_chains": n_auv},
        "calibration": calib, "n_honored": int(o.honored.sum()), "n_hc": int(o.hc.sum()), "files": files}
json.dump(clean({"n": len(o), "scale": SCALE, "meta": meta}), open(f"{SITE}/pa_index.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
json.dump(json.load(open(f"{PA}/pa_shapes.json")), open(f"{SITE}/pa_shapes.json", "w"), separators=(",", ":"))
o.drop(columns=["st", "ds"], errors="ignore").to_pickle(f"{PA}/stage2.pkl")
print("wrote", len(o), "places (", int(len(nv)), "restaurants ) |", {f["region"]: f["restaurants"] for f in files},
      "| KB:", {f["file"]: os.path.getsize(f"{SITE}/{f['file']}") // 1024 for f in files}, "| tiers:", nv.tier.value_counts().to_dict())
