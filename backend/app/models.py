from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BuildingType = Literal[
    "single_family",
    "duplex",
    "townhouse",
    "apartment",
    "mixed_use",
    "office",
    "community",
]
RoofType = Literal["pitched", "flat", "green", "solar_green"]
Material = Literal["mass_timber", "brick", "recycled_steel", "rammed_earth", "concrete"]
BudgetTier = Literal["affordable", "standard", "premium"]


class DesignRequest(BaseModel):
    address: str = Field(..., min_length=2, examples=["Portland, Oregon"])
    lot_width_m: float = Field(18, ge=6, le=200)
    lot_depth_m: float = Field(30, ge=8, le=200)
    building_type: BuildingType = "single_family"
    stories: int = Field(2, ge=1, le=12)
    units: int = Field(1, ge=1, le=80)
    bedrooms: int = Field(3, ge=0, le=20)
    roof_type: RoofType = "green"
    primary_material: Material = "mass_timber"
    solar_panels: bool = True
    rainwater_harvesting: bool = True
    native_landscaping: bool = True
    ev_charging: bool = True
    parking_spaces: int = Field(1, ge=0, le=80)
    green_space_priority: int = Field(4, ge=1, le=5)
    budget_tier: BudgetTier = "standard"


class GeoLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    admin: str | None = None


class EnvironmentReport(BaseModel):
    location: GeoLocation
    climate_zone: str
    mean_temp_c: float
    annual_precip_mm: float
    annual_solar_kwh_m2: float
    pm25: float | None = None
    aqi: float | None = None
    nearby_green_m2: float
    nearby_park_count: int
    tree_cover_score: float
    ecological_sensitivity: str
    notes: list[str]


class ComplianceCheck(BaseModel):
    code: str
    title: str
    passed: bool
    required: str
    actual: str
    severity: Literal["required", "recommended"]
    guidance: str


class ComplianceReport(BaseModel):
    jurisdiction: str
    zone: str
    passed: bool
    score: int
    checks: list[ComplianceCheck]


class ZoningReport(BaseModel):
    city: str
    district: str | None = None
    jurisdiction: str
    source: str
    far: float
    height_m: float
    coverage: float
    front_m: float
    rear_m: float
    side_m: float
    stories: int
    green: float
    notes: list[str] = []
    rules: dict = Field(default_factory=dict)


class CostReport(BaseModel):
    estimate_usd: int
    cap_usd: int
    tier: str
    within_budget: bool
    basis: str


class ImpactMetrics(BaseModel):
    floor_area_m2: float
    lot_coverage_pct: float
    green_space_pct: float
    embodied_kg_co2e: float
    annual_ops_kg_co2e: float
    annual_offset_kg_co2e: float
    net_annual_kg_co2e: float
    trees_equivalent: float
    stormwater_retained_m3: float


class BuildingSpec(BaseModel):
    width_m: float
    depth_m: float
    stories: int
    story_height_m: float
    roof_type: RoofType
    material: Material
    setback_front_m: float
    setback_rear_m: float
    setback_side_m: float
    solar_panels: bool
    green_roof: bool
    rain_garden: bool
    tree_count: int
    parking_spaces: int
    ev_charging: bool
    building_type: BuildingType


class StockPeerStats(BaseModel):
    n_peers: int
    n_with_measured_eui: int
    median_eui_kbtu_ft2: float | None = None
    median_far: float | None = None
    median_stories: float | None = None
    source: str


class SearchCandidate(BaseModel):
    material: Material
    roof_type: RoofType
    stories: int
    width_m: float
    depth_m: float
    solar_panels: bool
    embodied_kg_co2e: float
    net_annual_kg_co2e: float
    score: float


class SearchReport(BaseModel):
    n_sampled: int
    n_legal: int
    selected_reason: str
    proposed_eui_kbtu_ft2: float
    eui_percentile: float | None = None
    knn_eui_kbtu_ft2: float | None = None
    knn_n: int = 0
    budget_rejected: int = 0
    ai_method: str = ""
    peers: StockPeerStats
    runners_up: list[SearchCandidate] = []


class DesignResult(BaseModel):
    id: str
    request: DesignRequest
    environment: EnvironmentReport
    zoning: ZoningReport | None = None
    cost: CostReport | None = None
    compliance: ComplianceReport
    proposed: BuildingSpec
    proposed_impact: ImpactMetrics
    conventional_impact: ImpactMetrics
    summary: str
    recommendations: list[str]
    blender_ready: bool
    blender_error: str | None = None
    files: dict[str, str]
    search: SearchReport | None = None
