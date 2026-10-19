"""Pennsylvania's counties, municipalities and Census places -> data/pa/

Sources (public domain):
- Census cartographic boundary files 2025 (500k, shoreline-clipped): counties (cb_2025_us_county_500k, PA only), county
  subdivisions (cb_2025_42_cousub_500k: Pennsylvania's cities, boroughs and townships, and Bloomsburg town) and places
  (cb_2025_42_place_500k: cities, boroughs and census-designated places).

Pennsylvania's mailing city is often not the municipality (ACHD's `city` PITTSBURGH with `municipal` MILLVALE; "Bensalem Twp" is
mailed as Bensalem or Feasterville-Trevose), so each listing keeps both: the municipality from the county subdivision its point is
in, the mailing name from its address.

Regions are ours (for the per-region data files and the region filter), by county.

Writes
- pa_counties.geojson   67 counties, full detail, with region
- pa_cousub.geojson     municipalities, full detail, with county and type (city, borough, township, town)
- pa_places.geojson     Census places
- pa_state_detail.geojson  the state outline (for the "outside Pennsylvania" check)
- pa_shapes.json        simplified state and county outlines for the maps
"""
import os, json, zipfile, urllib.request
import duckdb
from shapely import wkb
from shapely.geometry import mapping, Polygon
from shapely.ops import unary_union

PA = os.path.join(os.path.dirname(__file__), "..", "data", "pa")
GEO = os.path.join(PA, "geo")
os.makedirs(GEO, exist_ok=True)
UA = {"User-Agent": "pa-eats data pipeline (nick@eatsranked.com)"}

REGIONS = {
    "Philadelphia": ["Philadelphia"],
    "Philly Suburbs": ["Bucks", "Chester", "Delaware", "Montgomery"],
    "Lehigh Valley": ["Lehigh", "Northampton"],
    "South Central": ["Adams", "Berks", "Cumberland", "Dauphin", "Franklin", "Lancaster", "Lebanon", "Perry", "York"],
    "Northeast & Poconos": ["Carbon", "Lackawanna", "Luzerne", "Monroe", "Pike", "Schuylkill", "Susquehanna", "Wayne", "Wyoming"],
    "Central": ["Bedford", "Blair", "Cambria", "Centre", "Clearfield", "Columbia", "Fulton", "Huntingdon", "Juniata", "Mifflin",
                "Montour", "Northumberland", "Snyder", "Somerset", "Union"],
    "Pittsburgh Region": ["Allegheny", "Armstrong", "Beaver", "Butler", "Fayette", "Greene", "Indiana", "Lawrence", "Washington",
                          "Westmoreland"],
    "Northwest": ["Clarion", "Crawford", "Elk", "Erie", "Forest", "Jefferson", "McKean", "Mercer", "Venango", "Warren"],
    "Northern Tier": ["Bradford", "Cameron", "Clinton", "Lycoming", "Potter", "Sullivan", "Tioga"],
}
REGION_OF = {c: r for r, cs in REGIONS.items() for c in cs}


def get(url, dest):
    if not os.path.exists(dest):
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            open(dest, "wb").write(r.read())
    return dest


for name in ("cb_2025_us_county_500k", "cb_2025_42_cousub_500k", "cb_2025_42_place_500k"):
    z = get(f"https://www2.census.gov/geo/tiger/GENZ2025/shp/{name}.zip", f"{GEO}/{name}.zip")
    if not os.path.exists(f"{GEO}/{name}.shp"):
        zipfile.ZipFile(z).extractall(GEO)

con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial;")
rows = con.execute(f"SELECT NAME, GEOID, ST_AsWKB(geom) FROM ST_Read('{GEO}/cb_2025_us_county_500k.shp') WHERE STATEFP = '42' ORDER BY NAME").fetchall()
counties = [(n, g, wkb.loads(bytes(w)).buffer(0)) for n, g, w in rows]
assert len(counties) == 67 and all(n in REGION_OF for n, _, _ in counties), [n for n, _, _ in counties if n not in REGION_OF]
json.dump({"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"county": n, "geoid": g, "region": REGION_OF[n]}, "geometry": mapping(geom)}
    for n, g, geom in counties]}, open(f"{PA}/pa_counties.geojson", "w"))

rows = con.execute(f"SELECT NAME, NAMELSAD, NAMELSADCO, GEOID, ST_AsWKB(geom) FROM ST_Read('{GEO}/cb_2025_42_cousub_500k.shp') ORDER BY GEOID").fetchall()
subs = []
for n, lsad, co, g, w in rows:
    kind = lsad.split()[-1] if lsad else ""
    subs.append({"type": "Feature", "properties": {"name": n, "kind": kind, "county": co.replace(" County", ""), "geoid": g},
                 "geometry": mapping(wkb.loads(bytes(w)).buffer(0))})
json.dump({"type": "FeatureCollection", "features": subs}, open(f"{PA}/pa_cousub.geojson", "w"))

rows = con.execute(f"SELECT NAME, NAMELSAD, GEOID, ST_AsWKB(geom) FROM ST_Read('{GEO}/cb_2025_42_place_500k.shp') ORDER BY GEOID").fetchall()
pl = [{"type": "Feature", "properties": {"name": n, "kind": lsad.split()[-1] if lsad else "", "geoid": g}, "geometry": mapping(wkb.loads(bytes(w)).buffer(0))}
      for n, lsad, g, w in rows]
json.dump({"type": "FeatureCollection", "features": pl}, open(f"{PA}/pa_places.geojson", "w"))


def rings(geom, tol, min_area, holes=False):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon" and p.area >= min_area]
    r = lambda ring: [[round(x, 4), round(y, 4)] for x, y in ring.coords]
    if holes:
        return [[r(p.exterior)] + [r(h) for h in p.interiors if abs(Polygon(h).area) >= min_area] for p in polys]
    return [r(p.exterior) for p in polys]


state = unary_union([g for _, _, g in counties]).buffer(0)
json.dump(mapping(state.simplify(0.0003, preserve_topology=True)), open(f"{PA}/pa_state_detail.geojson", "w"))
out = {"state": rings(state, 0.002, 0.00005, holes=True),
       "counties": [{"name": n, "region": REGION_OF[n], "c": rings(geom, 0.003, 0.00005)} for n, _, geom in counties]}
json.dump(out, open(f"{PA}/pa_shapes.json", "w"), separators=(",", ":"))
kinds = {}
for s in subs:
    kinds[s["properties"]["kind"]] = kinds.get(s["properties"]["kind"], 0) + 1
print("counties:", len(counties), "| municipalities:", len(subs), kinds, "| census places:", len(pl),
      "| shapes", os.path.getsize(f"{PA}/pa_shapes.json") // 1024, "KB")
