/**
 * TypeScript mirror of ledger/schemas.py (the shared contract). Keep in sync.
 * Conventions: times are minutes after midnight of the service day (may exceed 1440);
 * money is USD per person per month unless a field says `_total`; durations are minutes.
 */

// ---------------------------------------------------------------- enums
export type Day = 'M' | 'T' | 'W' | 'R' | 'F' | 'S' | 'U';
export const ALL_DAYS: Day[] = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
export const WEEKDAYS: Day[] = ['M', 'T', 'W', 'R', 'F'];

export type Mode = 'walk' | 'bus' | 'bike';
export type Provenance = 'observed' | 'estimated' | 'assumed' | 'computed' | 'synthetic' | 'user';
export const PROVENANCES: Provenance[] = ['observed', 'estimated', 'assumed', 'computed', 'synthetic', 'user'];
export type Season = 'fall' | 'winter' | 'spring';
export type Criterion = 'cash' | 'time' | 'late_night' | 'fit';

// ---------------------------------------------------------------- places
export interface Point {
  lat: number;
  lon: number;
  id?: string | null;
}

export type Campus = 'central' | 'north' | 'medical' | 'south' | 'downtown' | 'other';

export interface Building {
  id: string;
  name: string;
  campus: Campus;
  lat: number;
  lon: number;
  aliases: string[];
  source: string;
  hours_note?: string | null;
}

// ---------------------------------------------------------------- routine
export interface Event {
  label: string;
  building_id?: string | null;
  point?: Point | null;
  days: Day[];
  start_min: number;
  end_min: number;
  fixed: boolean;
  source_quote?: string | null;
  provenance: Provenance;
}

export interface ScheduleTemplate {
  id: string;
  name: string;
  description: string;
  slots: Event[][];
  provenance: Provenance;
  source: string;
}

export interface Profile {
  events: Event[];
  template_id?: string | null;
  modes: Mode[];
  rent_cap: number;
  all_in_cap?: number | null;
  bedrooms_min: number;
  household_size: number;
  max_single_trip_min?: number | null;
  needs_parking: boolean;
  pet: boolean;
  hourly_wage?: number | null;
  value_of_time?: number | null;
  value_of_time_range?: [number, number] | null;
  winter_aversion: number;
  late_night_weight: number;
  weights: Partial<Record<Criterion, number>>;
  preferences: Record<string, number>;
  season: Season;
  month?: number | null;
}

// ---------------------------------------------------------------- listings
export interface Fee {
  label: string;
  amount: number;
  period: 'once' | 'monthly' | 'annual';
  per: 'person' | 'unit';
  provenance: Provenance;
  quote?: string | null;
}

export type Utility = 'heat' | 'electric' | 'water' | 'gas' | 'internet' | 'trash';

export interface ListingRoom {
  id: string;
  sqft?: number;
  private_bath?: boolean;
  [k: string]: unknown;
}

/** A photo the team has the right to show (property's own site with permission, or their own). */
export interface ListingPhoto {
  src: string;
  credit: string;
  source_url?: string;
  license?: string;
  /** CSS object-position for the 16:10 crop, e.g. "center 30%" for tall towers */
  position?: string;
}

export interface Listing {
  id: string;
  name: string;
  address?: string | null;
  lat: number;
  lon: number;
  neighborhood?: string | null;
  provenance: 'observed' | 'synthetic';
  source_url?: string | null;
  observed_on?: string | null;
  rent: number;
  rent_basis: 'unit' | 'bed';
  rent_is_range: boolean;
  rent_low?: number | null;
  rent_high?: number | null;
  bedrooms: number;
  baths?: number | null;
  sqft?: number | null;
  rooms: ListingRoom[];
  fees: Fee[];
  utilities_included: Utility[];
  building_type: 'tower' | 'house' | 'duplex' | 'apartment' | 'coop' | 'other';
  year_built?: number | null;
  heating?: 'gas' | 'electric_resistance' | 'heat_pump' | 'steam' | 'unknown' | null;
  furnished?: boolean | null;
  in_unit_laundry?: boolean | null;
  parking_monthly?: number | null;
  pets_allowed?: boolean | null;
  lease_term_months?: number | null;
  lease_start?: string | null;
  amenities: string[];
  notes: string;
  /** co-ops: the charge includes food (compare carefully) */
  board_included?: boolean;
  /** co-ops: required member labor, hours per week */
  member_labor_hours_week?: number | null;
  /** how an observed listing was verified; search_extract = copied from search-engine text, page not loaded */
  verification?: ListingVerification | null;
  /** Licensed photos (API field, merged with /photos/manifest.json client-side). Empty → map thumbnail. */
  photos?: ListingPhoto[];
}

export type ListingVerification = 'page_fetched' | 'search_extract' | 'user_verified';

// ---------------------------------------------------------------- trips
export type LegKind = 'walk' | 'wait' | 'bus' | 'bike';

export interface TripLeg {
  kind: LegKind;
  start_min: number;
  end_min: number;
  route?: string | null;
  agency?: string | null;
  from_name?: string | null;
  to_name?: string | null;
  meters?: number | null;
  /** Ordered (lat, lon) points: bus legs = stop coordinates, walk legs = street-network path. Empty/absent on older engines. */
  path?: [number, number][] | null;
}

export interface Trip {
  feasible: boolean;
  mode: Mode;
  depart_min: number;
  arrive_min: number;
  total_min: number;
  walk_min: number;
  wait_min: number;
  in_vehicle_min: number;
  bike_min: number;
  transfers: number;
  outdoor_after_22_min: number;
  legs: TripLeg[];
  note: string;
}

// ---------------------------------------------------------------- engine outputs
export interface LedgerLine {
  key: string;
  label: string;
  usd_month: number;
  low: number;
  high: number;
  provenance: Provenance;
  note: string;
  in_cash_total: boolean;
}

export interface DayTour {
  day: Day;
  trips: Trip[];
  total_min: number;
  generalized_min: number;
  home_returns: number;
}

export interface CommuteSummary {
  weekly_min: number;
  weekly_generalized_min: number;
  weekly_walk_min: number;
  weekly_wait_min: number;
  weekly_in_vehicle_min: number;
  late_night_outdoor_min: number;
  max_single_trip_min: number;
  tours: DayTour[];
}

export interface ListingEvaluation {
  listing_id: string;
  feasible: boolean;
  violations: string[];
  rank?: number | null;
  score?: number | null;
  criteria: Partial<Record<Criterion, number>>;
  pareto: boolean;
  ledger: LedgerLine[];
  cash_total: number;
  cash_low: number;
  cash_high: number;
  all_in_total: number;
  commute?: CommuteSummary | null;
  explanation_facts: string[];
}

export interface Infeasibility {
  binding_constraint: string;
  eliminated: Record<string, number>;
  minimal_relaxation: Record<string, number>;
  /** constraint -> number of listings restored by applying its minimal relaxation */
  restores?: Record<string, number>;
}

export interface Manifest {
  feeds?: { name: string; valid_from?: string; valid_to?: string; used_service_date?: string; [k: string]: unknown }[];
  assumptions?: Record<string, unknown>;
  engine_version?: string;
  provider?: string;
  warning?: string;
  [k: string]: unknown;
}

export interface EvaluationResult {
  evaluations: ListingEvaluation[];
  value_of_time_used: number;
  value_of_time_derivation: string[];
  warnings: string[];
  infeasibility?: Infeasibility | null;
  baseline_ranking: string[];
  manifest: Manifest;
}

export interface Breakeven {
  a: string;
  b: string;
  parameter: string;
  value: number | null;
  direction: string;
}

export interface RobustnessResult {
  samples: number;
  seed: number;
  p_rank1: Record<string, number>;
  rank_quantiles: Record<string, [number, number, number]>;
  cost_quantiles: Record<string, [number, number, number]>;
  breakevens: Breakeven[];
  drivers: string[];
  mc_standard_error: number;
}

export interface CounterfactualResult {
  a: string;
  b: string;
  feasible: boolean;
  delta_weights: Partial<Record<Criterion, number>>;
  alternative_changes: string[];
}

// ---------------------------------------------------------------- compare / diff (api-level shapes)
export interface LineDiff {
  key: string;
  label: string;
  a: number;
  b: number;
  delta: number;
}

export interface TripDiff {
  day?: Day;
  label?: string;
  a_min?: number;
  b_min?: number;
  delta_min?: number;
  [k: string]: unknown;
}

export interface CompareResult {
  a: ListingEvaluation;
  b: ListingEvaluation;
  line_diffs: LineDiff[];
  trip_diffs: TripDiff[];
  breakevens: Breakeven[];
  facts: string[];
}

export interface RankChange {
  listing_id: string;
  before: number | null;
  after: number | null;
}

export interface DiffDelta {
  cash: number;
  time_h: number;
  late_night: number;
  all_in: number;
}

export interface DiffResult {
  rank_changes: RankChange[];
  deltas: Record<string, DiffDelta>;
  causes: string[];
  top_changed: boolean;
}

// ---------------------------------------------------------------- group mode
export interface Member {
  alias: string;
  profile: Profile;
  budget_cap?: number | null;
  room_values?: Record<string, number> | null;
}

export interface GroupSplit {
  listing_id: string;
  feasible: boolean;
  assignment: Record<string, string>;
  rent: Record<string, number>;
  utility: Record<string, number>;
  envy_matrix: number[][];
  maximin_utility?: number | null;
  equal_split_max_envy?: number | null;
  relaxation: Record<string, number>;
  explanation_facts: string[];
}

export interface GroupResult {
  splits: GroupSplit[];
  ranking: string[];
  warnings: string[];
}

// ---------------------------------------------------------------- AI parsing
export type AiMode = 'live' | 'cached' | 'regex';

export interface ParseScheduleResult {
  events: Event[];
  unparsed: { text: string; reason: string }[];
  needs_confirmation: { event_index: number; field: string; reason: string }[];
  mode: AiMode;
}

export interface ExtractedFact {
  field: string;
  value: string | number | boolean;
  quote: string;
  start: number;
  end: number;
}

export interface ListingFlag {
  rule: string;
  fact_field?: string;
  advice: string;
  [k: string]: unknown;
}

export interface ExtractListingResult {
  facts: ExtractedFact[];
  not_stated: string[];
  flags: ListingFlag[];
  listing_patch: Partial<Listing>;
  mode: AiMode;
}

// ---------------------------------------------------------------- endpoints without a Pydantic model
// (shapes proposed in coordination/requests-frontend.md; rendering is defensive)
export interface Health {
  status: string;
  ai_mode?: AiMode | 'off' | string;
  [k: string]: unknown;
}

export interface DemoProfile {
  id: string;
  name: string;
  description?: string;
  profile: Profile;
  narrative?: string[];
}

export interface MethodAssumption {
  key: string;
  label: string;
  value: number | string;
  unit?: string;
  range?: [number, number] | null;
  provenance: Provenance;
  source?: string;
}

export interface MethodEquation {
  name: string;
  latex: string;
  explanation: string;
}

export interface MethodSource {
  name: string;
  kind: string;
  date?: string;
  valid?: string;
  url?: string;
  license?: string;
  note?: string;
}

export interface MethodsResult {
  sources: MethodSource[];
  assumptions: MethodAssumption[];
  equations: MethodEquation[];
  limitations: string[];
  [k: string]: unknown;
}
