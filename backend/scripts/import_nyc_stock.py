"""Download NYC PLUTO lots + LL84 energy and store a local SQLite stock.

Run from the backend folder:
    python scripts/import_nyc_stock.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.stock import (  # noqa: E402
    FT2_TO_M2,
    FT_TO_M,
    clf_kg_per_m2,
    connect,
    init_schema,
    map_landuse,
    typical_eui,
)

UA = {"User-Agent": "EcoInfraStudio/1.0 (research importer)"}
PLUTO = "https://data.cityofnewyork.us/resource/64uk-42ks.json"
LL84 = "https://data.cityofnewyork.us/resource/5zyy-y8am.json"


def fetch(url: str, params: dict, retries: int = 3) -> list[dict]:
    q = urllib.parse.urlencode(params, safe="$><='")
    full = f"{url}?{q}"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.loads(res.read().decode())
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed {full}: {last}")


def to_float(value, default=None):
    try:
        if value in (None, "", "Not Available", "NA"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=None):
    n = to_float(value, default)
    return int(n) if n is not None else default


def normalize_bbl(raw) -> str | None:
    if raw is None:
        return None
    text = str(raw).split(";")[0].split(",")[0]
    text = text.replace("-", "").replace(" ", "")
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 10:
        return digits[:10]
    if digits:
        return digits.zfill(10)
    return None


def load_ll84() -> dict[str, float]:
    eui_by_bbl: dict[str, float] = {}
    offset = 0
    page = 5000
    while offset < 40000:
        rows = fetch(
            LL84,
            {
                "$limit": page,
                "$offset": offset,
                "$select": "report_year,nyc_borough_block_and_lot,site_eui_kbtu_ft,weather_normalized_site_eui",
            },
        )
        if not rows:
            break
        for row in rows:
            bbl = normalize_bbl(row.get("nyc_borough_block_and_lot"))
            eui = to_float(row.get("weather_normalized_site_eui")) or to_float(row.get("site_eui_kbtu_ft"))
            if eui is None or eui < 5 or eui > 180:
                continue
            if bbl and bbl not in eui_by_bbl:
                eui_by_bbl[bbl] = eui
        print(f"  LL84 offset {offset}: {len(rows)} rows, unique BBL with EUI {len(eui_by_bbl)}")
        if len(rows) < page:
            break
        offset += page
    return eui_by_bbl


def load_pluto() -> list[dict]:
    fields = (
        "bbl,address,borough,zipcode,zonedist1,landuse,lotarea,bldgarea,numfloors,"
        "unitsres,lotfront,lotdepth,yearbuilt,builtfar,latitude,longitude"
    )
    out = []
    seen = set()
    queries = [
        ("numfloors > 0", 15000),
        ("bldgarea > 20000", 20000),
    ]
    for where, cap in queries:
        offset = 0
        page = 5000
        while offset < cap:
            rows = fetch(
                PLUTO,
                {
                    "$limit": page,
                    "$offset": offset,
                    "$select": fields,
                    "$where": where,
                },
            )
            if not rows:
                break
            for row in rows:
                bbl = row.get("bbl")
                if bbl in seen:
                    continue
                seen.add(bbl)
                out.append(row)
            print(f"  PLUTO {where} offset {offset}: +{len(rows)}, unique {len(out)}")
            if len(rows) < page:
                break
            offset += page
    return out


def main():
    print("Fetching NYC LL84 energy…")
    eui_by_bbl = load_ll84()
    print("Fetching NYC PLUTO lots…")
    lots = load_pluto()

    con = connect()
    init_schema(con)
    con.execute("DELETE FROM buildings")

    inserted = 0
    measured = 0
    for row in lots:
        bbl = normalize_bbl(row.get("bbl"))
        units = to_int(row.get("unitsres"), 0) or 0
        btype = map_landuse(str(row.get("landuse") or ""), units)
        if not bbl or not btype:
            continue
        lot_ft2 = to_float(row.get("lotarea"), 0) or 0
        bldg_ft2 = to_float(row.get("bldgarea"), 0) or 0
        lot_m2 = lot_ft2 * FT2_TO_M2
        floor_m2 = bldg_ft2 * FT2_TO_M2
        if lot_m2 < 40 or floor_m2 < 30:
            continue
        stories = to_float(row.get("numfloors"), 1) or 1
        far = to_float(row.get("builtfar"))
        if far is None and lot_ft2:
            far = bldg_ft2 / lot_ft2
        coverage = 100.0 * min(1.0, (floor_m2 / max(stories, 1)) / lot_m2)
        eui = eui_by_bbl.get(bbl)
        if eui:
            eui_source = "ll84"
            measured += 1
        else:
            eui = typical_eui(btype, "Temperate")
            eui_source = "typical"
        embodied = round(floor_m2 * clf_kg_per_m2(btype), 0)
        con.execute(
            """
            INSERT OR REPLACE INTO buildings VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                bbl,
                row.get("address"),
                row.get("borough"),
                str(row.get("zipcode") or ""),
                to_float(row.get("latitude")),
                to_float(row.get("longitude")),
                row.get("zonedist1"),
                str(row.get("landuse") or ""),
                btype,
                to_int(row.get("yearbuilt")),
                stories,
                units,
                round(lot_m2, 1),
                round(floor_m2, 1),
                round(coverage, 1),
                round(far or 0, 3),
                round((to_float(row.get("lotfront"), 0) or 0) * FT_TO_M, 2),
                round((to_float(row.get("lotdepth"), 0) or 0) * FT_TO_M, 2),
                eui,
                eui_source,
                embodied,
                "clf_typical_intensity",
            ),
        )
        inserted += 1
    con.commit()
    print(f"Stored {inserted} lots ({measured} with LL84 measured EUI) in {ROOT / 'data' / 'building_stock.sqlite'}")


if __name__ == "__main__":
    main()
