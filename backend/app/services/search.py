from __future__ import annotations

from app.models import (
    BuildingSpec,
    DesignRequest,
    EnvironmentReport,
    Material,
    RoofType,
    SearchCandidate,
    SearchReport,
    ZoningReport,
)
from app.services.analysis import _metrics
from app.services.compliance import _rules, evaluate_compliance, propose_building
from app.services.cost import budget_cap_usd, estimate_cost_usd
from app.services.stock import estimated_eui_kbtu_ft2, eui_percentile, peer_stats, predict_eui_knn

MATERIALS: list[Material] = ["mass_timber", "rammed_earth", "brick", "recycled_steel", "concrete"]
ROOFS: list[RoofType] = ["green", "solar_green", "pitched", "flat"]


def _spec(
    req: DesignRequest,
    env: EnvironmentReport,
    zoning: ZoningReport | None,
    *,
    width: float,
    depth: float,
    stories: int,
    material: Material,
    roof: RoofType,
    solar: bool,
    rain: bool,
) -> BuildingSpec:
    rules = _rules(req, env, zoning)
    lot_area = req.lot_width_m * req.lot_depth_m
    story_h = 3.2 if req.building_type in {"apartment", "office", "mixed_use"} else 3.0
    trees = max(2, int((lot_area - width * depth) / 28) + (3 if req.native_landscaping else 0))
    return BuildingSpec(
        width_m=round(width, 2),
        depth_m=round(depth, 2),
        stories=stories,
        story_height_m=story_h,
        roof_type=roof,
        material=material,
        setback_front_m=rules["front"],
        setback_rear_m=rules["rear"],
        setback_side_m=rules["side"],
        solar_panels=solar or roof == "solar_green",
        green_roof=roof in {"green", "solar_green"},
        rain_garden=rain,
        tree_count=min(trees, 24),
        parking_spaces=req.parking_spaces,
        ev_charging=req.ev_charging,
        building_type=req.building_type,
    )


def _knn(req: DesignRequest, spec: BuildingSpec, lot_area: float) -> tuple[float | None, int]:
    far = (spec.width_m * spec.depth_m * spec.stories) / max(lot_area, 1)
    floor = spec.width_m * spec.depth_m * spec.stories
    return predict_eui_knn(req.building_type, spec.stories, far, floor)


def search_legal_designs(
    req: DesignRequest,
    env: EnvironmentReport,
    zoning: ZoningReport | None = None,
) -> tuple[BuildingSpec, SearchReport]:
    """Legal envelopes only. Score with carbon + KNN energy. Budget is a hard cap."""
    baseline = propose_building(req, env, zoning)
    rules = _rules(req, env, zoning)
    lot_w, lot_d = req.lot_width_m, req.lot_depth_m
    lot_area = lot_w * lot_d
    max_w = max(4.0, lot_w - 2 * rules["side"])
    max_d = max(5.0, lot_d - rules["front"] - rules["rear"])
    story_h = 3.2 if req.building_type in {"apartment", "office", "mixed_use"} else 3.0
    max_stories = min(int(rules["stories"]), max(1, int(rules["height"] // story_h)), 8)
    cap = budget_cap_usd(req)

    wanted = max(1, min(req.stories, max_stories))
    far_per_story = rules["far"] / max(wanted, 1)
    coverages = [
        c
        for c in (0.18, 0.22, 0.28, 0.34, 0.40, 0.48, 0.55)
        if c <= rules["coverage"] + 0.001 and c <= far_per_story + 0.01
    ]
    if not coverages:
        coverages = [min(0.35, rules["coverage"], far_per_story)]
    aspects = (0.85, 1.0, 1.2)
    stories_opts = [wanted]
    materials = list(dict.fromkeys([req.primary_material, *MATERIALS]))
    roofs = list(dict.fromkeys([req.roof_type, *ROOFS]))
    solar_opts = [True, False]
    rain = True

    legal: list[tuple[float, BuildingSpec, float, float, int]] = []
    sampled = 0
    budget_rejected = 0
    knn_n_seen = 0

    def consider(spec: BuildingSpec, pref: float) -> None:
        nonlocal knn_n_seen, budget_rejected
        report = evaluate_compliance(req, spec, env, zoning)
        if not all(c.passed for c in report.checks if c.severity == "required"):
            return
        cost = estimate_cost_usd(req, spec)
        if cost > cap:
            budget_rejected += 1
            return
        impact = _metrics(req, spec, env, conventional=False)
        knn_eui, knn_n = _knn(req, spec, lot_area)
        knn_n_seen = max(knn_n_seen, knn_n)
        energy_term = (knn_eui if knn_eui is not None else estimated_eui_kbtu_ft2(impact.annual_ops_kg_co2e, impact.floor_area_m2)) / 180.0
        score = (
            impact.embodied_kg_co2e / 180000
            + max(impact.net_annual_kg_co2e, 0) / 18000
            + energy_term
            + (cost / max(cap, 1)) * 0.10
            - pref
            - (impact.green_space_pct / 100) * 0.06
        )
        legal.append((score, spec, impact.embodied_kg_co2e, impact.net_annual_kg_co2e, cost))

    for stories in stories_opts:
        for cov in coverages:
            foot = lot_area * cov
            for aspect in aspects:
                depth = min(max_d, (foot / aspect) ** 0.5)
                width = min(max_w, foot / max(depth, 1))
                if width < 7 or depth < 8:
                    continue
                if width * stories * depth > rules["far"] * lot_area + 1:
                    continue
                for material in materials:
                    for roof in roofs:
                        for solar in solar_opts:
                            sampled += 1
                            spec = _spec(
                                req,
                                env,
                                zoning,
                                width=width,
                                depth=depth,
                                stories=stories,
                                material=material,
                                roof=roof,
                                solar=solar,
                                rain=rain,
                            )
                            pref = (
                                (0.08 if spec.material == req.primary_material else 0)
                                + (0.05 if spec.roof_type == req.roof_type else 0)
                                + (0.03 if spec.solar_panels == req.solar_panels else 0)
                            )
                            consider(spec, pref)

    consider(baseline, 0.2)

    ai_method = (
        "Multi-objective search over envelopes that already pass this area's setback, height, "
        "coverage, FAR, open-space, and stormwater checks, then a hard construction-budget cap. "
        "Energy uses a k-nearest-neighbor model on measured NYC LL84 site EUI (stories, FAR, floor area). "
        "The model ranks options; it cannot waive the zoning overlay."
    )

    def empty_report(spec: BuildingSpec, reason: str, n_legal: int) -> SearchReport:
        impact = _metrics(req, spec, env, conventional=False)
        eui = estimated_eui_kbtu_ft2(impact.annual_ops_kg_co2e, impact.floor_area_m2)
        knn_eui, knn_n = _knn(req, spec, lot_area)
        return SearchReport(
            n_sampled=sampled,
            n_legal=n_legal,
            selected_reason=reason,
            proposed_eui_kbtu_ft2=eui,
            eui_percentile=eui_percentile(req.building_type, knn_eui or eui),
            knn_eui_kbtu_ft2=knn_eui,
            knn_n=knn_n,
            budget_rejected=budget_rejected,
            ai_method=ai_method,
            peers=peer_stats(req.building_type, env.climate_zone),
            runners_up=[],
        )

    if not legal:
        return baseline, empty_report(
            baseline,
            "No variant passed both the area zoning overlay and the budget cap; showing the preference envelope for review.",
            0,
        )

    legal.sort(key=lambda row: row[0])
    best_score, best, *_ = legal[0]
    for score, spec, _e, _n, _c in legal:
        if spec.material == req.primary_material and spec.roof_type == req.roof_type and spec.stories == min(req.stories, max_stories):
            if score <= best_score * 1.08:
                best, best_score = spec, score
                break

    best_impact = _metrics(req, best, env, conventional=False)
    eui = estimated_eui_kbtu_ft2(best_impact.annual_ops_kg_co2e, best_impact.floor_area_m2)
    knn_eui, knn_n = _knn(req, best, lot_area)
    peers = peer_stats(req.building_type, env.climate_zone)
    pct = eui_percentile(req.building_type, knn_eui or eui)
    city = zoning.city if zoning else env.location.name
    district = (zoning.district + " ") if zoning and zoning.district else ""

    reason = (
        f"Applied {city} {district}rules (FAR ≤ {rules['far']:.2f}, height ≤ {rules['height']:.1f} m, "
        f"coverage ≤ {rules['coverage']*100:.0f}%). Searched {sampled} envelopes; {len(legal)} were legal "
        f"and within the {req.budget_tier} cap of ${cap:,} ({budget_rejected} over budget). "
        f"Selected {best.stories}-story {best.material.replace('_', ' ')} with a {best.roof_type.replace('_', ' ')} roof "
        f"using the lowest combined embodied carbon, KNN energy, and cost among legal options"
    )
    if best.material == req.primary_material and best.roof_type == req.roof_type:
        reason += " while staying close to your stated preferences"
    reason += "."
    if knn_eui is not None:
        reason += f" KNN predicted site EUI {knn_eui} kBtu/ft² from {knn_n:,} measured LL84 peers of this use type."
    elif pct is not None:
        reason += f" Screening EUI {eui} kBtu/ft² is better than {pct:.0f}% of measured LL84 peers."

    runners: list[SearchCandidate] = []
    seen = set()
    for score, spec, embodied, net, _cost in legal:
        key = (spec.material, spec.roof_type, spec.stories, round(spec.width_m, 1))
        if spec.model_dump() == best.model_dump() or key in seen:
            continue
        seen.add(key)
        runners.append(
            SearchCandidate(
                material=spec.material,
                roof_type=spec.roof_type,
                stories=spec.stories,
                width_m=spec.width_m,
                depth_m=spec.depth_m,
                solar_panels=spec.solar_panels,
                embodied_kg_co2e=embodied,
                net_annual_kg_co2e=net,
                score=round(score, 4),
            )
        )
        if len(runners) >= 3:
            break

    return best, SearchReport(
        n_sampled=sampled,
        n_legal=len(legal),
        selected_reason=reason,
        proposed_eui_kbtu_ft2=eui,
        eui_percentile=pct,
        knn_eui_kbtu_ft2=knn_eui,
        knn_n=knn_n,
        budget_rejected=budget_rejected,
        ai_method=ai_method,
        peers=peers,
        runners_up=runners,
    )
