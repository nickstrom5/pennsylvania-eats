"""Checks every website link the app ships before it ships, because map listings carry stale and hijacked domains.

Chicago found about 3% of its listing websites redirected to gambling, betting or adult sites, including a starred restaurant's.
A link survives only if:
  - the final response is 2xx,
  - it stays on the same registered domain (or the page plainly belongs to the place),
  - the page mentions a distinctive word of the place's name,
  - and nothing looks like gambling spam, adult content, a parked or for-sale domain, an expired account or "coming soon".
The name test reads the page's text only, never its URL (a lapsed "thebrickhousect.com" placeholder names itself), and matches words at
their start. A page that sends the browser on by itself (a meta refresh or a script setting window.location: parking landers and
hijacks do this) is judged where it leads, one hop.
A site that blocks the check, times out or errors is dropped too: no link beats a wrong link. The one exception is a chain's own
domain (mcdonalds.com for McDonald's): when it refuses the check (403, 429, connection refused), its links stay, because the domain
plainly belongs to the brand; a store page it answers 404 for is dropped.

Polite by design: an honest user agent, one request at a time per host (a second apart on a chain's domain), and a domain that refuses
twice isn't asked again in that run. Never bypasses bot protection.
Verdicts carry the date they were checked; an ok verdict older than RECHECK_DAYS, or from an older version of these rules, is
fetched again. `--fresh` re-checks everything (do that before each App Store submission).

Usage: ../.venv/bin/python check_websites.py [--fresh | --retry-errors]   (reads data/pa/website_candidates.json) → data/pa/website_check.json
({url: {"ok": bool, "why": str, "final": str, "checked": "YYYY-MM-DD", "v": RULES}}).
The app export (pennsylvania.py, PA_APP=1) drops every link that isn't ok, and ships no links at all without this file.
"""
import collections
import datetime
import html
import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import sys

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = f"{ROOT}/data/pa/website_check.json"
RULES = 2            # bump when the rules change: every cached verdict from older rules is fetched again
RECHECK_DAYS = 14
TODAY = datetime.date.today().isoformat()
UA = "PennsylvaniaEatsLinkCheck/1.0 (+https://pennsylvania.eatsranked.com/; nick@eatsranked.com)"
GENERIC = set("""the and of a an at on in restaurant restaurants bar bars grill grille cafe caffe coffee pizza pizzeria pub tavern house
supper club inn lounge kitchen bistro eatery diner bakery deli market express food foods co company inc llc ltd corp ny nyc new york brooklyn queens bronx manhattan
family original new old north south east west st saint mt sports place spot shop shoppe taproom brewing brewery
tap taps bbq barbecue burger burgers chicken subs sub sandwich sandwiches tacos taco mexican chinese thai sushi asian italian
american cuisine catering events""".split())
# Hijacked domains carry Indonesian slot and lottery spam, Turkish betting pages or porn links: any of these marks a page.
SPAM = re.compile(r"slot ?gacor|situs (?:slot|judi|togel)|slot online|\bslot ?88\b|\btogel\b|judi (?:online|bola|slot|qq|poker)|perjudian|"
                  r"bandar ?(?:slot|qq|togel)|\bmaxwin\b|\brtp slot|\bsbobet\b|\bbahis|casino siteleri|\b1win\b|watch porn|free porn|"
                  r"porn videos?|\bpornhub\b|\bxvideos\b|\bxnxx\b|escort service|adult dating|sex cam|camgirl|"
                  r"\bviagra\b|\bcialis\b|\bkamagra\b|\blevitra\b|"
                  r"สล็อต|บาคาร่า|แทงบอล|슬롯|카지노|토토사이트|百家乐|娱乐城|博彩|老虎机|nhà cái|казино|ставки на спорт", re.I)
BLOBS = re.compile(r"[A-Za-z0-9+/=_-]{100,}")   # base64 images and tokens: random letters spell anything
# Words a real casino's restaurant or a brewery near the sportsbook uses too: they count only in the page title or description,
# or repeated in the body, and never on a casino's own page.
BETTING = re.compile(r"online casino|casino online|deposit bonus|sportsbook|\bbaccarat\b|bet365|no deposit", re.I)
HEAD = re.compile(r"<title[^>]*>(.*?)</title>|<meta[^>]+name=.description.[^>]+content=\"([^\"]*)", re.S)
CASINO_PLACE = re.compile(r"casino|gaming|foxwoods|mohegan|mashantucket|pequot|"
                          r"resorts world|great cedar", re.I)
PARKED = re.compile(r"domain (?:is|may be) for sale|buy this domain|this domain is parked|parked free|sedoparking|hugedomains|"
                    r"afternic|domain has expired|this domain name has expired|account (?:has been )?suspended|website coming soon|"
                    r"site (?:is )?coming soon|domain is coming soon|future home of|launching soon|godaddy\.com/domainsearch|dan\.com|"
                    r"parking-lander|wsimg\.com/parking|ap:\s*[\"']parking|defaultwebpage\.cgi|/cgi-sys/|default web site page|"
                    r"parkingcrew|bodis\.com|above\.com/marketplace|domain parking|welcome to nginx|apache2 (?:ubuntu|debian) default page|"
                    r"<title>\s*index of /", re.I)
# directories, listings, review sites, shorteners and fundraisers: not the place's own page. Matched by registered domain, never as a
# substring ("restaurant.com" is in salepeperestaurant.com: Wisconsin once dropped 171 real sites that way)
BAD_DOMAINS = {"business.site", "negocio.site", "google.com", "goo.gl", "g.co", "share.google", "yelp.com", "doordash.com", "grubhub.com", "ubereats.com", "seamless.com", "allmenus.com", "menupix.com",
             "zmenu.com", "restaurantji.com", "yellowpages.com", "liyellowpages.com", "superpages.com", "whitepages.com", "chamberofcommerce.com",
             "cortera.com", "dandb.com", "bizapedia.com", "city-data.com", "mapquest.com", "citysearch.com", "yahoo.com", "hub.biz",
             "edan.io", "poi.place", "placeweb.site", "jany.io", "lany.io", "keeq.io", "restoguides.com", "dinehere.us", "foodspot.com",
             "gastrobars.com", "indulgery.com", "clubplanet.com", "restaurant.com", "groupon.com", "seatgeek.com", "opentable.com",
             "menuism.com", "barfinder.com", "friendseat.com", "local.com", "usplaces.com", "foodeist.com", "jmaps.net", "kwickmenu.com",
             "tinyurl.com", "bit.ly", "forms.gle", "gofund.me", "gofundme.com", "cash.app", "tiktok.com", "reverbnation.com",
             "youtube.com", "youtu.be", "singleplatform.com"}
BAD_PATHS = ("facebook.com/pages",)
BAD_LABELS = {"tripadvisor"}   # every country's tripadvisor.*
SHADY = re.compile(r"(?:^|\.)food\d+\.com$|\.top$")   # food73.com-style listing farms, .top redirect farms
# a brand that moved its stores to a short domain
ALIASES = {"burgerking.com": "bk.com"}
BLOCKED = re.compile(r"^(?:http 40[39]|http 429|error: (?:ConnectionError|ConnectTimeout|ReadTimeout))$")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s.replace("'", "")).strip()


def regdom(host):
    parts = host.lower().removeprefix("www.").split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host_of(url):
    p = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    return p.netloc.lower().rsplit("@", 1)[-1].split(":")[0].removeprefix("www."), p.path.lower()


def bad_host(url):
    host, path = host_of(url)
    rd = regdom(host)
    return rd in BAD_DOMAINS or rd.split(".")[0] in BAD_LABELS or any((rd + path).startswith(b) for b in BAD_PATHS) \
        or bool(SHADY.search(rd))


def words(name):
    return [w for w in norm(name).split() if len(w) >= 4 and w not in GENERIC]


def mentioned(name, text):
    """A distinctive word of the name at the start of a word in the page text ("pepes" -> "pepe"); a name of generic words only
    ("The Pizza House") must appear whole."""
    ws = words(name)
    if not ws:
        phrase = " ".join(w for w in norm(name).split() if w not in ("the", "a", "and"))
        return bool(phrase) and f" {phrase} " in f" {text} "
    return any(re.search(r"\b" + re.escape(w[:-1] if len(w) > 4 and w.endswith("s") else w), text) for w in ws)


# a page that moves the browser on by itself: <meta http-equiv="refresh" content="0;url=...">, window.location = "...",
# location.replace("..."). Judged on small pages only (a real site's menu script can mention location.href in passing).
META_REFRESH = re.compile(r"<meta[^>]+http-equiv=[\"']?refresh[\"']?[^>]*content=[\"']?\s*\d*\s*;?\s*url\s*=\s*['\"]?([^\"'>\s]+)", re.I)
JS_REDIRECT = re.compile(r"(?:window\.|document\.|top\.|self\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']|"
                         r"location\.(?:replace|assign)\(\s*[\"']([^\"']+)[\"']", re.I)


def client_redirect(body):
    visible = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", body, flags=re.S | re.I)
    if len(norm(visible)) > 600:
        return None
    m = META_REFRESH.search(body)
    if m:
        return m.group(1)
    m = JS_REDIRECT.search(body)
    return (m.group(1) or m.group(2)) if m else None


host_locks = collections.defaultdict(threading.Lock)
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "text/html,*/*;q=0.5", "Accept-Language": "en-US"})


refusals = collections.Counter()   # registered domain -> times it refused the check this run


def fetch(u, gap):
    host = urllib.parse.urlparse(u).netloc.lower()
    with host_locks[regdom(host)]:
        if refusals[regdom(host)] >= 2:
            return None, "", u, "http 403 (domain refused earlier)"
        try:
            r = session.get(u, timeout=(8, 15), allow_redirects=True, stream=True)
            body = r.raw.read(400_000, decode_content=True).decode(r.encoding or "utf-8", "ignore") if r.ok else ""
            final = r.url
            r.close()
        except Exception as e:
            return None, "", u, "error: " + type(e).__name__
        finally:
            time.sleep(gap)
    if r.status_code in (403, 429):
        refusals[regdom(host)] += 1
    return r, body, final, None


def check(url, name, gap=0.3):
    u = url if url.startswith("http") else "https://" + url
    host = urllib.parse.urlparse(u).netloc.lower()
    if bad_host(u):
        return {"ok": False, "why": "directory or Google link", "final": u}
    r, body, final, err = fetch(u, gap)
    if err:
        return {"ok": False, "why": err, "final": final}
    if r.ok:
        hop = client_redirect(body)
        if hop and not hop.lower().startswith(("javascript:", "data:", "#")):
            target = urllib.parse.urljoin(final, hop)
            if bad_host(target):
                return {"ok": False, "why": "redirects to a directory", "final": target}
            r, body, final, err = fetch(target, gap)
            if err:
                return {"ok": False, "why": err, "final": final}
    if not r.ok:
        return {"ok": False, "why": f"http {r.status_code}", "final": final}
    text = BLOBS.sub(" ", body).lower()
    head = " ".join(a or b for a, b in HEAD.findall(text[:60_000]))
    casino = CASINO_PLACE.search(name) or CASINO_PLACE.search(urllib.parse.urlparse(final).netloc)
    if SPAM.search(text) or SPAM.search(final) or (not casino and (BETTING.search(head) or len(BETTING.findall(text)) >= 2)):
        return {"ok": False, "why": "gambling or adult content", "final": final}
    if PARKED.search(text[:60_000]):
        return {"ok": False, "why": "parked, expired or coming soon", "final": final}
    if bad_host(final):
        return {"ok": False, "why": "redirects to a directory", "final": final}
    ws = words(name)
    # the site's own domain name never counts as a mention: every parked lander and placeholder repeats it ("thebrickhousect.com")
    stems_ = {h.removeprefix("www.").split(".")[0] for h in (urllib.parse.urlparse(final).netloc.lower(), host)} - {""}
    def own(t):
        t = t.lower()
        for st_ in stems_:
            t = t.replace(st_, " ")
        return t
    page = norm(own(html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", body, flags=re.S | re.I))))
    page = page + " " + norm(own(html.unescape(" ".join(a or b for a, b in HEAD.findall(body[:60_000])))))   # the title and description count too
    same = regdom(urllib.parse.urlparse(final).netloc) in (regdom(host), ALIASES.get(regdom(host)))
    if not mentioned(name, page) and len(page) < 400:
        # a site drawn by scripts has little text: its source may still name the place (a page-data blob)
        raw = norm(own(html.unescape(body)))
        if mentioned(name, raw):
            page = page + " " + raw
    if not mentioned(name, page):
        return {"ok": False, "why": "page doesn't mention the place", "final": final}
    if not same and not any(w in norm(urllib.parse.urlparse(final).netloc) for w in ws):
        return {"ok": False, "why": "moved to another domain", "final": final}
    return {"ok": True, "why": "ok", "final": final}


def main():
    # every link the export considered (written by pennsylvania.py, PA_APP=1), so a link dropped last time gets another chance
    cands = json.load(open(f"{ROOT}/data/pa/website_candidates.json"))
    jobs = collections.defaultdict(list)   # registered domain -> [(url, name)]
    for w, name in cands.items():
        u = w if w.startswith("http") else "https://" + w
        jobs[regdom(urllib.parse.urlparse(u).netloc)].append((w, name))
    prev = json.load(open(OUT)) if os.path.exists(OUT) and "--fresh" not in sys.argv else {}
    stale = (datetime.date.today() - datetime.timedelta(days=RECHECK_DAYS)).isoformat()
    # an ok verdict is trusted for RECHECK_DAYS under the same rules; a failure is kept for the same time (a dead site gets another chance)
    prev = {u: v for u, v in prev.items() if v.get("v") == RULES and v.get("checked", "") >= stale}
    if "--retry-errors" in sys.argv:   # after a network outage: fetch again every link that failed to connect or timed out
        prev = {u: v for u, v in prev.items() if not v["why"].startswith("error:")}
    for a in sys.argv:   # --retry-why=<verdict>: fetch again every link with that verdict (after a rule for it changed)
        if a.startswith("--retry-why="):
            prev = {u: v for u, v in prev.items() if v["why"] != a.split("=", 1)[1]}
    todo, chain_hosts, brand_of = [], {}, {}
    for dom, items in jobs.items():
        uniq = list(dict.fromkeys(items))
        top, n = collections.Counter(name for _, name in uniq).most_common(1)[0]
        if len(uniq) >= 5 and n >= 0.8 * len(uniq):   # a chain's own domain: every store page is checked, a second apart
            chain_hosts[dom] = [u for u, _ in uniq]
            brand_of[dom] = top
        todo += [(u, name, 1.0 if dom in chain_hosts else 0.3) for u, name in uniq]
    todo = [t for t in todo if t[0] not in prev]
    # round-robin across domains: a chain's hundreds of store pages (one at a time, a second apart) mustn't hold every worker
    by_dom = collections.defaultdict(list)
    for t in todo:
        by_dom[regdom(urllib.parse.urlparse(t[0] if t[0].startswith("http") else "https://" + t[0]).netloc)].append(t)
    todo = [t for group in __import__("itertools").zip_longest(*by_dom.values()) for t in group if t]
    print(f"{sum(len(v) for v in jobs.values())} links, {len(jobs)} domains, {len(chain_hosts)} chain domains; checking {len(todo)}")
    results, done = dict(prev), 0
    lock = threading.Lock()

    def run(item):
        nonlocal done
        res = dict(check(*item), checked=TODAY, v=RULES)
        with lock:
            results[item[0]] = res
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                json.dump(results, open(OUT, "w"))

    with ThreadPoolExecutor(max_workers=24) as ex:
        list(ex.map(run, todo))
    for dom, urls in chain_hosts.items():
        # the brand's own domain refused the check: its store links stay (the domain plainly belongs to the brand); a 404 doesn't
        if not any(w in norm(dom) for w in words(brand_of[dom])):
            continue
        for u in urls:
            if not results[u]["ok"] and BLOCKED.match(results[u]["why"].replace(" (domain refused earlier)", "")):
                results[u] = {**results[u], "ok": True, "why": "brand's own site (blocked the check)"}
            elif not results[u]["ok"] and results[u]["why"] == "page doesn't mention the place" and \
                    regdom(urllib.parse.urlparse(results[u]["final"]).netloc) == dom:
                results[u] = {**results[u], "ok": True, "why": "brand's own site (store page drawn by scripts)"}
    json.dump(results, open(OUT, "w"), indent=0)
    c = collections.Counter(v["why"] if not v["ok"] else "ok" for v in results.values())
    print("results:", c.most_common())


if __name__ == "__main__":
    main()
