from __future__ import annotations

from app.models import BuildingSpec, CostReport, DesignRequest

# Screening construction cost USD per m2 of floor (not a bid).
COST_PER_M2 = {
    "mass_timber": 2900,
    "rammed_earth": 2400,
    "brick": 2700,
    "recycled_steel": 3100,
    "concrete": 2500,
}

TIER_CAP_PER_M2 = {
    "affordable": 2600,
    "standard": 3400,
    "premium": 4600,
}


def estimate_cost_usd(req: DesignRequest, spec: BuildingSpec) -> int:
    floor = spec.width_m * spec.depth_m * spec.stories
    footprint = spec.width_m * spec.depth_m
    total = floor * COST_PER_M2[spec.material]
    if spec.green_roof:
        total += footprint * 190
    if spec.solar_panels:
        total += footprint * 0.40 * 430
    if spec.rain_garden:
        total += 14000
    if spec.ev_charging:
        total += 4000
    if spec.roof_type == "pitched":
        total += footprint * 85
    return int(round(total, -2))


def budget_cap_usd(req: DesignRequest) -> int:
    typical_floor = req.lot_width_m * req.lot_depth_m * 0.32 * max(req.stories, 1)
    typical_floor = max(typical_floor, 90)
    return int(typical_floor * TIER_CAP_PER_M2[req.budget_tier])


def cost_report(req: DesignRequest, spec: BuildingSpec) -> CostReport:
    est = estimate_cost_usd(req, spec)
    cap = budget_cap_usd(req)
    return CostReport(
        estimate_usd=est,
        cap_usd=cap,
        tier=req.budget_tier,
        within_budget=est <= cap * 1.02,
        basis=(
            f"{spec.material.replace('_', ' ')} at ${COST_PER_M2[spec.material]:,}/m² floor, "
            f"plus roof/PV/water adders. {req.budget_tier} cap ${cap:,} "
            f"(~${TIER_CAP_PER_M2[req.budget_tier]:,}/m² × typical floor). Screening, not a contractor bid."
        ),
    )
