from __future__ import annotations

from app.models import (
    BuildingSpec,
    ComplianceCheck,
    ComplianceReport,
    DesignRequest,
    EnvironmentReport,
    ZoningReport,
)


def _base_rules(building_type: str) -> dict:
    table = {
        "single_family": dict(front=5.0, rear=6.0, side=1.5, height=10.5, coverage=0.40, far=0.60, green=0.30, parking=1.0, stories=3),
        "duplex": dict(front=4.5, rear=5.0, side=1.2, height=11.5, coverage=0.45, far=0.80, green=0.25, parking=1.0, stories=3),
        "townhouse": dict(front=3.0, rear=4.5, side=0.0, height=12.5, coverage=0.55, far=1.10, green=0.20, parking=1.0, stories=4),
        "apartment": dict(front=4.0, rear=5.0, side=3.0, height=18.0, coverage=0.50, far=1.80, green=0.20, parking=0.8, stories=6),
        "mixed_use": dict(front=3.0, rear=4.0, side=2.5, height=22.0, coverage=0.60, far=2.40, green=0.15, parking=0.6, stories=7),
        "office": dict(front=5.0, rear=5.0, side=3.0, height=20.0, coverage=0.55, far=2.00, green=0.18, parking=1.5, stories=6),
        "community": dict(front=6.0, rear=6.0, side=3.0, height=12.0, coverage=0.35, far=0.70, green=0.35, parking=2.0, stories=3),
    }
    return dict(table[building_type])


def _rules(req: DesignRequest, env: EnvironmentReport, zoning: ZoningReport | None = None) -> dict:
    if zoning and zoning.rules:
        return dict(zoning.rules)
    urban = env.nearby_green_m2 < 12000 or env.tree_cover_score < 40
    rules = _base_rules(req.building_type)
    if urban:
        rules["parking"] *= 0.6
        rules["coverage"] = min(0.70, rules["coverage"] + 0.05)
        rules["front"] = max(1.5, rules["front"] - 1.0)
    if env.annual_precip_mm > 1200:
        rules["green"] += 0.05
    return rules


def propose_building(req: DesignRequest, env: EnvironmentReport, zoning: ZoningReport | None = None) -> BuildingSpec:
    rules = _rules(req, env, zoning)
    lot_w, lot_d = req.lot_width_m, req.lot_depth_m
    story_h = 3.2 if req.building_type in {"apartment", "office", "mixed_use"} else 3.0
    max_by_height = max(1, int(rules["height"] // story_h))
    stories = min(req.stories, int(rules["stories"]), max_by_height)

    buildable_w = max(4.0, lot_w - 2 * rules["side"])
    buildable_d = max(5.0, lot_d - rules["front"] - rules["rear"])
    lot_area = lot_w * lot_d
    priority = req.green_space_priority / 5.0

    target_coverage = rules["coverage"] * (0.78 + 0.22 * (1 - priority * 0.55))
    target_area = min(buildable_w * buildable_d, lot_area * target_coverage)
    aspect = min(1.45, max(0.75, buildable_w / max(buildable_d, 0.1)))
    depth = min(buildable_d, (target_area / aspect) ** 0.5)
    width = min(buildable_w, target_area / max(depth, 1))
    # Livable rooms need a real envelope
    min_w, min_d = (12.0, 14.0) if req.building_type in {"apartment", "office", "mixed_use"} else (9.5, 11.0)
    width = min(buildable_w, max(width, min_w))
    depth = min(buildable_d, max(depth, min_d))
    # FAR cap
    far_area = rules["far"] * lot_area
    footprint = width * depth
    if footprint * stories > far_area:
        footprint = far_area / stories
        depth = min(buildable_d, (footprint / aspect) ** 0.5)
        width = min(buildable_w, footprint / max(depth, 1))

    green_roof = req.roof_type in {"green", "solar_green"}
    solar = req.solar_panels or req.roof_type in {"solar_green"}
    trees = max(2, int((lot_area - width * depth) / 28) + (3 if req.native_landscaping else 0))
    trees = min(trees, 24)

    return BuildingSpec(
        width_m=round(width, 2),
        depth_m=round(depth, 2),
        stories=stories,
        story_height_m=story_h,
        roof_type=req.roof_type,
        material=req.primary_material,
        setback_front_m=rules["front"],
        setback_rear_m=rules["rear"],
        setback_side_m=rules["side"],
        solar_panels=solar,
        green_roof=green_roof,
        rain_garden=req.rainwater_harvesting,
        tree_count=trees,
        parking_spaces=req.parking_spaces,
        ev_charging=req.ev_charging,
        building_type=req.building_type,
    )


def evaluate_compliance(
    req: DesignRequest,
    spec: BuildingSpec,
    env: EnvironmentReport,
    zoning: ZoningReport | None = None,
) -> ComplianceReport:
    rules = _rules(req, env, zoning)
    lot_area = req.lot_width_m * req.lot_depth_m
    footprint = spec.width_m * spec.depth_m
    height = spec.stories * spec.story_height_m + (1.8 if spec.roof_type == "pitched" else 0.45)
    coverage = footprint / lot_area
    far = (footprint * spec.stories) / lot_area
    remaining = max(0.0, lot_area - footprint)
    green = remaining / lot_area
    if spec.green_roof:
        green += 0.45 * (footprint / lot_area)
    parking_ratio = req.parking_spaces / max(req.units, 1)

    def check(code, title, passed, required, actual, guidance, severity="required"):
        return ComplianceCheck(
            code=code,
            title=title,
            passed=passed,
            required=required,
            actual=actual,
            severity=severity,
            guidance=guidance,
        )

    checks = [
        check(
            "SET-F",
            "Front setback",
            spec.setback_front_m >= rules["front"] - 0.01,
            f"{rules['front']:.1f} m",
            f"{spec.setback_front_m:.1f} m",
            "Keep the buildable envelope behind the front yard line.",
        ),
        check(
            "SET-S",
            "Side setbacks",
            spec.width_m <= req.lot_width_m - 2 * rules["side"] + 0.05,
            f"{rules['side']:.1f} m each side",
            f"{(req.lot_width_m - spec.width_m) / 2:.1f} m",
            "Maintain side yards for light, access, and fire separation.",
        ),
        check(
            "HGT",
            "Maximum height",
            height <= rules["height"] + 0.05,
            f"{rules['height']:.1f} m",
            f"{height:.1f} m",
            "Reduce a story or roof pitch if the envelope is exceeded.",
        ),
        check(
            "COV",
            "Lot coverage",
            coverage <= rules["coverage"] + 0.001,
            f"≤ {rules['coverage']*100:.0f}%",
            f"{coverage*100:.1f}%",
            "Shrink the footprint or add a story within height/FAR limits.",
        ),
        check(
            "FAR",
            "Floor area ratio",
            far <= rules["far"] + 0.001,
            f"≤ {rules['far']:.2f}",
            f"{far:.2f}",
            "Lower floor area or increase unbuilt lot area.",
        ),
        check(
            "GRN",
            "Minimum green / open space",
            green >= rules["green"] - 0.01,
            f"≥ {rules['green']*100:.0f}%",
            f"{min(green, 1)*100:.1f}%",
            "Add landscaping, a green roof, or reduce paving.",
        ),
        check(
            "PRK",
            "Parking provision",
            parking_ratio + 1e-6 >= rules["parking"] * 0.5 or req.building_type in {"townhouse", "apartment", "mixed_use"},
            f"~{rules['parking']:.1f} spaces / unit (context-adjusted)",
            f"{parking_ratio:.2f} spaces / unit",
            "Right-size parking; credit EV-ready spaces and nearby transit.",
            "recommended",
        ),
        check(
            "STR",
            "Stormwater retention",
            spec.rain_garden or spec.green_roof or coverage < 0.35,
            "On-site retention if coverage is high",
            "Rain garden / cistern" if spec.rain_garden else ("Green roof" if spec.green_roof else "None"),
            "Provide a rain garden, cistern, or vegetated roof.",
        ),
        check(
            "MAT",
            "Lower-carbon materials",
            spec.material != "concrete",
            "Prefer timber, earth, brick, or recycled steel",
            spec.material.replace("_", " "),
            "Concrete is allowed but raises embodied carbon substantially.",
            "recommended",
        ),
    ]
    required = [c for c in checks if c.severity == "required"]
    passed_all = all(c.passed for c in required)
    score = int(100 * sum(1 for c in checks if c.passed) / len(checks))
    place = ", ".join(p for p in [env.location.name, env.location.admin, env.location.country] if p)
    if zoning:
        place = zoning.jurisdiction or place
        district = zoning.district or req.building_type.replace("_", " ").title()
        zone = f"{district} · FAR {zoning.far:.2f} · {zoning.city}"
    else:
        zone = f"{req.building_type.replace('_', ' ').title()} / {env.climate_zone}"
    return ComplianceReport(
        jurisdiction=place or "Local model code (IBC-inspired)",
        zone=zone,
        passed=passed_all,
        score=score,
        checks=checks,
    )
