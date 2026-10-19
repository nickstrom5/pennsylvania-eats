"""Stage 1: every Pennsylvania eating/drinking listing, cleaned, placed and matched to Google's Sep 2021 listings -> data/pa/stage1.pkl

Overture Maps places (2026-09-23.1 release) are the statewide base. Each listing is placed by its point in one of the 67 counties
(and so one of our nine regions) and one of the 2,571 municipalities (cities, boroughs and townships: Census county subdivisions).
The mailing name (Pittsburgh for a Millvale bar, Feasterville-Trevose for a Bensalem diner) is kept as `place` and shown; the
municipality is kept too and stays searchable.
This stage cleans names, drops junk and matches each listing to at most one Google 2021 listing (web leaderboard only). It keeps
every listing (with flags) so calibrate.py can measure which kinds of listings turn out to be real restaurants.
"""
import os, re, json, gzip, math, html
import numpy as np, pandas as pd, duckdb
import shapely
from shapely.geometry import shape
from rapidfuzz import fuzz
from common import norm_name, nice, name_sim, FOODCAT, NOTFOOD, GENERIC, _stems, DATA, PA, canon_city, town_key
from brands import brand_of

EAT = ("restaurant", "casual_eatery", "bar", "fast_food_restaurant", "coffee_shop", "cafe", "smoothie_juice_bar", "brewery", "food_court")

o = duckdb.connect().execute(f"""
  SELECT id, name, cat, tax, confidence, status, brand, street, city, zip, lat, lon, web, phone, ds, n_soc, n_web, n_ph
  FROM '{PA}/overture_pa.parquet' WHERE cat IN {EAT} AND name IS NOT NULL
""").df()
o["src"] = o.ds.map(lambda x: next((s for s in x if s not in ("Overture", "Overture-signals")), None) if x is not None else None)
o["ov_closed"] = o.status.eq("permanently_closed")
print("Overture PA eating listings:", len(o), "| marked permanently closed by Overture:", int(o.ov_closed.sum()), flush=True)


def fix_text(t):
    """Repair UTF-8 read as Latin-1 ("CafÃ©"), HTML entities ("&amp"), keyword tails after "|", and corporate suffixes."""
    if not isinstance(t, str):
        return t
    if re.search(r"[ÃÂ][\u0080-¿]", t):
        try:
            t = t.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    t = html.unescape(t)
    t = re.split(r"\s*\|\s*", t)[0]
    t = re.split(r"\s+f/?k/?a\s+", t, flags=re.I)[0]
    m = re.search(r"\bd/?b/?a\.?\s+(.+)$", t, flags=re.I)
    if m:
        t = m.group(1)
    t = re.sub(r"(?:,?\s+(?:Inc|LLC|L\.L\.C|Corp|Corporation|Ltd)\.?)+\s*$", "", t, flags=re.I)
    t = re.sub(r"(?<![&\s])(?<!\band)(?<!\bAnd)(?<!\bAND),?\s+Co\.?\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


o["name"] = o.name.map(fix_text)
o["street"] = o.street.map(lambda t: html.unescape(t).strip() if isinstance(t, str) else t)
ADDR = re.compile(r"(?:\d+(?:-\d+)?[A-Z]?)\s+(?:[NSEW]\.?\s+)?[\w.' ]+?\b(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Blvd|Ln|Lane|Way|Ct|Pl|Hwy|Pkwy|Trl|Pike|Cir|Ter|Tpke|Turnpike|Broadway|Bowery)\b\.?(?:\s*(?:#|Ste|Suite|Unit)\s*\w+)?", re.I)


def tidy_street(t):
    if not isinstance(t, str) or not re.search(r"(?i)located in|please|between|next to|inside|back door|entrance|across from", t):
        return t
    hits = ADDR.findall(t)
    return hits[-1].strip() if hits else t


o["street"] = o.street.map(tidy_street)
CLOSED = re.compile(r"\b(?:permanently|temporarily)\s+closed\b|\bclosed\s+(?:permanently|for business|at\b)|coming soon|\bnow closed\b"
                    r"|[-–(|]\s*['\"]?closed['\"]?\s*\)?\s*$|^closed\s*[-–:]", re.I)
JUNKNAME = re.compile(r"^[\d\s#-]+$")
NOTFOOD_NAME = re.compile(r"\b(?:radiator|auto (?:repair|body|parts|sales)|tires?|insurance|barber|dental|chiropractic|plumbing|realty|food pantry|"
                          r"distribution cent(?:er|re)|bakery warehouse|restaurant equipment|wholesale (?:distributor|supply|foods?)|"
                          r"meal program|soup kitchen|church|parish|funeral|daycare|day care|salon|storage|apartments?|condominiums?|operations)\b", re.I)
z5 = o.zip.fillna("").astype(str).str.strip().str[:5]
o["nowhere"] = o.street.fillna("").str.strip().eq("") & z5.eq("")
o["j_closedname"] = o.name.fillna("").str.contains(CLOSED)
o["j_junk"] = (o.name.fillna("").str.match(JUNKNAME) | o.name.fillna("").str.contains(NOTFOOD_NAME)
               | (z5.ne("") & ~z5.str.match(r"^(?:1[5-9]\d{3})$"))
               | o.street.fillna("").map(lambda t: bool(re.search(r"[^\x00-ɏ]", t))))
closed = o[o.j_closedname]
twin = np.zeros(len(o), bool)
for la, lo, k in [(la, lo, norm_name(CLOSED.sub(" ", n))) for la, lo, n in zip(closed.lat, closed.lon, closed.name)]:
    near = (np.abs(o.lat - la) < 0.0015) & (np.abs(o.lon - lo) < 0.002)
    for i in np.flatnonzero(near.to_numpy()):
        if k and fuzz.token_set_ratio(k, norm_name(o.name.iat[i])) >= 90:
            twin[i] = True
o["j_closedname"] |= twin

# ---- the mailing name ("place"): one spelling each; a missing one from the address text, else from the zip's usual place
o["city"] = o.city.map(canon_city)
tk = o.city.dropna().map(town_key)
main = o.city.dropna().groupby(tk).agg(lambda x: x[~x.str.islower()].mode().iat[0] if (~x.str.islower()).any() else x.mode().iat[0])
o["city"] = o.city.map(lambda c: main.get(town_key(c), c) if isinstance(c, str) else c)
TOWN_TAIL = r",\s*([A-Za-z .'-]+?),\s*(?:PA|Pa\.|Penna\.?|Pennsylvania)\b.*$"
miss = o.city.isna()
o.loc[miss, "city"] = o.loc[miss, "street"].fillna("").str.extract(TOWN_TAIL)[0].map(canon_city)
o["street"] = o.street.str.replace(TOWN_TAIL, "", regex=True)
zip_town = o[o.city.notna()].assign(z=o.zip.fillna("").astype(str).str[:5]).groupby("z").city.agg(lambda x: x.mode().iat[0])
miss = o.city.isna()
o.loc[miss, "city"] = o.loc[miss, "zip"].fillna("").astype(str).str[:5].map(zip_town)
print("places still without a mailing name:", int(o.city.isna().sum()), flush=True)


def dom(w):
    from urllib.parse import urlparse
    if not isinstance(w, str) or not w.strip():
        return None
    try:
        h = urlparse(w if "://" in w else "http://" + w).netloc.lower()
    except ValueError:
        return None
    parts = re.sub(r"^www\d?\.", "", h).split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else None


AGGREGATOR = {"facebook.com", "business.site", "grubhub.com", "doordash.com", "ubereats.com", "yelp.com", "toasttab.com", "square.site",
              "order.online", "google.com", "instagram.com", "menufy.com", "chownow.com", "clover.com", "wixsite.com", "godaddysites.com",
              "squarespace.com", "weebly.com", "linktr.ee", "slicelife.com", "beyondmenu.com", "seamless.com", "co.uk", "wordpress.com",
              "tripadvisor.com", "orderonline.com", "spoton.com", "popmenu.com", "bentobox.com", "places.singleplatform.com",
              "chamberofcommerce.com", "hub.biz", "restaurantji.com", "menupix.com", "allmenus.com", "zmenu.com", "opentable.com", "resy.com",
              "exploretock.com", "wix.com", "site123.me", "webs.com", "yellowpages.com", "mapquest.com", "foursquare.com", "tumblr.com",
              "blogspot.com", "carrd.co", "square.com", "toast.site", "hungerrush.com", "gloriafood.com", "mobilebytes.com",
              "orderspoon.com", "revelup.com", "wordpress.org", "godaddy.com", "myshopify.com", "linkedin.com", "twitter.com", "x.com",
              "menupages.com", "caviar.com", "postmates.com", "sevenrooms.com", "tock.com"}
o["dom"] = o.web.map(dom).where(lambda d: ~d.isin(AGGREGATOR))

# ---- placement: county (-> region) and municipality. Vectorized point-in-polygon (STRtree).
pts = shapely.points(o.lon.to_numpy(), o.lat.to_numpy())


def locate(path, props, max_deg=0.015):
    feats = json.load(open(path))["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    tree = shapely.STRtree(geoms)
    pi, gi = tree.query(pts, predicate="within")
    out = [None] * len(o)
    for p, g in zip(pi, gi):
        if out[p] is None:
            out[p] = g
    # a point a few meters offshore (piers, marinas) takes the nearest polygon within ~1.5 km
    left = [i for i, v in enumerate(out) if v is None]
    if left:
        near, dist = tree.query_nearest(pts[left], return_distance=True, all_matches=False)
        for (k, g), d_ in zip(near.T, dist):
            if d_ < max_deg:
                out[left[k]] = g
    return [None if g is None else tuple(feats[g]["properties"].get(p) for p in props) for g in out]


cty = locate(f"{PA}/pa_counties.geojson", ("county", "region"))
o["county"] = [c[0] if c else None for c in cty]
o["region"] = [c[1] if c else None for c in cty]
sub = locate(f"{PA}/pa_cousub.geojson", ("name", "kind"))
o["muni"] = [s[0] if s else None for s in sub]
o["muni_kind"] = [s[1] if s else None for s in sub]
o["hood"] = None
o["j_outside"] = o.county.isna()
med = o.groupby("city")[["lat", "lon"]].transform("median")
size = o.groupby("city").lat.transform("size")
# far from every other place sharing its mailing name (Philadelphia and Pittsburgh mailing names cover a whole city, so looser there)
lim = np.where(o.city.isin(["Philadelphia", "Pittsburgh"]), 40, 30)
o["j_far"] = ((size >= 5) & (np.hypot((o.lat - med.lat) * 111, (o.lon - med.lon) * 83) > lim)).fillna(False)
# the shown city: the mailing name, else the municipality; in Philadelphia (city and county are one) always Philadelphia
o["place"] = o.city
o["city"] = ["Philadelphia" if co == "Philadelphia" else (c if isinstance(c, str) else m) for co, c, m in zip(o.county, o.place, o.muni)]
print("listings outside Pennsylvania:", int(o.j_outside.sum()), "| by region:", o.region.value_counts().to_dict(), flush=True)
print("junk names:", int(o.j_junk.sum()), "| closed per name:", int(o.j_closedname.sum()), "| far from their mailing place:",
      int((o.j_far & ~o.j_outside).sum()), flush=True)

# names carrying their place ("Wawa - Media", "Subway of Erie, PA") or only a place ("Scranton, Pennsylvania")
TAIL = re.compile(r"\s*(?:[-–|,:]\s*|\s(?:of|in|at)\s+)[A-Z][A-Za-z.' ]{1,30},\s*(?:PA|Pa\.|Pennsylvania)\.?\s*$")
TOWNS = set(o.place.dropna().str.strip().str.lower()) | set(o.muni.dropna().str.lower()) | {"philadelphia", "pittsburgh", "pennsylvania"}


def clean_name(n, city, brand):
    n0 = n.strip()
    if isinstance(city, str) and city:
        c = re.escape(city.strip())
        n = re.sub(rf"(?:\s*[-–|,:]\s*|\s(?:of|in|at)\s+|\s|^){c},?\s*(?:PA|Pa\.|Pennsylvania)\.?\s*$", "", n, flags=re.I)
        n = re.sub(rf"\s*[-–|:]\s*{c}\s*$", "", n, flags=re.I)
        m = re.match(rf"^(.*\S)\s+{c}$", n, flags=re.I)
        if m and not re.search(r"\b(?:of|in|at|de|del|la|el|the|and|&|du|on)$", m.group(1), re.I) and (_stems(norm_name(m.group(1))) - GENERIC) \
                and isinstance(brand, str):
            n = m.group(1)   # only chains drop a bare place tail ("Sheetz Altoona"); "Pittsburgh Steak Company" keeps it
        if n.strip().lower() == city.strip().lower():
            n = ""
    if n.strip().lower() in TOWNS:
        n = ""
    n = TAIL.sub("", n).strip(" -–|,")
    m = re.fullmatch(r"([A-Za-z.' ]+),\s*(?:PA|Pennsylvania)", n0)
    if not n or (m and m.group(1).strip().lower() in TOWNS):
        return brand if isinstance(brand, str) and brand else None
    return n


o["name"] = [clean_name(n, c, b) for n, c, b in zip(o.name, o.place, o.brand)]
o = o[o.name.notna()].reset_index(drop=True)
label = [isinstance(b, str) and b.strip() != "" and src in ("AllThePlaces", "DAC") and fuzz.partial_ratio(norm_name(b), norm_name(n)) < 70
         for n, b, src in zip(o.name, o.brand, o.src)]
o.loc[label, "name"] = o.loc[label, "brand"].map(fix_text)
print("store-label names replaced by the brand:", int(sum(label)), flush=True)

# ---------------------------------------------------------------- Google 2021 listings (all of Pennsylvania; used by the web leaderboard only)
HOST = re.compile(r"shopping (?:mall|center)|outlet|botanical garden|garden center|museum|zoo|aquarium|water park|amusement|theme park|"
                  r"movie theater|cinema|golf|country club|hotel|motel|resort|lodge|casino|stadium|arena|university|college|school|hospital|"
                  r"airport|library|church|grocery|supermarket|warehouse club|department store|home improvement|hardware|book store|"
                  r"gift shop|salon|spa\b|gym|tobacco|vaporizer|cigar|adult entertainment|appliance|furniture|fireplace|wedding venue|"
                  r"event venue|indoor playground|mover|landscaping|boutique|produce market|beverage distributor|food products supplier|"
                  r"swimming pool|skating|sports complex|association|video arcade|convenience store|gas station|truck stop|campground|"
                  r"rv park|marina|ski resort|bowling|cheese manufacturer|cheese shop|dairy farm|farm|orchard|winery|fairground|"
                  r"fraternal organization|veterans organization|social club|community center|senior citizen center|cabin rental", re.I)
G = []
with gzip.open(f"{DATA}/meta-Pennsylvania.json.gz", "rt") as f:
    for line in f:
        d = json.loads(line)
        cats = d.get("category") or []
        if d.get("latitude") and any(FOODCAT.search(c) for c in cats) and not NOTFOOD.search(cats[0] if cats else "") \
                and not HOST.search(cats[0] if cats else ""):
            for k in ("relative_results", "hours", "MISC", "description", "url"):
                d.pop(k, None)
            G.append(d)
G = pd.DataFrame(G)
G["k"] = G.name.map(norm_name)
G["st"] = G.k.map(lambda k: _stems(k) - GENERIC if k else set())
G["closed21"] = G.state.fillna("").str.startswith("Permanently closed")
G["num"] = G.address.fillna("").map(lambda a: (re.search(r",\s*(\d+)(?:-(\d+))?\s", "," + a.split(",", 1)[-1]) or [None, None])[1])
grid = {}
for i, (la, lo) in enumerate(zip(G.latitude, G.longitude)):
    grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(i)
print("Google 2021 PA food listings:", len(G), "| permanently closed by 2021:", int(G.closed21.sum()), flush=True)

TOWNWORDS = set(" ".join(list(o.place.dropna().map(norm_name)) + list(o.muni.dropna().map(norm_name))).split()) | set("""PENNSYLVANIA PHILLY PA
JAPANESE PANCAKE PANCAKES BUFFET CUISINE RESTAURANT CAFE CAFFE DINER STEAKHOUSE SUSHI HIBACHI RAMEN TAQUERIA CANTINA BISTRO EATERY LOUNGE
SALOON SPORTS FAMILY AMERICAN MEXICAN ITALIAN GREEK KOREAN VIETNAMESE INDIAN ASIAN THAI CHINESE BAKERY PUB TAP HOUSE ROOM TAVERN INN
PIZZERIA SEAFOOD BAGEL BAGELS DELI HALAL GYRO""".split())
G["st2"] = G.st.map(lambda st: st - TOWNWORDS)
o["k"] = o.name.map(norm_name)
o["brand_n"] = [brand_of(k, norm_name(b) if isinstance(b, str) else None) for k, b in zip(o.k, o.brand)]
o["st"] = o.k.map(lambda k: _stems(k) - GENERIC if k else set())
o["num"] = o.street.fillna("").map(lambda a: (lambda m: (m.group(1) + (m.group(2) if m.group(2) and len(m.group(2)) == 2 and len(m.group(1)) <= 3 else ""))
                                              if m else None)(re.match(r"\s*(\d+)(?:-(\d+))?", a)))
G["num"] = [n if n else None for n in G.num]
GLA, GLO = G.latitude.to_numpy(), G.longitude.to_numpy()
GK, GNUM, GST, GST2 = G.k.tolist(), G.num.tolist(), G.st.tolist(), G.st2.tolist()
grid_np = {k: np.array(v) for k, v in grid.items()}
pairs = []
for oi, (k, la, lo, num, st) in enumerate(zip(o.k, o.lat, o.lon, o.num, o.st)):
    if not k:
        continue
    gy, gx = round(la / 0.0015), round(lo / 0.002)
    cand = [grid_np[c] for c in ((gy + dy, gx + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) if c in grid_np]
    if not cand:
        continue
    cand = np.concatenate(cand)
    dist = np.hypot((GLA[cand] - la) * 111000, (GLO[cand] - lo) * 83000)
    sel = dist <= 200
    mine = st - TOWNWORDS
    for gi, d_ in zip(cand[sel].tolist(), dist[sel].tolist()):
        gk = GK[gi]
        if not gk:
            continue
        gnum = GNUM[gi]
        same_num = isinstance(num, str) and isinstance(gnum, str) and (gnum == num or (gnum == num[:len(gnum)] and len(num) - len(gnum) == 2))
        s = name_sim(k, gk)
        if same_num and st & GST[gi]:
            s = max(s, 80)
        if s < 95 and not mine & GST2[gi]:
            continue
        if (s >= 88 and d_ < 150) or (s >= 75 and same_num):
            pairs.append((s + (10 if same_num else 0) - d_ / 25, oi, gi))
taken_o, taken_g, gmatch = set(), set(), {}
for sc, oi, gi in sorted(pairs, key=lambda t: -t[0]):
    if oi in taken_o or gi in taken_g:
        continue
    taken_o.add(oi); taken_g.add(gi); gmatch[oi] = gi
o["gi"] = o.index.map(gmatch)
o["in21"] = o.gi.notna()
o["closed21"] = [bool(G.closed21.iat[int(v)]) if v is not None and v == v else False for v in o.gi]
print("matched to Google 2021:", int(o.in21.sum()), "| of those, closed by 2021:", int(o.closed21.sum()), flush=True)
o.to_pickle(f"{PA}/stage1.pkl")
G.to_pickle(f"{PA}/google21.pkl")
print("wrote stage1:", len(o), "listings")
