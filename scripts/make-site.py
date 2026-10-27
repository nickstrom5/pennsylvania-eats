"""Writes the public website in docs/ from the same data the app ships (data/app/index.json + places-<region>.json).

Pages: the landing page; one page per app guide with 4 or more hand-checked places (Cheesesteaks, Roast Pork & Hoagies; Tomato Pie &
Old Forge Pizza; Pierogies & Pittsburgh Classics; Pennsylvania Dutch; Soft Pretzel Bakeries; Diners), as
PennsylvaniaEats/Models/Guide.swift defines them; Pennsylvania icons and the oldest places; one page per region (our nine, by county)
and per big city; privacy, terms, support, 404; the web app at explore/; plus sitemap.xml, robots.txt, site.webmanifest and
playbook/site-numbers.json.

The product's promise, checked here on every page: no Google-derived data and no ratings or reviews from anyone; Allegheny County's
placards are the Health Department's own, labeled official and always shown with their date (only once Nick's WPRDC download is in);
Philadelphia places show whether an active L&I food license was matched; everywhere else the pages link the agencies' search-only
portals and quote the PA Department of Agriculture's "snapshot" disclosure verbatim. Guides list hand-checked places only (a listing
merely named "... Steaks" stays in the directory).

Modeled on ny-eats/scripts/make-site.py (New York). Never hand-edit docs/*.html: change this file and re-run it.

Usage (from pa-eats/): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then run scripts/qa-site.py. When the restaurant count changes it also redraws docs/og.png
(swift scripts/make-brand.swift og "<tagline>"), whose tagline carries that number.
"""
import base64
import datetime
import gzip
import hashlib
import html
import json
import math
import os
import re
import sys
import shutil
import statistics
import subprocess
import urllib.parse
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
# Where the site lives. Today: GitHub Pages at the project address, because pennsylvania.eatsranked.com has no DNS record yet.
# Once Nick adds the Cloudflare record (CNAME pennsylvania -> nickstrom5.github.io, DNS only) and `dig` shows it, set
# CUSTOM_DOMAIN = "pennsylvania.eatsranked.com", re-run, push, and switch PennsylvaniaEats/App/Links.swift with it.
CUSTOM_DOMAIN = ""
DOMAIN = f"https://{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else "https://nickstrom5.github.io/pennsylvania-eats"
BASE = "" if CUSTOM_DOMAIN else "/pennsylvania-eats"     # path prefix for root-relative links
BRAND = "Pennsylvania Eats"
SHORT = "PA Eats"
TAGLINE = "Cheesesteaks to pierogies"
EMAIL = "nick@eatsranked.com"
# Once the App Store listing exists, paste its URL here (https://apps.apple.com/app/id...) and re-run: every "Ask for early access"
# button becomes an App Store link (Apple's badge if docs/img/app-store-badge.svg is there; never draw the Apple logo), the notes stop
# saying "coming", the privacy page says the label "is", and the web app's place panel links the App Store (window.APP_STORE_URL).
APP_STORE_URL = ""
TODAY = datetime.date.today().isoformat()
CHECKED = "October 2026"
TERMS_UPDATED = "2026-10-21"
PRIVACY_UPDATED = "2026-10-26"   # the app's data updates (OTA-DATA.md)
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
# The PA Department of Agriculture's own disclosure on its inspection search (pafoodsafety.pa.gov), quoted verbatim wherever we link it
PDA_DISCLOSURE = ("Please remember that any inspection is a 'snapshot' of the day and time of the inspection. An inspection conducted on "
                  "any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of "
                  "the inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.")
PHILLY_DISCLAIMER = ("The City of Philadelphia makes no representation about the accuracy of any specific information in this data and is "
                     "provided “as is” and without Warranty of any kind.")
MICHELIN_TM = "MICHELIN and the MICHELIN Guide are trademarks of Michelin."
JBF_TM = "James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation."
PDA_SEARCH = "https://www.pafoodsafety.pa.gov/Web/Inspection/PublicInspectionSearch.aspx"
PHILLY_SEARCH = "https://philadelphia-pa.healthinspections.us/philadelphia/"
BUCKS_SEARCH = "https://bucks-pa.healthinspections.us/"
MONT_SEARCH = "https://pa.healthinspections.us/montgomery/"
ACHD_PAGE = "https://www.alleghenycounty.us/Services/Health-Department/Food-Safety"


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {y}"


# ---------------------------------------------------------------- data
IX = json.load(open(f"{ROOT}/data/app/index.json"))
SHAPES = json.load(open(f"{ROOT}/data/pa/pa_shapes.json"))
OUTLINE = json.load(open(f"{ROOT}/playbook/state-outline.json"))
# website links: only those the link check passed (pipeline/check_websites.py -> data/pa/website_check.json). Until that file
# exists, only the hand-checked research's own links are shown: no link beats a wrong link (the playbook's hijacked-domain lesson).
WEB_CHECK_FILE = f"{ROOT}/data/pa/website_check.json"
WEB_CHECK = json.load(open(WEB_CHECK_FILE)) if os.path.exists(WEB_CHECK_FILE) else None
if WEB_CHECK is not None:
    # the export strips tracking tags (pipeline/tracking_params.py) after the check ran on the tagged URL: the same page, so the
    # cleaned URL keeps that verdict (as in ny-eats). The next check run records the cleaned URLs themselves.
    sys.path.insert(0, f"{ROOT}/pipeline")
    import tracking_params
    for _url, _verdict in list(WEB_CHECK.items()):
        WEB_CHECK.setdefault(tracking_params.clean(_url), _verdict)
# Websites the site never links, whatever the link check said (pipeline/website_blocklist.json: hacked with hidden casino or pharmacy
# links, expired, or another business's page): [{"domain", "match": "domain" (it and every subdomain) | "url" (that page only, for one
# site on a shared host; give "url" too), "place", "reason", "severity", "evidence", "found"}]. Only the link goes, never the place: it
# shows like any place without a website, on the pages and in the web app's data. New entries need no code change, just a re-run;
# scripts/qa-site.py fails if any listed domain or URL is anywhere in docs/, and on a missing or empty list.
BLOCKLIST_FILE = f"{ROOT}/pipeline/website_blocklist.json"
BLOCKLIST = json.load(open(BLOCKLIST_FILE, encoding="utf-8"))
assert isinstance(BLOCKLIST, list), "pipeline/website_blocklist.json: a list of entries"
for _b in BLOCKLIST:
    assert isinstance(_b, dict) and _b.get("domain") and _b.get("match", "domain") in ("domain", "url") and _b.get("reason"), \
        f"pipeline/website_blocklist.json: each entry needs domain, reason and match 'domain' or 'url': {_b!r}"
    assert _b.get("match", "domain") == "domain" or _b.get("url"), f"pipeline/website_blocklist.json: a 'url' entry needs its url: {_b!r}"
BLOCKED = Counter()   # links dropped per entry (domain or url), reported at the end and in playbook/site-numbers.json


def _host_path(u):
    """(host without www. or a trailing dot, path without a trailing slash), lower case; a bare host reads as a URL."""
    s = urllib.parse.urlsplit(u.strip() if re.match(r"^[a-z][a-z0-9+.-]*://", u.strip(), re.I) else "//" + u.strip())
    return (s.hostname or "").lower().rstrip(".").removeprefix("www."), s.path.rstrip("/").lower()


def blocked(u):
    """The blocklist entry that covers link `u`, or None."""
    if not u:
        return None
    host, path = _host_path(u)
    for b in BLOCKLIST:
        if b.get("match", "domain") == "url":
            if (host, path) == _host_path(b["url"]):
                return b
        else:
            d = _host_path(b["domain"])[0]
            if host == d or host.endswith("." + d):
                return b
    return None


def unblocked(u, count=True):
    """u, or "" if the blocklist covers it (counted against its entry)."""
    b = blocked(u)
    if b and count:
        BLOCKED[b.get("url") if b.get("match") == "url" else b["domain"]] += 1
    return "" if b else u


DATA_DATE = IX["generated"]
RT = IX["records_through"]
REGIONS, SLUGS, COUNTIES = IX["regions"], IX["slugs"], IX["counties"]
CITIES, MAILING, HOODS, MUNIS, CUISINES, BRANDS = IX["cities"], IX["mailing"], IX["hoods"], IX["munis"], IX["cuisines"], IX["brands"]
COUNTY_REGION = {c: REGIONS[r] for c, r in zip(COUNTIES, IX["county_region"])}
REGION_SLUG = dict(zip(REGIONS, SLUGS))
REGION_IN = {r: (f"in the {r}" if r in ("Philly Suburbs", "Lehigh Valley", "Northeast & Poconos", "Pittsburgh Region", "Northern Tier")
                else "in Central Pennsylvania" if r == "Central" else "in Northwestern Pennsylvania" if r == "Northwest"
                else "in South Central Pennsylvania" if r == "South Central" else f"in {r}") for r in REGIONS}
# the bit meanings must match the app (PennsylvaniaEats/Models/Place.swift: PlaceTags and Kinds); a reordering fails here, loudly
assert IX["tags"] == ["steak", "pie", "pierogi", "dutch", "pretzel", "diner", "oldest"], IX["tags"]
assert IX["kinds"] == ["cheesesteak", "roast pork", "hoagie", "tomato pie", "old forge", "pierogi", "pittsburgh sandwich", "pa dutch",
                       "pretzel", "diner", "oldest"], IX["kinds"]
assert REGIONS[0] == "Philadelphia" and len(REGIONS) == 9, REGIONS
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", RT["philly"]), RT
HAS_ACHD = bool(RT.get("achd"))   # Allegheny placards ship only once Nick's WPRDC download is in (pipeline/official.py)
TAG = {t: 1 << i for i, t in enumerate(IX["tags"])}
KIND = {k: 1 << i for i, k in enumerate(IX["kinds"])}
KIND_LABEL = {"cheesesteak": "Cheesesteaks", "roast pork": "Roast pork", "hoagie": "Hoagies", "tomato pie": "Tomato pie",
              "old forge": "Old Forge pizza", "pierogi": "Pierogies", "pittsburgh sandwich": "Pittsburgh sandwich", "pa dutch": "PA Dutch",
              "pretzel": "Soft pretzels", "diner": "Diner", "oldest": "Historic"}
MI_LABEL = {1: "MICHELIN Guide", 2: "Bib Gourmand", 3: "1 MICHELIN Star", 4: "2 MICHELIN Stars", 5: "3 MICHELIN Stars"}


def at(lst, i):
    return lst[i] if i is not None and 0 <= i < len(lst) else None


class P:
    """One place, with the same meaning the app gives each field (PennsylvaniaEats/Models/Place.swift)."""

    def __init__(self, r, ri, row):
        self.r, self.ri, self.row = r, ri, row
        self.id = r["id"]
        self.name = r["n"]
        self.city = at(CITIES, r.get("c"))
        self.mailing = at(MAILING, r.get("pl")) or None
        self.hood = at(HOODS, r.get("hd"))
        self.muni = at(MUNIS, r.get("mu"))
        self.county = COUNTIES[r["co"]]
        self.region = COUNTY_REGION[self.county]
        self.cuisine = CUISINES[r["cu"]]
        self.brand = at(BRANDS, r.get("b"))
        a = r.get("a") or ""
        self.addr = "" if re.search(r"https?:|www\.|\.com\b", a, re.I) else a   # a link pasted as an address is no address
        self.addr = re.sub(r",\s*P\.?\s?O\.? Box \d+\b", "", self.addr, flags=re.I)   # a PO box isn't where the place is
        for town in {at(CITIES, r.get("c")), at(MAILING, r.get("pl")), at(HOODS, r.get("hd"))} - {None, ""}:
            self.addr = re.sub(rf",\s*{re.escape(town)}$", "", self.addr, flags=re.I)   # the town follows on its own
        self.zip = r.get("z") or ""
        self.lat, self.lon = r.get("la"), r.get("lo")
        self.chain_n = r.get("ch") or 1
        self.chain = self.chain_n >= 5
        self.tier = r["t"]
        self.jur = r.get("j") or 0
        self.venue = r.get("v") == 1
        self.tags = r.get("g") or 0
        self.kinds = r.get("k") or 0
        # hc: checked open against a 2025-26 source (our research, or an honoree with current evidence). Only these are ever called
        # "checked open". on_guide: on one of the app's guides (a research kind); every guide place is hc (asserted below). An honor
        # alone (MICHELIN, James Beard, without current evidence) is a fact about a listing, never an open-check.
        self.hc = r.get("hc") == 1
        self.on_guide = bool(self.kinds)
        self.h = r.get("h") or 0
        self.mi = r.get("mi")
        self.ip = r.get("ip")
        self.note = r.get("note") or ""
        # the James Beard Foundation calls its finalists "nominees"; never a finalist or nominee called a winner
        self.jbf = re.sub(r"\bfinalist\b", "nominee", r.get("jbf") or "")
        self.dish = r.get("dish") or ""
        self.season = r.get("sea") or ""
        self.seasonal = r.get("seas") == 1
        self.branch = r.get("br") or ""
        self.chef = r.get("chef") or ""
        self.founded = r.get("f")
        self.fnote = r.get("fn") or ""
        self.ac = r.get("ac")            # Allegheny County placard {"p", "d"} (official)
        self.phl = r.get("phl") == 1     # an active Philadelphia L&I food license matched
        self.gs = r.get("gs") == 1       # MICHELIN Green Star
        w = r.get("w") or ""
        ok_scheme = urllib.parse.urlsplit(w).scheme in ("http", "https")   # never javascript:, data: or a bare host
        verified = (WEB_CHECK or {}).get(w, {}).get("ok") if WEB_CHECK is not None else False
        bad_host = re.search(r"google\.|goo\.gl|business\.site|yelp\.|tripadvisor\.|citysearch\.|doordash\.|grubhub\.|ubereats\.|seamless\.",
                             urllib.parse.urlsplit(w).netloc.lower())   # directories and Google pages are never a place's own site
        # with the link check's results, only links it passed; without them, only our research's own links
        self.site = w if ok_scheme and not bad_host and (verified if WEB_CHECK is not None else self.on_guide) else ""
        self.site = unblocked(self.site)   # hacked, expired or another business's (pipeline/website_blocklist.json): no link at all
        ph = r.get("ph") or ""
        self.phone = ph if re.fullmatch(r"\+1[2-9]\d{9}", ph) else ""

    @property
    def place_name(self):
        """"Pittsburgh", or "Feasterville-Trevose, Bensalem"-style, as the app's Place.placeName."""
        if not self.city:
            return self.mailing or ""
        n = self.mailing
        return f"{n}, {self.city}" if n and n != self.city else self.city

    @property
    def mail_town(self):
        """The town in the mailing address (Place.fullAddress)."""
        return self.mailing or self.city

    @property
    def jb_label(self):
        return ("America's Classic" if self.h & 1 else "James Beard winner" if self.h & 2 else "James Beard nominee" if self.h & 4
                else "James Beard semifinalist" if self.h & 8 else None)

    @property
    def mi_label(self):
        return "MICHELIN Green Star" if self.mi == 1 and self.gs else MI_LABEL.get(self.mi)

    def kind_names(self):
        return [KIND_LABEL[k] for k in IX["kinds"] if self.kinds & KIND[k]]

    def featured_key(self):
        # the app's "Featured first" (Guide.swift Ranking): honored places first, then the verified year at this address, then name
        return (-(self.ip if self.ip is not None else -1), self.founded or 9999, self.name.lower())


PLACES = []
# one file per region (the app decodes them in parallel); `row` counts across files
for f in IX["files"]:
    ri = REGIONS.index(f["region"])
    d = json.load(open(f"{ROOT}/data/app/{f['file']}"))
    assert d["region"] == f["region"] and len(d["places"]) == f["count"], f
    PLACES += [P(r, ri, len(PLACES) + row) for row, r in enumerate(d["places"])]
assert [REGIONS.index(f["region"]) for f in IX["files"]] == sorted(REGIONS.index(f["region"]) for f in IX["files"]), "files out of region order"
assert all(p.region == REGIONS[p.ri] for p in PLACES), "a place in the wrong region file"
assert len({p.id for p in PLACES}) == len(PLACES), "duplicate ids"
REST = [p for p in PLACES if not p.venue]
N_REST = len(REST)
assert N_REST == IX["count_restaurants"], (N_REST, IX["count_restaurants"])
assert all(not p.venue for p in PLACES if p.hc), "a hand-checked place is hidden as a non-restaurant"
# guide kinds need the research flag (a 2025-26 source shows the place open); an honor alone (MICHELIN, James Beard) is a fact about a
# listed place and doesn't make it "checked open"
assert all(p.hc for p in PLACES if p.kinds), "guide kinds without the research flag"
assert all(p.jb_label != "James Beard winner" or re.search(r"\bwinner\b", p.jbf, re.I) for p in PLACES), "a winner label without a win"
assert all(not p.ac or re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.ac.get("d") or "") for p in PLACES), "a placard without its date"
assert all(not p.ac or p.county == "Allegheny" for p in PLACES), "an ACHD placard outside Allegheny County"
assert all(not p.phl or p.county == "Philadelphia" for p in PLACES), "a Philadelphia license outside Philadelphia"
CITY_COUNT = Counter(p.city for p in REST if p.city)
N_CITIES = len(CITY_COUNT)
REGION_COUNT = Counter(p.region for p in REST)


def guide(cond):
    return sorted([p for p in REST if p.on_guide and cond(p)], key=P.featured_key)


def kmask(*names):
    return sum(KIND[n] for n in names)


# the app's guides (PennsylvaniaEats/Models/Guide.swift): hand-checked only, by `k` kind bits
ALL_GUIDES = [
    # key, page, short name, title-case name, kinds, Guide.swift subtitle
    ("steak", "philadelphia-cheesesteaks-hoagies.html", "Cheesesteaks & hoagies", "Cheesesteaks, Roast Pork & Hoagies",
     ("cheesesteak", "roast pork", "hoagie"), "Philadelphia's steak shops, roast pork and hoagie counters"),
    ("pie", "tomato-pie-old-forge-pizza.html", "Tomato pie & Old Forge", "Tomato Pie & Old Forge Pizza", ("tomato pie", "old forge"),
     "Square tomato pie and Old Forge-style trays"),
    ("pierogi", "pittsburgh-pierogies.html", "Pierogies & Pittsburgh", "Pierogies & Pittsburgh Classics", ("pierogi", "pittsburgh sandwich"),
     "Pierogi kitchens and Pittsburgh's sandwich classics"),
    ("dutch", "pennsylvania-dutch-restaurants.html", "Pennsylvania Dutch", "Pennsylvania Dutch", ("pa dutch",),
     "Family-style dining rooms and smorgasbords"),
    ("pretzel", "soft-pretzel-bakeries.html", "Soft pretzels", "Soft Pretzel Bakeries", ("pretzel",), "Hand-twisted soft pretzels, baked daily"),
    ("diner", "pennsylvania-diners.html", "Diners", "Diners", ("diner",), "Counters, booths and breakfast all day"),
]
G_ALL = {k: guide(lambda p, m=kmask(*kinds): p.kinds & m) for k, _, _, _, kinds, _ in ALL_GUIDES}
# the app hides a classic with fewer than 4 hand-checked places (AppModel.hasEnough); so does the site: no page until it has 4
GUIDES = [g for g in ALL_GUIDES if len(G_ALL[g[0]]) >= 4]
G = {k: G_ALL[k] for k, *_ in GUIDES}
GUIDE_URL = {k: "/" + pg for k, pg, *_ in GUIDES}
GUIDE_WORD = {"steak": "Cheesesteaks", "pie": "Tomato Pie", "pierogi": "Pierogies", "dutch": "PA Dutch", "pretzel": "Pretzels", "diner": "Diners"}
GUIDE_NAME = {k: n for k, _, n, *_ in GUIDES}


def lc(s):
    """Lowercase a guide name for the middle of a sentence, keeping its proper names: "Old Forge", "Pennsylvania Dutch"."""
    return re.sub(r"\b(old forge|pennsylvania|pittsburgh|philadelphia|pa)\b", lambda m: m.group(0).upper() if m.group(0).lower() == "pa" else m.group(0).title(), s.lower())


def guide_word(k, ps):
    return GUIDE_WORD[k]


ON_GUIDES = [p for p in REST if p.on_guide]
CLASSIC = sorted({p.id: p for k in G for p in G[k]}.values(), key=P.featured_key)
ICONS = sorted([p for p in REST if p.ip is not None], key=P.featured_key)
OLDEST = sorted([p for p in REST if p.founded and p.hc], key=lambda p: (p.founded, p.name.lower()))
MICHELIN = [p for p in REST if p.mi]
JBF = [p for p in REST if p.h & 15]
ICONS_PAGE = ("pennsylvania-icons.html", "Pennsylvania icons")
OLDEST_PAGE = ("pennsylvania-oldest-restaurants.html", "Oldest places")
HAS_OLDEST = len(OLDEST) >= 3   # the oldest-places page needs a first, second and third
# directory places named like a classic that our research hasn't checked: shown in the directory, never on a guide
NAMED = {"steak": sum(1 for p in REST if re.search(r"\b(cheese ?steaks?|steaks|hoagies?)\b", p.name, re.I) and not p.on_guide),
         "pie": sum(1 for p in REST if re.search(r"\btomato pie\b|\bold forge\b", p.name, re.I) and not p.on_guide),
         "pierogi": sum(1 for p in REST if re.search(r"\bpierog", p.name, re.I) and not p.on_guide),
         "dutch": sum(1 for p in REST if re.search(r"\b(dutch|amish|smorgasbord)\b", p.name, re.I) and not p.on_guide),
         "pretzel": sum(1 for p in REST if re.search(r"\bpretzels?\b", p.name, re.I) and not p.on_guide),
         "diner": sum(1 for p in REST if re.search(r"\bdiner\b", p.name, re.I) and not p.on_guide)}
N_AC = sum(1 for p in REST if p.ac)
N_PHL = sum(1 for p in REST if p.phl)


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "")).strip("-")


def and_list(xs):
    xs = list(xs)
    if not xs:
        return ""
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + (", and " if len(xs) > 2 else " and ") + xs[-1]


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


# A private address must never reach a public page. Only the sha256 digests of its pieces live here (the address, its user and
# domain), so this public file doesn't spell it out; private_words() reports any word or email on a page that hashes to one.
PRIVATE_DIGESTS = {
    "4a7e25559b2ffc162afaef2b1680778c6e77d8c2982c3870595f6ee8fea7a455",
    "ff8ea15b513b5561b1c48b725aff52338eddb8ecdd46af58759e2f2c554b0582",
    "31b7679e2f02e2b0561693acc0c78f067633b6713ac53fb5980dcb0f7c2ea237",
    "928009cbd52e0a32a3542c0f41efa0ac8feef2e05974b8126f26c7d4f9b593e3",
}


def private_words(text):
    t = text.lower()
    words = set(re.findall(r"[\w.%+-]+@[\w.-]+", t)) | set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", t)) | set(re.findall(r"[a-z0-9]+", t))
    return [w for w in words if hashlib.sha256(w.encode()).hexdigest() in PRIVATE_DIGESTS]


def explore_url(**params):
    """A web app link with its state in the hash, e.g. explore_url(g="all", r="pittsburgh-region", town="Pittsburgh")."""
    return "/explore/#" + urllib.parse.urlencode({k: v for k, v in params.items() if v})


def fit(options, lo, hi):
    for o in options:
        if lo <= len(o) <= hi:
            return o
    raise ValueError(f"nothing fits {lo}-{hi}: {[(len(o), o) for o in options]}")


def fit_combo(cores, tails, lo, hi):
    """The first core + tail that fits (cores in order of preference, tails too); never two colons in one title."""
    return fit([c + t for c in cores if c for t in tails if not (":" in c and t.startswith(":"))], lo, hi)


def checked_open(ps):
    return f"checked in business in {CHECKED}" if any(p.seasonal for p in ps) else f"checked open in {CHECKED}"


# The app icon in miniature (scripts/make-brand.swift pretzel(), Nick's pick Oct 19, 2026, in the Eats Ranked flat style): one gold
# rope on hemlock, the crossing arm over the other with a hemlock ring, six cream salt crystals. Same path as the Swift (y from the top,
# the x squeezed by 0.86 about the middle), at 64 x 64.
def _pretzel_svg():
    s = 64
    n = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    P_ = lambda x, y: f"{n((0.5 + (x - 0.5) * 0.86) * s)},{n(y * s)}"
    a = (f"M{P_(0.385, 0.700)}C{P_(0.430, 0.610)} {P_(0.500, 0.520)} {P_(0.560, 0.470)}C{P_(0.640, 0.390)} {P_(0.730, 0.300)} {P_(0.800, 0.330)}"
         f"C{P_(0.880, 0.370)} {P_(0.880, 0.560)} {P_(0.770, 0.640)}C{P_(0.690, 0.705)} {P_(0.590, 0.735)} {P_(0.500, 0.735)}")
    b = (f"M{P_(0.500, 0.735)}C{P_(0.410, 0.735)} {P_(0.310, 0.705)} {P_(0.230, 0.640)}C{P_(0.120, 0.560)} {P_(0.120, 0.370)} {P_(0.200, 0.330)}"
         f"C{P_(0.270, 0.300)} {P_(0.360, 0.390)} {P_(0.440, 0.470)}C{P_(0.500, 0.520)} {P_(0.570, 0.610)} {P_(0.615, 0.700)}")
    cross = f"M{P_(0.440, 0.470)}C{P_(0.500, 0.520)} {P_(0.570, 0.610)} {P_(0.615, 0.700)}"
    w = 0.105 * s
    rope = lambda d, col, width, extra="": f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{n(width)}" stroke-linecap="round" stroke-linejoin="round"{extra}/>'
    out = [f'<rect width="{s}" height="{s}" rx="14" fill="#2E4E3F"/>', rope(a, "#E8A33D", w), rope(b, "#E8A33D", w),
           rope(cross, "#2E4E3F", w + 0.026 * s, f' stroke-dasharray="{n(150 / 1024 * s)} 999"'), rope(cross, "#E8A33D", w)]
    for x, y in ((0.255, 0.345), (0.745, 0.345), (0.165, 0.480), (0.835, 0.480), (0.330, 0.715), (0.670, 0.715)):
        cx, cy = P_(x, y).split(",")
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{n(0.043 * s / 2)}" fill="#F6F1E7"/>')
    return "".join(out)


LOGO = f'<svg viewBox="0 0 64 64" width="32" height="32" aria-hidden="true">{_pretzel_svg()}</svg>'
FAVICON = "data:image/svg+xml," + LOGO.replace('width="32" height="32" ', "").replace(' aria-hidden="true"', "").replace(
    "<svg ", "<svg xmlns='http://www.w3.org/2000/svg' ").replace('"', "'").replace("#", "%23").replace("<", "%3C").replace(">", "%3E")


def state_svg(cls="state", h=40, main="#2E4E3F"):
    """The one Pennsylvania element: the state's outline (playbook/state-outline.json), the Erie notch and the Delaware River edge."""
    a = OUTLINE["aspect"]
    W, H = 100 * a, 100
    pts = " ".join(f"{x * W:.1f},{y * H:.1f}" for x, y in OUTLINE["outline"])
    return (f'<svg class="{cls}" viewBox="0 0 {W:.1f} {H}" width="{h * a:.0f}" height="{h}" aria-hidden="true" focusable="false">'
            f'<polygon fill="{main}" points="{pts}"/></svg>')


STATE = state_svg()
# the app's food glyphs (PennsylvaniaEats/Design/Glyphs.swift, exported by scripts/export-glyphs.py): one even-odd path each, 48 x 48.
# Diners use the SF Symbol cup in the app; the site draws a plain cup and saucer.
GLYPHS = {**json.load(open(f"{ROOT}/scripts/glyphs.json")),
          "diner": "M8 14H34V26C34 32.6 28.6 38 22 38H20C13.4 38 8 32.6 8 26ZM34 17H38C41.3 17 44 19.7 44 23C44 26.3 41.3 29 38 29H35V25H38C39.1 25 40 24.1 40 23C40 21.9 39.1 21 38 21H34ZM4 41H40V44H4Z"}


def glyph_svg(k, size=36, cls="glyph"):
    return (f'<svg class="{cls}" viewBox="0 0 48 48" width="{size}" height="{size}" aria-hidden="true" focusable="false">'
            f'<path fill="currentColor" fill-rule="evenodd" d="{GLYPHS[k]}"/></svg>')

CSS = """
  :root {
    color-scheme: light;
    --bg: #fbf8f2; --surface: #fff; --surface2: #f6f1e7; --surface3: #ece4d3; --rule: #e3dccd; --rule2: #857c6a;   /* --rule2 outlines controls: 3:1 or more */
    --gray: #a69c88;   /* rules only, never text */
    --ink: #1b1f1c; --ink2: #34403a; --muted: #525c55;
    /* Penn's Woods (Nick, 2026-10-19). The family's token names: --blue is the main dark colour (hemlock), --blue2 its lighter step. */
    --blue: #2e4e3f; --blue2: #3e6553; --barn: #a23b2a;
    --gold: #e8a33d;   /* a fill under near-black text only, never text (2.2:1 on white; hemlock on gold is 4.3:1) */
    --goldsoft: #f8e3bd; --ongoldsoft: #5a3a00;
    --radius: 16px;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  a { color: var(--blue2); text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible { outline: 3px solid var(--blue); outline-offset: 3px; border-radius: 6px; }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--blue); color: #fff; padding: 10px 14px; font-weight: 700; z-index: 30; }
  .skip:focus { left: 8px; top: 8px; }
  .wrap { max-width: 780px; margin: 0 auto; padding: 0 20px; }
  header.site { background: var(--surface); border-bottom: 5px solid var(--blue); box-shadow: 0 3px 0 var(--barn); }
  header.site .bar { display: flex; align-items: center; gap: 12px 18px; padding: 14px 20px; flex-wrap: wrap; }
  header.site .state { flex: 0 0 auto; display: block; }
  .logo { display: flex; align-items: center; gap: 10px; min-height: 44px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .01em; color: var(--blue); text-decoration: none; }
  .logo svg { flex: 0 0 auto; border-radius: 8px; }
  header.site nav { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-left: auto; justify-content: flex-end; }
  header.site nav a { color: var(--blue2); text-decoration: none; font-size: 15px; font-weight: 600; }
  header.site nav a:hover { text-decoration: underline; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--blue); letter-spacing: -.005em; }
  h1 { font-size: clamp(34px, 7.2vw, 54px); line-height: 1.02; margin: 0 0 16px; text-transform: uppercase; overflow-wrap: anywhere; }
  .kicker { font: 700 15px/1.4 -apple-system, system-ui, sans-serif; letter-spacing: .06em; color: var(--muted); margin: 0 0 12px; }
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 40px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; gap: 10px; background: var(--gold); color: var(--ink); border: 2px solid var(--blue); font-weight: 800; padding: 12px 18px; border-radius: 14px; text-decoration: none; font-size: 17px; }
  .btn-ghost { background: transparent; color: var(--blue); }
  .store-badge { display: inline-block; border-radius: 10px; }
  .store-badge img { display: block; height: 50px; width: auto; }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-top: 5px solid var(--gold); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--blue); }
  .stats span { font-size: 14px; color: var(--muted); }
  /* the app's masthead: white type and the state outline in white on hemlock, a barn-red rule */
  .masthead { background: var(--blue); color: #fff; border-radius: 24px; padding: 28px 24px 24px; margin-top: 24px; box-shadow: inset 0 -6px 0 var(--barn); }
  .masthead h1 { color: #fff; }
  .masthead .kicker, .masthead .pill { color: rgba(255,255,255,.86); }
  .masthead .lede { color: rgba(255,255,255,.93); }
  .masthead .btn-ghost { color: #fff; border-color: #fff; }
  .masthead a:focus-visible { outline-color: #fff; }
  .masthead .stats li { background: var(--blue2); border: 0; border-top: 4px solid var(--gold); }
  .masthead .stats b { color: #fff; }
  .masthead .stats span { color: rgba(255,255,255,.86); }
  .mast-top { display: flex; gap: 16px; align-items: flex-start; justify-content: space-between; }
  .mast-top { margin: 0 0 6px; }
  .mast-top .kicker { min-width: 0; margin: 4px 0 0; }
  .mast-state { flex: 0 0 auto; width: clamp(84px, 22vw, 150px); height: auto; }
  /* Pennsylvania classics: the app's soft-gold cards, each with its food glyph and a faint copy of it as texture */
  a.card.classic { position: relative; overflow: hidden; background: var(--goldsoft); border-color: transparent; }
  a.card.classic h3 { font: 800 25px/1.05 var(--display); color: var(--blue); margin-top: 10px; }
  a.card.classic p { color: var(--ongoldsoft); position: relative; }
  .card-top { display: flex; justify-content: space-between; align-items: flex-start; color: var(--blue); }
  .card-top .count { font: 800 30px/1 var(--display); color: var(--blue); text-align: right; }
  .card-top .count small { display: block; font: 600 12px/1.3 -apple-system, system-ui, sans-serif; color: var(--ongoldsoft); }
  a.card.classic .wm { position: absolute; right: -16px; bottom: -16px; width: 104px; height: 104px; color: var(--blue); opacity: .07; }
  .guide-mark { display: inline-grid; place-items: center; width: 64px; height: 64px; border-radius: 18px; background: var(--goldsoft); color: var(--blue); margin: 0 0 14px; }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--gold); color: var(--ink); font-weight: 800; display: grid; place-items: center; }
  .step p { margin: 4px 0 0; color: var(--ink2); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .card p { margin: 6px 0 0; color: var(--ink2); }
  a.card { display: block; text-decoration: none; color: var(--ink); }
  a.card h3 { color: var(--blue); }
  a.card:hover h3 { text-decoration: underline; }
  .towns { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
  .towns a { display: inline-flex; align-items: center; min-height: 44px; padding: 8px 12px; border-radius: 999px; border: 1px solid var(--rule); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .towns a:hover { border-color: var(--blue); }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 14px 0; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--blue); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 16px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 6px; }
  nav.crumbs li + li::before { content: "/"; content: "/" / ""; margin-right: 6px; color: var(--gray); }
  nav.crumbs a { color: var(--muted); }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .link { margin: 6px 0 0; font-size: 14px; }
  .insp { display: flex; align-items: center; gap: 10px; margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .insp small { display: block; color: var(--muted); font-size: 14px; }
  .pl { flex: 0 0 auto; display: inline-block; padding: 3px 9px; border-radius: 6px; border: 2px solid; font-size: 13px; font-weight: 800; letter-spacing: .03em; text-transform: uppercase; }
  .pl-green { background: #e6f2ea; color: #1d5b37; border-color: #2f7a4c; } .pl-yellow { background: #fff3c4; color: #5a4300; border-color: #c9a200; }
  .pl-red { background: #fbe3df; color: #8a1f12; border-color: #a23b2a; } .pl-other { background: #f1f1f1; color: #444; border-color: #999; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--goldsoft); color: var(--ongoldsoft); border-radius: 6px; padding: 1px 6px; margin: 0 4px 2px 0; }
  .tag-hon { background: var(--blue); color: #fff; }
  .tag-plain { background: var(--surface2); color: var(--blue); }
  .tag-dash { background: transparent; color: var(--muted); border: 1px dashed var(--rule2); }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .fine { font-size: 14px; color: var(--muted); }
  .notes p { font-size: 14px; color: var(--ink2); }
  .notes blockquote, .legal blockquote { margin: 0 0 10px; padding: 12px 16px; background: var(--surface); border: 1px solid var(--rule); border-left: 4px solid var(--gold); border-radius: 10px; font-size: 14px; color: var(--ink2); overflow-wrap: anywhere; }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  .legal blockquote p { margin: 0 0 8px; }
  footer { padding: 32px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--gray); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 8px 16px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .masthead { border-radius: 18px; padding: 22px 18px 18px; margin-top: 16px; }
    .toc { columns: 1; }
    header.site .bar { padding: 10px 20px 4px; }
    header.site nav { margin-left: 0; justify-content: flex-start; flex-basis: 100%; gap: 0 16px; }
    /* 44 px touch targets */
    header.site nav a, footer nav a { display: inline-block; padding: 11px 0; }
    nav.crumbs a { display: inline-block; padding: 12px 0; }
    nav.crumbs { padding-top: 4px; }
    nav.crumbs ol { align-items: center; }
    .places .link a { display: inline-block; padding: 11px 0; }
    .places .link { margin: 0; }
  }
"""


def find_keys(obj, keys):
    if isinstance(obj, dict):
        return [k for k in obj if k in keys] + [x for v in obj.values() for x in find_keys(v, keys)]
    if isinstance(obj, list):
        return [x for v in obj for x in find_keys(v, keys)]
    return []


def jsonld(obj):
    # no ratings or reviews from anyone, ever (structured data included)
    bad = find_keys(obj, {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue"})
    assert not bad, bad
    big = obj.get("@type") == "ItemList"
    text = json.dumps(obj, ensure_ascii=False, indent=None if big else 1, separators=(",", ":") if big else None)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">\n' + text + "\n</script>"


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    # structured data lists real pages only: "Regions" (/#regions) is the home page again, so it stays a visible link but no item
    pages_only = [(n, u) for n, u in trail if "#" not in u]
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(pages_only)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


def store_button(label="Ask for early access"):
    if APP_STORE_URL:
        if os.path.exists(f"{DOCS}/img/app-store-badge.svg"):
            return (f'<a class="store-badge" href="{e(APP_STORE_URL)}" rel="noopener"><img src="/img/app-store-badge.svg" '
                    'alt="Download on the App Store" width="150" height="50"></a>')
        return f'<a class="btn store-btn" href="{e(APP_STORE_URL)}" rel="noopener">Download on the App Store</a>'
    # pre-launch: no App Store link exists yet, so the button asks for early access by email. Only Nick's internal TestFlight group
    # exists (Nick, 2026-10-13): the copy ends at an ask, and nothing says we'll send an invite or a link, or that access is by invite.
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=Pennsylvania%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'{label}</a>')


def store_note(text="Free on iPhone and iPad."):
    return f'{text} Not in the App Store yet.' if not APP_STORE_URL else text


REGION_PAGE = {r: f"regions/{REGION_SLUG[r]}.html" for r in REGIONS}
CITY_PAGES = ["Philadelphia", "Pittsburgh", "Allentown", "Lancaster", "Erie", "Harrisburg", "Reading", "Scranton", "State College",
              "York", "Bethlehem", "Wilkes-Barre", "West Chester", "Altoona", "Williamsport", "Johnstown", "Easton", "Hershey"]
CITY_PAGES = [c for c in CITY_PAGES if CITY_COUNT[c] >= 100]   # a town page needs 100 restaurants
CITY_REGION = {c: Counter(p.region for p in REST if p.city == c).most_common(1)[0][0] for c in CITY_PAGES}


def city_url(c):
    return f"/cities/{slug(c)}.html"


# datePublished: when each page first went out (dateModified and the sitemap's lastmod follow TODAY). New pages go here.
FIRST_PUBLISHED = dict.fromkeys(["index.html", "explore/index.html", "privacy.html", "terms.html", "support.html", ICONS_PAGE[0], OLDEST_PAGE[0]]
                                + [pg for _, pg, *_ in GUIDES] + list(REGION_PAGE.values()) + [city_url(c)[1:] for c in CITY_PAGES], "2026-10-21")


def inspection_notes(body):
    """The explainer for each kind of inspection result the page shows: Allegheny's placards, Philadelphia's licenses and search,
    Bucks' and Montgomery's search portals, and PDA's search with its disclosure, verbatim. Added at the end of <main>."""
    out = []
    if 'class="insp ac-insp' in body:
        out.append("<p><b>Allegheny County placards</b> are the Allegheny County Health Department's own, labeled official and shown with the date "
                   "of the inspection: green “Inspected &amp; Permitted”, yellow “Consumer Alert” (up to 10 days to correct), red for a closure. "
                   "We compute no grade. Source: ACHD inspections via the Western Pennsylvania Regional Data Center"
                   + (f", records through {nice_date(RT['achd'])}" if HAS_ACHD else "") + f'; reports on <a href="{ACHD_PAGE}" rel="noopener">ACHD\'s site</a>.</p>')
    if 'class="insp phl-insp' in body:
        out.append("<p><b>In Philadelphia</b>, “licensed” means an active City of Philadelphia L&amp;I food license was matched to the place "
                   f"(OpenDataPhilly, City of Philadelphia License; licenses issued through {nice_date(RT['philly'])}). It says the place is "
                   "licensed, not how an inspection went. The Department of Public Health posts inspection reports one search at a time, with "
                   f'no grade or score: <a href="{PHILLY_SEARCH}" rel="noopener">Philadelphia inspection reports</a>. In the City\'s words:</p>'
                   f"<blockquote><p>“{PHILLY_DISCLAIMER}”</p></blockquote>")
    if 'class="insp county-insp' in body:
        out.append(f'<p><b>Bucks and Montgomery counties</b> inspect their own restaurants and post reports one search at a time, so we link to them: '
                   f'<a href="{BUCKS_SEARCH}" rel="noopener">Bucks County</a>, <a href="{MONT_SEARCH}" rel="noopener">Montgomery County</a>.</p>')
    if 'class="insp pda-insp' in body:
        out.append("<p><b>Everywhere else</b>, the Pennsylvania Department of Agriculture and about 100 local health departments post inspection "
                   f'results in one search, place by place: the <a href="{PDA_SEARCH}" rel="noopener">PA Food Safety Inspection Search</a>. '
                   "We link to it and don't copy it, and there is no statewide grade. In the Department's words:</p>"
                   f"<blockquote><p>“{PDA_DISCLOSURE}”</p></blockquote>")
    if not out:
        return body
    sec = f'<section id="inspection-notes" class="notes"><h2>About inspections</h2>{"".join(out)}</section>\n  '
    i = body.rfind("</main>")
    assert i >= 0
    return body[:i] + sec + body[i:]


# The publisher, on every page (404 included): the Eats Ranked hub lists this site as a subOrganization, and this node says so from
# this side too (the same parentOrganization on every Eats Ranked state site)
ORG_LD = {"@context": "https://schema.org", "@type": "Organization", "@id": f"{DOMAIN}/#org", "name": BRAND, "url": f"{DOMAIN}/",
          "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "email": EMAIL,
          "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"},
          "parentOrganization": {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked",
                                 "url": "https://eatsranked.com/"}}


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None, extra_css="", head_extra=""):
    assert 50 <= len(title) <= 60 or path == "404.html", (path, len(title), title)
    assert 140 <= len(desc) <= 160 or path == "404.html", (path, len(desc), desc)
    assert body.count("<h1") == 1, path
    assert path in FIRST_PUBLISHED or path == "404.html", f"add {path} to FIRST_PUBLISHED"
    body = inspection_notes(body)
    url = DOMAIN + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))
    canonical = "" if path == "404.html" else f'<link rel="canonical" href="{url}">\n'
    og_url = "" if path == "404.html" else f'<meta property="og:url" content="{url}">\n'
    og_alt = og_alt or f"{BRAND}: {TAGLINE.lower()}. Pennsylvania restaurants, with hand-checked cheesesteaks, tomato pie and Pennsylvania Dutch dining rooms."
    ld = "\n".join(jsonld(x) for x in [*lds, ORG_LD])
    doc = f"""<!DOCTYPE html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{canonical}<meta name="robots" content="{robots}">
<meta name="theme-color" content="#2E4E3F">
<meta name="color-scheme" content="light">
<!-- Smart App Banner: once the App Store Connect record exists, replace APP_ID with the numeric Apple ID and uncomment.
<meta name="apple-itunes-app" content="app-id=APP_ID">
-->
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
{og_url}<meta property="og:type" content="{'website' if path == 'index.html' else 'article'}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{DOMAIN}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{DOMAIN}/og.png">
<meta name="twitter:image:alt" content="{e(og_alt)}">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
{head_extra}<style>{CSS}{extra_css}</style>
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="bar wrap">
    <a class="logo" href="/" aria-label="{BRAND} home">{LOGO}{BRAND}</a>
    {STATE}
    <nav aria-label="Main">
      <a href="{GUIDE_URL['steak']}">Cheesesteaks</a>
      <a href="{GUIDE_URL['pie']}">Tomato pie</a>
      <a href="/#regions">Regions</a>
      <a href="/explore/">Search</a>
    </nav>
  </div>
</header>
<div class="wrap">
{body}
  <footer>
    <nav aria-label="Footer">
      <a href="/">{BRAND} app</a>
      <a href="/explore/">Search Pennsylvania restaurants</a>
      {"".join(f'<a href="/{pg}">{e(n)}</a>' for _, pg, n, *_ in GUIDES)}
      <a href="/{ICONS_PAGE[0]}">{ICONS_PAGE[1]}</a>
      {f'<a href="/{OLDEST_PAGE[0]}">{OLDEST_PAGE[1]}</a>' if HAS_OLDEST else ""}
      <a href="/support.html">Support</a>
      <a href="/privacy.html">Privacy policy</a>
      <a href="/terms.html">Terms of use</a>
    </nav>
    <p>Place data: hand-checked research by {BRAND} (checked {CHECKED}); Overture Maps Foundation places (CDLA Permissive 2.0, and Apache 2.0 for Foursquare data, with the <a href="/terms.html#sources">Foursquare NOTICE</a>); City of Philadelphia L&amp;I business licenses (OpenDataPhilly){"; Allegheny County Health Department inspections (Western Pennsylvania Regional Data Center)" if HAS_ACHD else ""}; U.S. Census Bureau outlines. In the app, maps and each place's live card come from Apple Maps. Data as of {nice_date(DATA_DATE)}.</p>
    <p>{BRAND} is independent: not affiliated with, endorsed by or operated by the Commonwealth of Pennsylvania or any of its agencies (the Department of Agriculture and the Liquor Control Board included), the City of Philadelphia or its departments, Allegheny, Bucks or Montgomery County or their health departments, the Western Pennsylvania Regional Data Center, Michelin, the James Beard Foundation, Apple, or any restaurant, team or chain. {MICHELIN_TM} {JBF_TM} Places open and close, so check before you go.</p>
    <p>Questions or corrections: <a href="mailto:{EMAIL}">{EMAIL}</a>. © 2026 {BRAND}. Part of <a href="https://eatsranked.com/">Eats Ranked</a>, restaurant apps state by state.</p>
  </footer>
</div>
</body>
</html>
"""
    if BASE:   # served under /pennsylvania-eats/: every root-relative link and asset gets the prefix
        doc = re.sub(r'(href|src|srcset)="/', rf'\1="{BASE}/', doc)
    # A Content-Security-Policy in a meta tag (GitHub Pages can't send headers), first in <head>: only this page's own inline scripts
    # run, by hash (JSON-LD blocks are data, not scripts), and nothing loads from any other site.
    scripts = re.findall(r"<script>(.*?)</script>", doc, re.S)
    hashes = " ".join(f"'sha256-{base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()}'" for x in scripts) or "'none'"
    csp = (f"default-src 'none'; script-src {hashes}; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
           "manifest-src 'self'; base-uri 'none'; form-action 'none'; upgrade-insecure-requests")
    doc = doc.replace("<head>\n", f'<head>\n<meta http-equiv="Content-Security-Policy" content="{csp}">\n', 1)
    # data honesty, checked on every page
    low = doc.lower()
    assert "google" not in low, path
    assert "★" not in doc and "&#9733;" not in doc, path
    assert not re.search(r"james beard finalist", low), path
    assert not private_words(doc), path
    assert MICHELIN_TM in doc and JBF_TM in doc, path
    assert "@gmail.com" not in doc and f"mailto:{EMAIL}" in doc, path
    assert 'Part of <a href="https://eatsranked.com/">Eats Ranked</a>' in doc, path
    assert not re.search(r"\b(confirmed|verified) open\b", re.sub(r"<[^>]+>", " ", doc), re.I), path
    if 'class="insp pda-insp' in doc:
        assert html.escape(PDA_DISCLOSURE, quote=False) in doc or PDA_DISCLOSURE in doc, f"{path}: the PDA link without PDA's disclosure"
    if 'class="insp phl-insp' in doc:
        assert PHILLY_DISCLAIMER in doc, f"{path}: Philadelphia licenses without the City's disclaimer"
    for m in re.finditer(r'class="insp ac-insp[^"]*"><span class="pl', doc):   # an official placard always carries its date
        tail = doc[m.end():m.end() + 400]
        assert re.search(r"inspected [A-Z][a-z]{2} \d{1,2}, \d{4}", tail), (path, tail[:120])
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w", encoding="utf-8").write(doc)
    return path


def chips(p):
    out = []
    if p.mi_label:
        out.append(f'<span class="tag tag-hon">{p.mi_label}</span>')
    if p.jb_label:
        out.append(f'<span class="tag tag-hon">{p.jb_label}</span>')
    out += [f'<span class="tag">{k}</span>' for k in p.kind_names() if k != "Historic"]
    if p.seasonal:
        out.append('<span class="tag tag-plain">Seasonal</span>')
    return "".join(out)


PL_CLASS = lambda t: ("green" if t == "Inspected & Permitted" else "yellow" if "consumer alert" in t.lower() else
                      "red" if "clos" in t.lower() else "other")


def insp_html(p):
    """The official record for one place, kept to its own jurisdiction (never blended, never ranked)."""
    if p.county == "Allegheny":
        if p.ac:
            t = p.ac["p"]
            return (f'<p class="insp ac-insp"><span class="pl pl-{PL_CLASS(t)}">{e(t)}</span><span><b>Official placard · inspected {nice_date(p.ac["d"])}</b>'
                    '<small>Allegheny County Health Department</small></span></p>')
        return ""
    if p.county == "Philadelphia":
        return ('<p class="insp phl-insp"><span><b>' + ("Active City food license" if p.phl else "No City food license matched")
                + '</b><small>City of Philadelphia L&amp;I; inspection reports are search-only</small></span></p>')
    if p.county in ("Bucks", "Montgomery"):
        return f'<p class="insp county-insp"><span><small>{p.county} County posts inspection reports one search at a time.</small></span></p>'
    return '<p class="insp pda-insp"><span><small>Inspections: the PA Food Safety Inspection Search, one search at a time.</small></span></p>'


def place_where(p, here_city=None):
    """"600 Wendover St, Philadelphia", with the city linked to its page when it has one (and isn't this page's)."""
    town = e(p.place_name)
    if p.city in CITY_PAGES and p.city != here_city:
        town = f'<a href="{city_url(p.city)}">{town}</a>'
    return ", ".join(x for x in (e(p.addr), town) if x)


def place_item(p, extra=None, here_city=None):
    """One place on a guide, region or city page, anchored as #p-<id> (the JSON-LD list items point there)."""
    facts = []
    if p.dish:
        facts.append(f"<b>Known for:</b> {e(p.dish.replace('; ', ', '))}")
    if p.season:
        facts.append(f"<b>Season:</b> {e(p.season)}")
    elif p.seasonal:
        facts.append("<b>Season:</b> seasonal; check before you go")
    if p.founded:
        facts.append(f"<b>At this address since</b> {p.founded}")
    if p.branch:
        facts.append(f"<b>A branch of</b> {e(p.branch)}")
    where = place_where(p, here_city)
    if extra:
        where += f" · {e(extra)}"
    out = [f'<li id="p-{p.id}"><h3>{e(p.name)}</h3>', f'<p class="where">{where}</p>']
    c = chips(p)
    if c or facts:
        out.append('<p class="facts">' + c + (" " if c and facts else "") + " · ".join(facts) + "</p>")
    if p.note:
        out.append(f'<p class="note">{e(p.note)}</p>')
    if p.mi_label:
        out.append(f'<p class="note"><b>MICHELIN Guide, Philadelphia, 2025 selection:</b> {p.mi_label}</p>')
    if p.jbf:
        out.append(f'<p class="note"><b>James Beard:</b> {e(p.jbf)}</p>')
    out.append(insp_html(p))
    if p.site:
        host = re.sub(r"^https?://(www\.)?", "", p.site).split("/")[0]
        out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(host)}</a></p>')
    out.append("</li>")
    return "".join(out)


def restaurant_ld(p, url):
    a = {"@type": "PostalAddress", "streetAddress": p.addr, "addressLocality": p.mail_town, "addressRegion": "PA",
         "postalCode": p.zip, "addressCountry": "US"}
    x = {"@type": "Restaurant", "name": p.name, "url": f"{url}#p-{p.id}", "address": {k: v for k, v in a.items() if v}}
    if p.lat is not None and p.lon is not None:
        x["geo"] = {"@type": "GeoCoordinates", "latitude": round(p.lat, 5), "longitude": round(p.lon, 5)}
    if p.phone:
        x["telephone"] = p.phone
    if p.site:
        x["sameAs"] = p.site
    if p.cuisine and p.cuisine != "American & Other":
        x["servesCuisine"] = p.cuisine
    return x


def item_list(name, places, url):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{url}#p-{p.id}", "item": restaurant_ld(p, url)}
                                for i, p in enumerate(places)]}


def article_ld(url, headline, desc):
    path = url[len(DOMAIN) + 1:]
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
            "datePublished": FIRST_PUBLISHED[path], "dateModified": TODAY, "inLanguage": "en", "mainEntityOfPage": url,
            "image": f"{DOMAIN}/og.png", "author": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/"},
            "publisher": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/", "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png"}}}


def by_region(places):
    groups = defaultdict(list)
    for p in places:
        groups[p.region].append(p)
    return [(r, sorted(groups[r], key=lambda p: (p.city or "", p.name.lower()))) for r in REGIONS if groups.get(r)]


def region_sections(places, noun, nouns=None):
    regions = by_region(places)
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{REGION_SLUG[r]}">{e(r)}</a> ({len(ps)})</li>' for r, ps in regions) + "</ul>"
    secs = []
    for r, ps in regions:
        cities = Counter(p.city for p in ps).most_common(3)
        secs.append(f'<section id="{REGION_SLUG[r]}" aria-labelledby="h-{REGION_SLUG[r]}"><h2 id="h-{REGION_SLUG[r]}">{e(r)}</h2>'
                    f'<p class="sub">{plural(len(ps), noun, nouns)}, by city or town'
                    + (f", most in {e(and_list([c for c, _ in cities]))}" if len(cities) > 1 else "")
                    + f'. See the <a href="/{REGION_PAGE[r]}">{e(r)} page</a> for the region.</p><ol class="places">'
                    + "".join(place_item(p) for p in ps) + "</ol></section>")
    return toc, "\n".join(secs)


def year_line(ps, n):
    return "; ".join(f'<a href="#p-{p.id}">{e(p.name)}</a> in {e(p.place_name)}, there since {p.founded}'
                     for p in sorted([p for p in ps if p.founded], key=lambda p: (p.founded, p.name))[:n])


def how_checked(order="the order is by region and city"):
    return (f"In {CHECKED} we looked up every place here in a 2025 or 2026 source (the shop's own site or menu, a dated post, local "
            "reporting, or a tourism listing) and matched its address. No current source, no listing. Review sites played no part, and "
            f"{order}, not by anyone's rating. Menus and hours move, so call first.")


def regions_line():
    return f"grouped by {len(REGIONS)} regions of the state, Philadelphia first"


def region_links():
    return '<ul class="towns">' + "".join(f'<li><a href="/{REGION_PAGE[r]}">{e(r)}</a></li>' for r in REGIONS) + "</ul>"


def city_links(cities=None):
    return '<ul class="towns">' + "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in (cities or CITY_PAGES)) + "</ul>"


def city_line():
    return f'<p class="fine">City pages: {", ".join(f"<a href={chr(34)}{city_url(c)}{chr(34)}>{e(c)}</a>" for c in CITY_PAGES)}.</p>'


written = []

# ---------------------------------------------------------------- the guide pages (those with 4+ hand-checked places)
def _n(ps, kind):
    return sum(1 for p in ps if p.kinds & KIND[kind])


GUIDE_COPY = {
    "steak": dict(
        h1="Philadelphia cheesesteaks, roast pork &amp; hoagies",
        lede=lambda n, ps: f"{n} steak shops, roast pork counters and hoagie delis, most in Philadelphia, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Three sandwiches, one city",
        about=("A cheesesteak is thin-sliced beef cooked on the griddle with onions if you want them and provolone, American or Whiz, on a "
               "long roll. Roast pork is the other Philadelphia sandwich: thin-sliced pork with sharp provolone and broccoli rabe or greens. "
               "A hoagie is the cold one: Italian meats, provolone, lettuce, tomato, onion and oil on a seeded roll. Who invented the "
               "cheesesteak is a legend, not a fact we rank."),
        parts=lambda ps: [plural(_n(ps, "cheesesteak"), "steak shop"), plural(_n(ps, "roast pork"), "roast pork counter"),
                          plural(_n(ps, "hoagie"), "hoagie shop")],
        named=("steak", "“steaks”, “cheesesteak” or “hoagie”"), map_label="See them on a map"),
    "pie": dict(
        h1="Tomato pie &amp; Old Forge pizza",
        lede=lambda n, ps: f"{n} bakeries and pizzerias for Philadelphia tomato pie or Old Forge-style trays, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Two square pies, two ends of the state",
        about=("Philadelphia tomato pie is a thick, square-cut focaccia-like crust under a sweet tomato sauce with a little grated cheese and "
               "no mozzarella, usually sold by the slice or the half-sheet at room temperature. Old Forge pizza, from the borough of Old Forge "
               "near Scranton, is baked in rectangular trays and sold by the tray or the cut: red with sauce and cheese, or white, a double "
               "crust with onions and herbs."),
        parts=lambda ps: [plural(_n(ps, "tomato pie"), "tomato pie bakery or pizzeria", "tomato pie bakeries and pizzerias"),
                          plural(_n(ps, "old forge"), "Old Forge-style pizzeria")],
        named=("pie", "“tomato pie” or “Old Forge”"), map_label="See them on a map"),
    "pierogi": dict(
        h1="Pierogies &amp; Pittsburgh classics",
        lede=lambda n, ps: f"{n} places for pierogies and Pittsburgh's own sandwich, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Dumplings and a sandwich with the fries inside",
        about=("Pierogies are half-moon dumplings filled with potato and cheese, sauerkraut or farmer's cheese, boiled and often fried in "
               "butter with onions, the food of western Pennsylvania's Polish, Slovak and Ukrainian kitchens. Pittsburgh's own sandwich puts "
               "the fries and the coleslaw inside, with grilled meat and provolone on Italian bread."),
        parts=lambda ps: [plural(_n(ps, "pierogi"), "pierogi kitchen"), plural(_n(ps, "pittsburgh sandwich"), "sandwich shop")],
        named=("pierogi", "“pierogi”"), map_label="See them on a map"),
    "dutch": dict(
        h1="Pennsylvania Dutch restaurants",
        lede=lambda n, ps: f"{n} Pennsylvania Dutch dining rooms, smorgasbords and market counters, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Family style and smorgasbord",
        about=("Pennsylvania Dutch cooking is the farm food of Lancaster County's Amish, Mennonite and other German-speaking families: chicken "
               "pot pie with square noodles, chicken and waffles, ham balls, chow-chow, apple dumplings and shoofly pie. Many dining rooms "
               "serve it family style or as a smorgasbord, and many close on Sundays, which isn't closed."),
        parts=lambda ps: [], named=("dutch", "“Dutch”, “Amish” or “smorgasbord”"), map_label="See them on a map"),
    "pretzel": dict(
        h1="Soft pretzel bakeries",
        lede=lambda n, ps: f"{n} bakeries twisting soft pretzels, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Philly's figure eight and the Dutch Country knot",
        about=("A Philadelphia soft pretzel is baked in long strips of figure eights and sold by the strip or the dozen, often from a bakery "
               "window early in the morning; Dutch Country bakers twist the classic knot and roll them by hand."),
        parts=lambda ps: [], named=("pretzel", "“pretzel”"), map_label="See them on a map"),
    "diner": dict(
        h1="Pennsylvania diners",
        lede=lambda n, ps: f"{n} diners and luncheonettes, each {checked_open(ps)} against a dated 2025 or 2026 source.",
        about_h="Counters, booths and breakfast all day",
        about=("Pennsylvania built many of the country's prefabricated diners, and plenty still serve scrapple, creamed chipped beef and pie "
               "at the counter."),
        parts=lambda ps: [], named=("diner", "“diner”"), map_label="See them on a map"),
}
guide_stats = {}
for k, pg, short, title_name, kinds, sub in GUIDES:
    ps = G[k]
    n = len(ps)
    cp = GUIDE_COPY[k]
    url = f"{DOMAIN}/{pg}"
    n_regions = len({p.region for p in ps})
    title = fit_combo(cp.get("titles", []) + [f"Pennsylvania {title_name}: {n} Checked Places", f"{title_name} in Pennsylvania: {n} Checked Places",
                       f"{title_name} in Pennsylvania: {n} Places", f"{title_name}: {n} Checked Places", f"{title_name}: {n} Places in PA",
                       f"{title_name}: {n} Places"],
                      [f" | {BRAND}", f" | {SHORT}", "", " | PA Guide", " | Pennsylvania", " in Pennsylvania"], 50, 60)
    parts = [x for x in cp["parts"](ps) if not x.startswith("0 ")]
    desc = fit_combo([f"{n} hand-checked {lc(short)} places in Pennsylvania, each {checked_open(ps)}, by region and city",
                      f"{n} {lc(short)} places in Pennsylvania, each {checked_open(ps)} against a 2025 or 2026 source, by region and city",
                      f"{n} {lc(short)} places across Pennsylvania, {checked_open(ps)}, by region and city",
                      f"{n} {lc(short)} places in Pennsylvania, {checked_open(ps)}"],
                     [". Free, no ads, no ratings.", ". Free, no ratings, no sign-up.", ". Free, no ratings.", ". Free.", "."], 140, 160)
    toc, secs = region_sections(ps, "place")
    nav, bc = crumbs([("Home", "/"), (short, "/" + pg)])
    h1 = cp["h1"]
    named_txt = ""
    if cp["named"] and NAMED.get(cp["named"][0]):
        named_txt = (f" {NAMED[cp['named'][0]]:,} other places in the app's directory have {cp['named'][1]} in their name; they're in the "
                     "directory and the web search, but not on this list until we check them.")
    yl = year_line(ps, 4)
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <div class="guide-mark">{glyph_svg(k, 40)}</div>
    <p class="kicker">{BRAND} guide · checked {CHECKED}</p>
    <h1>{h1}</h1>
    <p class="lede">{cp["lede"](n, ps)}</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g=k, r="all", view="map"))}">{cp["map_label"]}</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-{k}">
    <h2>{cp["about_h"]}</h2>
    <p>{cp["about"]}</p>
    <h2>The {n} on this list</h2>
    <p>{(and_list(parts) + ", some of them more than one. ") if len(parts) > 1 else ""}They're in {plural(n_regions, "region")} of the state.{(" The longest at the same address: " + yl + ".") if yl else ""}{named_txt}</p>
    <p>How the list was built: {how_checked()}</p>
    <p>Each place shows its official record where one is published in bulk{" (Allegheny County's placard with its date)" if HAS_ACHD else ""}, whether a Philadelphia place holds an active City food license, and elsewhere a link to the agency's own inspection search. In the app, this list puts the nearest places first, with Apple Maps' live card a tap away for hours and photos.</p>
    <h2>Jump to a region</h2>
    <p class="sub">The list is {regions_line()}.</p>
    {toc}
    {city_line()}
  </section>
{secs}
  </main>"""
    written.append(page(pg, title, desc, body, [article_ld(url, html.unescape(h1), desc), bc,
                                                 item_list(f"{title_name} in Pennsylvania", ps, url)]))
    guide_stats[k] = n

# ---------------------------------------------------------------- Pennsylvania icons (MICHELIN, James Beard, institutions)
url = f"{DOMAIN}/{ICONS_PAGE[0]}"
n = len(ICONS)
n_star = sum(1 for p in ICONS if p.mi and p.mi >= 3)
n_bib = sum(1 for p in ICONS if p.mi == 2)
n_jb = sum(1 for p in ICONS if p.h & 15)
n_old = sum(1 for p in ICONS if p.kinds & KIND["oldest"])
title = fit_combo([f"Pennsylvania Restaurant Icons: {n} Honored Places", f"Pennsylvania Icons: {n} Honored Restaurants",
                   f"Pennsylvania Icons: MICHELIN & James Beard Honorees"], [f" | {SHORT}", f" | {BRAND}", ""], 50, 60)
desc = fit_combo([f"{n} Pennsylvania restaurants with a MICHELIN distinction or a James Beard honor, from Philadelphia's first MICHELIN selection, by region and city",
                  f"{n} Pennsylvania restaurants with MICHELIN or James Beard honors, by region and city"],
                 [". Honors are facts, not ratings.", ". Facts, not ratings.", ". Free, no ratings.", "."], 140, 160)
toc, secs = region_sections(ICONS, "place")
nav, bc = crumbs([("Home", "/"), ("Pennsylvania icons", "/" + ICONS_PAGE[0])])
h1 = "Pennsylvania icons"
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · honors and history</p>
    <h1>{h1}</h1>
    <p class="lede">{n} places with a MICHELIN distinction or a James Beard honor: {plural(n_star, "MICHELIN-starred restaurant")}, {plural(n_bib, "Bib Gourmand")} and {plural(n_jb, "James Beard honoree")}, some more than one.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="icons", r="all", view="map"))}">See them on a map</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-icons">
    <h2>Honors are facts, not ratings</h2>
    <p>Each honor is written out as it was given: "1 MICHELIN Star", "Bib Gourmand" or "Green Star" from the MICHELIN Guide's first Philadelphia selection (November 2025), and James Beard awards and America's Classics from the James Beard Foundation's own announcements (2025 and 2026). A nominee is never called a winner. Every MICHELIN selection in the state is in Philadelphia so far; Pittsburgh's first comes with the guide's Great Lakes edition in 2027.</p>
    <p>The order on this page is by region and city, never by anyone's rating. The app's Pennsylvania Icons list orders the same places by their honors; those points are not a rating. Places open and close, so check before you go. {MICHELIN_TM} {JBF_TM}</p>
    <h2>Jump to a region</h2>
    {toc}
    {city_line()}
  </section>
{secs}
  </main>"""
written.append(page(ICONS_PAGE[0], title, desc, body, [article_ld(url, h1, desc), bc, item_list("Pennsylvania restaurant icons", ICONS, url)]))

# ---------------------------------------------------------------- the oldest places (years at the same address)
# Only once our research has dated 3 or more places at their current address (McGillin's 1860 is its own claim, not yet tied to
# Drury Street: data/research/app/LEADS.md). Until then the page isn't written and nothing links to it.
if HAS_OLDEST:
    url = f"{DOMAIN}/{OLDEST_PAGE[0]}"
    n = len(OLDEST)
    first, second, third = OLDEST[0], OLDEST[1], OLDEST[2]
    title = fit_combo([f"Pennsylvania's Oldest Restaurants, From {first.name} On", f"Oldest Pennsylvania Restaurants: {first.name} & {n - 1} More"],
                      ["", f" | {SHORT}", f" | {BRAND}"], 50, 60)
    desc = fit_combo([f"{first.name} ({first.founded}) and {n - 1} more Pennsylvania restaurants, oldest first by the year each opened at its current address"],
                     [". Facts, not ratings.", ". Free, no ratings.", "."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Oldest places", "/" + OLDEST_PAGE[0])])
    h1 = "Pennsylvania's oldest restaurants"
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · since {first.founded}, checked {CHECKED}</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{e(first.name)} in {e(first.place_name)} has stood at its address since {first.founded}, {e(second.name)} since {second.founded} and {e(third.name)} since {third.founded}. They lead the {n} places on our hand-checked lists whose year at their current address we could pin down.</p>
  </section>
  <section id="about-oldest"><h2>What a year here means</h2><p>The year is when the place opened where it stands today, from its own history page or local reporting. A move resets the clock. How the list was built: {how_checked("the order is by years at the same address")}</p></section>
  <section id="all"><h2>Oldest first</h2><ol class="places">{"".join(place_item(p) for p in OLDEST)}</ol></section>
  </main>"""
    written.append(page(OLDEST_PAGE[0], title, desc, body, [article_ld(url, h1, desc), bc, item_list("Pennsylvania's oldest restaurants", OLDEST, url)]))


# ---------------------------------------------------------------- region pages
def inspections_for(counties, here=""):
    """Which official records cover these counties, in plain words (each jurisdiction kept to itself)."""
    cs = set(counties)
    out = []
    if "Philadelphia" in cs:
        out.append("In Philadelphia, the app shows whether an active City of Philadelphia L&amp;I food license was matched to each place; the "
                   "Department of Public Health's inspection reports are search-only, with no grade or score, so the app links to them.")
    if "Allegheny" in cs:
        out.append("In Allegheny County, the Health Department posts a placard after every inspection: green “Inspected &amp; Permitted”, yellow "
                   "“Consumer Alert”, red for a closure. " + ("The app shows that official placard with its inspection date."
                                                               if HAS_ACHD else "Those placards aren't in this version of the app yet; the app links to the county's reports."))
    co = sorted(cs & {"Bucks", "Montgomery"})
    if co:
        out.append(f"{and_list([c + ' County' for c in co])} {'inspects' if len(co) == 1 else 'inspect'} on {'its' if len(co) == 1 else 'their'} own and "
                   "{'posts' if len(co) == 1 else 'post'} reports one search at a time, so the app links to them.".replace("{'posts' if len(co) == 1 else 'post'}", "posts" if len(co) == 1 else "post"))
    rest = sorted(cs - {"Philadelphia", "Allegheny", "Bucks", "Montgomery"})
    if rest:
        out.append(f"{'In ' + and_list([c + ' County' for c in rest]) if len(rest) <= 3 else 'In the other counties'}, the Pennsylvania Department "
                   "of Agriculture or a local health department inspects, and the results are in the PA Food Safety Inspection Search, one "
                   "search at a time; the app links to it. There is no statewide grade, and we don't make one.")
    return " ".join(out)


region_stats = {}
# what searchers call a region (the page keeps our region name in its h1 and links)
REGION_SEARCH_NAME = {"Philly Suburbs": "Philadelphia Suburbs", "Pittsburgh Region": "Pittsburgh Area", "Central": "Central PA",
                      "Northwest": "Northwest PA", "Northern Tier": "PA Northern Tier", "South Central": "South Central PA"}
SECTION_ORDER = [(k, GUIDE_NAME[k]) for k, *_ in GUIDES]
for r in REGIONS:
    sl = REGION_SLUG[r]
    path = REGION_PAGE[r]
    url = f"{DOMAIN}/{path}"
    here_all = [p for p in REST if p.region == r]
    n_r = len(here_all)
    counties = sorted(c for c in COUNTIES if COUNTY_REGION[c] == r)
    hc_here = sorted([p for p in here_all if p.on_guide], key=P.featured_key)
    icons_here = sorted([p for p in here_all if p.ip is not None and not p.on_guide], key=P.featured_key)
    in_guide = {k: [p for p in hc_here if p in set(G[k])] for k in G}
    gwords = [guide_word(k, in_guide[k]) for k, _ in sorted(SECTION_ORDER, key=lambda x: -len(in_guide[x[0]])) if in_guide[k]]   # most first
    top_cities = CITY_COUNT and Counter(p.city for p in here_all).most_common(6)
    cuis = Counter(p.cuisine for p in here_all if p.cuisine != "American & Other").most_common(8)
    pages_here = [c for c in CITY_PAGES if CITY_REGION[c] == r]
    rs = REGION_SEARCH_NAME.get(r, r)
    title = fit_combo([f"{rs} Restaurants: {' & '.join(gwords[:2])}" if gwords else f"{rs} Restaurants",
                       f"{rs} Restaurants & Classics", f"{rs} Restaurants"],
                      [f" | {BRAND}", f" | {SHORT}", ", Pennsylvania", " Guide", " and More", " in Pennsylvania", " in Pennsylvania | PA Eats",
                       " Guide | Pennsylvania Eats", ": Guides & Inspections", ": a Free Guide | PA Eats", ": the Free Guide | PA Eats",
                       ": a Free Restaurant Guide | PA Eats"], 50, 60)
    lw = and_list([w.lower() for w in gwords]) if gwords else "classics"
    desc = fit_combo([f"{n_r:,} restaurants {REGION_IN[r]}, with hand-checked {lw} and where each county posts its inspections",
                      f"{n_r:,} restaurants {REGION_IN[r]}, Pennsylvania, with hand-checked {lw} and official records",
                      f"{n_r:,} restaurants {REGION_IN[r]}, Pennsylvania, with hand-checked classics and official records",
                      f"{n_r:,} restaurants, cafés, bars and bakeries {REGION_IN[r]}, Pennsylvania, with where each county posts its inspections",
                      f"{n_r:,} restaurants, cafés, bars and bakeries {REGION_IN[r]}, Pennsylvania, with the official records each county keeps"],
                     [". Free, no ratings.", ". Free, no ads.", ". Free.", ", in a free app.", ", from open data. Free, no ads, no ratings.", "."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Regions", "/#regions"), (r, "/" + path)])
    h1 = f"{r} restaurants"
    county_txt = and_list(["the city and county of Philadelphia" if c == "Philadelphia" else f"{c} County" for c in counties])
    facts = [f"Our directory counts {n_r:,} restaurants, cafés, bars and bakeries {REGION_IN[r]}"
             + (f"; the places with the most are {and_list(e(c) + ' (' + format(k, ',') + ')' for c, k in top_cities[:4])}" if top_cities else "") + "."]
    if cuis:
        facts.append(f"{and_list(e(c) + ' (' + format(k, ',') + ')' for c, k in cuis[:4])} lead the kinds of food.")
    facts.append(f"{plural(len(hc_here), 'place')} {'is' if len(hc_here) == 1 else 'are'} on our hand-checked guides"
                 + (f", and {plural(len(icons_here), 'more carries', 'more carry')} a MICHELIN or James Beard honor" if icons_here else "") + ".")
    if r == "Philadelphia":
        facts.append(f"{sum(1 for p in here_all if p.phl):,} hold an active City food license we matched (licenses issued through {nice_date(RT['philly'])}).")
    secs = []
    for k, name in SECTION_ORDER:
        ps = in_guide[k]
        if not ps:
            continue
        secs.append(f'<section id="{k}"><h2>{e(name)} {REGION_IN[r]}</h2><p class="sub">{plural(len(ps), "place")}, by city. '
                    f'<a href="{GUIDE_URL[k]}">All {len(G[k])} in Pennsylvania</a>.</p><ol class="places">'
                    + "".join(place_item(p) if p.id not in shown_ids else
                              f'<li class="again"><h3><a href="#p-{p.id}">{e(p.name)}</a></h3><p class="where">{place_where(p)}; listed above</p></li>'
                              for shown_ids in [set(x.id for kk, _ in SECTION_ORDER[:[a for a, _ in SECTION_ORDER].index(k)] for x in in_guide[kk])]
                              for p in sorted(ps, key=lambda p: (p.city or "", p.name.lower())))
                    + "</ol></section>")
    other_hc = [p for p in hc_here if not any(p in in_guide[k] for k in G)]
    if other_hc or icons_here:
        lst = sorted(other_hc + icons_here, key=lambda p: (p.city or "", p.name.lower()))
        secs.append(f'<section id="icons"><h2>Icons and old-timers {REGION_IN[r]}</h2><p class="sub">{plural(len(lst), "place")} with a MICHELIN or '
                    f'James Beard honor or a long history at the same address, by city. Honors are facts, not ratings. '
                    f'<a href="/{ICONS_PAGE[0]}">All Pennsylvania icons</a>.</p><ol class="places">' + "".join(place_item(p) for p in lst) + "</ol></section>")
    pills = "".join(f'<li><a href="{e(explore_url(g="all", r=sl, kind=c))}">{e(c)} ({k:,})</a></li>' for c, k in cuis)
    region_stats[r] = {"restaurants": n_r, "hand_checked": len(hc_here), "honored_not_checked": len(icons_here),
                       **{k: len(v) for k, v in in_guide.items()}}
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · region guide</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{n_r:,} restaurants, cafés, bars and bakeries in {"the " + rs + ": " if rs != r else ""}{county_txt}{", including " + plural(len(hc_here), "place") + " on our hand-checked guides, " + checked_open(hc_here) if hc_here else ""}.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="all", r=sl))}">Search {e(r)}</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-region">
    <h2>{e(r)} at a glance</h2>
    <p>{" ".join(facts)}</p>
    <h3>Health inspections here</h3>
    <p>{inspections_for(counties)}</p>
    {('<p class="fine">City pages here: ' + ", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in pages_here) + ".</p>") if pages_here else ""}
  </section>
{chr(10).join(secs)}
  {f'<section id="cuisines"><h2>What {e(r)} eats</h2><p class="sub">Tap a kind of food to search the {n_r:,} places in the region for it.</p><ul class="towns">{pills}</ul></section>' if pills else ""}
  <section id="more"><h2>Other regions</h2>{region_links()}</section>
  </main>"""
    uniq = list({p.id: p for p in hc_here + icons_here}.values())
    written.append(page(path, title, desc, body, [article_ld(url, h1, desc), bc, item_list(f"Hand-checked places and icons in {r}", uniq, url)]))

# ---------------------------------------------------------------- city pages
STREET_TYPE = {"street": "St", "st": "St", "avenue": "Ave", "ave": "Ave", "av": "Ave", "road": "Rd", "rd": "Rd", "drive": "Dr", "dr": "Dr",
               "boulevard": "Blvd", "blvd": "Blvd", "place": "Pl", "pl": "Pl", "lane": "Ln", "ln": "Ln", "parkway": "Pkwy", "pkwy": "Pkwy",
               "turnpike": "Tpke", "tpke": "Tpke", "highway": "Hwy", "hwy": "Hwy", "court": "Ct", "ct": "Ct", "square": "Sq", "sq": "Sq",
               "plaza": "Plz", "plz": "Plz", "terrace": "Ter", "ter": "Ter", "circle": "Cir", "cir": "Cir", "way": "Way", "sq.": "Sq"}
DIRS = {"north": "N", "n": "N", "south": "S", "s": "S", "east": "E", "e": "E", "west": "W", "w": "W"}


def street_of(addr, town):
    """"1237 East Passyunk Avenue, Philadelphia" -> "E Passyunk Ave"; None for a route number, a PO box or no house number."""
    a = re.sub(rf",\s*{re.escape(town)}\b.*$", "", addr or "", flags=re.I).split(",")[0]
    a = re.sub(r"\s+(#|ste\b|suite\b|unit\b|apt\b|fl\b|floor\b|rm\b|bldg\b|spc\b|space\b|store\b|\().*$", "", a, flags=re.I).strip()
    m = re.match(r"^\d+[A-Za-z]?(?:[- ]\d+)?\s+(.+)$", a)
    if not m or re.search(r"\d", m.group(1)):
        return None
    words = re.sub(r"[.]", "", m.group(1)).split()
    if len(words) < 2 or words[-1].lower() not in STREET_TYPE:
        return None
    if len(words) >= 3 and words[0].lower() in DIRS:   # "South Rd" is a road called South, "S Main St" a direction
        words[0] = DIRS[words[0].lower()]
    words[-1] = STREET_TYPE[words[-1].lower()]
    # "MAIN" and "main" become "Main"; "McLean", "US" and "USA" keep their own capitals
    return " ".join(w if (w.isupper() and len(w) <= 3) or not (w.isupper() or w.islower()) else w[:1].upper() + w[1:].lower()
                    for w in words)


def top_streets(ps, town, n=10, at_least=3):
    """The streets with the most places in a town (a city page's own, findable in the web search by name)."""
    cnt = Counter(st for p in ps if (st := street_of(p.addr, town)))
    return [(st, k) for st, k in cnt.most_common(n) if k >= at_least]


city_stats = {}
NEAR_N, NEAR_MI = 6, 20
for c in CITY_PAGES:
    r = CITY_REGION[c]
    sl = REGION_SLUG[r]
    path = city_url(c)[1:]
    url = f"{DOMAIN}/{path}"
    # the city's own region only: a few listings carry a city name from across a county line, and the web search a city page links
    # to filters by region and town, so its counts must match
    here_all = [p for p in REST if p.city == c and p.region == r]
    n_c = len(here_all)
    borough = False
    center = (statistics.median(p.lat for p in here_all), statistics.median(p.lon for p in here_all))
    hc_here = sorted([p for p in here_all if p.on_guide], key=P.featured_key)
    icons_here = sorted([p for p in here_all if p.ip is not None and not p.on_guide], key=P.featured_key)
    near = sorted([(miles(center, (p.lat, p.lon)), p) for p in ON_GUIDES if p.city != c and p.lat is not None],
                  key=lambda x: (x[0], x[1].name.lower()))
    near = [x for x in near if x[0] <= NEAR_MI][:NEAR_N]
    cuis = Counter(p.cuisine for p in here_all if p.cuisine != "American & Other").most_common(10)
    hoods = []
    per_guide = {k: sum(1 for p in hc_here if p in set(G[k])) for k, *_ in GUIDES}
    words = [guide_word(k, [p for p in hc_here if p in set(G[k])]) for k, *_ in sorted(GUIDES, key=lambda g: -per_guide[g[0]]) if per_guide[k]]
    cin = c
    where_c = f"{c}, PA"
    cn = f"{c}, PA"
    title = fit_combo([f"{cn} Restaurants: {' & '.join(words[:2])}" if words else f"{cn} Restaurants & Classics Nearby" if near else None,
                       f"{cn} Restaurants: {words[0]}" if words else None,
                       f"{c}, PA Restaurants & Inspections", f"{c}, PA Restaurants"],
                      [f" | {BRAND}", f" | {SHORT}", ", Pennsylvania", " Guide", " & More", " & More | PA Eats", " Guide | Pennsylvania Eats",
                       ": a Free Guide | PA Eats", " Guide and Map | PA Eats", ": the Free Guide | Pennsylvania Eats",
                       " Guide and Map | Pennsylvania Eats", ": a Free Restaurant Guide | PA Eats"], 50, 60)
    county0 = Counter(p.county for p in here_all).most_common(1)[0][0]
    official = ("with the City's food licenses" if county0 == "Philadelphia" else
                "with the county's official placards" if county0 == "Allegheny" and HAS_ACHD else
                "with links to each county's inspection reports")
    lw = and_list([w.lower() for w in words]) if words else "the nearest hand-checked classics" if near else None
    lwh = f"hand-checked {lw}" if words else lw   # "plus hand-checked wings", or "plus the nearest hand-checked classics"
    desc = fit_combo([f"{n_c:,} restaurants in {where_c}, {official}, plus {lwh}" if lw else None,
                      f"{n_c:,} restaurants, cafés, bars and bakeries in {where_c}, {official}, plus {lwh}" if lw else None,
                      f"{n_c:,} restaurants in {where_c}, {official}, plus {lw}" if lw else None,
                      f"{n_c:,} restaurants, cafés, bars and bakeries in {where_c}, {official}, plus the nearest hand-checked classics" if near else None,
                      f"{n_c:,} restaurants, cafés, bars and bakeries in {where_c}, {official}",
                      f"{n_c:,} restaurants, cafés, bars and bakeries in {where_c}, by street and kind of food, {official}"],
                     [". Free, no ads, no ratings.", ". Free, no ratings.", ". Free, no ads.", ". Free.", ", in a free app.", ".",
                      ", in and near the city. Free, no ads, no ratings." if near else "", ", in and near the city. Free." if near else "",
                      ", in a free web search and iPhone app.", ", in a free web search and app. No ratings."], 140, 160)
    nav, bc = crumbs([("Home", "/"), (r, "/" + REGION_PAGE[r]), (c, "/" + path)])
    h1 = f"{c} restaurants" + (f": {' & '.join(w.lower() for w in words[:2])}" if words else "")
    facts = [f"Our directory counts {n_c:,} places to eat and drink in {e(cin)}"
             + (f", in neighborhoods from {e(and_list([h for h, _ in hoods[:3]]))} on" if hoods else "")
             + (f". {and_list(e(k) + ' (' + format(v, ',') + ')' for k, v in cuis[:3])} lead the kinds of food." if cuis else ".")]
    n_lq = sum(1 for p in here_all if p.r.get("lq"))
    if n_lq:
        facts.append(f"{plural(n_lq, 'holds', 'hold')} a liquor license from the Pennsylvania Liquor Control Board.")
    n_chain = sum(1 for p in here_all if p.chain)
    if n_chain:
        facts.append(f"{plural(n_chain, 'is a location', 'are locations')} of a chain with five or more in Pennsylvania.")
    if hc_here:
        old = sorted([p for p in hc_here if p.founded], key=lambda p: p.founded)
        facts.append(("One is" if len(hc_here) == 1 else f"{len(hc_here)} are") + " on our hand-checked guides"
                     + (f"; the longest at the same address is <a href=\"#p-{old[0].id}\">{e(old[0].name)}</a>, there since {old[0].founded}." if old else "."))
    else:
        facts.append(f"None of our {len(ON_GUIDES)} hand-checked guide places is in {e(cin)} yet, so the nearest ones are below." if near else
                     f"None of our {len(ON_GUIDES)} hand-checked guide places is in {e(cin)} or within {NEAR_MI} miles of it yet.")
    insp = inspections_for([county0]) + (f" We matched an active City food license to {sum(1 for p in here_all if p.phl):,} of the {n_c:,} places here."
                                          if county0 == "Philadelphia" else f" {sum(1 for p in here_all if p.ac):,} places here carry an ACHD placard in the app."
                                          if county0 == "Allegheny" and HAS_ACHD else "")
    city_stats[c] = {"restaurants": n_c, "region": r, "hand_checked": len(hc_here), "honored_not_checked": len(icons_here), "nearby_shown": len(near)}
    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · {e(c)}, {e(r)}</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{n_c:,} restaurants, cafés, bars and bakeries in {e(cin)}{"; " + plural(len(hc_here), "place") + " on our hand-checked guides, " + checked_open(hc_here) if hc_here else ""}.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="all", r=sl, town=c))}">Search {e(cin)}</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-city"><h2>{e(cin[:1].upper() + cin[1:])} at a glance</h2><p>{" ".join(facts)}</p><h3>Health inspections here</h3><p>{insp}</p></section>"""]
    rendered = set()
    if hc_here:
        rendered.update(p.id for p in hc_here)
        parts.append(f'<section id="classics"><h2>On our guides in {e(cin)}</h2><p class="sub">Every place in {e(cin)} on our hand-checked guides, '
                     f'most honored first (honors and years at the address; not a rating).</p><ol class="places">'
                     + "".join(place_item(p, here_city=c) for p in hc_here) + "</ol></section>")
    if icons_here:
        rendered.update(p.id for p in icons_here)
        parts.append(f'<section id="icons"><h2>Honored in {e(cin)}</h2><p class="sub">{plural(len(icons_here), "place")} with a MICHELIN '
                     f'distinction or a James Beard honor, by name. Honors are facts, not ratings. <a href="/{ICONS_PAGE[0]}">All Pennsylvania icons</a>.</p>'
                     f'<ol class="places">' + "".join(place_item(p, here_city=c) for p in sorted(icons_here, key=lambda p: p.name.lower())) + "</ol></section>")
    if near:
        lo, hi = near[0][0], near[-1][0]
        parts.append(f'<section id="nearby"><h2>Hand-checked classics near {e(cin)}</h2><p class="sub">The {len(near)} nearest places on our guides '
                     f'outside {e(cin)}, within {NEAR_MI} miles of its center, closest first.</p><ol class="places">'
                     + "".join(place_item(p, extra=f"{d:.1f} mi from {c}" if d < 10 else f"{d:.0f} mi from {c}", here_city=c) for d, p in near) + "</ol></section>")
    if hoods:
        hp = "".join(f'<li><a href="{e(explore_url(g="all", r=sl, q=h))}">{e(h)} ({k:,})</a></li>' for h, k in hoods)
        parts.append(f'<section id="neighborhoods"><h2>{e(cin[:1].upper() + cin[1:])} by neighborhood</h2><p class="sub">The neighborhoods with the most places '
                     f'(NYC Department of City Planning\'s 2020 neighborhood areas). Each opens the web search.</p><ul class="towns">{hp}</ul></section>')
    # a city's busiest streets for eating out: its own, so no two city pages read alike
    streets = [] if borough else top_streets(here_all, c)
    if len(streets) >= 4:   # a sentence, not search links: the search reads street words its own way
        parts.append(f'<section id="streets"><h2>{e(c)} by street</h2><p>The streets in {e(cin)} with the most places to eat and drink: '
                     + and_list(f"{e(st)} ({k:,})" for st, k in streets) + ".</p></section>")
    else:
        streets = []
    if cuis:
        pills = "".join(f'<li><a href="{e(explore_url(g="all", r=sl, town=c, kind=k))}">{e(k)} ({v:,})</a></li>' for k, v in cuis)
        parts.append(f'<section id="cuisines"><h2>What {e(cin)} eats</h2><p class="sub">Tap a kind of food to search {e(cin)}\'s {n_c:,} '
                     f'places for it.</p><ul class="towns">{pills}</ul></section>')
    parts.append(f'<section id="more"><h2>More cities</h2>{city_links([x for x in CITY_PAGES if x != c])}'
                 f'<p class="fine">Or see the <a href="/{REGION_PAGE[r]}">{e(r)}{"" if r.endswith(" Region") else " region"}</a>.</p></section>\n  </main>')
    uniq = list({p.id: p for p in hc_here + icons_here + [p for _, p in near]}.values())
    written.append(page(path, title, desc, "\n".join(parts), [article_ld(url, h1, desc), bc,
                                                               item_list(f"Hand-checked and honored places in and near {c}", uniq, url)]))

# ---------------------------------------------------------------- web app data (docs/data/): an index, the guides, and per-region core + detail
DATA_OUT = f"{DOCS}/data"
if os.path.isdir(DATA_OUT):
    for fname in os.listdir(DATA_OUT):   # old region files from an earlier layout don't linger
        if fname.endswith(".json"):
            os.remove(f"{DATA_OUT}/{fname}")
os.makedirs(DATA_OUT, exist_ok=True)
# core: what the list, the search and the map need. Placard + its date travel together (an official placard always shows its date).
CORE_KEYS = ["n", "c", "co", "cu", "t", "s", "pl", "hd", "mu", "a", "z", "la", "lo", "b", "ch", "j", "v", "g", "hc", "k", "h", "mi",
             "ip", "f", "seas", "br", "dish", "ap", "ad", "phl", "gs"]
LOOKUPS = {"c": "cities", "pl": "mailing", "hd": "hoods", "mu": "munis", "cu": "cuisines", "b": "brands", "ap": "placards"}


def core_value(p, k):
    r = p.r
    if k == "c":
        return p.city
    if k == "pl":
        return p.mailing
    if k == "hd":
        return p.hood
    if k == "mu":
        return p.muni
    if k == "cu":
        return p.cuisine
    if k == "b":
        return p.brand
    if k == "ap":
        return (p.ac or {}).get("p")
    if k == "ad":   # days since 2000-01-01 (the reader turns it back into a date)
        d = (p.ac or {}).get("d")
        return (datetime.date.fromisoformat(d) - EPOCH).days if d else None
    if k == "phl":
        return 1 if p.phl else None
    if k == "gs":
        return 1 if p.gs else None
    if k == "hc":   # 1: checked open (P.hc); 2: an honor without a current open-check (only ever shown as a fact)
        return 1 if p.hc else (2 if (p.ip is not None or p.mi or p.h) else None)
    if k == "dish":
        return p.dish or None
    if k == "a":
        return p.addr or None
    if k in ("la", "lo"):   # in 1e-5 degrees, less the file's own minimum (la0, lo0)
        return round(r[k] * 1e5) if r.get(k) is not None else None
    return r.get(k)


EPOCH = datetime.date(2000, 1, 1)


def columnar(ps, extra=None):
    """Columns plus this file's own lookup tables (strings stored once), so each file stands alone."""
    tables = {name: [] for name in LOOKUPS.values()}
    index = {name: {} for name in LOOKUPS.values()}
    cols = {k: [] for k in CORE_KEYS + list(extra or {})}
    for p in ps:
        for k in CORE_KEYS:
            v = core_value(p, k)
            if k in LOOKUPS and v is not None:
                t = LOOKUPS[k]
                if v not in index[t]:
                    index[t][v] = len(tables[t])
                    tables[t].append(v)
                v = index[t][v]
            cols[k].append(v)
        for k, fn in (extra or {}).items():
            cols[k].append(fn(p))
    base = {}
    for k in ("la", "lo"):
        lo_ = min(v for v in cols[k] if v is not None)
        base[k + "0"] = lo_
        cols[k] = [None if v is None else v - lo_ for v in cols[k]]
    # columns with nothing in them are left out (the reader treats a missing column as all null); mostly empty ones are sparse:
    # {"i": [row gaps], "v": [values]}
    out = {}
    for k, v in cols.items():
        rows = [i for i, x in enumerate(v) if x is not None]
        if not rows:
            continue
        if len(rows) < 0.25 * len(v):
            out[k] = {"i": [b - a for a, b in zip([0] + rows[:-1], rows)], "v": [v[i] for i in rows]}
        else:
            out[k] = v
    return {**tables, **base, "count": len(ps), "cols": out}


def detail_of(p):
    d = {}
    for k in ("note", "jbf", "chef", "sea", "fn", "src"):
        v = p.r.get(k)
        if v:
            d[k] = v
    if p.jbf:
        d["jbf"] = p.jbf
    if p.phone:
        d["ph"] = p.phone
    if p.site:
        d["w"] = p.site
    if p.r.get("lq"):
        d["lq"] = IX["liqt"][p.r["lq"]]
    if p.r.get("src") and not urllib.parse.urlsplit(p.r["src"]).scheme in ("http", "https"):
        d.pop("src", None)
    if d.get("src") and not unblocked(d["src"]):   # our research's source on a blocklisted site goes too
        d.pop("src")
    return d or None


sizes = {}
by_reg = defaultdict(list)
for p in PLACES:
    by_reg[p.region].append(p)
for r in REGIONS:
    sl = REGION_SLUG[r]
    ps = by_reg[r]
    core = {"region": r, "slug": sl, **columnar(ps)}
    detail = {"ids": [p.id for p in ps], "d": [detail_of(p) for p in ps]}   # ids here, not in core: they're 1/4 of it
    for name, obj in ((f"core-{sl}.json", core), (f"detail-{sl}.json", detail)):
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        assert not private_words(raw), f"a private address in {name}"
        assert "google" not in raw.lower(), name
        open(f"{DATA_OUT}/{name}", "w", encoding="utf-8").write(raw)
        sizes[name] = (len(raw.encode()), len(gzip.compress(raw.encode(), 9)))
# the guides' places statewide (hand-checked and honored), so every guide opens at once whatever region is loaded; each row knows its
# region and its row in that region's files (for the detail and to merge when the region loads)
GUIDE_PLACES = sorted([p for p in PLACES if p.hc or p.ip is not None], key=lambda p: (p.ri, p.row))
row_in_region = {}
for r in REGIONS:
    for i, p in enumerate(by_reg[r]):
        row_in_region[p.id] = i
guides = {"generated": DATA_DATE, **columnar(GUIDE_PLACES, {"id": lambda p: p.id, "ri": lambda p: p.ri, "rr": lambda p: row_in_region[p.id]})}
raw = json.dumps(guides, separators=(",", ":"), ensure_ascii=False)
open(f"{DATA_OUT}/guides.json", "w", encoding="utf-8").write(raw)
sizes["guides.json"] = (len(raw.encode()), len(gzip.compress(raw.encode(), 9)))
# every city name with its region, so a search for "erie" from Philadelphia can switch to the Northwest
town_region = defaultdict(Counter)
for p in REST:
    if p.city:
        town_region[p.city][p.ri] += 1
web_index = {"generated": DATA_DATE, "overture": IX["overture_release"], "records_through": RT, "regions": REGIONS, "slugs": SLUGS,
             "counties": COUNTIES, "county_region": IX["county_region"], "tags": IX["tags"], "kinds": IX["kinds"], "srcs": IX["srcs"],
             "calibration": IX.get("calibration", {}), "has_achd": HAS_ACHD, "count_restaurants": N_REST,
             "files": [{"region": r, "slug": REGION_SLUG[r], "count": len(by_reg[r]), "restaurants": REGION_COUNT[r],
                        "core": f"core-{REGION_SLUG[r]}.json", "detail": f"detail-{REGION_SLUG[r]}.json"} for r in REGIONS],
             "towns": [[t, c.most_common(1)[0][0], sum(c.values())] for t, c in sorted(town_region.items(), key=lambda x: -sum(x[1].values()))]}
raw = json.dumps(web_index, separators=(",", ":"), ensure_ascii=False)
open(f"{DATA_OUT}/index.json", "w", encoding="utf-8").write(raw)
sizes["index.json"] = (len(raw.encode()), len(gzip.compress(raw.encode(), 9)))
json.dump(SHAPES, open(f"{DATA_OUT}/pa_shapes.json", "w"), separators=(",", ":"))
sizes["pa_shapes.json"] = (os.path.getsize(f"{DATA_OUT}/pa_shapes.json"), len(gzip.compress(open(f"{DATA_OUT}/pa_shapes.json", "rb").read(), 9)))

EXPLORE_CSS = """
  [hidden] { display: none !important; }
  .ex-hero { padding: 28px 0 8px; }
  .ex-hero h1 { font-size: clamp(30px, 6vw, 44px); }
  .ex-controls { background: var(--bg); padding: 10px 0 8px; border-bottom: 1px solid var(--rule); }
  .ex-guides { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; scrollbar-width: none; }
  .ex-guides.more { -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 44px), transparent); mask-image: linear-gradient(90deg, #000 calc(100% - 44px), transparent); }
  @media (min-width: 601px) { .ex-guides { flex-wrap: wrap; overflow-x: visible; } }
  .ex-guides button, .ex-view button, .ex-small { flex: 0 0 auto; border: 1px solid var(--rule2); background: var(--surface); color: var(--blue); border-radius: 999px; padding: 7px 12px; font-family: inherit; font-size: 14px; font-weight: 600; line-height: 1.2; cursor: pointer; }
  #ex-app :disabled { opacity: .55; cursor: default; }
  .ex-guides button[aria-pressed="true"], .ex-view button[aria-pressed="true"] { background: var(--blue); color: #fff; border-color: var(--blue); }
  .ex-row1 { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .ex-row1 input[type=search] { flex: 1 1 200px; min-width: 0; font-family: inherit; font-size: 16px; line-height: 1.3; padding: 10px 12px; border: 2px solid var(--blue); border-radius: 12px; background: var(--surface); color: var(--ink); }
  .ex-row2 { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px; font-size: 14px; color: var(--ink2); }
  .ex-row2 label { display: inline-flex; align-items: center; gap: 6px; }
  .ex-row2 select { font-family: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid var(--rule2); border-radius: 8px; background: var(--surface); color: var(--ink); width: 11.5em; max-width: 46vw; }
  .ex-row2 #ex-region { font-weight: 700; color: var(--blue); border: 2px solid var(--blue); width: 13em; }
  .ex-row2 #ex-sort { width: 9.5em; }
  .ex-view { margin-left: auto; display: flex; gap: 4px; }
  #ex-count { margin: 8px 0 0; font-size: 14px; color: var(--muted); min-height: 1.55em; }
  #ex-sub { margin: 4px 0 0; font-size: 14px; color: var(--ink2); min-height: 1.55em; }
  #ex-listwrap { min-height: 70vh; }
  #ex-locmsg { font-size: 13px; color: var(--muted); margin: 4px 0 0; min-height: 1.2em; }
  .ex-list { list-style: none; padding: 0; margin: 10px 0; }
  .ex-list li + li { border-top: 1px solid var(--rule); }
  .ex-row { width: 100%; display: flex; gap: 12px; align-items: center; text-align: left; background: none; border: 0; padding: 12px 4px; cursor: pointer; color: var(--ink); font: inherit; }
  .ex-row:hover { background: var(--surface2); }
  .ex-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; overflow-wrap: anywhere; }
  .ex-main b { font-weight: 650; }
  .ex-town { font-size: 14px; color: var(--muted); }
  .ex-gline { font-size: 13px; color: var(--ink2); display: flex; align-items: center; gap: 6px; }
  .ex-gline .pl { font-size: 11px; padding: 1px 6px; }
  .ex-metric { text-align: right; display: flex; flex-direction: column; }
  .ex-metric b { font: 800 22px/1 var(--display); color: var(--blue); }
  .ex-metric small { font-size: 11px; color: var(--muted); }
  .ex-rank { flex: 0 0 34px; height: 34px; display: grid; place-items: center; font: 800 20px var(--display); color: var(--blue); border-radius: 8px; }
  .ex-rank.top { background: var(--gold); color: var(--blue); }
  .ex-empty { padding: 24px 4px; color: var(--muted); }
  .ex-empty button { margin-top: 10px; }
  .ex-wider { padding: 12px 4px 4px; }
  .ex-wide { text-align: left; border-radius: 12px; }
  .ex-wide span { white-space: nowrap; }
  #ex-more { display: block; margin: 8px auto 24px; }
  #ex-mapwrap { position: relative; height: min(68vh, 560px, calc(60vw + 60px)); margin: 10px 0 20px; border: 1px solid var(--rule); border-radius: 16px; overflow: hidden; background: #eef2ec; }
  #ex-map { width: 100%; height: 100%; display: block; touch-action: none; cursor: grab; }
  .ex-zoom { position: absolute; right: 10px; top: 10px; display: flex; flex-direction: column; gap: 6px; }
  .ex-zoom button { width: 44px; height: 44px; border-radius: 10px; border: 1px solid var(--rule2); background: var(--surface); color: var(--blue); font-family: inherit; font-size: 20px; font-weight: 700; line-height: 1; cursor: pointer; }
  #ex-maphint { position: absolute; left: 10px; bottom: 8px; margin: 0; font-size: 13px; background: var(--surface); padding: 3px 8px; border-radius: 999px; color: var(--ink2); }
  .ex-chooser { position: absolute; z-index: 5; width: min(280px, calc(100% - 20px)); max-height: 60%; overflow-y: auto; background: var(--surface); border: 1px solid var(--rule2); border-radius: 12px; box-shadow: 0 6px 20px rgba(46,78,63,.18); padding: 6px 8px; }
  .ex-chooser p { margin: 4px 6px 6px; font-size: 13px; color: var(--muted); }
  .ex-chooser ul { list-style: none; margin: 0; padding: 0; }
  .ex-chooser button { display: block; width: 100%; min-height: 44px; text-align: left; background: none; border: 0; border-top: 1px solid var(--rule); padding: 8px 6px; font: inherit; font-size: 15px; color: var(--ink); cursor: pointer; }
  .ex-chooser button:hover { background: var(--surface2); }
  .ex-panel { position: fixed; z-index: 20; right: 0; top: 0; bottom: 0; width: clamp(320px, 40vw, 440px); overflow-y: auto; background: var(--surface); border-left: 1px solid var(--rule); box-shadow: -8px 0 24px rgba(46,78,63,.14); padding: 18px 20px 40px; overflow-wrap: anywhere; }
  @media (max-width: 600px) { .ex-panel { width: 100%; top: auto; height: 86vh; border-left: 0; border-top: 5px solid var(--gold); border-radius: 18px 18px 0 0; } }
  @media (min-width: 601px) { body.ex-open .wrap { margin-left: auto; margin-right: calc(clamp(320px, 40vw, 440px) + 12px); } }
  .ex-close { position: sticky; top: 0; float: right; width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--rule2); background: var(--surface); font-size: 24px; line-height: 1; cursor: pointer; color: var(--ink); }
  .ex-kicker { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .1em; color: var(--blue2); }
  .ex-panel h2 { font-size: 34px; margin: 4px 0 6px; text-transform: uppercase; }
  .ex-addr, .ex-dist { margin: 0 0 4px; color: var(--ink2); font-size: 15px; }
  .ex-actions { margin: 14px 0 8px; display: grid; gap: 8px; }
  .ex-apple { justify-content: center; background: var(--blue); color: #fff; }
  .ex-act-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .ex-act-row a, .ex-act-row button { flex: 1 1 auto; min-width: 0; min-height: 44px; white-space: nowrap; text-align: center; padding: 10px 12px; border: 1px solid var(--rule2); border-radius: 12px; text-decoration: none; color: var(--blue); font-family: inherit; font-size: 15px; font-weight: 600; background: var(--surface); cursor: pointer; }
  .ex-act-row button[aria-pressed="true"] { background: var(--goldsoft); color: var(--ongoldsoft); }
  .ex-sec { margin-top: 18px; padding: 0; border-top: 0; }
  .ex-sec h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink2); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 8px; }
  .ex-sec p, .ex-sec li { font-size: 15px; color: var(--ink2); margin: 6px 0; }
  .ex-kv { display: flex; justify-content: space-between; gap: 12px; font-size: 15px; padding: 3px 0; }
  .ex-kv span { color: var(--ink2); }
  .ex-kv b { text-align: right; }
  .ex-fine { font-size: 13px !important; color: var(--muted) !important; }
  .ex-grade { display: flex; align-items: center; gap: 12px; }
  .ex-grade .pl { font-size: 15px; padding: 6px 12px; }
  .ex-grade b { display: block; color: var(--ink); font-size: 17px; }
  .ex-app { margin-top: 22px; font-size: 14px; color: var(--muted); }
  .ex-short { display: none; }
  body.ex-open { overflow: hidden; }
  @media (min-width: 601px) { body.ex-open { overflow: auto; } }
  @media (max-width: 600px) {
    .ex-long { display: none; }
    .ex-short { display: inline; }
    #ex-sub { min-height: 3.1em; }
    .ex-guides button, .ex-view button, .ex-small, .ex-row2 select { min-height: 44px; }
    .ex-row2 select { font-size: 16px; }   /* iOS Safari zooms the page into a form field under 16px */
    .ex-row2 #ex-town, .ex-row2 #ex-cuisine { max-width: calc(50% - 4px); }   /* still two to a row */
    .ex-row2 #ex-region { max-width: 100%; }   /* on a row of its own: "Northeast & Poconos" in full */
    .ex-row2 label { min-height: 44px; }
    .ex-row2 input[type=checkbox] { width: 20px; height: 20px; margin: 0; }
  }
  /* the search field has a row of its own on every phone, so its placeholder is never cut off (it was "…street, or dis" at 375px
     and lost half its words beside "Use my location" at 414px); scripts/qa-site.py measures it */
  @media (max-width: 600px) { .ex-row1 input[type=search] { flex-basis: 100%; } }
"""
url = f"{DOMAIN}/explore/"
title = fit(["Pennsylvania Restaurant Search & Map | Pennsylvania Eats", "Pennsylvania Restaurant Search: Cheesesteaks to Pierogies"], 50, 60)
desc = fit_combo([f"Look up any of {N_REST:,} Pennsylvania restaurants by name, street or town, with {len(CLASSIC)} hand-checked classics and each county's inspection records",
                  f"Look up {N_REST:,} Pennsylvania restaurants by name, street or town, with {len(CLASSIC)} hand-checked classics on a map"],
                 [".", ", on a map.", ". Free."], 140, 160)
nav, bc = crumbs([("Home", "/"), ("Search", "/explore/")])
EX_GUIDES = ([(k, {"steak": "Cheesesteaks", "pie": "Tomato pie", "pierogi": "Pierogies", "dutch": "PA Dutch", "pretzel": "Pretzels",
                     "diner": "Diners"}[k]) for k, *_ in GUIDES]
             + [("icons", "Icons")] + ([("oldest", "Oldest")] if HAS_OLDEST else []) + [("near", "Near me"), ("all", "All restaurants"), ("saved", "Saved")])
guide_buttons = "".join(f'<button type="button" data-g="{k}" aria-pressed="false" disabled>{e(t)}</button>' for k, t in EX_GUIDES)
region_opts = ('<option value="all">All of Pennsylvania</option>'
               + "".join(f'<option value="{REGION_SLUG[r]}"{" selected" if r == "Philadelphia" else ""}>{e(r)}</option>' for r in REGIONS))
sort_opts = "".join(f"<option>{s}</option>" for s in ("Featured first", "Nearest", "Oldest first", "A to Z"))
body = f"""{nav}
  <main id="main">
  <section class="ex-hero">
    <p class="kicker">{BRAND} · on the web</p>
    <h1>Search Pennsylvania restaurants</h1>
    <p class="sub"><span class="ex-long">From Philadelphia to Pittsburgh and Erie: {N_REST:,} restaurants, cafés, bars and bakeries in {N_CITIES:,} cities and towns. The {len(CLASSIC)} hand-checked classics load first; pick a region for everything else. Each place links to its county's inspection records. It's the app's own data, and what you save stays in this browser.</span><span class="ex-short">{N_REST:,} places, one region at a time; the hand-checked lists load first.</span></p>
  </section>
  <noscript><p>The search needs JavaScript. The guides work without it: {", ".join(f'<a href="/{pg}">{e(n)}</a>' for _, pg, n, *_ in GUIDES)}.</p></noscript>
  <div id="ex-app" aria-busy="true">
    <div class="ex-controls">
      <div class="ex-guides" role="group" aria-label="Guides">{guide_buttons}</div>
      <div class="ex-row1">
        <label class="skip" for="ex-q">Search</label>
        <input id="ex-q" type="search" placeholder="Name, town, street or dish" autocomplete="off" enterkeyhint="search" disabled>
        <button type="button" id="ex-locate" class="ex-small" disabled>Use my location</button>
      </div>
      <div class="ex-row2">
        <select id="ex-region" aria-label="Region" disabled>{region_opts}</select>
        <label>Sort <select id="ex-sort" aria-label="Sort" disabled>{sort_opts}</select></label>
        <select id="ex-town" aria-label="City or town" disabled><option value="">All towns</option></select>
        <select id="ex-cuisine" aria-label="Kind of place" disabled><option value="">All kinds</option></select>
        <label><input type="checkbox" id="ex-chains" disabled> Hide chains</label>
        <label><input type="checkbox" id="ex-conf" disabled> High-confidence only</label>
        <label id="ex-bibwrap" hidden><input type="checkbox" id="ex-bib" disabled> <span>Bib Gourmand <span id="ex-bibn"></span></span></label>
        <button type="button" id="ex-clear" class="ex-small" hidden>Clear filters</button>
        <div class="ex-view" role="group" aria-label="View"><button type="button" data-v="list" aria-pressed="true" disabled>List</button><button type="button" data-v="map" aria-pressed="false" disabled>Map</button></div>
      </div>
      <p id="ex-sub"></p>
      <p id="ex-count" aria-live="polite"></p>
      <p id="ex-locmsg"></p>
    </div>
    <div id="ex-listwrap"><ol id="ex-list" class="ex-list"><li class="ex-empty" id="ex-loading">Loading the restaurant list…</li></ol><button type="button" id="ex-more" class="ex-small" hidden></button></div>
    <div id="ex-mapwrap" hidden>
      <canvas id="ex-map" role="img" aria-label="Map of Pennsylvania's 67 counties with a dot for each place in the list. The list view has the same places."></canvas>
      <div class="ex-zoom"><button type="button" id="ex-zin" aria-label="Zoom in">+</button><button type="button" id="ex-zout" aria-label="Zoom out">−</button></div>
      <div id="ex-chooser" class="ex-chooser" role="dialog" aria-labelledby="ex-chooser-h" hidden></div>
      <p id="ex-maphint"></p>
    </div>
    <p class="fine">High-confidence only keeps places on an official list (a Philadelphia food license{", an Allegheny County permit" if HAS_ACHD else ""}), high-confidence map listings and places we checked by hand. Convenience-store counters, members-only clubs and other non-restaurants are left out. There is no statewide grade, and this site doesn't make one. County outlines: U.S. Census Bureau. See also <a href="/{ICONS_PAGE[0]}">Pennsylvania icons</a>.</p>
  </div>
  <div id="ex-panel" class="ex-panel" role="complementary" aria-labelledby="ex-pname" hidden></div>
  </main>
<script>
// read by explore.js for the place panel's app link (set APP_STORE_URL in scripts/make-site.py)
window.APP_STORE_URL = {json.dumps(APP_STORE_URL)};
{open(f"{ROOT}/scripts/explore.js").read()}
</script>"""
webapp_ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{BRAND} web app", "url": url,
             "applicationCategory": "TravelApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
             "description": desc, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": {"@id": f"{DOMAIN}/#org"}}
explore_head = ('<link rel="preload" href="/data/index.json" as="fetch" crossorigin>\n'
                '<link rel="preload" href="/data/guides.json" as="fetch" crossorigin>\n'
                '<noscript><style>#ex-app { display: none; }</style></noscript>\n')
written.append(page("explore/index.html", title, desc, body, [webapp_ld, bc], extra_css=EXPLORE_CSS, head_extra=explore_head))

# ---------------------------------------------------------------- landing page
faq = [
    ("How do restaurant inspections work in Pennsylvania?", "There is no statewide restaurant grade. The Pennsylvania Department of Agriculture and about 100 local health departments inspect, and post results one search at a time; Philadelphia, Allegheny, Bucks and Montgomery counties keep their own. Allegheny County's Health Department posts a placard after each inspection: green, yellow \"Consumer Alert\" or red for a closure. " + ("The app shows that placard, labeled official, with its date. " if HAS_ACHD else "") + "For every other place, the app links the agency's own search; we never compute a grade. In the Department of Agriculture's words: \"" + PDA_DISCLOSURE + "\""),
    ("What's the difference between a cheesesteak, roast pork and a hoagie?", "A cheesesteak is griddled, thin-sliced beef with cheese on a long roll; roast pork is thin-sliced pork, usually with sharp provolone and greens; a hoagie is the cold sandwich of Italian meats and provolone on a seeded roll. All three are on the hand-checked Cheesesteaks list."),
    ("Where do the lists come from?", f"From our own research in {CHECKED}: every place on the cheesesteak, tomato pie, Pennsylvania Dutch and other lists has a dated 2025 or 2026 source, such as a newspaper or tourism guide, or its own website. The rest of the {N_REST:,} restaurants come from Overture Maps' open place data and the City of Philadelphia's food licenses."),
    ("What about MICHELIN stars and James Beard awards?", "They're in, as facts: \"1 MICHELIN Star\", \"Bib Gourmand\" or \"Green Star\" from the MICHELIN Guide's first Philadelphia selection (November 2025), and James Beard awards and America's Classics from 2025 and 2026, as the foundation named them. They're never shown as a row of stars."),
    ("Why are there no star ratings?", "No list here is ordered by ratings, and the app keeps none, ours or anyone else's. The \"Ratings, hours & photos\" button on a place opens Apple Maps' live card, and whatever that card shows is Apple's."),
    ("Does the app track where I am?", "No. If you allow location, it's used on your iPhone or iPad (or, on this site, in your browser) to put the nearest places first, and it's never sent to us. Say no and everything but Near me still works."),
    ("Spotted a closed shop or a missing pierogi kitchen?", f"Write to {EMAIL} with the place's name and its town. Fixes ship with the next data update."),
    ("Does it cost anything, and is there an Android version?", f"It costs nothing: no price, no subscription, no ads and no account. The app is for iPhone and iPad for now; on Android, the web search on this site has the same places and lists."),
]
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_entity = {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": BRAND,
              "alternateName": [SHORT, f"{BRAND}: Restaurants", f"{BRAND}: {TAGLINE}"],
              "description": f"A free guide to {N_REST:,} Pennsylvania restaurants, with hand-checked lists: " + and_list(f"{guide_stats[k]} {lc(short)} places" for k, _, short, *_ in GUIDES) + ". Sort by distance, open Apple Maps' live place card for hours and photos, and save places for later.",
              "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication",
              "applicationSubCategory": "Food & Drink", "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"},
              "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}}
app_ld = {"@context": "https://schema.org", "@graph": [
    app_entity,
    {"@type": "WebSite", "@id": f"{DOMAIN}/#website", "name": BRAND, "alternateName": [SHORT, f"{BRAND} app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"}}]}
title = fit([f"{BRAND}: Cheesesteaks to Pierogies Restaurant App", f"{BRAND}: Cheesesteak & Restaurant Guide App"], 50, 60)
desc = fit_combo([f"{len(CLASSIC)} hand-checked cheesesteak, roast pork, hoagie, tomato pie and PA Dutch stops, and {N_REST:,} Pennsylvania restaurants in one free iPhone app",
                  f"{len(CLASSIC)} hand-checked cheesesteak, tomato pie and Pennsylvania Dutch stops and {N_REST:,} Pennsylvania restaurants in one free app"],
                 [".", ". No ads, no ratings.", ""], 140, 160)
guide_cards = "".join(f'<a class="card classic" href="/{pg}"><div class="card-top">{glyph_svg(k)}<b class="count">{guide_stats[k]}<small>hand-checked</small></b></div>'
                      f'<h3>{e(short)}</h3><p>{e(sub.replace(", hand-checked", ""))}.</p>{glyph_svg(k, 104, "wm")}</a>'
                      for k, pg, short, _, _, sub in GUIDES)
region_rows = "".join(f'<tr><td><a href="/{REGION_PAGE[r]}">{e(r)}</a></td><td class="n">{REGION_COUNT[r]:,}</td>'
                      f'<td class="n">{region_stats[r]["hand_checked"]}</td></tr>' for r in REGIONS)
body = f"""  <main id="main">
  <section class="hero masthead">
    <div class="mast-top"><p class="kicker">{BRAND}: {TAGLINE.lower()}, for iPhone and iPad</p>{state_svg("mast-state", 100, main="#FFFFFF")}</div>
    <h1>{N_REST:,} Pennsylvania restaurants, from a South Philly cheesesteak to a Lancaster smorgasbord</h1>
    <p class="lede">Philadelphia to Pittsburgh and Erie: {BRAND} puts {N_REST:,} restaurants, cafés, bars and bakeries in one free app. The short lists are ours, checked by hand: steak shops and roast pork counters, tomato pie by the square and Old Forge trays, Pennsylvania Dutch dining rooms and the state's MICHELIN and James Beard honorees.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="/explore/">Search on the web</a><span class="pill">{store_note("No ads, no sign-up, no charge.")}</span></div>
    <ul class="stats" aria-label="What's in the app">
      <li><b>{len(CLASSIC)}</b><span>hand-checked classics</span></li>
      <li><b>{len(ICONS)}</b><span>MICHELIN and James Beard honorees</span></li>
      <li><b>{len(REGIONS)}</b><span>regions, Philadelphia to Erie</span></li>
      <li><b>{N_REST:,}</b><span>restaurants statewide</span></li>
    </ul>
  </section>

  <section id="what">
    <h2>Built on the orders Pennsylvanians drive for</h2>
    <p class="sub">A star count can't tell a roast pork from a hoagie, or Philadelphia tomato pie from an Old Forge white tray, so {BRAND} leaves stars out and starts from the order itself. Every place on those lists was {checked_open(CLASSIC)} against a dated 2025 or 2026 source. Hours and photos come from Apple Maps' live card for each place.</p>
  </section>

  <section id="how">
    <h2>From craving to counter</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Choose a list.</h3><p>{e(and_list([t for _, _, _, t, *_ in GUIDES]))} or Pennsylvania Icons, or look up any of {N_REST:,} restaurants by name, town or street.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>Narrow it down.</h3><p>Closest first, or by region, town or kind of food; the map shows the same places as dots.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Head out.</h3><p>Hours and photos are on Apple Maps' live card. Call the counter, get directions, or keep it for a Saturday drive down the Turnpike.</p></div></li>
    </ol>
  </section>

  <section id="guides">
    <h2>The Pennsylvania lists</h2>
    <p class="sub">Every list is on the web too, place by place, with each county's inspection records.</p>
    <div class="grid2">
      {guide_cards}
      <a class="card" href="/{ICONS_PAGE[0]}"><h3>Pennsylvania icons</h3><p>{len(ICONS)} places with a MICHELIN distinction or a James Beard honor.</p></a>
    </div>
  </section>

  <section id="regions">
    <h2>By region</h2>
    <p class="sub">Nine regions of the state, each with its classics, where its counties post inspections, and what it eats.</p>
    <table><thead><tr><th>Region</th><th class="n">Restaurants</th><th class="n">Hand-checked</th></tr></thead><tbody>{region_rows}</tbody></table>
  </section>

  <section id="cities">
    <h2>Cities</h2>
    <p class="sub">The state's biggest restaurant towns, with the classics in and near each.</p>
    {city_links()}
  </section>

  <section id="inspections">
    <h2>Health inspections: official ones only</h2>
    <p class="sub">Pennsylvania has no statewide restaurant grade, and we don't invent one. Each agency's records stay its own: {f"Allegheny County's placards with their dates ({N_AC:,} places), " if HAS_ACHD else ""}whether a Philadelphia place holds an active City food license ({N_PHL:,} places), and links to the inspection searches the Department of Agriculture, Bucks and Montgomery counties and Philadelphia keep. Nothing is ranked by any of it.</p>
  </section>

  <section id="pricing">
    <h2>What it costs: nothing</h2>
    <p class="sub">There's nothing to buy and nothing to sign up for, and there are no ads. The {N_REST:,} places ship inside the app, so a list opens on a back road with no signal.</p>
  </section>

  <section id="privacy">
    <h2>Where you eat stays with you</h2>
    <p class="sub">The app has no account and no analytics, and sends us nothing. Location, if you allow it, puts the nearest places first on your phone and goes nowhere else. Saved places live on your phone; on this website they live in your browser, which gets no cookies and no trackers. The <a href="/privacy.html">privacy policy</a> has the details.</p>
  </section>

  <section id="faq">
    <h2>Questions</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Find the next cheesesteak</h2>
    <p class="sub">{f"{BRAND} is free on the App Store for iPhone and iPad." if APP_STORE_URL else f"{BRAND} isn't in the App Store yet. It's free for iPhone and iPad, and you can ask to try it early."}</p>
    <div class="cta-row">{store_button()}</div>
  </section>
  </main>"""
written.append(page("index.html", title, desc, body, [app_ld, faq_ld]))

# ---------------------------------------------------------------- privacy, terms, support, 404
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {nice_date(PRIVACY_UPDATED)}.</p>
  </section>
  <section>
    <h2>The app</h2>
    <ul>
      <li><b>No account, no analytics, no ads.</b> The app has no sign-in, no advertising, and no analytics or crash-reporting code. We receive no data from it.</li>
      <li><b>Location.</b> If you allow it, your location is used on your device to sort places by distance and show where you are on the map. It is never sent to us. You can turn it off in Settings at any time.</li>
      <li><b>Saved places and filters</b> are stored only on your device and are deleted when you delete the app.</li>
      <li><b>Apple Maps.</b> When you open a place's hours and photos, or ask for directions, the app asks Apple Maps for that place. Apple handles that request under <a href="https://www.apple.com/legal/privacy/" rel="noopener">Apple's privacy policy</a>, as it does for any app that shows a map.</li>
      <li><b>Data updates.</b> When you open the app, it checks this website for newer restaurant data, at most once a day (or an hour later if a check didn't go through), and downloads it when there is some. These requests carry no location or identifiers. GitHub, which hosts this site, may keep standard server logs of them, as it does for any visit here.</li>
      <li><b>Spotlight.</b> The app may add its hand-checked places to your device's search index so you can find them from Spotlight. That index stays on your device.</li>
      <li><b>Calls, websites, and email</b> you start from a place open in the Phone app, your browser or Mail, and are handled by them.</li>
    </ul>
    <p>On the App Store, the app's privacy label {'is' if APP_STORE_URL else 'will be'} "Data Not Collected".</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts, maps, or scripts from anyone else. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <p>The <a href="/explore/">web search</a> keeps three things in your browser's local storage, on your device only: the places you save, the region each saved place is in (so the right file loads), and the last guide you opened. Clearing your browser's site data deletes them. If you tap "Use my location", open the "Near me" guide, or sort by "Nearest", your browser asks first, and your location is used in the page to sort by distance. It is never sent to us or anyone else.</p>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
written.append(page("privacy.html", "Pennsylvania Eats Privacy Policy: No Account, No Tracking",
                    fit(["The Pennsylvania Eats privacy policy: the app collects no data, keeps your location and saved places on your device, and this site sets no cookies."], 140, 160),
                    body, [bc]))

LIC_SRC = f"{ROOT}/PennsylvaniaEats/Resources/Licenses"
notice_lines = [l for l in open(f"{LIC_SRC}/Foursquare-NOTICE.txt").read().split("\n") if l.strip()]
notice_body = [l for l in notice_lines if not l.startswith("Notice of changes")]   # the bundled copy's own line may name another app; ours is below
notice_html = "".join(f"<p>{e(l)}</p>" for l in notice_body) + (
    f"<p>Notice of changes: {BRAND} filtered the Data to eating and drinking places in Pennsylvania, removed duplicates and closed, "
    "adult, or unverifiable listings, and reformatted it for this app and website (2026).</p>")
for other in ("Connecticut", "Wisconsin", "Chicago", "New York"):
    assert other not in notice_html, other
os.makedirs(f"{DOCS}/licenses", exist_ok=True)
for name in ("Apache-2.0.txt", "CDLA-Permissive-2.0.txt"):
    shutil.copyfile(f"{LIC_SRC}/{name}", f"{DOCS}/licenses/{name}")
open(f"{DOCS}/licenses/Foursquare-NOTICE.txt", "w").write("\n".join(notice_body) + "\n\n" + re.sub(r"<[^>]+>", "", notice_html.split("<p>")[-1]) + "\n")
nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {nice_date(TERMS_UPDATED)}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in Pennsylvania. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, and change their hours and menus, and some close for the season. Dishes, seasons, and years at an address are what each place or a named source said when we checked in {CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Health inspections</h2>
    <p>{BRAND} doesn't grade restaurants, and Pennsylvania has no statewide grade. {"In Allegheny County, the app and this site show the Health Department's own placard with the date of that inspection, as the department published it. " if HAS_ACHD else ""}In Philadelphia, they show whether an active City food license was matched; that says the place is licensed, not how an inspection went. Everywhere else they link the agencies' own inspection searches. The Pennsylvania Department of Agriculture: “{PDA_DISCLOSURE}” For the official record, see each agency's own site.</p>
    <h2>Other people's content</h2>
    <p>Hours, photos and other details in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. {MICHELIN_TM} {JBF_TM} Honors are reported as facts. {BRAND} is not affiliated with, endorsed by, or operated by the Commonwealth of Pennsylvania, its Department of Agriculture or Liquor Control Board, the City of Philadelphia or its Department of Public Health or Department of Licenses and Inspections, Allegheny, Bucks or Montgomery County or their health departments, the Western Pennsylvania Regional Data Center, Michelin, the James Beard Foundation, Apple, or any restaurant, team or chain.</p>
    <h2 id="sources">Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data (overturemaps.org), release {e(IX.get("overture_release", ""))}, filtered and reformatted for {BRAND}. Data from Meta, Microsoft, DAC, and BrightQuery under the Community Data License Agreement, Permissive 2.0 (<a href="/licenses/CDLA-Permissive-2.0.txt">CDLA Permissive 2.0 text</a>); data from Foursquare under the Apache License 2.0 (<a href="/licenses/Apache-2.0.txt">Apache 2.0 text</a>; <a href="/licenses/Foursquare-NOTICE.txt">NOTICE</a>, also below); data from AllThePlaces under CC0 1.0. The same licenses cover the web search's data files.</li>
      <li>City of Philadelphia, Licenses and Inspections Business Licenses (<a href="https://opendataphilly.org/datasets/licenses-and-inspections-business-licenses/" rel="noopener">OpenDataPhilly</a>, City of Philadelphia License), issued through {nice_date(RT["philly"])}: food licenses, used for the trade name, address and whether a license is active. Legal and owner names are never shown. {PHILLY_DISCLAIMER}</li>
      {f'<li>Allegheny County Health Department, Restaurant/Food Facility Inspections (<a href="https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations" rel="noopener">Western Pennsylvania Regional Data Center</a>, CC0), records through {nice_date(RT["achd"])}: the placard after the latest inspection and its date.</li>' if HAS_ACHD else ""}
      <li>Pennsylvania Department of Agriculture, <a href="{PDA_SEARCH}" rel="noopener">PA Food Safety Inspection Search</a>, and the inspection searches of Philadelphia, Bucks and Montgomery counties: linked, never copied.</li>
      <li>U.S. Census Bureau cartographic boundary files, 2025 (public domain): Pennsylvania's 67 counties and its municipalities, used to place each restaurant and to draw the web map.</li>
      <li>MICHELIN Guide's Philadelphia selection (November 2025) and James Beard Foundation awards and America's Classics (2025 and 2026), checked against public announcements and reported as facts.</li>
      <li>Cheesesteaks, roast pork, hoagies, tomato pie, Old Forge pizza, pierogies, Pennsylvania Dutch dining rooms, soft pretzels and diners: our own research, with a dated source recorded for every place.</li>
      <li>Maps, place cards, and directions in the app: Apple Maps.</li>
    </ul>
    <h2>Foursquare NOTICE</h2>
    <blockquote>{notice_html}</blockquote>
    <h2>Corrections</h2>
    <p>If a listing is wrong, or you own a restaurant and want something fixed, email <a href="mailto:{EMAIL}">{EMAIL}</a>. We fix mistakes in the next update.</p>
    <h2>Liability</h2>
    <p>To the extent the law allows, we are not liable for any loss arising from use of the app or site, including a wasted trip to a closed steak shop. Pennsylvania law governs these terms.</p>
    <h2>Changes</h2>
    <p>We may update these terms; the current version and its date are always on this page. See also the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
written.append(page("terms.html", "Pennsylvania Eats Terms of Use, Data Sources and Corrections",
                    fit(["The Pennsylvania Eats terms of use: a free Pennsylvania restaurant guide, provided as is. Check before you go, and see where each listing comes from."], 140, 160),
                    body, [bc]))

nav, bc = crumbs([("Home", "/"), ("Support", "/support.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Support</h1>
    <p class="lede">Help with the {BRAND} app and this website. Email <a href="mailto:{EMAIL}">{EMAIL}</a>; a person reads every message.</p>
  </section>
  <section>
    <h2>Report a closed, missing or wrong place</h2>
    <p>Send the place's name and town (and what's wrong) to <a href="mailto:{EMAIL}?subject=Pennsylvania%20Eats%20correction">{EMAIL}</a>. Corrections go into the next update of the app and this site. Restaurant owners can ask for a fix the same way.</p>
    <h2>Common questions</h2>
    <ul>
      <li><b>Why isn't my favorite steak shop on the Cheesesteaks list?</b> The guides list only places we checked by hand against a 2025 or 2026 source. The rest of the {N_REST:,} restaurants are in the directory and the <a href="/explore/">web search</a>. Tell us about a place and we'll check it.</li>
      <li><b>Where do inspection results come from?</b> Pennsylvania has no statewide grade. {"In Allegheny County the app shows the Health Department's own placard with its date; " if HAS_ACHD else ""}in Philadelphia, whether a City food license is active; everywhere else, a link to the agency's own inspection search.</li>
      <li><b>Lists don't sort by distance.</b> Allow location for {BRAND} in Settings › Privacy &amp; Security › Location Services, or in your browser for this site. Your location stays on your device.</li>
      <li><b>How do I delete my saved places?</b> In the app, tap Save again on a place, or delete the app. On the web, clear this site's data in your browser.</li>
      <li><b>Does the app work offline?</b> Yes. The whole guide is built into the app; only Apple Maps' live place cards and directions need a connection.</li>
    </ul>
    <h2>About the data</h2>
    <p>Where every listing comes from is on the <a href="/terms.html#sources">terms page</a>. Data as of {nice_date(DATA_DATE)}; Philadelphia licenses issued through {nice_date(RT["philly"])}.</p>
    <h2>Privacy</h2>
    <p>The app collects nothing. See the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
written.append(page("support.html", "Pennsylvania Eats Help: Corrections, Inspections, Location",
                    fit(["Help with the Pennsylvania Eats app: report a closed or missing restaurant, ask where inspection records come from, and reach a person by email."], 140, 160),
                    body, [bc]))

body = f"""  <main id="main">
  <section class="hero">
    <h1>Page not found</h1>
    <p class="lede">Nothing at this address, like a steak shop that moved down the block. Head back to the <a href="/">{BRAND} home page</a>, browse the <a href="{GUIDE_URL['steak']}">cheesesteaks</a> or the <a href="{GUIDE_URL['pie']}">tomato pie</a>, or look a place up in the <a href="/explore/">restaurant search</a>.</p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "This page doesn't exist.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
urls = ["" if w == "index.html" else w.replace("index.html", "") for w in written]
urls.sort(key=lambda u: (u != "", u.startswith("regions/"), u.startswith("cities/"), u))
open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": SHORT, "description": f"{TAGLINE}, plus {N_REST:,} Pennsylvania restaurants.", "start_url": f"{BASE}/",
           "display": "browser", "background_color": "#fbf8f2", "theme_color": "#2E4E3F",
           "icons": [{"src": f"{BASE}/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": f"{BASE}/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
if CUSTOM_DOMAIN:
    open(f"{DOCS}/CNAME", "w").write(CUSTOM_DOMAIN + "\n")
elif os.path.exists(f"{DOCS}/CNAME"):
    os.remove(f"{DOCS}/CNAME")
open(f"{DOCS}/.nojekyll", "w").write("")
# the share image (docs/og.png) prints the count in its tagline, so it's redrawn (og.png only, never the app icon) when it changes
OG_LINE = f"Cheesesteaks to pierogies: {N_REST:,} restaurants"
NUMBERS = f"{ROOT}/playbook/site-numbers.json"
og_line = json.load(open(NUMBERS)).get("og_line") if os.path.exists(NUMBERS) else None
if og_line != OG_LINE or not os.path.exists(f"{DOCS}/og.png"):
    try:
        subprocess.run(["swift", "scripts/make-brand.swift", "og", OG_LINE], cwd=ROOT, check=True, timeout=600)
        og_line = OG_LINE
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
        print(f"!! docs/og.png still shows the old counts ({ex}); run: swift scripts/make-brand.swift og \"{OG_LINE}\"")
json.dump({"generated": TODAY, "data_generated": DATA_DATE, "domain": DOMAIN, "og_line": og_line, "restaurants": N_REST, "cities": N_CITIES,
           "regions": len(REGIONS), "records_through": RT, "hand_checked_guides": len(CLASSIC), "checked_open": sum(1 for p in REST if p.hc), "honored_not_checked": sum(1 for p in REST if not p.hc and (p.ip is not None or p.mi or p.h)),
           **{f"guide_{k}": v for k, v in guide_stats.items()}, "icons": len(ICONS), "oldest_known_year": len(OLDEST),
           "michelin": len(MICHELIN), "james_beard": len(JBF), "achd_placards": N_AC, "philly_licensed": N_PHL, "has_achd": HAS_ACHD,
           "named_not_checked": NAMED, "guides_below_4": sorted(k for k, *_ in ALL_GUIDES if k not in G),
           "website_links_verified": WEB_CHECK is not None, "website_links_shown": sum(1 for p in PLACES if p.site),
           "website_blocklist": {"entries": len(BLOCKLIST), "links_dropped": dict(sorted(BLOCKED.items())),
                                 "matching_nothing": sorted(k for k in (b.get("url") if b.get("match") == "url" else b["domain"] for b in BLOCKLIST) if not BLOCKED[k])},
           "data_files": {k: {"bytes": v[0], "gzip": v[1]} for k, v in sizes.items()}, "regions_pages": region_stats, "city_pages": city_stats},
          open(NUMBERS, "w"), indent=1)
print("wrote", len(written) + 1, "pages:", ", ".join(w for w in written if not w.startswith(("regions/", "cities/"))) + ", 404.html",
      f"+ {sum(w.startswith('regions/') for w in written)} region pages + {sum(w.startswith('cities/') for w in written)} city pages")
print(f"restaurants {N_REST:,} in {N_CITIES:,} places | " + " | ".join(f"{k} {v}" for k, v in guide_stats.items())
      + f" | icons {len(ICONS)} | oldest {len(OLDEST)} | ACHD placards {N_AC:,} | Philadelphia licensed {N_PHL:,}")
print("data files (raw KB / gzip KB):", ", ".join(f"{k} {v[0] // 1024}/{v[1] // 1024}" for k, v in sizes.items()))
print(f"website blocklist ({len(BLOCKLIST)} entries, pipeline/website_blocklist.json): links dropped "
      + (", ".join(f"{k} x{n}" for k, n in sorted(BLOCKED.items())) or "none")
      + " | entries matching nothing: " + (", ".join(k for k in (b.get("url") if b.get("match") == "url" else b["domain"] for b in BLOCKLIST) if not BLOCKED[k]) or "none"))
if not BLOCKLIST:
    print("!! pipeline/website_blocklist.json is empty: scripts/qa-site.py fails until it lists the known bad sites")
if WEB_CHECK is None:
    print("!! no data/pa/website_check.json: only the hand-checked research's own website links are shown")
