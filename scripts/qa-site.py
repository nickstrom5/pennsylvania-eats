"""QA for the website in docs/: every sitemap page in headless Chrome at phone and desktop widths, served under the same path GitHub
Pages will use (/pennsylvania-eats/ until the custom domain is live).

Page checks: loads with 200, no horizontal scroll, no console errors, no Content-Security-Policy violations, no requests to any other
host, one <h1>, a 50-60 character title and 140-160 character description, valid JSON-LD with no ratings or reviews, no broken
internal links (including #anchors) or images.
Static checks (every page, 404 included): the CSP meta tag first in <head> with a hash per inline script; JSON-LD has no raw "<",
every list item points at its #p- anchor, no empty address, phones are +1 numbers, own sites are sameAs; no "google", no star
characters, no "James Beard finalist", the MICHELIN and James Beard trademark lines; the PA Department of Agriculture's disclosure
verbatim on every page that links its search, and the City of Philadelphia's disclaimer on every page that shows its licenses; every
Allegheny placard shown is the place's own with its own date, and none outside Allegheny County; each place's inspection line names
its own county's record; each guide page lists exactly the hand-checked places of its kinds; website links only where the link check
(or our research) vouches for them.
Web app checks (explore/): each classic guide lists exactly its hand-checked places; the region picker loads a region's file and
lists only that region; "Oyster House" finds it in Philadelphia and its panel shows the City's license section with the City's
disclaimer; an Allegheny place shows the ACHD section; a place in another county quotes PDA's disclosure and links its search; Save
survives a reload; a shared #p= link opens the place on a cold load; an emoji search lists nothing; Near me sorts by distance; a search
for a town in another region moves there; saved places stay under the pae- localStorage prefix (nickstrom5.github.io is shared by every
state's site).
Site-wide checks (check_site_seo), copy checks (check_copy_claims, check_copy_decisions) and the website blocklist (check_blocklist), as
New York's.

Usage: .venv/bin/python scripts/qa-site.py      (serves docs/ itself on a free localhost port; exits 1 on any problem)
  QA_DOCS=<dir>   check another copy of docs/ (used to confirm that each check can fail)
  QA_SHOTS=<dir>  also save a few screenshots there
  QA_PAGES=<n>    check only the first n sitemap pages in the browser (a quick run; the static checks still read every page)
  QA_WIDTHS=1280  only these viewport widths (default 375,1280)
  QA_PORT=<n>     serve on this localhost port (default: any free one)
  QA_BLOCKLIST=<file>  read another website blocklist (used to confirm that check_blocklist fails on a missing or empty one)
Ported from ny-eats/scripts/qa-site.py. Never drives anyone's own browser: headless Chrome only.
"""
import base64
import datetime
import functools
import hashlib
import html as H
import http.server
import json
import math
import os
import re
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.abspath(os.environ.get("QA_DOCS") or os.path.join(ROOT, "docs"))
SHOTS = os.environ.get("QA_SHOTS")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAP = [e.text for e in ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot().findall("s:url/s:loc", NS)]
HOME = urllib.parse.urlparse(SITEMAP[0])
DOMAIN_HOST = HOME.netloc
BASE = HOME.path.rstrip("/")                        # "/pennsylvania-eats" on github.io, "" on a custom domain
CITY_HALL = {"latitude": 39.9524, "longitude": -75.1636}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
BANNED_LD = {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue"}
PDA_DISCLOSURE = ("Please remember that any inspection is a 'snapshot' of the day and time of the inspection. An inspection conducted on "
                  "any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of "
                  "the inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.")
PHILLY_DISCLAIMER = ("The City of Philadelphia makes no representation about the accuracy of any specific information in this data and is "
                     "provided “as is” and without Warranty of any kind.")
MICHELIN_TM = "MICHELIN and the MICHELIN Guide are trademarks of Michelin."
JBF_TM = "James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation."
INIT = """window.__csp = []; window.__cls = 0;
document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || '')));
try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({type: 'layout-shift', buffered: true}); } catch (e) {}"""
PRIVATE_DIGESTS = {
    "4a7e25559b2ffc162afaef2b1680778c6e77d8c2982c3870595f6ee8fea7a455",
    "ff8ea15b513b5561b1c48b725aff52338eddb8ecdd46af58759e2f2c554b0582",
    "31b7679e2f02e2b0561693acc0c78f067633b6713ac53fb5980dcb0f7c2ea237",
    "928009cbd52e0a32a3542c0f41efa0ac8feef2e05974b8126f26c7d4f9b593e3",
}
CSP_REST = ("style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; base-uri 'none'; "
            "form-action 'none'; upgrade-insecure-requests")
ALL_GUIDE_KINDS = {"philadelphia-cheesesteaks-hoagies.html": ("steak", ["cheesesteak", "roast pork", "hoagie"]),
                   "tomato-pie-old-forge-pizza.html": ("pie", ["tomato pie", "old forge"]),
                   "pittsburgh-pierogies.html": ("pierogi", ["pierogi", "pittsburgh sandwich"]),
                   "pennsylvania-dutch-restaurants.html": ("dutch", ["pa dutch"]),
                   "soft-pretzel-bakeries.html": ("pretzel", ["pretzel"]),
                   "pennsylvania-diners.html": ("diner", ["diner"])}
ICONS_PAGE, OLDEST_PAGE = "pennsylvania-icons.html", "pennsylvania-oldest-restaurants.html"
PANEL_READY = "!document.querySelector('#ex-panel').hidden && document.querySelector('#ex-panel').dataset.ready === '1'"
ENTRY = re.compile(r'<li id="p-([^"]+)"><h3>(.*?)</h3>(.*?)</li>', re.S)   # a full place entry ("listed above" pointers aren't)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves DOCS at BASE/, the way GitHub Pages serves the project site; anything outside BASE is a 404."""

    def translate_path(self, path):
        p = urllib.parse.urlsplit(path).path
        if BASE and p != BASE and not p.startswith(BASE + "/"):
            return os.path.join(DOCS, "__not_under_base__")
        return super().translate_path(path[len(BASE):] if BASE else path)

    def log_message(self, *a):
        pass


def serve():
    port = int(os.environ.get("QA_PORT") or 0)   # a fixed port when the machine is shared (each session has its own range)
    # the statewide view asks for all 18 region files at once: the default listen queue (5) resets some of them under load
    srv = type("Server", (http.server.ThreadingHTTPServer,), {"request_queue_size": 64})(("127.0.0.1", port), functools.partial(Handler, directory=DOCS))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def local_file(path):
    path = urllib.parse.unquote(path)
    if BASE and path != BASE and not path.startswith(BASE + "/"):
        return None
    f = os.path.join(DOCS, path[len(BASE):].lstrip("/"))
    if os.path.isfile(f):
        return f
    if os.path.isfile(os.path.join(f, "index.html")):
        return os.path.join(f, "index.html")
    return None


def banned_keys(obj):
    if isinstance(obj, dict):
        return [k for k in obj if k in BANNED_LD] + [x for v in obj.values() for x in banned_keys(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in banned_keys(v)]
    return []


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {y}"


def private_words(text):
    t = text.lower()
    words = set(re.findall(r"[\w.%+-]+@[\w.-]+", t)) | set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", t)) | set(re.findall(r"[a-z0-9]+", t))
    return [w for w in words if hashlib.sha256(w.encode()).hexdigest() in PRIVATE_DIGESTS]


# ---------------------------------------------------------------- the web app's data, decoded the way explore.js reads it
def read_cols(d):
    n, C = d["count"], {}
    for k, v in d["cols"].items():
        if isinstance(v, list):
            C[k] = v
            continue
        a, r = [None] * n, 0
        for gap, val in zip(v["i"], v["v"]):
            r += gap
            a[r] = val
        C[k] = a
    lk = lambda t, v: None if v is None else d[t][v]
    rows = []
    for i in range(n):
        g = lambda k: C[k][i] if k in C else None
        ad = g("ad")
        rows.append({"id": g("id"), "n": g("n"), "c": lk("cities", g("c")), "co": g("co"), "cu": lk("cuisines", g("cu")), "t": g("t") or 0,
                     "la": None if g("la") is None else (g("la") + d["la0"]) / 1e5, "lo": None if g("lo") is None else (g("lo") + d["lo0"]) / 1e5,
                     "a": g("a"), "pl": lk("mailing", g("pl")), "hd": lk("hoods", g("hd")), "ch": g("ch") or 1, "v": g("v") == 1, "hc": g("hc") or 0, "k": g("k") or 0, "ip": g("ip"), "f": g("f"), "mi": g("mi"),
                     "br": g("br"), "ap": lk("placards", g("ap")), "ad": None if ad is None else (datetime.date(2000, 1, 1) + datetime.timedelta(days=ad)).isoformat(),
                     "phl": g("phl") == 1,
                     "ri": g("ri"), "rr": g("rr") if g("rr") is not None else i})
    return rows


class Data:
    def __init__(self):
        dd = os.path.join(DOCS, "data")
        self.ix = json.load(open(os.path.join(dd, "index.json")))
        self.slugs = self.ix["slugs"]
        self.kbit = {k: 1 << i for i, k in enumerate(self.ix["kinds"])}
        self.guides = read_cols(json.load(open(os.path.join(dd, "guides.json"))))
        self.region_rows, self.details = {}, {}
        self.by_id = {}
        for ri, f in enumerate(self.ix["files"]):
            rows = read_cols(json.load(open(os.path.join(dd, f["core"]))))
            det = json.load(open(os.path.join(dd, f["detail"])))
            assert len(det["ids"]) == len(rows) == len(det["d"]), f
            for i, r in enumerate(rows):
                r["id"], r["ri"], r["rr"], r["d"] = det["ids"][i], ri, i, det["d"][i] or {}
                self.by_id[r["id"]] = r
            self.region_rows[ri] = rows
        self.all = [r for ri in sorted(self.region_rows) for r in self.region_rows[ri]]

    def guide_ids(self, kinds):
        mask = sum(self.kbit[k] for k in kinds)
        return {r["id"] for r in self.guides if r["hc"] == 1 and r["k"] & mask and not r["v"]}


def check_static_guides(data, problems):
    """Each guide page lists exactly the hand-checked places of its kinds (a place merely named "... Bagels" is not enough); the
    icons page the honored places; the oldest page the hand-checked places with a year at the same address."""
    # a guide with fewer than 4 hand-checked places has no page (the app hides its card too); one with 4+ must have one
    pages = {name: ids for name, (_, kinds) in ALL_GUIDE_KINDS.items() if len(ids := data.guide_ids(kinds)) >= 4}
    for name, (_, kinds) in ALL_GUIDE_KINDS.items():
        if name not in pages and os.path.exists(os.path.join(DOCS, name)):
            problems.append(f"{name}: a page for a guide with fewer than 4 hand-checked places")
    pages[ICONS_PAGE] = {r["id"] for r in data.guides if r["ip"] is not None and not r["v"]}
    oldest = {r["id"] for r in data.guides if r["f"] is not None and r["hc"] == 1 and not r["v"]}
    if len(oldest) >= 3:
        pages[OLDEST_PAGE] = oldest
    elif os.path.exists(os.path.join(DOCS, OLDEST_PAGE)):
        problems.append(f"{OLDEST_PAGE}: written with fewer than 3 dated places")
    for name, want in pages.items():
        f = os.path.join(DOCS, name)
        if not os.path.exists(f):
            problems.append(f"{name}: missing")
            continue
        got = [m.group(1) for m in ENTRY.finditer(open(f).read())]
        if Counter(got) != Counter(want):
            extra = [data.by_id[i]["n"] + ("" if data.by_id.get(i, {}).get("hc") == 1 else " (NOT hand-checked)") for i in set(got) - want if i in data.by_id]
            problems.append(f"{name}: lists {len(got)} places, expected {len(want)} (extra {sorted(extra)[:4]}, "
                            f"missing {sorted(data.by_id[i]['n'] for i in want - set(got))[:4]})")
        if any(data.by_id[i]["hc"] != 1 for i in got if i in data.by_id) and name != ICONS_PAGE:
            problems.append(f"{name}: lists places that aren't hand-checked")


def all_html():
    out = []
    for d, _, files in os.walk(DOCS):
        out += [os.path.join(d, x) for x in files if x.endswith(".html")]
    return sorted(out)


def check_static_pages(data, problems):
    rt = data.ix["records_through"]
    rt_ok = {nice_date(v) for v in rt.values()}
    wc_file = os.path.join(ROOT, "data", "pa", "website_check.json")
    link_ok = json.load(open(wc_file)) if os.path.exists(wc_file) else None   # pipeline/check_websites.py's verdict per link
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import tracking_params
    if link_ok is not None:   # the same page without its tracking tags keeps the verdict, as in make-site.py
        for _url, _verdict in list(link_ok.items()):
            link_ok.setdefault(tracking_params.clean(_url), _verdict)
    # the over-the-air copy keeps the previous version's files for phones part way through an update: only the current one counts
    mf = os.path.join(DOCS, "data", "app", "manifest.json")
    current = {os.path.basename(v["path"]) for v in json.load(open(mf))["files"].values()} | {"manifest.json"} if os.path.exists(mf) else None
    for d, _, files in os.walk(DOCS):   # no tracking tag on any link we publish (QA 2026-10-26 PA-1), pages and data alike
        for fn in files:
            if current is not None and os.path.abspath(d) == os.path.abspath(os.path.dirname(mf)) and fn not in current:
                continue
            if fn.endswith((".html", ".json", ".js")):
                txt = open(os.path.join(d, fn), encoding="utf-8").read()
                hits = tracking_params.tracked(txt) + re.findall(r"""https?://[^\s"'<>\\#]+#(?:[^\s"'<>\\]*&)?utm_[^\s"'<>\\]*""", txt.replace("\\/", "/"))
                if hits:
                    problems.append(f"{os.path.relpath(os.path.join(d, fn), DOCS)}: {len(hits)} links with tracking tags, e.g. {hits[0]}")
    vouched = lambda r, href: (link_ok.get(href) or {}).get("ok") if link_ok is not None else (r["hc"] == 1 and r["k"])
    for f in all_html():
        name = os.path.relpath(f, DOCS)
        doc = open(f, encoding="utf-8").read()
        low = doc.lower()
        m = re.search(r"<head>\s*<meta http-equiv=\"Content-Security-Policy\" content=\"([^\"]+)\">", doc)
        scripts = re.findall(r"<script>(.*?)</script>", doc, re.S)
        hashes = " ".join(f"'sha256-{base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()}'" for x in scripts) or "'none'"
        want = f"default-src 'none'; script-src {hashes}; {CSP_REST}"
        if not m:
            problems.append(f"{name}: no Content-Security-Policy meta tag first in <head>")
        elif m.group(1) != want:
            problems.append(f"{name}: CSP is {m.group(1)[:100]!r}…, expected {want[:100]!r}…")
        if re.search(r"<script(?![^>]*application/ld\+json)[^>]*\bsrc=", doc) or re.search(r"\son[a-z]+=\"", doc):
            problems.append(f"{name}: an external script or an inline event handler")
        ids = set(re.findall(r'\bid="([^"]+)"', doc))
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
            if "<" in raw or ">" in raw:
                problems.append(f"{name}: JSON-LD has a raw < or >")
            try:
                ld = json.loads(raw)
            except ValueError:
                continue
            if ld.get("@type") == "ItemList":
                for it in ld["itemListElement"]:
                    frag = urllib.parse.urlparse(it.get("url", "")).fragment
                    r = it.get("item", {})
                    if not frag.startswith("p-") or frag not in ids or r.get("url") != it.get("url"):
                        problems.append(f"{name}: list item {r.get('name')!r} doesn't point at its #p- entry ({it.get('url')})")
                    if any(v == "" for v in r.get("address", {}).values()):
                        problems.append(f"{name}: {r.get('name')!r} has an empty address field")
                    if "telephone" in r and not re.fullmatch(r"\+1[2-9]\d{9}", r["telephone"]):
                        problems.append(f"{name}: {r.get('name')!r} has telephone {r['telephone']!r}")
                    if "sameAs" in r and urllib.parse.urlsplit(r["sameAs"]).scheme not in ("http", "https"):
                        problems.append(f"{name}: {r.get('name')!r} sameAs {r['sameAs']!r}")
        text = H.unescape(re.sub(r"<[^>]+>", " ", doc))
        for bad in ("James Beard finalist", "Every Pennsylvania restaurant", "every restaurant in Pennsylvania"):
            if bad.lower() in text.lower():
                problems.append(f"{name}: says {bad!r}")
        if re.search(r"(?<!Who )invented the (cheesesteak|hoagie|tomato pie)", text, re.I):   # origin stories are legends, never our claim
            problems.append(f"{name}: claims who invented a dish")
        if "google" in low:
            problems.append(f"{name}: mentions Google")
        if "★" in doc or "&#9733;" in doc:
            problems.append(f"{name}: a star character (honors are written out, never stars)")
        if MICHELIN_TM not in doc or JBF_TM not in doc:
            problems.append(f"{name}: no MICHELIN or James Beard trademark line")
        if 'class="insp pda-insp' in doc and PDA_DISCLOSURE not in " ".join(H.unescape(doc).split()):
            problems.append(f"{name}: links PDA's search without PDA's disclosure (verbatim)")
        if 'class="insp phl-insp' in doc and PHILLY_DISCLAIMER not in H.unescape(doc):
            problems.append(f"{name}: shows Philadelphia licenses without the City's disclaimer (verbatim)")
        for d in re.findall(r"records through ([A-Z][a-z]{2} \d{1,2}, \d{4})", text):
            if d not in rt_ok:
                problems.append(f"{name}: says records through {d}, but the data says {sorted(rt_ok)}")
        # every inspection result on a static page is the place's own
        for pid, pname, rest in ENTRY.findall(doc):
            r = data.by_id.get(pid)
            if not r:
                problems.append(f"{name}: entry #p-{pid} isn't in the data")
                continue
            county = data.ix["counties"][r["co"]]
            a = re.search(r'class="insp ac-insp"><span class="pl pl-(\w+)">(.*?)</span><span><b>Official placard · inspected ([A-Z][a-z]{2} \d{1,2}, \d{4})</b>', rest)
            if 'ac-insp' in rest and county != "Allegheny":
                problems.append(f"{name}: {H.unescape(pname)!r} shows an ACHD placard outside Allegheny County")
            if a and (H.unescape(a.group(2)) != r["ap"] or not r["ad"] or a.group(3) != nice_date(r["ad"])):
                problems.append(f"{name}: {H.unescape(pname)!r} shows placard {a.group(2)!r} {a.group(3)}, the data says {r['ap']!r} {r['ad']}")
            if r["ap"] and not a:
                problems.append(f"{name}: {H.unescape(pname)!r} has an ACHD placard in the data that the page doesn't show")
            want_cls = ("ac-insp" if county == "Allegheny" and r["ap"] else None if county == "Allegheny" else "phl-insp" if county == "Philadelphia"
                        else "county-insp" if county in ("Bucks", "Montgomery") else "pda-insp")
            if want_cls and f'class="insp {want_cls}' not in rest:
                problems.append(f"{name}: {H.unescape(pname)!r} ({county} County) doesn't show its county's record ({want_cls})")
            if county == "Philadelphia" and ("Active City food license" in rest) != r["phl"]:
                problems.append(f"{name}: {H.unescape(pname)!r} license line disagrees with the data (phl {r['phl']})")
            for href in re.findall(r'<p class="link"><a href="([^"]+)"', rest):
                if not vouched(r, H.unescape(href)):
                    problems.append(f"{name}: {H.unescape(pname)!r} links {href}, which the link check didn't pass")
        if private_words(doc):
            problems.append(f"{name}: contains a private email address or part of one")
        if "M16.4 12.6c0-2.5" in doc:
            problems.append(f"{name}: draws the Apple logo")
        if 'name="twitter:image:alt"' not in doc:
            problems.append(f"{name}: no twitter:image:alt")
        if name == "404.html" and ('rel="canonical"' in doc or 'property="og:url"' in doc):
            problems.append("404.html: has a canonical URL or og:url")
    for d, _, files in os.walk(DOCS):   # the data files, license texts, sitemap and manifest are public too
        for x in files:
            if x.endswith((".json", ".txt", ".xml", ".webmanifest")):
                body = open(os.path.join(d, x), encoding="utf-8", errors="replace").read()
                if private_words(body):
                    problems.append(f"{os.path.relpath(os.path.join(d, x), DOCS)}: contains a private email address or part of one")
                if x.endswith(".json") and "google" in body.lower():
                    problems.append(f"{os.path.relpath(os.path.join(d, x), DOCS)}: mentions Google")
    bad = [r["n"] for r in data.all if r["d"].get("w") and not vouched(r, r["d"]["w"])]   # the web app's links, same rule
    if bad:
        problems.append(f"data: {len(bad)} website links the link check didn't pass ({bad[:3]})")


BLOCKLIST = os.path.abspath(os.environ.get("QA_BLOCKLIST") or os.path.join(ROOT, "pipeline", "website_blocklist.json"))


def blocklist_patterns(entries):
    """One case-insensitive pattern per pipeline/website_blocklist.json entry. A "domain" entry matches the domain and every subdomain,
    with or without www. or a scheme ("HTTP://WWW.Example.com", "shop.example.com", "//example.com"), but not a longer name that ends
    the same way ("dellaroccospizza.com" isn't "roccospizza.com"). A "url" entry matches that page with http or https, with or
    without www. and its trailing slash, and nothing else on its (shared) host."""
    out = []
    for b in entries:
        if b.get("match", "domain") == "url":
            u = urllib.parse.urlsplit(b["url"].strip() if "://" in b["url"] else "//" + b["url"].strip())
            host, path = re.escape((u.hostname or "").lower().rstrip(".").removeprefix("www.")), re.escape(u.path.rstrip("/"))
            out.append((b, re.compile(rf"(?<![a-z0-9.-])(?:www\.)?{host}{path}/?(?![a-z0-9/_%-]|\.[a-z0-9])", re.I)))
        else:
            d = re.escape(b["domain"].strip().lower().rstrip(".").removeprefix("www."))
            out.append((b, re.compile(rf"(?<![a-z0-9-])(?:[a-z0-9-]+\.)*{d}(?![a-z0-9-])", re.I)))
    return out


def check_blocklist(problems):
    """No blocklisted website (hacked, expired or another business's; pipeline/website_blocklist.json) anywhere in docs/: pages,
    JSON-LD, the web app's data files, sitemap, manifest. Fails on a missing, empty or malformed list too, so it can't pass by having
    nothing to look for."""
    try:
        entries = json.load(open(BLOCKLIST, encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"{BLOCKLIST}: missing (make-site.py drops the websites listed there; the link sweep found hacked ones)")
        return
    except ValueError as ex:
        problems.append(f"{BLOCKLIST}: not JSON ({ex})")
        return
    if not isinstance(entries, list) or not entries:
        problems.append(f"{BLOCKLIST}: empty or not a list, so there is nothing to check (the link sweep found a hacked site)")
        return
    good = []
    for b in entries:
        if not isinstance(b, dict) or not b.get("domain") or b.get("match", "domain") not in ("domain", "url") or not b.get("reason") \
                or (b.get("match") == "url" and not b.get("url")):
            problems.append(f"website_blocklist.json: malformed entry {b!r}")
        else:
            good.append(b)
    pats = blocklist_patterns(good)
    for d, _, files in os.walk(DOCS):
        for x in sorted(files):
            if x.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2")):
                continue
            raw = open(os.path.join(d, x), encoding="utf-8", errors="replace").read()
            flat = H.unescape(raw.replace("\\/", "/"))   # JSON-escaped slashes and HTML entities read as what they say
            for b, pat in pats:
                hits = pat.findall(flat)
                if hits:
                    problems.append(f"{os.path.relpath(os.path.join(d, x), DOCS)}: publishes the blocklisted website "
                                    f"{b.get('url') if b.get('match') == 'url' else b['domain']} ({b.get('place', '')}; {b['reason'][:60]}) x{len(hits)}")


OLD_EMAIL, EMAIL = "work-with-nick@gmail.com", "nick@eatsranked.com"   # Nick, 2026-10-12: the site's contact is nick@eatsranked.com
FAMILY = 'Part of <a href="https://eatsranked.com/">Eats Ranked</a>, restaurant apps state by state.'
PARENT = {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked", "url": "https://eatsranked.com/"}
# Nick, 2026-10-13: "High-confidence listing", never "Confirmed listing"; and the site promises no TestFlight invite or link (only his
# internal TestFlight group exists), so the early-access copy ends at an ask ("Ask for early access")
OLD_LABEL = re.compile(r"confirmed\s+listing", re.I)
NEW_LABEL = "High-confidence listing"
OLD_FILTER = re.compile(r"\bconfirmed\s+only\b", re.I)   # the web app's filter is "High-confidence only" (code comments may still say "confirmed")
PROMISES = [re.compile(r"\b(we'll|we will|we'd|we would|you'll|you will|you'd|you would)\b[^.]{0,60}\b(invites?|invitations?|testflight|beta)\b", re.I),
            re.compile(r"\b(send|email|text|mail)(s|ing)? you\b[^.]{0,40}\b(invites?|invitations?|testflight|beta|link)\b", re.I),
            re.compile(r"\bget (early access|an? (testflight|beta|invite|invitation)|the (testflight|beta)( (link|build|app))?|invited)\b", re.I),
            re.compile(r"\b(early access|access|testflight|the beta)\b[^.]{0,20}\bby invit(e|ation)\b", re.I),   # "early access is by invite"
            re.compile(r"\bask for\b[^.]{0,40}\band (then )?(try|get|use|download|install)\b", re.I),         # "ask for an invite and try it"
            re.compile(r"\btestflight\s+(invit|link)", re.I)]   # offering "a TestFlight invite/link" (a mailto body is %20-encoded, so it's left alone)
TITLE_WORDS = {"Cheesesteaks": ["cheesesteak", "roast pork", "hoagie"], "Tomato Pie": ["tomato pie", "old forge"], "Pierogies": ["pierogi", "pittsburgh sandwich"],
               "PA Dutch": ["pa dutch"], "Pretzels": ["pretzel"], "Diners": ["diner"]}


def page_meta(doc):
    title = H.unescape((re.search(r"<title>(.*?)</title>", doc, re.S) or [None, ""])[1])
    desc = H.unescape((re.search(r'<meta name="description" content="([^"]*)"', doc) or [None, ""])[1])
    canon = (re.search(r'<link rel="canonical" href="([^"]+)"', doc) or [None, None])[1]
    og = (re.search(r'<meta property="og:url" content="([^"]+)"', doc) or [None, None])[1]
    return title, desc, canon, og


def check_copy_decisions(problems):
    """Nick's 2026-10-13 copy decisions, over every text file in docs/ (pages, attributes, JSON-LD, the web app's code and data; entities
    decoded and curly apostrophes straightened, so "we&#39;ll" and "we’ll" count): no "Confirmed listing", the web app's tier label is
    "High-confidence listing", and nothing promises a TestFlight invite or link."""
    for d, _, files in os.walk(DOCS):
        for x in files:
            if not x.endswith((".html", ".json", ".txt", ".xml", ".webmanifest", ".js", ".css")):
                continue
            f = os.path.join(d, x)
            rel = os.path.relpath(f, DOCS)
            t = H.unescape(open(f, encoding="utf-8", errors="replace").read()).replace("\u2019", "'")
            if OLD_LABEL.search(t):
                problems.append(f"{rel}: says \"Confirmed listing\" (the label is \"{NEW_LABEL}\")")
            if OLD_FILTER.search(t):
                problems.append(f"{rel}: says \"Confirmed only\" (the web app's filter is \"High-confidence only\")")
            for rx in PROMISES:
                m = rx.search(t)
                if m:
                    problems.append(f"{rel}: promises a TestFlight invite or early access: {m.group(0)!r} (the copy ends at an ask)")
    js = open(os.path.join(DOCS, "explore", "index.html"), encoding="utf-8").read()
    if not re.search(r'const TIER = \{[^}]*1: "' + re.escape(NEW_LABEL) + '"', js):
        problems.append(f"explore/index.html: the place panel's tier label isn't \"{NEW_LABEL}\"")


def check_site_seo(data, problems):
    """The site-wide promises a push depends on: one contact address and never the old one (any file in docs/); every page says it's
    part of Eats Ranked and the Organization names its parent; canonical = og:url = its sitemap entry, unique titles and descriptions;
    breadcrumbs list real pages; no "confirmed/verified open"; city pages claim nearby classics only when they show some, and a
    city's or region's title leads with the guide it has most places on; the web app keeps its storage under its own prefix."""
    for d, _, files in os.walk(DOCS):
        for x in files:
            f = os.path.join(d, x)
            if OLD_EMAIL.encode() in open(f, "rb").read():
                problems.append(f"{os.path.relpath(f, DOCS)}: still has {OLD_EMAIL}")
    if os.path.exists(os.path.join(DOCS, "CNAME")) and BASE:
        problems.append("docs/CNAME exists while the sitemap is on github.io (Pages would forward to a name with no DNS)")
    if not os.path.exists(os.path.join(DOCS, ".nojekyll")):
        problems.append("docs/.nojekyll is missing")
    seen_t, seen_d = defaultdict(list), defaultdict(list)
    sitemap = set(SITEMAP)
    for f in all_html():
        name = os.path.relpath(f, DOCS)
        doc = open(f, encoding="utf-8").read()
        title, desc, canon, og = page_meta(doc)
        text = H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", doc, flags=re.S)))
        if FAMILY not in doc:
            problems.append(f"{name}: no 'Part of Eats Ranked' line in the footer")
        if f'href="mailto:{EMAIL}' not in doc:
            problems.append(f"{name}: no mailto:{EMAIL}")
        if re.search(r"\b(confirmed|verified) open\b", text, re.I):
            problems.append(f"{name}: says 'confirmed/verified open' (we checked each place open; we can't confirm it)")
        if BASE and re.search(rf'(?:href|src|srcset)="/(?!{re.escape(BASE.strip("/"))}/)', doc):
            problems.append(f"{name}: a root-relative link without {BASE}/ (it would 404 on github.io)")
        orgs = []
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
            ld = json.loads(raw)
            for node in ld.get("@graph", [ld]):
                if node.get("@type") == "Organization" and node.get("@id") == f"{HOME.scheme}://{HOME.netloc}{BASE}/#org":
                    orgs.append(node)
        if len(orgs) != 1 or orgs[0].get("parentOrganization") != PARENT:
            problems.append(f"{name}: {len(orgs)} #org Organization nodes; it should be one, naming Eats Ranked as its parent")
        elif orgs[0].get("email") != EMAIL or (orgs[0].get("contactPoint") or {}).get("email") != EMAIL:
            problems.append(f"{name}: the Organization's email isn't {EMAIL}")
        if name == "404.html":
            continue
        seen_t[title].append(name)
        seen_d[desc].append(name)
        want = f"{HOME.scheme}://{HOME.netloc}{BASE}/" + ("" if name == "index.html" else name.removesuffix("index.html"))
        if canon != want or og != want or want not in sitemap:
            problems.append(f"{name}: canonical {canon}, og:url {og}, in sitemap {want in sitemap}; expected {want}")
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
            ld = json.loads(raw)
            if ld.get("@type") == "BreadcrumbList":
                for it in ld["itemListElement"]:
                    if "#" in it["item"] or not local_file(urllib.parse.urlparse(it["item"]).path):
                        problems.append(f"{name}: breadcrumb item {it['item']} isn't a page of its own")
                if ld["itemListElement"][-1]["item"] != want:
                    problems.append(f"{name}: the last breadcrumb isn't this page")
        if name.startswith("cities/"):
            if ("Classics Nearby" in title or "the nearest ones are below" in text or "the nearest hand-checked classics" in desc) \
                    and 'id="nearby"' not in doc:
                problems.append(f"{name}: promises nearby classics but shows none ({title!r})")
        if name.startswith(("cities/", "regions/")):
            m = re.match(r"(.+?)(?:, PA)? Restaurants(?:: ([A-Za-z -]+?)(?: & ([A-Za-z -]+?))?(?: Guide| &| \||$))?", title)
            place = H.unescape(re.search(r"<h1>(.*?)</h1>", doc).group(1)).split(" restaurants")[0]
            if not m or m.group(1) not in (place, {"Philly Suburbs": "Philadelphia Suburbs", "Pittsburgh Region": "Pittsburgh Area", "Central": "Central PA",
                                                   "Northwest": "Northwest PA", "Northern Tier": "PA Northern Tier", "South Central": "South Central PA"}.get(place)):
                problems.append(f"{name}: title {title!r} doesn't start with '{place} Restaurants'")
                continue
            if name.startswith("cities/"):
                here = [r for r in data.guides if r["c"] == place and r["hc"] == 1 and not r["v"]]
            else:
                ri = data.ix["slugs"].index(name[len("regions/"):-len(".html")])
                here = [r for r in data.guides if r["ri"] == ri and r["hc"] == 1 and not r["v"]]
            per = {w: sum(1 for r in here if r["k"] & sum(data.kbit[k] for k in TITLE_WORDS[w])) for w in TITLE_WORDS}
            first = m.group(2)
            if first and first in per and per[first] < max(per.values()):
                problems.append(f"{name}: title leads with {first!r} ({per[first]} places) but the page has more of another guide ({per})")
    for t, ns in seen_t.items():
        if len(ns) > 1:
            problems.append(f"title {t!r} on {len(ns)} pages: {ns[:3]}")
    for d, ns in seen_d.items():
        if len(ns) > 1:
            problems.append(f"description {d[:50]!r}… on {len(ns)} pages: {ns[:3]}")
    js = open(os.path.join(ROOT, "scripts", "explore.js"), encoding="utf-8").read()
    calls = re.findall(r"localStorage\.(?:getItem|setItem|removeItem)\(([^,)]+)", js)
    if not calls or any(not c.strip().startswith('"pae-"') for c in calls) or re.search(r"localStorage\.clear|sessionStorage|document\.cookie", js):
        problems.append(f"explore.js: storage outside the pae- prefix ({calls}); several state sites share nickstrom5.github.io")
    # the FAQPage structured data mirrors the visible questions and answers exactly (Google's rule; the FAQ was rewritten 2026-10-12)
    home = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
    squash = lambda t: " ".join(H.unescape(re.sub(r"<[^>]+>", " ", t)).split())
    seen_qa = [(squash(q), squash(a)) for q, a in re.findall(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", home, re.S)]
    ld_qa = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', home, re.S):
        ld = json.loads(raw)
        if ld.get("@type") == "FAQPage":
            ld_qa = [(" ".join(x["name"].split()), " ".join(x["acceptedAnswer"]["text"].split())) for x in ld["mainEntity"]]
    if not seen_qa or seen_qa != ld_qa:
        problems.append(f"index.html: the FAQPage JSON-LD doesn't mirror the visible FAQ ({len(seen_qa)} shown, {len(ld_qa)} in JSON-LD; "
                        f"first difference {next(((a, b) for a, b in zip(seen_qa, ld_qa) if a != b), None)})")
    # a city page's "what it eats" pills open the web search filtered to the region, the town and the kind: the count on each pill is
    # what that search lists (a listing named for a town across a county line isn't in that town's region file)
    for f in all_html():
        name = os.path.relpath(f, DOCS)
        if not name.startswith("cities/"):
            continue
        doc = open(f, encoding="utf-8").read()
        sec = re.search(r'<section id="cuisines">(.*?)</section>', doc, re.S)
        for href, label, n in re.findall(r'<a href="([^"]+)">([^<]+) \(([\d,]+)\)</a>', sec.group(1) if sec else ""):
            h = urllib.parse.parse_qs(urllib.parse.urlparse(H.unescape(href)).fragment)
            ri = data.ix["slugs"].index(h["r"][0])
            got = sum(1 for r in data.region_rows[ri] if not r["v"] and r["c"] == h["town"][0] and r["cu"] == h["kind"][0])
            if got != int(n.replace(",", "")):
                problems.append(f"{name}: the {H.unescape(label)!r} pill says {n}, the web search lists {got}")
    # the privacy page names everything the web app keeps in the browser (each store.set key, in plain words)
    said = {"saved": "the places you save", "savedr": "the region each saved place is in", "guide": "the last guide you opened"}
    privacy = H.unescape(re.sub(r"<[^>]+>", " ", open(os.path.join(DOCS, "privacy.html"), encoding="utf-8").read()))
    for k in sorted(set(re.findall(r'store\.set\("([^"]+)"', js))):
        if k not in said or said[k] not in " ".join(privacy.split()):
            problems.append(f"privacy.html: doesn't say the web app keeps {k!r} in the browser ({said.get(k, 'no wording for it yet')})")
    # each state's site stands on its own (App Store 4.3(a)): no other state's app, repo or name in page text, comments or scripts;
    # a place's own name or address ("402 Connecticut St", "California Brew Haus", Florida, NY) is fine, so place entries, place
    # data and structured data are left out
    other = re.compile(r"\b(Wisconsin|Connecticut|Colorado|Florida|California|Washington State|Maine|Idaho|Illinois|Chicago|New York|Texas|Hawaii|"
                       r"(?:wi|ct|co|fl|ca|wa|me|id|chi|il|ny|tx|hi)-eats|(?:wisconsin|connecticut|colorado|florida|california|washington|maine|idaho|new-york|texas|hawaii)-eats|"
                       r"(?:ce|we|wae|cae|me|nye|coeats|fleats|ideats)-(?:saved|guide))\b")
    for f in all_html():
        doc = open(f, encoding="utf-8").read()
        doc = re.sub(r'<li id="p-[^"]+">.*?</li>|<li class="again">.*?</li>|<script type="application/ld\+json">.*?</script>', " ", doc, flags=re.S)
        doc = re.sub(r'<section id="(?:streets|cuisines|neighborhoods)">.*?</section>', " ", doc, flags=re.S)   # street and place-kind names
        for m in other.finditer(doc):
            problems.append(f"{os.path.relpath(f, DOCS)}: names another state's site: …{doc[max(0, m.start() - 40):m.end() + 30]!r}…")
    for m in other.finditer(js):
        problems.append(f"explore.js: names another state's site: …{js[max(0, m.start() - 40):m.end() + 30]!r}…")




def check_copy_claims(data, problems):
    """Guards ported from New York's 2026-10-12 verification pass: a title has at most one colon; a city page says ", PA" in its title
    (the names are shared with other states); an address never repeats its town or carries a PO box; descriptions never say
    "hand-checked the nearest hand-checked"; the FAQ never says every list works without location (Near me needs it); no "all/every
    <N> restaurants" (the copy rule)."""
    for f in all_html():
        name = os.path.relpath(f, DOCS)
        doc = open(f, encoding="utf-8").read()
        title, desc, _, _ = page_meta(doc)
        text = " ".join(H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", doc, flags=re.S))).split())
        if title.count(":") > 1:
            problems.append(f"{name}: two colons in the title {title!r}")
        if name.startswith("cities/"):
            place = H.unescape(re.search(r"<h1>(.*?)</h1>", doc).group(1)).split(" restaurants")[0]
            if not title.startswith(f"{place}, PA "):
                problems.append(f"{name}: title {title!r} doesn't say '{place}, PA' (the name is shared with other states)")
        for addr in re.findall(r'<p class="where">(.*?)</p>', doc, re.S) + re.findall(r'"streetAddress":\s*"([^"]*)"', doc):
            a = H.unescape(re.sub(r"<[^>]+>", "", addr))
            if re.search(r"\bP\.?\s?O\.?\s?Box\b", a, re.I) or re.search(r",\s*([A-Z][\w.' -]+?),\s*\1\b", a):
                problems.append(f"{name}: address repeats its town or carries a PO box: {a!r}")
        if re.search(r"hand-checked the\b", desc) or re.search(r"\b(philadelphia|pittsburgh|old forge)\b", desc):
            problems.append(f"{name}: description reads wrong: {desc!r}")
        m = re.search(r"\b(?:all|every) (?:of (?:our |the )?)?\d[\d,]* (?:restaurants|places)\b", text, re.I)
        if m:
            problems.append(f"{name}: 'all/every N restaurants' ({m.group(0)!r})")
        if re.search(r"\b(the|a|an|and|of|in|to|region) \1\b", text, re.I):
            problems.append(f"{name}: a doubled word: {re.search(r'.{0,30}\b(the|a|an|and|of|in|to|region) \1\b.{0,20}', text, re.I).group(0)!r}")
        if name == "index.html" and re.search(r"every list[^.]{0,40}still works?\b", text, re.I):
            problems.append(f"{name}: says every list works without location (Near me needs it)")


# ---------------------------------------------------------------- the web app
def rows(page):
    return page.evaluate("""[...document.querySelectorAll('#ex-list .ex-row')].map(b => ({
        key: b.dataset.key, name: b.querySelector('.ex-name')?.textContent || '', town: b.querySelector('.ex-town')?.textContent || '',
        placard: b.querySelector('.ex-gline')?.textContent || '', metric: b.querySelector('.ex-metric b')?.textContent || ''}))""")


def all_rows(page):
    while page.locator("#ex-more").is_visible():
        page.locator("#ex-more").click()
        page.wait_for_timeout(80)
    return rows(page)


def wait_js(page, expr, timeout=30000, arg=None, every=150):
    """Polls a page expression until it's truthy; False on timeout. Not page.wait_for_function: that evaluates a string predicate
    with eval inside the page, which the site's Content-Security-Policy (rightly, no 'unsafe-eval') blocks, so it threw at once and
    every wait silently became no wait. page.evaluate goes through the DevTools protocol, which the CSP doesn't govern."""
    end = time.time() + timeout / 1000
    while True:
        try:
            ok = page.evaluate(expr, arg) if arg is not None else page.evaluate(expr)
        except Exception:   # the page was between documents
            ok = False
        if ok:
            return True
        if time.time() > end:
            return False
        page.wait_for_timeout(every)


def search(page, text):
    before = page.locator("#ex-count").text_content()
    page.locator("#ex-q").fill(text)
    wait_js(page, "b => document.querySelector('#ex-count').textContent !== b", 4000, arg=before)   # the same count is a fair result too
    page.wait_for_timeout(300)


def close_panel(page):
    if page.locator("#ex-close").count() and page.locator("#ex-close").is_visible():
        page.locator("#ex-close").click()
        page.wait_for_timeout(200)


def pick_guide(page, g):
    page.locator(f'.ex-guides button[data-g="{g}"]').click()
    page.wait_for_timeout(300)


def wait_list(page, timeout=60000):   # a region file can take a while to parse on a busy machine
    ok = wait_js(page, "document.querySelector('#ex-app').getAttribute('aria-busy') === 'false' && "
                       "!/^Loading/.test(document.querySelector('#ex-count').textContent)", timeout)
    page.wait_for_timeout(250)
    return ok


def open_by_key(page, key):
    page.locator(f'#ex-list .ex-row[data-key="{key}"]').click()
    wait_js(page, PANEL_READY)
    page.wait_for_timeout(200)


def check_explore(page, base, width, data, problems, errors):
    where = f"explore @{width}"
    errors.clear()
    ix = data.ix
    key = lambda r: f"{r['ri']}:{r['rr']}"
    slug_i = lambda s: ix["slugs"].index(s)
    county = lambda r: ix["counties"][r["co"]]

    def fresh(hash_):
        page.goto("about:blank")
        page.goto(base + BASE + "/explore/#" + hash_, wait_until="networkidle")
        wait_list(page)

    # 0. nothing moves when the data arrives (the controls and the list's space are there from the first paint)
    slow = lambda route: (time.sleep(1), route.continue_())
    page.route("**/data/guides.json", slow)
    page.goto(base + BASE + "/explore/", wait_until="networkidle")
    loaded = wait_js(page, "document.querySelectorAll('#ex-list .ex-row').length > 0", 30000)
    page.unroute("**/data/guides.json", slow)
    if not loaded:
        problems.append(f"{where}: the list never loaded")
        return
    page.wait_for_timeout(500)
    cls = page.evaluate("window.__cls || 0")
    if cls > 0.1:
        problems.append(f"{where}: layout shift while the list loaded (CLS {cls:.3f})")

    # 1. each classic guide with a page, statewide, lists exactly its hand-checked places (by kind; a name alone is not enough)
    for name, (g, kinds) in ALL_GUIDE_KINDS.items():
        want = {key(r) for r in data.guides if r["id"] in data.guide_ids(kinds)}
        if len(want) < 4:
            continue
        fresh(f"g={g}&r=all")
        got = {r["key"] for r in all_rows(page)}
        if got != want:
            problems.append(f"{where}: the {g} guide shows {len(got)} places, expected the {len(want)} hand-checked ones")

    # 1b. the Bib Gourmand box, statewide: exactly the MICHELIN Bib Gourmands (mi 2, a guide row or a region row), nothing else
    bibs = {key(r) for r in data.guides + data.all if r["mi"] == 2 and not r["v"]}
    fresh("g=all&r=all&bib=1")
    wait_js(page, "(n) => document.querySelector('#ex-count').textContent.startsWith(n + ' place')", 30000, f"{len(bibs):,}")
    got = all_rows(page)
    box = page.locator("#ex-bibwrap")
    if not bibs:
        problems.append(f"{where}: the data has no Bib Gourmand (mi 2) places")
    elif {r["key"] for r in got} != bibs:
        problems.append(f"{where}: Bib Gourmand shows {len(got)} places, expected the {len(bibs)} with mi 2 "
                        f"(extra {sorted({r['key'] for r in got} - bibs)[:3]}, missing {sorted(bibs - {r['key'] for r in got})[:3]})")
    if not box.is_visible() or box.inner_text().strip() != f"Bib Gourmand ({len(bibs):,})" or not page.locator("#ex-bib").is_checked():
        problems.append(f"{where}: the Bib Gourmand box isn't shown ticked as 'Bib Gourmand ({len(bibs):,})' ({box.inner_text().strip()!r})")
    tags = page.evaluate("[...document.querySelectorAll('#ex-list .ex-row')].map(r => [...r.querySelectorAll('.tag-hon')].map(t => t.textContent))")
    wrong = [t for t in tags if "Bib Gourmand" not in t or any("MICHELIN Star" in x for x in t)]
    if wrong:
        problems.append(f"{where}: Bib Gourmand rows without the Bib Gourmand tag, or with stars: {wrong[:3]}")
    page.locator("#ex-bib").uncheck()
    if not wait_js(page, "(n) => !document.querySelector('#ex-count').textContent.startsWith(n + ' place')", 5000, f"{len(bibs):,}"):
        problems.append(f"{where}: unticking Bib Gourmand didn't bring the whole list back")

    # 2. the region picker loads a region's file and lists only that region; the count is the region's restaurants
    fresh("g=all&r=philadelphia")
    pgh = slug_i("pittsburgh-region")
    reqs = []
    page.on("request", lambda rq: reqs.append(rq.url))
    page.select_option("#ex-region", "pittsburgh-region")
    wait_list(page)
    rs = rows(page)
    want_n = ix["files"][pgh]["restaurants"]
    if not any("core-pittsburgh-region.json" in u for u in reqs):
        problems.append(f"{where}: picking the Pittsburgh Region didn't load its file")
    if not rs or any(not r["key"].startswith(f"{pgh}:") for r in rs):
        problems.append(f"{where}: the Pittsburgh Region lists places from other regions")
    if not page.locator("#ex-count").text_content().startswith(f"{want_n:,} places"):
        problems.append(f"{where}: Pittsburgh Region count says {page.locator('#ex-count').text_content()!r}, expected {want_n:,} places")
    if "r=pittsburgh-region" not in page.url:
        problems.append(f"{where}: the region isn't in the URL ({page.url})")

    # 3. "Oyster House" finds it in Philadelphia; its panel shows the City's license section with the City's disclaimer
    fresh("g=all&r=philadelphia")
    search(page, "Oyster House")
    oh = [r for r in data.region_rows[0] if r["n"] == "Oyster House" and not r["v"]]
    hits = [r for r in rows(page) if r["name"] == "Oyster House"]
    if not oh or not hits:
        problems.append(f"{where}: search \"Oyster House\" didn't find it ({[r['name'] for r in rows(page)][:5]})")
    else:
        open_by_key(page, hits[0]["key"])
        panel = page.locator("#ex-panel")
        text = " ".join((panel.inner_text() if panel.is_visible() else "").split())
        if "Oyster House" not in (page.locator("#ex-pname").text_content() or "") or "PHILADELPHIA" not in page.locator(".ex-kicker").text_content():
            problems.append(f"{where}: opening Oyster House didn't show its details")
        for need in ("Licenses & inspections · City of Philadelphia", "L&I food license", " ".join(PHILLY_DISCLAIMER.split()), "America's Classic"):
            if need.lower() not in text.lower():
                problems.append(f"{where}: the Oyster House panel doesn't say {need[:60]!r}")
        if "ACHD" in text or "Allegheny" in text:
            problems.append(f"{where}: a Philadelphia panel mentions Allegheny's placards")
        # 4. Save, then the Saved guide lists it, also after a reload (localStorage, under its own prefix)
        panel.locator("#ex-save").click()
        keys = page.evaluate("Object.keys(localStorage)")
        if not keys or any(not k.startswith("pae-") for k in keys):
            problems.append(f"{where}: localStorage keys outside Pennsylvania's pae- prefix: {keys}")
        close_panel(page)
        pick_guide(page, "saved")
        page.locator("#ex-q").fill("")
        wait_list(page)
        if hits[0]["key"] not in {r["key"] for r in rows(page)}:
            problems.append(f"{where}: a saved place isn't in the Saved guide")
        page.reload(wait_until="networkidle")
        wait_list(page)
        page.wait_for_timeout(800)
        if hits[0]["key"] not in {r["key"] for r in rows(page)}:
            problems.append(f"{where}: a saved place was gone after a reload")
        if SHOTS and width == 375:
            open_by_key(page, hits[0]["key"])
            page.screenshot(path=os.path.join(SHOTS, "site-explore-panel-375.png"))
            close_panel(page)
        # 5. a shared link (#p=<id>) opens the place on a cold load
        fresh(f"g=all&r=philadelphia&p={oh[0]['id']}")
        wait_js(page, PANEL_READY)
        if not page.locator("#ex-panel").is_visible() or (page.locator("#ex-pname").text_content() or "") != "Oyster House":
            problems.append(f"{where}: a #p= link didn't open the place")
        close_panel(page)

    # 6. one place per kind of record: an Allegheny place (ACHD section), a Bucks place (its county's search), a South Central place
    #    (PDA's disclosure, verbatim, and its search)
    cases = [("Allegheny", "pittsburgh-region", ["Allegheny County Health Department", "ACHD food safety and inspection reports"]),
             ("Bucks", "philly-suburbs", ["Bucks County inspection reports"]),
             ("Lancaster", "south-central", [" ".join(PDA_DISCLOSURE.split()), "PA Food Safety Inspection Search"])]
    for cty, slug, need in cases:
        r = next((r for r in data.region_rows[slug_i(slug)] if county(r) == cty and not r["v"] and r["a"]), None)
        if not r:
            problems.append(f"{where}: no {cty} County place to check")
            continue
        fresh(f"g=all&r={slug}&p={r['id']}")
        wait_js(page, PANEL_READY)
        text = " ".join((page.locator("#ex-panel").inner_text() if page.locator("#ex-panel").is_visible() else "").split())
        for n_ in need:
            if n_.lower() not in text.lower():
                problems.append(f"{where}: a {cty} County panel ({r['n']}) doesn't say {n_[:60]!r}")
        if cty != "Allegheny" and "Official placard" in text:
            problems.append(f"{where}: a {cty} County panel shows an ACHD placard")
        close_panel(page)

    # 7. an emoji search lists nothing; "pierogies in millvale"-style stop words; a town in another region moves there
    fresh("g=all&r=philadelphia")
    search(page, "🥨")
    if rows(page):
        problems.append(f"{where}: an emoji search lists places")
    search(page, "altoona")   # not "erie": Brasserie and Pâtisserie match it in Philadelphia, so it rightly stays
    page.wait_for_timeout(1500)
    wait_list(page)
    if "r=central" not in page.url:
        problems.append(f"{where}: searching 'altoona' from Philadelphia didn't move to Central ({page.url})")

    # 8. Near me sorts by distance from the browser's location (City Hall)
    fresh("g=near&r=philadelphia")
    if page.locator("#ex-locate").is_enabled():
        page.locator("#ex-locate").click()
    wait_list(page)
    page.wait_for_timeout(800)
    near = rows(page)[:5]
    if not near:
        problems.append(f"{where}: Near me lists nothing with a location")
    else:
        dist = lambda k: math.dist((CITY_HALL["latitude"], CITY_HALL["longitude"] * 0.766),
                                   (lambda r: (r["la"], r["lo"] * 0.766))(data.region_rows[int(k.split(":")[0])][int(k.split(":")[1])]))
        ds = [dist(r["key"]) for r in near]
        if ds != sorted(ds):
            problems.append(f"{where}: Near me isn't sorted by distance ({[r['name'] for r in near]})")
    problems.extend(f"{where}: console error: {x}" for x in errors)
    problems.extend(f"{where}: CSP violation: {x}" for x in page.evaluate("window.__csp || []"))


def app_data_checks(problems):
    """docs/data/app/, the app's data updates (scripts/publish_app_data.py, OTA-DATA.md): every manifest entry's hash, size and
    row count match its file, the head file's date matches, and no old copy lingers."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from publish_app_data import check_app_data, app_data_dir
    found, notes = check_app_data(DOCS, app_data_dir())
    problems.extend("app data: " + x for x in found)
    for x in notes:
        print("  note: app data:", x)


def main():
    base = serve()
    pages = [base + urllib.parse.urlparse(u).path for u in SITEMAP]
    if os.environ.get("QA_PAGES"):
        pages = pages[:int(os.environ["QA_PAGES"])]
    data = Data()
    problems = []
    check_static_guides(data, problems)
    check_static_pages(data, problems)
    check_site_seo(data, problems)
    check_copy_decisions(problems)
    check_copy_claims(data, problems)
    check_blocklist(problems)
    app_data_checks(problems)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for width in [int(w) for w in os.environ.get("QA_WIDTHS", "375,1280").split(",")]:
            ctx = browser.new_context(viewport={"width": width, "height": 900}, geolocation=CITY_HALL, permissions=["geolocation"])
            ctx.add_init_script(INIT)
            page = ctx.new_page()
            page.set_default_timeout(30000)
            errors, offsite = [], []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            local = urllib.parse.urlparse(base).netloc
            page.on("request", lambda r: offsite.append(r.url) if urllib.parse.urlparse(r.url).scheme in ("http", "https")
                    and urllib.parse.urlparse(r.url).netloc != local else None)
            for url in pages:
                errors.clear(); offsite.clear()
                try:
                    resp = page.goto(url, wait_until="networkidle")
                except Exception as ex:
                    problems.append(f"{url} @{width}: didn't load ({str(ex).splitlines()[0]})")
                    continue
                path = urllib.parse.urlparse(url).path
                where = f"{path} @{width}"
                if not resp or resp.status != 200:
                    problems.append(f"{where}: HTTP {resp.status if resp else 'no response'}")
                    continue
                over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if over > 1:
                    problems.append(f"{where}: scrolls sideways by {over}px")
                if page.locator("h1").count() != 1:
                    problems.append(f"{where}: {page.locator('h1').count()} <h1>")
                title = page.title()
                desc = page.evaluate("document.querySelector('meta[name=description]')?.content || ''")
                if not 50 <= len(title) <= 60:
                    problems.append(f"{where}: title is {len(title)} characters")
                if not 140 <= len(desc) <= 160:
                    problems.append(f"{where}: description is {len(desc)} characters")
                for raw in page.locator('script[type="application/ld+json"]').all_text_contents():
                    try:
                        bad = banned_keys(json.loads(raw))
                        if bad:
                            problems.append(f"{where}: JSON-LD has ratings or reviews ({sorted(set(bad))})")
                    except ValueError as ex:
                        problems.append(f"{where}: bad JSON-LD ({ex})")
                if width == 1280:   # links are the same at both widths
                    refs = page.evaluate("""[...document.querySelectorAll('a[href],img[src],link[href],script[src],source[srcset]')]
                        .map(e => e.getAttribute('href') || e.getAttribute('src') || e.getAttribute('srcset'))""")
                    cache = {}
                    for ref in refs:
                        full = urllib.parse.urljoin(url, ref)
                        p = urllib.parse.urlparse(full)
                        if p.scheme in ("mailto", "tel", "data"):
                            continue
                        if p.netloc not in (local, DOMAIN_HOST):
                            continue
                        if p.netloc == DOMAIN_HOST and not p.path.startswith(BASE + "/") and p.path != BASE:
                            continue
                        f = local_file(p.path)
                        if not f:
                            problems.append(f"{where}: broken link {ref}")
                        elif p.fragment and "=" not in p.fragment and f.endswith(".html"):
                            if f not in cache:
                                cache[f] = open(f).read()
                            if not re.search(rf'id="{re.escape(p.fragment)}"', cache[f]):
                                problems.append(f"{where}: link to a missing anchor {ref}")
                    imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.src)")
                    problems += [f"{where}: image didn't load {s}" for s in imgs]
                if SHOTS and path in (BASE + "/", BASE + "/philadelphia-cheesesteaks-hoagies.html", BASE + "/cities/pittsburgh.html"):
                    name = {BASE + "/": "home", BASE + "/philadelphia-cheesesteaks-hoagies.html": "cheesesteaks", BASE + "/cities/pittsburgh.html": "pittsburgh"}[path]
                    page.screenshot(path=os.path.join(SHOTS, f"site-{name}-{width}.png"), full_page=(name != "home"))
                problems += [f"{where}: console error: {x}" for x in errors]
                problems += [f"{where}: CSP violation: {x}" for x in page.evaluate("window.__csp || []")]
                problems += [f"{where}: request to another site: {u}" for u in offsite]
            offsite.clear()
            try:
                check_explore(page, base, width, data, problems, errors)
            except Exception as ex:   # a broken page shouldn't stop the report
                problems.append(f"explore @{width}: the checks stopped: {str(ex).splitlines()[0]}")
            problems += [f"explore @{width}: request to another site: {u}" for u in offsite]
            ctx.close()
        browser.close()
    print(f"{len(pages)} pages × 2 widths + the web app (served at {BASE or '/'} from {DOCS})")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
