"""How often is a map listing a real food business? Measured against Pennsylvania's official lists -> data/pa/calibration.json

Yardsticks:
- Philadelphia: L&I's active "Food Preparing and Serving" licenses (every sit-down or take-out food business in the city holds
  one), so the rate is absolute for Philadelphia.
- Allegheny: ACHD's facilities inspected in the current table (when Nick's WPRDC download is present).
- Statewide, partial: PLCB on-premises licenses (when Nick's export is present; only places that serve alcohol hold one).
- Statewide, stale: PDA's 2018-2020 inspection list (data.pa.gov etb6-jzdg, active facilities, no coordinates; matched by address).
  It shows which listings were food businesses in 2020, not which are open now.
A match = the same business name nearby, or the same street address with a distinctive name word in common (listings_util).
"""
import json
import numpy as np, pandas as pd
from common import PA
import official
from listings_util import official_match

o = pd.read_pickle(f"{PA}/stage1.pkl")
F = official.load()
o = o[~o.j_junk & ~o.j_outside].reset_index(drop=True)
TOWNWORDS = frozenset(w for t in pd.concat([o.place.dropna(), o.muni.dropna()]).unique() for w in t.upper().split())


def groups_web(L):
    s = L.src.fillna("none")
    return np.select([L.closed21, L.ov_closed, (s == "meta") & L.in21, s == "meta", s.isin(["AllThePlaces", "DAC"]) & L.in21,
                      s.isin(["AllThePlaces", "DAC"]), L.in21, s == "Foursquare", s == "BrightQuery", s == "Microsoft"],
                     ["Google 2021 says closed", "Overture says closed", "Meta + open in Google 2021", "Meta only",
                      "brand feed + Google 2021", "brand feed only", "Foursquare/BrightQuery/Microsoft + Google 2021",
                      "Foursquare only", "BrightQuery only", "Microsoft only"], "other")


def groups_app(L):
    conf, s = L.confidence.fillna(0), L.src.fillna("none")
    return np.select([L.ov_closed, (s == "meta") & (conf >= 0.95), (s == "meta") & (conf >= 0.9), s.isin(["AllThePlaces", "DAC"]),
                      (s == "BrightQuery") & (conf >= 0.95), s == "meta"],
                     ["Overture says closed", "Meta, confidence 0.95+", "Meta, 0.90-0.95", "brand feed", "BrightQuery 0.95+", "Meta, below 0.90"],
                     "other sources")


def measure(L, R, grp_fn, label):
    L = L.reset_index(drop=True)
    m = official_match(L, R.reset_index(drop=True), town_words=TOWNWORDS)
    L["hit"] = L.index.map(lambda i: i in m)
    L["grp"] = grp_fn(L)
    t = L.groupby("grp").hit.agg(["size", "mean"]).sort_values("size", ascending=False)
    print(f"\n== {label}: {len(L)} listings vs {R.biz.nunique()} businesses", flush=True)
    print(t.assign(mean=(t["mean"] * 100).round(1)).rename(columns={"size": "listings", "mean": "% matched"}).to_string(), flush=True)
    got = set(R.reset_index(drop=True).biz.iloc[list(m.values())])
    return L, {g: {"n": int(r["size"]), "matched": round(float(r["mean"]), 3)} for g, r in t.iterrows()}, got


res = {"web": {}, "app": {}, "coverage": {}}
A = F[F.active]
areas = {"philly_restaurant_licenses": (o.county == "Philadelphia", A[(A.jur == "philly") & (A.kind == "restaurant")])}
if (A.jur == "achd").any():
    areas["allegheny_achd"] = (o.county == "Allegheny", A[A.jur == "achd"])
if (A.jur == "plcb").any():
    areas["statewide_plcb"] = (o.county.notna(), A[(A.jur == "plcb") & A.kind.isin(official.ON_PREMISE)])
areas["pda_2018_2020"] = (~o.county.isin(["Allegheny", "Bucks", "Montgomery"]) & o.county.notna(), A[A.jur == "pda2020"])
for area, (sel, R) in areas.items():
    for kind, fn in (("web", groups_web), ("app", groups_app)):
        L, res[kind][area], got = measure(o[sel], R, fn, f"{area}, {kind} grouping")
    RB = R.drop_duplicates("biz")
    res["coverage"][area] = {"n": int(len(RB)), "found": round(float(RB.biz.isin(got).mean()), 3)}
    print(f"{area}: official businesses found among the map listings: {res['coverage'][area]['found']:.1%} of {len(RB)}", flush=True)
json.dump(res, open(f"{PA}/calibration.json", "w"), indent=1)
print("\nwrote calibration.json")
