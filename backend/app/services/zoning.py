from __future__ import annotations

import json
import urllib.parse
import urllib.request

from app.config import DATA_DIR
from app.models import BuildingType, DesignRequest, EnvironmentReport, ZoningReport

UA = {"User-Agent": "EcoInfraStudio/1.0"}


def _profiles() -> dict:
    return json.loads((DATA_DIR / "city_zoning.json").read_text(encoding="utf-8"))


def _city_key(location_name: str, admin: str | None) -> str | None:
    blob = f"{location_name} {admin or ''}".lower()
    for key, spec in _profiles()["cities"].items():
        if any(m in blob for m in spec["match"]):
            return key
    return None


def _http_json(url: str, timeout: float = 12.0):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode())


def _nyc_live(lat: float, lon: float, building_type: BuildingType) -> dict | None:
    # Bbox ~250 m. PLUTO residfar / zonedist1 is the mapped district at nearby lots.
    dlat, dlon = 0.0022, 0.0028
    where = (
        f"latitude between {lat - dlat} and {lat + dlat} "
        f"and longitude between {lon - dlon} and {lon + dlon} "
        f"and numfloors > 0"
    )
    params = {
        "$limit": "25",
        "$select": "address,zonedist1,residfar,commfar,builtfar,numfloors,landuse,latitude,longitude",
        "$where": where,
    }
    url = "https://data.cityofnewyork.us/resource/64uk-42ks.json?" + urllib.parse.urlencode(params)
    try:
        rows = _http_json(url)
    except Exception:
        return None
    if not rows:
        return None
    fars = []
    heights = []
    districts = []
    for row in rows:
        try:
            far = float(row.get("residfar") or 0)
            if building_type in {"office", "mixed_use"}:
                far = max(far, float(row.get("commfar") or 0))
            if far > 0:
                fars.append(far)
            fl = float(row.get("numfloors") or 0)
            if fl > 0:
                heights.append(fl * 3.05)
            if row.get("zonedist1"):
                districts.append(str(row["zonedist1"]))
        except (TypeError, ValueError):
            continue
    if not fars:
        return None
    fars.sort()
    heights.sort()
    district = max(set(districts), key=districts.count) if districts else None
    return {
        "district": district,
        "far": fars[len(fars) // 2],
        "height": heights[len(heights) // 2] if heights else None,
        "n": len(rows),
        "source": f"NYC PLUTO live: {len(rows)} lots within ~250 m, district {district or 'unknown'}",
    }


def _apply_profile(base: dict, city: str, building_type: str) -> tuple[dict, str]:
    city_spec = _profiles()["cities"][city]
    overlay = city_spec.get(building_type)
    if not overlay:
        if building_type in {"mixed_use", "office", "community", "apartment"}:
            overlay = city_spec.get("apartment") or city_spec.get("mixed_use") or city_spec.get("single_family")
        else:
            overlay = city_spec.get("duplex") or city_spec.get("single_family")
    merged = dict(base)
    for key in ("front", "rear", "side", "height", "coverage", "far", "green", "stories"):
        if overlay and key in overlay:
            merged[key] = overlay[key]
    note = overlay.get("note", city) if overlay else city
    return merged, note


async def resolve_zoning(req: DesignRequest, env: EnvironmentReport) -> ZoningReport:
    from app.services.compliance import _base_rules

    base = _base_rules(req.building_type)
    city = _city_key(env.location.name, env.location.admin)
    district = None
    source = "IBC-style model code (no city overlay matched)"
    notes: list[str] = []
    rules = dict(base)

    if city:
        rules, note = _apply_profile(rules, city, req.building_type)
        source = f"City overlay: {city.title()} ({note})"
        notes.append(note)

    if city == "new york":
        live = _nyc_live(env.location.latitude, env.location.longitude, req.building_type)
        if live:
            district = live["district"]
            if live["far"]:
                rules["far"] = float(live["far"])
            source = live["source"]
            notes.append(
                f"Live mapped FAR {rules['far']:.2f} from nearby PLUTO lots. "
                "Height/setbacks stay on the city district profile so nearby shorter buildings do not cap a taller legal envelope."
            )

    # Keep climate tweaks after city overlay
    if env.nearby_green_m2 < 12000 or env.tree_cover_score < 40:
        rules["parking"] = rules.get("parking", 1.0) * 0.6
        rules["coverage"] = min(0.85, rules["coverage"] + 0.04)
        rules["front"] = max(0.0, rules["front"] - 0.5)
        notes.append("Urban/low-canopy adjustment applied on top of the city overlay.")
    if env.annual_precip_mm > 1200:
        rules["green"] = min(0.5, rules["green"] + 0.04)
    rules.setdefault("parking", 1.0)

    place = ", ".join(p for p in [env.location.name, env.location.admin, env.location.country] if p)
    return ZoningReport(
        city=city.title() if city else (env.location.name or "Unknown"),
        district=district,
        jurisdiction=place,
        source=source,
        far=round(float(rules["far"]), 2),
        height_m=round(float(rules["height"]), 1),
        coverage=round(float(rules["coverage"]), 2),
        front_m=round(float(rules["front"]), 1),
        rear_m=round(float(rules["rear"]), 1),
        side_m=round(float(rules["side"]), 1),
        stories=int(rules["stories"]),
        green=round(float(rules["green"]), 2),
        notes=notes,
        rules=rules,
    )
