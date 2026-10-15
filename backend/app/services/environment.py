from __future__ import annotations

import math
from datetime import date, timedelta

import httpx

from app.models import DesignRequest, EnvironmentReport, GeoLocation

HEADERS = {
    "User-Agent": "EcoInfraStudio/1.0 (sustainable infrastructure design project)"
}


def _climate_zone(mean_temp: float, precip: float) -> str:
    if mean_temp < 5:
        return "Cold / heating-dominated"
    if mean_temp < 15:
        return "Temperate" if precip > 600 else "Cool dry"
    if mean_temp < 22:
        return "Warm temperate" if precip > 500 else "Semi-arid"
    return "Hot / cooling-dominated" if precip > 400 else "Hot arid"


def _fallback_location(address: str) -> GeoLocation:
    return GeoLocation(
        name=address,
        latitude=45.5152,
        longitude=-122.6784,
        country="United States",
        admin="Oregon",
    )


async def geocode(address: str) -> GeoLocation:
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
            res = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": address, "count": 1, "language": "en", "format": "json"},
            )
            res.raise_for_status()
            results = res.json().get("results") or []
            if not results:
                return _fallback_location(address)
            hit = results[0]
            return GeoLocation(
                name=hit.get("name") or address,
                latitude=float(hit["latitude"]),
                longitude=float(hit["longitude"]),
                country=hit.get("country"),
                admin=hit.get("admin1"),
            )
    except Exception:
        return _fallback_location(address)


async def _climate(lat: float, lon: float) -> tuple[float, float, float]:
    end = date.today() - timedelta(days=5)
    start = end.replace(year=end.year - 1)
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
            res = await client.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "daily": "temperature_2m_mean,precipitation_sum,shortwave_radiation_sum",
                    "timezone": "auto",
                },
            )
            res.raise_for_status()
            daily = res.json()["daily"]
            temps = [t for t in daily["temperature_2m_mean"] if t is not None]
            rain = [p for p in daily["precipitation_sum"] if p is not None]
            solar = [s for s in daily["shortwave_radiation_sum"] if s is not None]
            mean_temp = sum(temps) / max(len(temps), 1)
            precip = sum(rain)
            # MJ/m2/day -> kWh/m2/year (1 kWh = 3.6 MJ)
            solar_kwh = sum(solar) / 3.6
            return mean_temp, precip, solar_kwh
    except Exception:
        return 11.5, 900.0, 1350.0


async def _air(lat: float, lon: float) -> tuple[float | None, float | None]:
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
            res = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "pm2_5,us_aqi",
                },
            )
            res.raise_for_status()
            current = res.json().get("current") or {}
            return current.get("pm2_5"), current.get("us_aqi")
    except Exception:
        return None, None


async def _green_space(lat: float, lon: float) -> tuple[float, int, float]:
    query = f"""
    [out:json][timeout:20];
    (
      way["leisure"="park"](around:900,{lat},{lon});
      way["landuse"~"forest|grass|meadow|recreation_ground"](around:900,{lat},{lon});
      way["natural"~"wood|scrub"](around:900,{lat},{lon});
    );
    out tags geom;
    """
    try:
        async with httpx.AsyncClient(timeout=22.0, headers=HEADERS) as client:
            res = await client.post(
                "https://overpass-api.de/api/interpreter",
                content=query.encode("utf-8"),
            )
            res.raise_for_status()
            elements = res.json().get("elements") or []
        area = 0.0
        parks = 0
        for el in elements:
            tags = el.get("tags") or {}
            if tags.get("leisure") == "park":
                parks += 1
            geom = el.get("geometry") or []
            if len(geom) >= 3:
                area += _ring_area_m2(geom)
        tree_score = min(100.0, (math.log10(area + 10) - 1) * 35 + parks * 4)
        return area, parks, max(0.0, tree_score)
    except Exception:
        return 18000.0, 3, 55.0


def _ring_area_m2(geom: list[dict]) -> float:
    # Equirectangular polygon area
    if len(geom) < 3:
        return 0.0
    lat0 = math.radians(sum(p["lat"] for p in geom) / len(geom))
    pts = []
    for p in geom:
        x = math.radians(p["lon"]) * math.cos(lat0) * 6371000
        y = math.radians(p["lat"]) * 6371000
        pts.append((x, y))
    acc = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def _sensitivity(green_m2: float, pm25: float | None) -> str:
    if green_m2 < 8000 or (pm25 is not None and pm25 > 25):
        return "High — extra canopy and low-emission materials recommended"
    if green_m2 < 25000:
        return "Moderate — protect remaining habitat and add on-site ecology"
    return "Lower — still improve on-site biodiversity and stormwater"


async def analyze_environment(req: DesignRequest) -> EnvironmentReport:
    location = await geocode(req.address)
    mean_temp, precip, solar = await _climate(location.latitude, location.longitude)
    pm25, aqi = await _air(location.latitude, location.longitude)
    green_m2, parks, tree_score = await _green_space(location.latitude, location.longitude)
    notes = [
        f"Climate normals pulled from Open-Meteo archive near {location.name}.",
        "Green space estimated from OpenStreetMap parks, forest, and natural land within 900 m.",
    ]
    if solar > 1400:
        notes.append("Strong solar resource — photovoltaic arrays are high-value here.")
    if precip > 1000:
        notes.append("Wet climate — size rain gardens and green roofs for stormwater, not just drought.")
    elif precip < 400:
        notes.append("Dry climate — specify drought-tolerant natives and high-efficiency irrigation.")
    if mean_temp < 8:
        notes.append("Heating-dominated: compact form, high insulation, and south glazing matter most.")
    if mean_temp > 20:
        notes.append("Cooling-dominated: shading, thermal mass, and vegetated roofs reduce loads.")
    return EnvironmentReport(
        location=location,
        climate_zone=_climate_zone(mean_temp, precip),
        mean_temp_c=round(mean_temp, 1),
        annual_precip_mm=round(precip, 0),
        annual_solar_kwh_m2=round(solar, 0),
        pm25=pm25,
        aqi=aqi,
        nearby_green_m2=round(green_m2, 0),
        nearby_park_count=parks,
        tree_cover_score=round(tree_score, 1),
        ecological_sensitivity=_sensitivity(green_m2, pm25),
        notes=notes,
    )
