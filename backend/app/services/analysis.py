from __future__ import annotations

from app.models import (
    BuildingSpec,
    DesignRequest,
    EnvironmentReport,
    ImpactMetrics,
)

EMBODIED = {
    "mass_timber": 48,
    "brick": 240,
    "recycled_steel": 175,
    "rammed_earth": 32,
    "concrete": 390,
}

OPS = {
    "mass_timber": 28,
    "brick": 34,
    "recycled_steel": 36,
    "rammed_earth": 26,
    "concrete": 40,
}


def _metrics(
    req: DesignRequest,
    spec: BuildingSpec,
    env: EnvironmentReport,
    *,
    conventional: bool = False,
) -> ImpactMetrics:
    lot = req.lot_width_m * req.lot_depth_m
    if conventional:
        footprint = min(lot * 0.55, spec.width_m * spec.depth_m * 1.25)
        stories = spec.stories
        floor = footprint * stories
        material = "concrete"
        green_pct = max(0.08, 1 - footprint / lot - 0.12)
        solar = False
        green_roof = False
        trees = 1
        rain = False
    else:
        footprint = spec.width_m * spec.depth_m
        stories = spec.stories
        floor = footprint * stories
        material = spec.material
        green_pct = max(0.0, (lot - footprint) / lot)
        if spec.green_roof:
            green_pct += 0.35 * (footprint / lot)
        solar = spec.solar_panels
        green_roof = spec.green_roof
        trees = spec.tree_count
        rain = spec.rain_garden

    embodied = floor * EMBODIED[material]
    climate_factor = 1.15 if env.mean_temp_c < 7 or env.mean_temp_c > 21 else 1.0
    ops = floor * OPS[material] * climate_factor
    if green_roof:
        ops *= 0.90
    if req.native_landscaping and not conventional:
        ops *= 0.97

    pv_m2 = 0.0
    if solar:
        pv_m2 = footprint * (0.28 if green_roof else 0.55)
    # ~18% module efficiency, performance ratio 0.8
    pv_kwh = pv_m2 * env.annual_solar_kwh_m2 * 0.18 * 0.80
    offset = pv_kwh * 0.38 + trees * 22 + (40 if green_roof else 0)
    net = ops - offset
    storm = 0.0
    if rain:
        storm += lot * 0.025
    if green_roof:
        storm += footprint * 0.04
    storm += green_pct * lot * 0.01

    return ImpactMetrics(
        floor_area_m2=round(floor, 1),
        lot_coverage_pct=round(100 * footprint / lot, 1),
        green_space_pct=round(100 * min(green_pct, 0.95), 1),
        embodied_kg_co2e=round(embodied, 0),
        annual_ops_kg_co2e=round(ops, 0),
        annual_offset_kg_co2e=round(offset, 0),
        net_annual_kg_co2e=round(net, 0),
        trees_equivalent=round(max(net, 0) / 22, 1),
        stormwater_retained_m3=round(storm, 1),
    )


def summarize(
    req: DesignRequest,
    env: EnvironmentReport,
    proposed: ImpactMetrics,
    conventional: ImpactMetrics,
    passed: bool,
) -> tuple[str, list[str]]:
    saved = conventional.embodied_kg_co2e - proposed.embodied_kg_co2e
    ops_delta = conventional.net_annual_kg_co2e - proposed.net_annual_kg_co2e
    summary = (
        f"A {req.stories}-story {req.building_type.replace('_', ' ')} in {env.location.name} "
        f"is sized to that city's building rules, your budget, and local environmental data. "
        f"Compared with a conventional concrete, high-coverage pattern, this design avoids "
        f"about {saved:,.0f} kg CO₂e in embodied carbon and {ops_delta:,.0f} kg CO₂e per year in net operations. "
        f"{'Required compliance checks passed.' if passed else 'Some required checks failed — review the code report before generating construction files.'}"
    )
    recs = list(env.notes)
    if req.primary_material == "concrete":
        recs.append("Switching the primary structure to mass timber or rammed earth would cut embodied carbon sharply.")
    if env.annual_solar_kwh_m2 > 1200 and not req.solar_panels:
        recs.append("This site has enough solar resource to justify rooftop PV even with a green roof split.")
    if env.nearby_green_m2 < 10000:
        recs.append("Neighborhood canopy is thin — keep as many on-site trees as the setbacks allow.")
    if req.green_space_priority >= 4:
        recs.append("High ecology priority: native understory, a rain garden, and a vegetated roof are included in the Blender model.")
    recs.append("Export the Blender file to refine interiors, then use the STL for a physical massing study.")
    return summary, recs[:8]
