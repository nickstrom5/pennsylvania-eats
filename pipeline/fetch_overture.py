"""Download the Overture Maps extract the Pennsylvania pipeline reads -> data/pa/

- overture_pa.parquet   every place Overture addresses to Pennsylvania (any category: restaurants, and the inns, farms, marinas,
                        groceries and gas stations hand-checked places or counters sit in), with the datasets each listing came from

Reads the public Overture bucket over S3 with DuckDB (no account needed). The bounding box is Pennsylvania plus a small margin;
`region = 'PA'` keeps Pennsylvania's own listings (a margin listing from New Jersey, Ohio or Delaware is dropped here). County outlines come
from the Census (pipeline/fetch_geo.py), not from Overture's divisions.
"""
import os, time
import duckdb

RELEASE = "2026-09-23.1"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "pa")
BBOX = "bbox.xmin BETWEEN -80.60 AND -74.60 AND bbox.ymin BETWEEN 39.65 AND 42.35"
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2'; SET threads=4;")
places = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*.parquet"

t = time.time()
if not os.path.exists(f"{OUT}/overture_pa.parquet"):
    con.execute(f"""
COPY (
  SELECT id, names.primary AS name, basic_category AS cat, taxonomy.primary AS tax, confidence,
         operating_status AS status, brand.names.primary AS brand, addresses[1].freeform AS street, addresses[1].locality AS city,
         addresses[1].postcode AS zip, addresses[1].region AS region, ST_Y(geometry) AS lat, ST_X(geometry) AS lon, websites[1] AS web,
         phones[1] AS phone, list_transform(sources, x -> x.dataset) AS ds, list_transform(sources, x -> x.update_time) AS ut,
         len(socials) AS n_soc, len(websites) AS n_web, len(phones) AS n_ph
  FROM read_parquet('{places}', hive_partitioning=1) WHERE {BBOX} AND addresses[1].region = 'PA'
) TO '{OUT}/overture_pa.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    print("places", round(time.time() - t), "s", flush=True)
EAT = "('restaurant','casual_eatery','bar','fast_food_restaurant','coffee_shop','cafe','smoothie_juice_bar','brewery','food_court')"
print(con.execute(f"SELECT count(*), count(*) FILTER (WHERE cat IN {EAT}) FROM '{OUT}/overture_pa.parquet'").fetchall(),
      round(time.time() - t), "s total")
