from __future__ import annotations

import json
import sqlite3
from statistics import median

from app.config import DATA_DIR, STOCK_DB
from app.models import BuildingType, StockPeerStats

FT2_TO_M2 = 0.092903
FT_TO_M = 0.3048
# 1 kBtu/ft2 = 3.155 kWh/m2; screening grid factor 0.38 kg/kWh (same as analysis.py)
KBTU_FT2_TO_KWH_M2 = 3.155


def _load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def clf_kg_per_m2(building_type: str) -> float:
    table = _load_json("clf_embodied.json")["by_type_kg_per_m2"]
    return float(table.get(building_type, 330))


def typical_eui(building_type: str, climate_zone: str) -> float:
    table = _load_json("eui_typicals.json")["by_type"]
    row = table.get(building_type) or table["apartment"]
    return float(row.get(climate_zone) or row.get("default") or 54)


def connect() -> sqlite3.Connection:
    STOCK_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(STOCK_DB)
    con.row_factory = sqlite3.Row
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS buildings (
            bbl TEXT PRIMARY KEY,
            address TEXT,
            borough TEXT,
            zipcode TEXT,
            latitude REAL,
            longitude REAL,
            zone_dist TEXT,
            landuse TEXT,
            building_type TEXT,
            year_built INTEGER,
            stories REAL,
            units_res INTEGER,
            lot_area_m2 REAL,
            floor_area_m2 REAL,
            coverage_pct REAL,
            far REAL,
            lot_front_m REAL,
            lot_depth_m REAL,
            site_eui_kbtu_ft2 REAL,
            eui_source TEXT,
            embodied_label_kg REAL,
            embodied_label_source TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_stock_type ON buildings(building_type)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_stock_eui ON buildings(site_eui_kbtu_ft2)")
    con.commit()


def count_rows() -> int:
    if not STOCK_DB.exists():
        return 0
    with connect() as con:
        row = con.execute("SELECT COUNT(*) AS n FROM buildings").fetchone()
        return int(row["n"] if row else 0)


def stats_overview() -> dict:
    if not STOCK_DB.exists():
        return {"n": 0, "n_measured_eui": 0, "by_type": {}}
    with connect() as con:
        n = con.execute("SELECT COUNT(*) AS n FROM buildings").fetchone()["n"]
        n_eui = con.execute(
            "SELECT COUNT(*) AS n FROM buildings WHERE eui_source = 'll84'"
        ).fetchone()["n"]
        by_type = {
            r["building_type"]: r["n"]
            for r in con.execute(
                "SELECT building_type, COUNT(*) AS n FROM buildings GROUP BY building_type"
            )
        }
    return {"n": int(n), "n_measured_eui": int(n_eui), "by_type": by_type, "path": str(STOCK_DB)}


def peer_stats(building_type: BuildingType, climate_zone: str) -> StockPeerStats:
    empty = StockPeerStats(
        n_peers=0,
        n_with_measured_eui=0,
        median_eui_kbtu_ft2=None,
        median_far=None,
        median_stories=None,
        source="No local stock yet. Run: python scripts/import_nyc_stock.py",
    )
    if not STOCK_DB.exists():
        return empty
    with connect() as con:
        rows = con.execute(
            "SELECT far, stories, site_eui_kbtu_ft2, eui_source FROM buildings WHERE building_type = ?",
            (building_type,),
        ).fetchall()
    if not rows:
        return empty
    eui = [r["site_eui_kbtu_ft2"] for r in rows if r["site_eui_kbtu_ft2"] and r["eui_source"] == "ll84"]
    far = [r["far"] for r in rows if r["far"] is not None]
    stories = [r["stories"] for r in rows if r["stories"] is not None]
    measured = len(eui)
    if not eui:
        eui = [typical_eui(building_type, climate_zone)]
    return StockPeerStats(
        n_peers=len(rows),
        n_with_measured_eui=measured,
        median_eui_kbtu_ft2=round(median(eui), 1) if eui else None,
        median_far=round(median(far), 2) if far else None,
        median_stories=round(median(stories), 1) if stories else None,
        source=(
            f"NYC PLUTO massing for {len(rows)} {building_type.replace('_', ' ')} lots; "
            f"{measured} have LL84 measured site EUI. "
            "Embodied labels use CLF typical intensities, not measured LCA."
        ),
    )


def eui_percentile(building_type: str, proposed_eui: float) -> float | None:
    """Share of measured-EUI peers with a *higher* (worse) EUI than proposed."""
    if not STOCK_DB.exists() or proposed_eui <= 0:
        return None
    with connect() as con:
        rows = con.execute(
            """
            SELECT site_eui_kbtu_ft2 FROM buildings
            WHERE building_type = ? AND eui_source = 'll84' AND site_eui_kbtu_ft2 > 1
            """,
            (building_type,),
        ).fetchall()
    vals = [float(r["site_eui_kbtu_ft2"]) for r in rows]
    if len(vals) < 8:
        return None
    better_than = sum(1 for v in vals if v > proposed_eui)
    return round(100.0 * better_than / len(vals), 1)


def estimated_eui_kbtu_ft2(annual_ops_kg: float, floor_m2: float) -> float:
    if floor_m2 <= 0:
        return 0.0
    return round(annual_ops_kg / (0.38 * KBTU_FT2_TO_KWH_M2 * floor_m2), 1)


_KNN_ROWS: dict[str, list[tuple[float, float, float, float]]] = {}


def _knn_rows(building_type: str) -> list[tuple[float, float, float, float]]:
    if building_type in _KNN_ROWS:
        return _KNN_ROWS[building_type]
    rows: list[tuple[float, float, float, float]] = []
    if STOCK_DB.exists():
        with connect() as con:
            fetched = con.execute(
                """
                SELECT stories, far, floor_area_m2, site_eui_kbtu_ft2
                FROM buildings
                WHERE building_type = ? AND eui_source = 'll84'
                  AND site_eui_kbtu_ft2 BETWEEN 8 AND 250
                  AND stories > 0 AND far > 0 AND floor_area_m2 > 50
                """,
                (building_type,),
            ).fetchall()
        rows = [
            (float(r["stories"]), float(r["far"]), float(r["floor_area_m2"]), float(r["site_eui_kbtu_ft2"]))
            for r in fetched
        ]
    _KNN_ROWS[building_type] = rows
    return rows


def predict_eui_knn(
    building_type: str,
    stories: float,
    far: float,
    floor_m2: float,
    k: int = 15,
) -> tuple[float | None, int]:
    """Distance-weighted EUI from measured LL84 peers. Returns (kBtu/ft², n_measured)."""
    import math

    rows = _knn_rows(building_type)
    if len(rows) < 8:
        return None, len(rows)
    scored: list[tuple[float, float]] = []
    log_floor = math.log(max(floor_m2, 50.0))
    for st, peer_far, area, eui in rows:
        ds = (st - stories) / 4.0
        df = (peer_far - far) / 2.0
        da = (math.log(max(area, 50.0)) - log_floor) / 1.5
        dist = (ds * ds + df * df + da * da) ** 0.5
        scored.append((dist, eui))
    scored.sort(key=lambda item: item[0])
    neigh = scored[: min(k, len(scored))]
    weights = [1.0 / (dist + 0.05) for dist, _ in neigh]
    pred = sum(w * eui for w, (_, eui) in zip(weights, neigh)) / sum(weights)
    return round(pred, 1), len(rows)


def map_landuse(landuse: str | None, units_res: int) -> str | None:
    code = (landuse or "").zfill(2)[-2:]
    table = {
        "01": "duplex" if units_res == 2 else "single_family",
        "02": "apartment",
        "03": "apartment",
        "04": "mixed_use",
        "05": "office",
        "08": "community",
    }
    if code == "01" and units_res >= 3:
        return "apartment"
    return table.get(code)
