"""Matching map listings to official records (used by calibrate.py and pennsylvania.py).

Same rules as ny-eats/pipeline/listings_util.py (from ct-eats), built for a big state: plain
lists instead of pandas lookups, and the name comparison only for records at the same address or within 150 m, the only ones a rule
can accept."""
import math
from rapidfuzz import fuzz
from common import name_sim, _stems, GENERIC
from official import street_key, street_nums


def _close_words(a, b):
    """A distinctive word in common, allowing a spelling slip ("HIMAL CHULI" / "HIMALI CHULO")."""
    return any(x == y or (len(x) >= 5 and len(y) >= 5 and fuzz.ratio(x, y) >= 85) for x in a for y in b)


SAME_ADDR_M = 1000   # how far apart a listing and an official record at "the same address" can be (geocoders differ by a block or two)


def official_match(L, R, one_to_one=False, town_words=frozenset(), street_col="street"):
    """L: listings with k (name key), street, lat, lon. R: official records with keys, num, street, addr, lat, lon.
    Returns {listing index: official index}. A match needs the same business name nearby, or the same street address
    with a distinctive (non-generic, non-town) name word in common. A record with no usable name matches only the one listing at its
    street address."""
    RA, RS, RK = list(R.addr), list(R.street), list(R["keys"])
    RLA, RLO = list(R.lat), list(R.lon)
    # a record whose only name is a legal entity or a person (Philadelphia: "HUI LIN" for Happy Garden) can also confirm the single
    # listing at its street address, like a nameless record
    RNL = list(R["name"].isna()) if "name" in R.columns else [False] * len(R)
    z5 = lambda z: str(z).strip()[:5] if isinstance(z, str) and z.strip()[:5].isdigit() else None
    RZ = [z5(z) for z in R["zip"]] if "zip" in R.columns else [None] * len(R)
    LZ = [z5(z) for z in L["zip"]] if "zip" in L.columns else [None] * len(L)
    by_addr, grid = {}, {}
    for j, (a, st) in enumerate(zip(RA, RS)):
        for n in street_nums(a):
            if st:
                by_addr.setdefault((n, st), []).append(j)
    for j, (la, lo) in enumerate(zip(RLA, RLO)):
        if la == la and lo == lo:
            grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
    rstems = [set().union(*[(_stems(k) - GENERIC - town_words) for k in ks]) if ks else set() for ks in RK]
    rnums = [street_nums(a) for a in RA]
    rsplit = [[set(rk.split()) for rk in ks] for ks in RK]
    # listings per street address: a nameless record (an SLA license with no trade name, most of Buffalo's list) can only confirm
    # the single listing at its address, never pick one of several tenants
    at_addr = {}
    for street in L[street_col]:
        _, st = street_key(street)
        if st:
            for n in street_nums(street):
                at_addr[(n, st)] = at_addr.get((n, st), 0) + 1
    pairs = []
    for i, (k, street, la, lo) in enumerate(zip(L.k, L[street_col], L.lat, L.lon)):
        if not k:
            continue
        _, st = street_key(street)
        nums = street_nums(street)
        cand = set()
        for n in nums:
            cand.update(by_addr.get((n, st), []))
        if la == la:
            gy, gx = round(la / 0.0015), round(lo / 0.002)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    cand.update(grid.get((gy + dy, gx + dx), []))
        mine = None
        ksplit = set(k.split())
        alone = any(at_addr.get((n, st), 0) == 1 for n in nums) if st else False
        for j in cand:
            same_addr = bool(st and RS[j] == st and nums & rnums[j])
            rl, ro = RLA[j], RLO[j]
            if same_addr:
                # Pennsylvania repeats street addresses (every borough has a 100 Main St):
                # the same address counts only within SAME_ADDR_M, or, for a record without coordinates, in the same ZIP code
                if rl == rl and la == la:
                    same_addr = math.hypot((rl - la) * 111000, (ro - lo) * 79000) <= SAME_ADDR_M
                elif RZ[j] and LZ[i] and RZ[j] != LZ[i]:
                    same_addr = False
            if not RK[j] or RNL[j]:
                if same_addr and alone:
                    pairs.append((50, i, j))
                if not RK[j]:
                    continue
            dist = math.hypot((rl - la) * 111000, (ro - lo) * 79000) if (rl == rl and la == la) else (40 if same_addr else 9999)
            if not same_addr and dist > 150:
                continue   # every rule below needs the same address or 150 m
            if mine is None:
                mine = _stems(k) - GENERIC - town_words
            s = max((name_sim(k, rk) for rk in RK[j]), default=0)
            shared = bool(mine & rstems[j]) or _close_words(mine, rstems[j])
            nested = same_addr and any(len(rs) >= 2 and (rs <= ksplit or ksplit <= rs) for rs in rsplit[j])
            if (same_addr and (s >= 75 or shared or nested)) or (dist <= 150 and s >= 88) or (dist <= 60 and s >= 80 and shared):
                pairs.append((s + (15 if same_addr else 0) - dist / 20, i, j))
    out, taken_l, taken_r = {}, set(), set()
    for sc, i, j in sorted(pairs, key=lambda t: -t[0]):
        if i in taken_l or (one_to_one and j in taken_r):
            continue
        taken_l.add(i); taken_r.add(j); out[i] = j
    return out
