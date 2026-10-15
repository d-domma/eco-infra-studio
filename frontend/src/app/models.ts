export interface DesignRequest {
  address: string;
  lot_width_m: number;
  lot_depth_m: number;
  building_type: string;
  stories: number;
  units: number;
  bedrooms: number;
  roof_type: string;
  primary_material: string;
  solar_panels: boolean;
  rainwater_harvesting: boolean;
  native_landscaping: boolean;
  ev_charging: boolean;
  parking_spaces: number;
  green_space_priority: number;
  budget_tier: string;
}

export interface GeoLocation {
  name: string;
  latitude: number;
  longitude: number;
  country?: string | null;
  admin?: string | null;
}

export interface EnvironmentReport {
  location: GeoLocation;
  climate_zone: string;
  mean_temp_c: number;
  annual_precip_mm: number;
  annual_solar_kwh_m2: number;
  pm25?: number | null;
  aqi?: number | null;
  nearby_green_m2: number;
  nearby_park_count: number;
  tree_cover_score: number;
  ecological_sensitivity: string;
  notes: string[];
}

export interface ComplianceCheck {
  code: string;
  title: string;
  passed: boolean;
  required: string;
  actual: string;
  severity: 'required' | 'recommended';
  guidance: string;
}

export interface ComplianceReport {
  jurisdiction: string;
  zone: string;
  passed: boolean;
  score: number;
  checks: ComplianceCheck[];
}

export interface ImpactMetrics {
  floor_area_m2: number;
  lot_coverage_pct: number;
  green_space_pct: number;
  embodied_kg_co2e: number;
  annual_ops_kg_co2e: number;
  annual_offset_kg_co2e: number;
  net_annual_kg_co2e: number;
  trees_equivalent: number;
  stormwater_retained_m3: number;
}

export interface BuildingSpec {
  width_m: number;
  depth_m: number;
  stories: number;
  story_height_m: number;
  roof_type: string;
  material: string;
  setback_front_m: number;
  setback_rear_m: number;
  setback_side_m: number;
  solar_panels: boolean;
  green_roof: boolean;
  rain_garden: boolean;
  tree_count: number;
  parking_spaces: number;
  ev_charging: boolean;
  building_type: string;
}

export interface StockPeerStats {
  n_peers: number;
  n_with_measured_eui: number;
  median_eui_kbtu_ft2?: number | null;
  median_far?: number | null;
  median_stories?: number | null;
  source: string;
}

export interface SearchCandidate {
  material: string;
  roof_type: string;
  stories: number;
  width_m: number;
  depth_m: number;
  solar_panels: boolean;
  embodied_kg_co2e: number;
  net_annual_kg_co2e: number;
  score: number;
}

export interface SearchReport {
  n_sampled: number;
  n_legal: number;
  selected_reason: string;
  proposed_eui_kbtu_ft2: number;
  eui_percentile?: number | null;
  knn_eui_kbtu_ft2?: number | null;
  knn_n?: number;
  budget_rejected?: number;
  ai_method?: string;
  peers: StockPeerStats;
  runners_up: SearchCandidate[];
}

export interface ZoningReport {
  city: string;
  district?: string | null;
  jurisdiction: string;
  source: string;
  far: number;
  height_m: number;
  coverage: number;
  front_m: number;
  rear_m: number;
  side_m: number;
  stories: number;
  green: number;
  notes: string[];
}

export interface CostReport {
  estimate_usd: number;
  cap_usd: number;
  tier: string;
  within_budget: boolean;
  basis: string;
}

export interface DesignResult {
  id: string;
  request: DesignRequest;
  environment: EnvironmentReport;
  zoning?: ZoningReport | null;
  cost?: CostReport | null;
  compliance: ComplianceReport;
  proposed: BuildingSpec;
  proposed_impact: ImpactMetrics;
  conventional_impact: ImpactMetrics;
  summary: string;
  recommendations: string[];
  blender_ready: boolean;
  blender_error?: string | null;
  files: Record<string, string>;
  search?: SearchReport | null;
}
