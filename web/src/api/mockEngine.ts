/**
 * MOCK evaluation engine — a deliberately simple, deterministic stand-in for ledger/engine so the UI
 * is fully interactive offline. It mirrors ledger/pipeline/mock.py (walk = haversine x 1.3 / 1.34 m/s;
 * bus with clock-aligned headways) plus time-of-day headways so schedule edits visibly matter.
 * Results are labeled MOCK everywhere they are shown.
 */
import type {
  Breakeven,
  Building,
  CommuteSummary,
  CompareResult,
  CounterfactualResult,
  Criterion,
  Day,
  DayTour,
  DiffResult,
  EvaluationResult,
  Event,
  Infeasibility,
  LedgerLine,
  Listing,
  ListingEvaluation,
  Mode,
  Point,
  Profile,
  RobustnessResult,
  ScheduleTemplate,
  Trip,
  TripLeg,
} from '../types';
import { ALL_DAYS } from '../types';
import { MOCK_MANIFEST } from './mockData';
import { DAY_LONG, DAY_SHORT, clock, usd, usdRate } from '../lib/format';

// ---------------------------------------------------------------- constants (all "assumed")
const WALK_MPS = 1.34;
const DETOUR = 1.3;
const BUS_KMH = 22;
const BIKE_M_PER_MIN = 250;
const BUFFER = 5;
const W_WALK = 1.5;
const W_WAIT = 2.0;
const W_BIKE = 1.2;
const XFER_PEN = 5;
const WEEKS_PER_MONTH = 52 / 12;
const LATE_USD_PER_MIN = 0.1;
const VOT_SHARE = 0.5;
const DEFAULT_WAGE = 15;

export interface EngineCtx {
  buildings: Map<string, Building>;
  listings: Listing[];
}

export function meters(a: Point, b: Point): number {
  const r = 6371000;
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((b.lon - a.lon) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h)) * DETOUR;
}

/** Straight-line km (no detour) — used by the portal-style baseline. */
export function crowKm(a: Point, b: Point): number {
  return meters(a, b) / DETOUR / 1000;
}

function headway(t: number): number | null {
  const m = ((t % 1440) + 1440) % 1440;
  if (m >= 390 && m < 1140) return 10; // 6:30–19:00
  if (m >= 1140) return 20; // 19:00–24:00
  if (m < 150) return 30; // 0:00–2:30
  return null; // 2:30–6:30 no service
}

function after22(start: number, end: number): number {
  return Math.max(0, end - Math.max(start, 1320));
}

const isNorth = (p: Point) => p.lat > 42.288 && p.lon > -83.73;
const isCentral = (p: Point) => p.lat < 42.282 && p.lat > 42.268 && p.lon > -83.745 && p.lon < -83.728;

function routeFor(a: Point, b: Point): { route: string; agency: string } {
  const n1 = isNorth(a);
  const n2 = isNorth(b);
  if (n1 !== n2 && (isCentral(a) || isCentral(b) || a.lat < 42.288 || b.lat < 42.288)) {
    const lon = Math.min(a.lon, b.lon);
    if (lon < -83.735) return { route: 'CN', agency: 'UM' };
    return { route: 'BB', agency: 'UM' };
  }
  if (n1 && n2) return { route: 'NW', agency: 'UM' };
  const south = Math.min(a.lat, b.lat) < 42.266;
  const east = Math.max(a.lon, b.lon) > -83.715;
  if (south) return { route: '5', agency: 'AAATA' };
  if (east) return { route: '4', agency: 'AAATA' };
  const west = Math.min(a.lon, b.lon) < -83.75;
  if (west) return { route: '30', agency: 'AAATA' };
  return { route: 'OS', agency: 'UM' };
}

interface Place extends Point { name: string }

function walkTrip(o: Place, d: Place, start: number, wMeters: number): Trip {
  const w = wMeters / WALK_MPS / 60;
  return {
    feasible: true, mode: 'walk', depart_min: start, arrive_min: start + w, total_min: w, walk_min: w, wait_min: 0,
    in_vehicle_min: 0, bike_min: 0, transfers: 0, outdoor_after_22_min: after22(start, start + w),
    legs: [{ kind: 'walk', start_min: start, end_min: start + w, from_name: o.name, to_name: d.name, meters: wMeters }], note: '',
  };
}

function bikeTrip(o: Place, d: Place, start: number, m: number): Trip {
  const t = m / BIKE_M_PER_MIN + 2;
  return {
    feasible: true, mode: 'bike', depart_min: start, arrive_min: start + t, total_min: t, walk_min: 0, wait_min: 0,
    in_vehicle_min: 0, bike_min: t, transfers: 0, outdoor_after_22_min: after22(start, start + t),
    legs: [{ kind: 'bike', start_min: start, end_min: start + t, from_name: o.name, to_name: d.name, meters: m }], note: '',
  };
}

/** Bus trip departing (from the door) at or after `t`. Returns null when no service. */
function busDepartAt(o: Place, d: Place, t: number, m: number): Trip | null {
  const hw = headway(t + 4);
  if (hw == null) return null;
  const ride = m / ((BUS_KMH * 1000) / 60);
  const board = Math.ceil((t + 4) / hw) * hw;
  if (headway(board) == null) return null;
  const arr = board + ride + 4;
  const { route, agency } = routeFor(o, d);
  const legs: TripLeg[] = [
    { kind: 'walk', start_min: t, end_min: t + 4, from_name: o.name, to_name: `${route} stop`, meters: 320 },
    { kind: 'wait', start_min: t + 4, end_min: board, from_name: `${route} stop` },
    { kind: 'bus', start_min: board, end_min: board + ride, route, agency, from_name: `${route} stop`, to_name: `${route} stop`, meters: m },
    { kind: 'walk', start_min: arr - 4, end_min: arr, from_name: `${route} stop`, to_name: d.name, meters: 320 },
  ];
  return {
    feasible: true, mode: 'bus', depart_min: t, arrive_min: arr, total_min: arr - t, walk_min: 8, wait_min: board - t - 4,
    in_vehicle_min: ride, bike_min: 0, transfers: 0,
    outdoor_after_22_min: after22(t, board) + after22(arr - 4, arr), legs, note: `${agency === 'UM' ? 'U-M' : 'TheRide'} ${route} every ${hw} min at this hour (mock)`,
  };
}

/** Arrive-by bus: latest aligned departure that arrives >= BUFFER before the deadline; counts a reliability wait of headway/4. */
function busArriveBy(o: Place, d: Place, deadline: number, m: number): Trip | null {
  const ride = m / ((BUS_KMH * 1000) / 60);
  const latestBoard = deadline - BUFFER - 4 - ride;
  const hw = headway(latestBoard);
  if (hw == null) return null;
  const board = Math.floor(latestBoard / hw) * hw;
  if (headway(board) == null) return null;
  const relWait = hw / 4;
  const dep = board - 4 - relWait;
  const arr = board + ride + 4;
  const { route, agency } = routeFor(o, d);
  const legs: TripLeg[] = [
    { kind: 'walk', start_min: dep, end_min: dep + 4, from_name: o.name, to_name: `${route} stop`, meters: 320 },
    { kind: 'wait', start_min: dep + 4, end_min: board, from_name: `${route} stop` },
    { kind: 'bus', start_min: board, end_min: board + ride, route, agency, from_name: `${route} stop`, to_name: `${route} stop`, meters: m },
    { kind: 'walk', start_min: arr - 4, end_min: arr, from_name: `${route} stop`, to_name: d.name, meters: 320 },
  ];
  return {
    feasible: true, mode: 'bus', depart_min: dep, arrive_min: arr, total_min: arr - dep, walk_min: 8, wait_min: relWait,
    in_vehicle_min: ride, bike_min: 0, transfers: 0,
    outdoor_after_22_min: after22(dep, board) + after22(arr - 4, arr), legs,
    note: `${agency === 'UM' ? 'U-M' : 'TheRide'} ${route} every ${hw} min at this hour (mock)`,
  };
}

function genMin(t: Trip, walkPenalty: number): number {
  return t.walk_min * W_WALK * walkPenalty + t.wait_min * W_WAIT + t.in_vehicle_min + t.bike_min * W_BIKE * walkPenalty + t.transfers * XFER_PEN;
}

function bestTrip(o: Place, d: Place, modes: Mode[], when: { arriveBy?: number; departAt?: number }, walkPenalty: number): Trip {
  const m = meters(o, d);
  const opts: Trip[] = [];
  const wDur = m / WALK_MPS / 60;
  const start = when.departAt ?? (when.arriveBy! - BUFFER - wDur);
  opts.push(walkTrip(o, d, start, m));
  if (modes.includes('bike')) {
    const bd = m / BIKE_M_PER_MIN + 2;
    opts.push(bikeTrip(o, d, when.departAt ?? (when.arriveBy! - BUFFER - bd), m));
  }
  if (modes.includes('bus') && m > 1200) {
    const bt = when.departAt != null ? busDepartAt(o, d, when.departAt, m) : busArriveBy(o, d, when.arriveBy!, m);
    if (bt) opts.push(bt);
  }
  opts.sort((a, b) => genMin(a, walkPenalty) - genMin(b, walkPenalty));
  return opts[0];
}

function eventPlace(e: Event, ctx: EngineCtx): Place | null {
  if (e.building_id) {
    const b = ctx.buildings.get(e.building_id);
    return b ? { lat: b.lat, lon: b.lon, name: b.name } : null;
  }
  if (e.point) return { lat: e.point.lat, lon: e.point.lon, name: e.label };
  return null;
}

function walkPenaltyFor(profile: Profile): number {
  const winter = profile.month != null ? [12, 1, 2, 3].includes(profile.month) : profile.season === 'winter';
  return winter ? 1 + 0.3 * profile.winter_aversion : 1;
}

export function commuteFor(home: Place, events: Event[], profile: Profile, ctx: EngineCtx): CommuteSummary {
  const wp = walkPenaltyFor(profile);
  const modes = profile.modes.length ? profile.modes : (['walk'] as Mode[]);
  const tours: DayTour[] = [];
  for (const day of ALL_DAYS) {
    const evs = events
      .filter((e) => e.days.includes(day))
      .map((e) => ({ e, p: eventPlace(e, ctx) }))
      .filter((x): x is { e: Event; p: Place } => x.p != null)
      .sort((a, b) => a.e.start_min - b.e.start_min);
    if (!evs.length) continue;
    const trips: Trip[] = [];
    let homeReturns = 0;
    trips.push(bestTrip(home, evs[0].p, modes, { arriveBy: evs[0].e.start_min }, wp));
    for (let i = 0; i < evs.length - 1; i++) {
      const cur = evs[i];
      const nxt = evs[i + 1];
      const gap = nxt.e.start_min - cur.e.end_min;
      const back = bestTrip(cur.p, home, modes, { departAt: cur.e.end_min }, wp);
      const out = bestTrip(home, nxt.p, modes, { arriveBy: nxt.e.start_min }, wp);
      if (gap > back.total_min + out.total_min + 30) {
        trips.push(back, out);
        homeReturns++;
      } else {
        trips.push(bestTrip(cur.p, nxt.p, modes, { departAt: cur.e.end_min }, wp));
      }
    }
    const last = evs[evs.length - 1];
    trips.push(bestTrip(last.p, home, modes, { departAt: last.e.end_min }, wp));
    tours.push({
      day,
      trips,
      total_min: trips.reduce((s, t) => s + t.total_min, 0),
      generalized_min: trips.reduce((s, t) => s + genMin(t, wp), 0),
      home_returns: homeReturns,
    });
  }
  const sum = (f: (t: Trip) => number) => tours.reduce((s, d) => s + d.trips.reduce((a, t) => a + f(t), 0), 0);
  return {
    weekly_min: sum((t) => t.total_min),
    weekly_generalized_min: tours.reduce((s, d) => s + d.generalized_min, 0),
    weekly_walk_min: sum((t) => t.walk_min),
    weekly_wait_min: sum((t) => t.wait_min),
    weekly_in_vehicle_min: sum((t) => t.in_vehicle_min),
    late_night_outdoor_min: sum((t) => t.outdoor_after_22_min),
    max_single_trip_min: Math.max(0, ...tours.flatMap((d) => d.trips.map((t) => t.total_min))),
    tours,
  };
}

// ---------------------------------------------------------------- money
export function rentPerPerson(l: Listing, profile: Profile): number {
  if (l.rent_basis === 'bed') return l.rent;
  return l.rent / Math.max(1, profile.household_size);
}

function occupants(l: Listing, profile: Profile): number {
  return l.rent_basis === 'bed' ? Math.max(1, l.bedrooms) : Math.max(1, profile.household_size);
}

function seasonOf(profile: Profile): 'fall' | 'winter' | 'spring' {
  if (profile.month != null) {
    if ([12, 1, 2, 3].includes(profile.month)) return 'winter';
    if ([9, 10, 11].includes(profile.month)) return 'fall';
    return 'spring';
  }
  return profile.season;
}

function utilities(l: Listing, profile: Profile, mult = 1): LedgerLine {
  const s = seasonOf(profile);
  const heatBase: Record<string, number> = { tower: 35, apartment: 45, house: 80, duplex: 65, coop: 60, other: 55 };
  const fuel: Record<string, Record<string, number>> = {
    gas: { fall: 0.9, winter: 2.1, spring: 0.5 },
    electric_resistance: { fall: 1.0, winter: 2.6, spring: 0.5 },
    heat_pump: { fall: 0.7, winter: 1.4, spring: 0.45 },
    steam: { fall: 1.0, winter: 2.0, spring: 0.5 },
    unknown: { fall: 1.0, winter: 2.2, spring: 0.55 },
  };
  const inc = new Set(l.utilities_included);
  const old = (l.year_built ?? 1990) < 1940 ? 1.25 : 1;
  const parts: [string, number][] = [];
  if (!inc.has('heat')) parts.push(['heat', heatBase[l.building_type] * fuel[l.heating ?? 'unknown'][s] * old]);
  if (!inc.has('electric')) parts.push(['electric', l.building_type === 'house' ? 70 : 55]);
  if (!inc.has('water')) parts.push(['water', 35]);
  if (!inc.has('internet')) parts.push(['internet', 60]);
  if (!inc.has('gas') && l.heating === 'gas') parts.push(['gas service', 15]);
  const unit = parts.reduce((a, [, v]) => a + v, 0) * mult;
  const pp = unit / occupants(l, profile);
  const note = parts.length
    ? `Not included: ${parts.map(([k]) => k).join(', ')}. ${s[0].toUpperCase()}${s.slice(1)} estimate for a ${l.year_built ?? 'unknown-year'} ${l.building_type} with ${String(l.heating ?? 'unknown').replace('_', ' ')} heat.`
    : 'All utilities included in rent.';
  return { key: 'utilities', label: 'Utilities', usd_month: pp, low: pp * 0.7, high: pp * 1.45, provenance: 'estimated', note, in_cash_total: true };
}

function feesMonthly(l: Listing, profile: Profile): { total: number; note: string } {
  let total = 0;
  const parts: string[] = [];
  const term = l.lease_term_months ?? 12;
  for (const f of l.fees) {
    const per = f.per === 'person' ? 1 : 1 / occupants(l, profile);
    const m = f.period === 'monthly' ? f.amount : f.period === 'annual' ? f.amount / 12 : f.amount / term;
    total += m * per;
    parts.push(`${f.label} ${usd(f.amount)}${f.period === 'monthly' ? '/mo' : f.period === 'annual' ? '/yr' : ' once'}`);
  }
  return { total, note: parts.length ? `${parts.join('; ')}. One-time fees spread over a ${term}-month lease.` : 'No fees listed.' };
}

export function valueOfTime(profile: Profile): { vot: number; derivation: string[] } {
  if (profile.value_of_time != null) {
    if (profile.value_of_time === 0) return { vot: 0, derivation: ['You set value of time to $0/h — cash-only ranking. Hours are still shown.'] };
    return { vot: profile.value_of_time, derivation: [`You set your time at ${usdRate(profile.value_of_time)}/h.`] };
  }
  const wage = profile.hourly_wage ?? DEFAULT_WAGE;
  const vot = VOT_SHARE * wage;
  return {
    vot,
    derivation: [
      profile.hourly_wage != null ? `Your wage: ${usdRate(wage)}/h (you entered it).` : `No wage entered — assumed ${usdRate(wage)}/h (typical campus job).`,
      `Value of time = 50% × ${usdRate(wage)}/h wage = ${usdRate(vot)}/h (common transport-appraisal rule of thumb; adjustable).`,
    ],
  };
}

function fitScore(l: Listing, profile: Profile): number {
  const prefs = Object.entries(profile.preferences).filter(([, v]) => v > 0);
  if (!prefs.length) return 0.5;
  const has = (k: string): boolean => {
    switch (k) {
      case 'in_unit_laundry': return !!l.in_unit_laundry;
      case 'furnished': return !!l.furnished;
      case 'parking': return l.parking_monthly != null;
      case 'pets': return !!l.pets_allowed;
      default: return l.amenities.some((a) => a.toLowerCase().includes(k.replace(/_/g, ' ')));
    }
  };
  const tot = prefs.reduce((s, [, v]) => s + v, 0);
  return prefs.reduce((s, [k, v]) => s + (has(k) ? v : 0), 0) / tot;
}

interface Knobs { vot?: number; utilMult?: number; extraEvents?: Event[] }

export function evaluateOne(l: Listing, profile: Profile, ctx: EngineCtx, knobs: Knobs = {}, voteInfo?: { vot: number }): ListingEvaluation {
  const vot = knobs.vot ?? voteInfo?.vot ?? valueOfTime(profile).vot;
  const home: Place = { lat: l.lat, lon: l.lon, name: 'Home' };
  const events = knobs.extraEvents ? [...profile.events, ...knobs.extraEvents] : profile.events;
  const commute = commuteFor(home, events, profile, ctx);
  const rent = rentPerPerson(l, profile);
  const fees = feesMonthly(l, profile);
  const util = utilities(l, profile, knobs.utilMult ?? 1);
  const prov = l.provenance === 'synthetic' ? 'synthetic' : 'observed';
  const lines: LedgerLine[] = [
    {
      key: 'rent', label: l.rent_basis === 'unit' && profile.household_size > 1 ? `Rent (your 1/${profile.household_size} share)` : 'Rent',
      usd_month: rent, low: l.rent_low != null ? rentPerPerson({ ...l, rent: l.rent_low }, profile) : rent,
      high: l.rent_high != null ? rentPerPerson({ ...l, rent: l.rent_high }, profile) : rent,
      provenance: prov, note: l.provenance === 'synthetic' ? 'Synthetic listing — fictional price.' : `Advertised ${usd(l.rent)}/${l.rent_basis}.`, in_cash_total: true,
    },
    { key: 'fees', label: 'Fees', usd_month: fees.total, low: fees.total, high: fees.total, provenance: l.fees.length ? prov : 'computed', note: fees.note, in_cash_total: true },
    util,
  ];
  const violations: string[] = [];
  if (profile.needs_parking) {
    if (l.parking_monthly == null) violations.push('No parking listed — you need parking.');
    else lines.push({ key: 'parking', label: 'Parking', usd_month: l.parking_monthly, low: l.parking_monthly, high: l.parking_monthly, provenance: prov, note: l.parking_monthly === 0 ? 'Included.' : 'Monthly parking.', in_cash_total: true });
  }
  const bikeUsed = commute.tours.some((d) => d.trips.some((t) => t.mode === 'bike'));
  lines.push({
    key: 'transport_cash', label: 'Bus fares & bike upkeep', usd_month: bikeUsed ? 8 : 0, low: 0, high: bikeUsed ? 15 : 0, provenance: 'assumed',
    note: 'U-M buses are fare-free; TheRide is fare-free for U-M students with an Mcard (verify).' + (bikeUsed ? ' Bike upkeep assumed $8/mo.' : ''), in_cash_total: true,
  });
  const hoursMo = (commute.weekly_generalized_min / 60) * WEEKS_PER_MONTH;
  const vr = profile.value_of_time_range ?? [vot * 0.5, vot * 2];
  lines.push({
    key: 'time_value', label: 'Your time (not cash)', usd_month: hoursMo * vot, low: hoursMo * Math.min(vr[0], vot), high: hoursMo * Math.max(vr[1], vot),
    provenance: 'computed', note: `${(commute.weekly_min / 60).toFixed(1)} h/wk door-to-door → ${hoursMo.toFixed(1)} weighted h/mo × ${usdRate(vot)}/h.`, in_cash_total: false,
  });
  const lateUsd = commute.late_night_outdoor_min * WEEKS_PER_MONTH * LATE_USD_PER_MIN * profile.late_night_weight;
  lines.push({
    key: 'late_night', label: 'Late-night walking (not cash)', usd_month: lateUsd, low: 0, high: lateUsd * 3, provenance: 'assumed',
    note: `${Math.round(commute.late_night_outdoor_min)} min/wk outdoors after 10 PM × $0.10/min × weight ${profile.late_night_weight}.`, in_cash_total: false,
  });
  const cash = lines.filter((x) => x.in_cash_total);
  const cashTotal = cash.reduce((s, x) => s + x.usd_month, 0);
  const allIn = lines.reduce((s, x) => s + x.usd_month, 0);
  if (rent > profile.rent_cap) violations.push(`Rent ${usd(rent)} is above your ${usd(profile.rent_cap)} cap.`);
  if (profile.all_in_cap != null && cashTotal > profile.all_in_cap) violations.push(`All-in cash ${usd(cashTotal)} is above your ${usd(profile.all_in_cap)} cap.`);
  if (profile.pet && l.pets_allowed === false) violations.push('No pets allowed.');
  if (l.bedrooms < profile.bedrooms_min) violations.push(`Only ${l.bedrooms} bedrooms (you need ${profile.bedrooms_min}).`);
  if (profile.household_size > 1 && l.rent_basis === 'unit' && Math.max(1, l.bedrooms) < profile.household_size) violations.push(`${l.bedrooms || 'Studio'} bedroom${l.bedrooms === 1 ? '' : 's'} for ${profile.household_size} people.`);
  if (profile.max_single_trip_min != null && commute.max_single_trip_min > profile.max_single_trip_min) violations.push(`Longest trip ${Math.round(commute.max_single_trip_min)} min exceeds your ${profile.max_single_trip_min}-min limit.`);
  const fit = fitScore(l, profile);
  const score = allIn - (Object.keys(profile.preferences).length ? (fit - 0.5) * 80 : 0);
  return {
    listing_id: l.id, feasible: violations.length === 0, violations, rank: null, score,
    criteria: { cash: cashTotal, time: commute.weekly_generalized_min / 60, late_night: commute.late_night_outdoor_min, fit },
    pareto: false, ledger: lines, cash_total: cashTotal,
    cash_low: cash.reduce((s, x) => s + x.low, 0), cash_high: cash.reduce((s, x) => s + x.high, 0),
    all_in_total: allIn, commute, explanation_facts: [],
  };
}

function facts(e: ListingEvaluation, l: Listing, profile: Profile, best: ListingEvaluation | undefined, ctx: EngineCtx): string[] {
  const out: string[] = [];
  const c = e.commute!;
  out.push(`Your week from here: ${(c.weekly_min / 60).toFixed(1)} h door-to-door (${Math.round(c.weekly_wait_min)} min waiting, ${Math.round(c.weekly_walk_min)} min walking).`);
  let worst: { d: Day; t: Trip } | null = null;
  for (const d of c.tours) for (const t of d.trips) if (!worst || t.total_min > worst.t.total_min) worst = { d: d.day, t };
  if (worst) {
    const bus = worst.t.legs.find((x) => x.kind === 'bus');
    const dest = worst.t.legs[worst.t.legs.length - 1]?.to_name ?? '';
    out.push(`Longest trip: ${DAY_LONG[worst.d]} ${clock(worst.t.depart_min)} → ${dest}, ${Math.round(worst.t.total_min)} min${bus ? ` via ${bus.route}` : ' on foot'}.`);
  }
  if (c.late_night_outdoor_min > 0) out.push(`${Math.round(c.late_night_outdoor_min)} min/wk walking or waiting outdoors after 10 PM.`);
  const util = e.ledger.find((x) => x.key === 'utilities');
  if (util && util.usd_month > 1) out.push(`Utilities ${usd(util.low)}–${usd(util.high)}/mo (estimated band; ${util.note.split('.')[0].toLowerCase()}).`);
  const rent = e.ledger.find((x) => x.key === 'rent')!;
  if (rent.usd_month <= profile.rent_cap) out.push(`Rent is ${usd(profile.rent_cap - rent.usd_month)} under your cap.`);
  if (best && best.listing_id !== e.listing_id && e.feasible) {
    out.push(`All-in it costs ${usd(e.all_in_total - best.all_in_total)}/mo more than #1 — ${usd(e.cash_total - best.cash_total)} cash, ${usd(e.all_in_total - e.cash_total - (best.all_in_total - best.cash_total))} time & late-night.`);
  }
  void l;
  void ctx;
  return out;
}

function mostFrequentBuilding(profile: Profile): string | null {
  const count = new Map<string, number>();
  for (const e of profile.events) if (e.building_id) count.set(e.building_id, (count.get(e.building_id) ?? 0) + e.days.length);
  let best: string | null = null;
  let n = -1;
  for (const [k, v] of count) if (v > n) { best = k; n = v; }
  return best;
}

export function baselineScores(profile: Profile, ctx: EngineCtx, listings: Listing[]): { id: string; rent: number; km: number; score: number }[] {
  const bid = mostFrequentBuilding(profile);
  const b = bid ? ctx.buildings.get(bid) : undefined;
  return listings
    .map((l) => {
      const rent = rentPerPerson(l, profile);
      const km = b ? crowKm(l, b) : 0;
      return { id: l.id, rent, km, score: rent + 100 * km };
    })
    .sort((a, b2) => a.score - b2.score);
}

function infeasibility(evals: ListingEvaluation[], listings: Listing[], profile: Profile): Infeasibility | null {
  if (evals.some((e) => e.feasible)) return null;
  const elim: Record<string, number> = {};
  const key = (v: string) => (v.startsWith('Rent') ? 'rent_cap' : v.startsWith('All-in') ? 'all_in_cap' : v.startsWith('No parking') ? 'needs_parking' : v.startsWith('No pets') ? 'pet' : v.startsWith('Longest') ? 'max_single_trip_min' : 'bedrooms');
  for (const e of evals) for (const v of e.violations) elim[key(v)] = (elim[key(v)] ?? 0) + 1;
  const binding = Object.entries(elim).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'rent_cap';
  const relax: Record<string, number> = {};
  const onlyRent = evals.filter((e) => e.violations.every((v) => key(v) === 'rent_cap'));
  if (onlyRent.length) {
    const rents = onlyRent.map((e) => rentPerPerson(listings.find((l) => l.id === e.listing_id)!, profile)).sort((a, b) => a - b);
    relax.rent_cap = Math.ceil(rents[0] / 10) * 10;
    relax.rent_cap_restores = rents.filter((r) => r <= relax.rent_cap + 100).length;
  }
  const onlyTrip = evals.filter((e) => e.violations.every((v) => key(v) === 'max_single_trip_min'));
  if (onlyTrip.length) relax.max_single_trip_min = Math.ceil(Math.min(...onlyTrip.map((e) => e.commute!.max_single_trip_min)));
  return { binding_constraint: binding, eliminated: elim, minimal_relaxation: relax };
}

export function evaluate(profile: Profile, ctx: EngineCtx, listingIds?: string[] | null): EvaluationResult {
  const listings = listingIds?.length ? ctx.listings.filter((l) => listingIds.includes(l.id)) : ctx.listings;
  const { vot, derivation } = valueOfTime(profile);
  const evals = listings.map((l) => evaluateOne(l, profile, ctx, {}, { vot }));
  const feas = evals.filter((e) => e.feasible).sort((a, b) => (a.score ?? 0) - (b.score ?? 0));
  feas.forEach((e, i) => (e.rank = i + 1));
  for (const e of feas) {
    e.pareto = !feas.some((o) => o !== e && o.criteria.cash! <= e.criteria.cash! && o.criteria.time! <= e.criteria.time! && o.criteria.late_night! <= e.criteria.late_night! &&
      (o.criteria.cash! < e.criteria.cash! || o.criteria.time! < e.criteria.time! || o.criteria.late_night! < e.criteria.late_night!));
  }
  const best = feas[0];
  for (const e of evals) e.explanation_facts = facts(e, listings.find((l) => l.id === e.listing_id)!, profile, best, ctx);
  const ordered = [...feas, ...evals.filter((e) => !e.feasible).sort((a, b) => a.all_in_total - b.all_in_total)];
  const warnings: string[] = ['MOCK mode: travel times come from a simplified model, not real timetables.'];
  if (!profile.events.length) warnings.push('Add your week to see travel costs — ranking is cash-only until then.');
  return {
    evaluations: ordered,
    value_of_time_used: vot,
    value_of_time_derivation: derivation,
    warnings,
    infeasibility: infeasibility(evals, listings, profile),
    baseline_ranking: baselineScores(profile, ctx, listings).map((x) => x.id),
    manifest: MOCK_MANIFEST,
  };
}

// ---------------------------------------------------------------- robustness (Monte Carlo over declared ranges)
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const i = (sorted.length - 1) * q;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

function votBreakeven(a: ListingEvaluation, b: ListingEvaluation, vot: number): Breakeven {
  const ta = (a.criteria.time ?? 0) * WEEKS_PER_MONTH;
  const tb = (b.criteria.time ?? 0) * WEEKS_PER_MONTH;
  const late = (x: ListingEvaluation) => x.ledger.find((l) => l.key === 'late_night')?.usd_month ?? 0;
  const dCash = b.cash_total + late(b) - (a.cash_total + late(a));
  const dT = ta - tb;
  const v = Math.abs(dT) < 1e-6 ? null : dCash / dT;
  let direction: string;
  if (v == null || v < 0 || v > 200) direction = `${b.listing_id} never beats ${a.listing_id} on value of time alone`;
  else if (tb < ta) direction = `${b.listing_id} wins if value_of_time > ${v.toFixed(2)}`;
  else direction = `${b.listing_id} wins if value_of_time < ${v.toFixed(2)}`;
  void vot;
  return { a: a.listing_id, b: b.listing_id, parameter: 'value_of_time', value: v != null && v >= 0 && v <= 200 ? Math.round(v * 100) / 100 : null, direction };
}

function utilBreakeven(a: ListingEvaluation, b: ListingEvaluation): Breakeven {
  const ua = a.ledger.find((l) => l.key === 'utilities')?.usd_month ?? 0;
  const ub = b.ledger.find((l) => l.key === 'utilities')?.usd_month ?? 0;
  const restA = a.all_in_total - ua;
  const restB = b.all_in_total - ub;
  const den = ua - ub;
  const k = Math.abs(den) < 1e-6 ? null : (restB - restA) / den;
  const ok = k != null && k > 0 && k < 5;
  return {
    a: a.listing_id, b: b.listing_id, parameter: 'utility_multiplier', value: ok ? Math.round(k! * 100) / 100 : null,
    direction: ok ? `${b.listing_id} wins if utilities run ${ub < ua ? 'above' : 'below'} ${k!.toFixed(2)}× the estimate` : `utility uncertainty alone never flips ${a.listing_id} vs ${b.listing_id}`,
  };
}

function rentBreakeven(a: ListingEvaluation, b: ListingEvaluation): Breakeven {
  const gap = b.all_in_total - a.all_in_total;
  return { a: a.listing_id, b: b.listing_id, parameter: 'rent_b', value: Math.round(gap), direction: `${b.listing_id} ties if its rent drops by ${usd(gap)}/mo` };
}

export function robustness(profile: Profile, ctx: EngineCtx, templates: ScheduleTemplate[], samples: number, seed: number, listingIds?: string[] | null): RobustnessResult {
  const listings = (listingIds?.length ? ctx.listings.filter((l) => listingIds.includes(l.id)) : ctx.listings);
  const base = evaluate(profile, ctx, listingIds);
  const feasIds = base.evaluations.filter((e) => e.feasible).map((e) => e.listing_id);
  const feasL = listings.filter((l) => feasIds.includes(l.id));
  const vot0 = base.value_of_time_used;
  const vr: [number, number] = profile.value_of_time_range ?? [vot0 * 0.5, Math.max(vot0 * 2, 1)];
  const tpl = profile.template_id ? templates.find((t) => t.id === profile.template_id) : undefined;
  const r = rng(seed);
  const cache = new Map<string, ListingEvaluation>();
  const evalAt = (l: Listing, choice: number[] | null) => {
    const key = `${l.id}|${choice?.join(',') ?? '-'}`;
    let e = cache.get(key);
    if (!e) {
      const extra = choice && tpl ? choice.map((c, i) => tpl.slots[i][c]) : undefined;
      e = evaluateOne(l, profile, ctx, { vot: 1, utilMult: 1, extraEvents: extra });
      cache.set(key, e);
    }
    return e;
  };
  // decompose all-in = (cash - util) + util*u + timeH*v + late
  const parts = (e: ListingEvaluation) => {
    const util = e.ledger.find((x) => x.key === 'utilities')?.usd_month ?? 0;
    const tv = e.ledger.find((x) => x.key === 'time_value')?.usd_month ?? 0; // at vot=1 => hours/mo
    const late = e.ledger.find((x) => x.key === 'late_night')?.usd_month ?? 0;
    return { fixed: e.cash_total - util, util, hrs: tv, late };
  };
  const nominalChoice = tpl ? tpl.slots.map(() => 0) : null;
  const total = (l: Listing, v: number, u: number, ch: number[] | null) => {
    const p = parts(evalAt(l, ch));
    return p.fixed + p.util * u + p.hrs * v + p.late;
  };
  const winnerOf = (v: number, u: number, ch: number[] | null) => {
    let best = '';
    let bv = Infinity;
    for (const l of feasL) {
      const t = total(l, v, u, ch);
      if (t < bv) { bv = t; best = l.id; }
    }
    return best;
  };
  const wins: Record<string, number> = {};
  const ranks: Record<string, number[]> = {};
  const costs: Record<string, number[]> = {};
  feasL.forEach((l) => { wins[l.id] = 0; ranks[l.id] = []; costs[l.id] = []; });
  const nominalWinner = winnerOf(vot0, 1, nominalChoice);
  const flipBy = { vot: 0, util: 0, schedule: 0, combined: 0 };
  let lowVotFlips: number[] = [];
  for (let s = 0; s < samples; s++) {
    const v = vr[0] + (vr[1] - vr[0]) * r();
    const u = 0.75 + 0.6 * r();
    const ch = tpl ? tpl.slots.map((slot) => Math.floor(r() * slot.length)) : null;
    const tot = feasL.map((l) => ({ id: l.id, t: total(l, v, u, ch) })).sort((a, b) => a.t - b.t);
    tot.forEach((x, i) => { ranks[x.id].push(i + 1); costs[x.id].push(x.t); });
    if (tot[0]) {
      wins[tot[0].id]++;
      if (tot[0].id !== nominalWinner) {
        if (winnerOf(v, 1, nominalChoice) !== nominalWinner) { flipBy.vot++; lowVotFlips.push(v); }
        else if (winnerOf(vot0, u, nominalChoice) !== nominalWinner) flipBy.util++;
        else if (ch && winnerOf(vot0, 1, ch) !== nominalWinner) flipBy.schedule++;
        else flipBy.combined++;
      }
    }
  }
  const p_rank1: Record<string, number> = {};
  const rank_quantiles: Record<string, [number, number, number]> = {};
  const cost_quantiles: Record<string, [number, number, number]> = {};
  for (const l of feasL) {
    p_rank1[l.id] = samples ? wins[l.id] / samples : 0;
    const rs = [...ranks[l.id]].sort((a, b) => a - b);
    const cs = [...costs[l.id]].sort((a, b) => a - b);
    rank_quantiles[l.id] = [Math.round(quantile(rs, 0.1)), Math.round(quantile(rs, 0.5)), Math.round(quantile(rs, 0.9))];
    cost_quantiles[l.id] = [quantile(cs, 0.1), quantile(cs, 0.5), quantile(cs, 0.9)];
  }
  const feasEvals = base.evaluations.filter((e) => e.feasible);
  const top = feasEvals[0];
  const breakevens: Breakeven[] = [];
  for (const o of feasEvals.slice(1, 4)) if (top) breakevens.push(votBreakeven(top, o, vot0), utilBreakeven(top, o));
  const name = (id: string) => listings.find((l) => l.id === id)?.name ?? id;
  const drivers: string[] = [];
  const flips = samples - (wins[nominalWinner] ?? 0);
  const fmt = (k: number) => `${k.toLocaleString('en-US')} of ${samples.toLocaleString('en-US')}`;
  if (top) {
    if (flips === 0) drivers.push(`${name(nominalWinner)} is #1 in every sampled semester — no declared uncertainty flips it.`);
    else {
      const ordered = (Object.entries(flipBy) as [keyof typeof flipBy, number][]).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
      for (const [k, n] of ordered) {
        if (k === 'vot') {
          lowVotFlips = lowVotFlips.sort((a, b) => a - b);
          drivers.push(`Value of time flips #1 in ${fmt(n)} semesters (sampled ${usdRate(vr[0])}–${usdRate(vr[1])}/h).`);
        } else if (k === 'util') drivers.push(`Utility costs (0.75×–1.35× the estimate) flip #1 in ${fmt(n)} semesters.`);
        else if (k === 'schedule') drivers.push(`Next semester's schedule (${tpl?.name ?? 'template'}) flips #1 in ${fmt(n)} semesters.`);
        else drivers.push(`Combinations of inputs flip #1 in ${fmt(n)} semesters.`);
      }
    }
  }
  const p = top ? p_rank1[top.listing_id] ?? 0 : 0;
  return { samples, seed, p_rank1, rank_quantiles, cost_quantiles, breakevens, drivers, mc_standard_error: Math.sqrt((p * (1 - p)) / Math.max(1, samples)) };
}

// ---------------------------------------------------------------- compare / counterfactual / diff
export function compare(profile: Profile, ctx: EngineCtx, a: string, b: string): CompareResult {
  const res = evaluate(profile, ctx);
  const ea = res.evaluations.find((e) => e.listing_id === a)!;
  const eb = res.evaluations.find((e) => e.listing_id === b)!;
  const keys = Array.from(new Set([...ea.ledger.map((l) => l.key), ...eb.ledger.map((l) => l.key)]));
  const line_diffs = keys.map((k) => {
    const la = ea.ledger.find((l) => l.key === k);
    const lb = eb.ledger.find((l) => l.key === k);
    const va = la?.usd_month ?? 0;
    const vb = lb?.usd_month ?? 0;
    return { key: k, label: (la ?? lb)!.label, a: va, b: vb, delta: vb - va };
  });
  line_diffs.push({ key: 'all_in', label: 'All-in', a: ea.all_in_total, b: eb.all_in_total, delta: eb.all_in_total - ea.all_in_total });
  const trip_diffs = ALL_DAYS.map((d) => {
    const ta = ea.commute?.tours.find((t) => t.day === d)?.total_min ?? 0;
    const tb = eb.commute?.tours.find((t) => t.day === d)?.total_min ?? 0;
    return { day: d, label: DAY_SHORT[d], a_min: ta, b_min: tb, delta_min: tb - ta };
  }).filter((x) => x.a_min || x.b_min);
  const breakevens = [votBreakeven(ea, eb, res.value_of_time_used), utilBreakeven(ea, eb), rentBreakeven(ea, eb)];
  const nm = (id: string) => ctx.listings.find((l) => l.id === id)?.name ?? id;
  const bigLine = [...line_diffs].filter((l) => l.key !== 'all_in').sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta))[0];
  const facts = [
    `${nm(b)} costs ${usd(Math.abs(eb.all_in_total - ea.all_in_total))}/mo ${eb.all_in_total > ea.all_in_total ? 'more' : 'less'} all-in than ${nm(a)}.`,
    bigLine ? `Biggest difference: ${bigLine.label.toLowerCase()} (${bigLine.delta > 0 ? '+' : '−'}${usd(Math.abs(bigLine.delta))}/mo).` : '',
    `Weekly travel: ${((ea.commute?.weekly_min ?? 0) / 60).toFixed(1)} h vs ${((eb.commute?.weekly_min ?? 0) / 60).toFixed(1)} h.`,
  ].filter(Boolean);
  return { a: ea, b: eb, line_diffs, trip_diffs, breakevens, facts };
}

export function counterfactual(profile: Profile, ctx: EngineCtx, a: string, b: string): CounterfactualResult {
  const c = compare(profile, ctx, a, b);
  const gap = c.b.all_in_total - c.a.all_in_total;
  const changes: string[] = [];
  if (gap > 0) changes.push(`${b} wins if its rent drops by ${usd(gap)}/mo`);
  const vb = c.breakevens[0];
  if (vb.value != null) changes.push(vb.direction.replace('value_of_time', 'your time is worth').replace(/(\d+\.\d\d)$/, '$$$1/h'));
  const tv = (e: ListingEvaluation) => e.ledger.find((l) => l.key === 'time_value')?.usd_month ?? 0;
  const dT = tv(c.b) - tv(c.a);
  const dRest = gap - dT;
  const k = Math.abs(dT) > 1e-6 ? -dRest / dT : null;
  const wt = profile.weights.time ?? 0.35;
  const delta_weights: Partial<Record<Criterion, number>> = k != null && k > 0 ? { time: Math.round((k - 1) * wt * 1000) / 1000 } : {};
  return { a, b, feasible: c.a.feasible && c.b.feasible, delta_weights, alternative_changes: changes };
}

function describeProfileChanges(before: Profile, after: Profile, ctx: EngineCtx): string[] {
  const out: string[] = [];
  const bname = (id?: string | null) => (id ? ctx.buildings.get(id)?.name ?? id : 'a custom place');
  const sig = (e: Event) => `${e.label}|${e.building_id}|${e.days.join('')}|${e.start_min}|${e.end_min}`;
  const bs = before.events.map(sig);
  const as = after.events.map(sig);
  const removed = before.events.filter((e) => !as.includes(sig(e)));
  const added = after.events.filter((e) => !bs.includes(sig(e)));
  const used = new Set<Event>();
  for (const r of removed) {
    const m = added.find((a) => !used.has(a) && a.label === r.label);
    if (m) {
      used.add(m);
      const dayStr = m.days.map((d) => DAY_SHORT[d]).join('/');
      if (m.start_min !== r.start_min || m.end_min !== r.end_min) out.push(`You moved “${m.label}” (${dayStr}) from ${clock(r.start_min)}–${clock(r.end_min)} to ${clock(m.start_min)}–${clock(m.end_min)}.`);
      if (m.building_id !== r.building_id) out.push(`You moved “${m.label}” from ${bname(r.building_id)} to ${bname(m.building_id)}.`);
      if (m.days.join() !== r.days.join()) out.push(`“${m.label}” now meets ${dayStr} (was ${r.days.map((d) => DAY_SHORT[d]).join('/')}).`);
    } else out.push(`You removed “${r.label}” at ${bname(r.building_id)}.`);
  }
  for (const a of added) if (!used.has(a)) out.push(`You added “${a.label}” at ${bname(a.building_id)} (${a.days.map((d) => DAY_SHORT[d]).join('/')} ${clock(a.start_min)}).`);
  if (before.season !== after.season || before.month !== after.month) out.push(`Season changed: ${before.season} → ${after.season}${after.season === 'winter' ? ' (walking minutes weigh more; heating bands widen)' : ''}.`);
  const vb = valueOfTime(before).vot;
  const va = valueOfTime(after).vot;
  if (Math.abs(vb - va) > 0.005) out.push(`Value of time ${usdRate(vb)}/h → ${usdRate(va)}/h${va === 0 ? ' (cash only)' : ''}.`);
  if (before.rent_cap !== after.rent_cap) out.push(`Rent cap ${usd(before.rent_cap)} → ${usd(after.rent_cap)}.`);
  if (before.modes.join() !== after.modes.join()) out.push(`Travel modes: ${before.modes.join(' + ')} → ${after.modes.join(' + ') || 'none'}.`);
  if (before.household_size !== after.household_size) out.push(`Household ${before.household_size} → ${after.household_size} people.`);
  if (before.needs_parking !== after.needs_parking) out.push(after.needs_parking ? 'You now need parking.' : 'You no longer need parking.');
  if (before.pet !== after.pet) out.push(after.pet ? 'You now have a pet.' : 'No pet now.');
  if (before.late_night_weight !== after.late_night_weight) out.push(`Late-night weight ${before.late_night_weight} → ${after.late_night_weight}.`);
  if (before.winter_aversion !== after.winter_aversion) out.push(`Winter aversion ${before.winter_aversion} → ${after.winter_aversion}.`);
  return out;
}

export function diff(before: Profile, after: Profile, ctx: EngineCtx, listingIds?: string[] | null): DiffResult {
  const rb = evaluate(before, ctx, listingIds);
  const ra = evaluate(after, ctx, listingIds);
  const ids = ra.evaluations.map((e) => e.listing_id);
  const rank_changes = ids.map((id) => ({
    listing_id: id,
    before: rb.evaluations.find((e) => e.listing_id === id)?.rank ?? null,
    after: ra.evaluations.find((e) => e.listing_id === id)?.rank ?? null,
  }));
  const deltas: DiffResult['deltas'] = {};
  for (const id of ids) {
    const b = rb.evaluations.find((e) => e.listing_id === id)!;
    const a = ra.evaluations.find((e) => e.listing_id === id)!;
    deltas[id] = {
      cash: a.cash_total - b.cash_total,
      time_h: ((a.commute?.weekly_min ?? 0) - (b.commute?.weekly_min ?? 0)) / 60,
      late_night: (a.commute?.late_night_outdoor_min ?? 0) - (b.commute?.late_night_outdoor_min ?? 0),
      all_in: a.all_in_total - b.all_in_total,
    };
  }
  const causes = describeProfileChanges(before, after, ctx);
  const nm = (id: string) => ctx.listings.find((l) => l.id === id)?.name ?? id;
  const topB = rb.evaluations.find((e) => e.rank === 1);
  const topA = ra.evaluations.find((e) => e.rank === 1);
  const top_changed = (topB?.listing_id ?? null) !== (topA?.listing_id ?? null);
  // trip-level cause for the most-moved listing
  const moved = Object.entries(deltas).sort((x, y) => Math.abs(y[1].all_in) - Math.abs(x[1].all_in))[0];
  if (moved && Math.abs(moved[1].all_in) >= 1) {
    const b = rb.evaluations.find((e) => e.listing_id === moved[0])!;
    const a = ra.evaluations.find((e) => e.listing_id === moved[0])!;
    let bestDay: Day | null = null;
    let bestD = 0;
    for (const d of ALL_DAYS) {
      const tb = b.commute?.tours.find((t) => t.day === d);
      const ta = a.commute?.tours.find((t) => t.day === d);
      const dd = (ta?.total_min ?? 0) - (tb?.total_min ?? 0);
      if (Math.abs(dd) > Math.abs(bestD)) { bestD = dd; bestDay = d; }
    }
    if (bestDay) {
      const tb = b.commute!.tours.find((t) => t.day === bestDay);
      const ta = a.commute!.tours.find((t) => t.day === bestDay);
      const dw = (ta?.trips.reduce((s, t) => s + t.wait_min, 0) ?? 0) - (tb?.trips.reduce((s, t) => s + t.wait_min, 0) ?? 0);
      const routes = Array.from(new Set((ta ?? tb)!.trips.flatMap((t) => t.legs.filter((l) => l.kind === 'bus').map((l) => l.route))));
      causes.push(`From ${nm(moved[0])}, ${DAY_LONG[bestDay]} door-to-door ${bestD > 0 ? '+' : '−'}${Math.abs(Math.round(bestD))} min${Math.abs(dw) >= 1 ? ` (${dw > 0 ? '+' : '−'}${Math.abs(Math.round(dw))} min waiting${routes.length ? ` for ${routes.join('/')}` : ''})` : ''}.`);
    } else if (Math.abs(moved[1].cash) >= 1) {
      causes.push(`${nm(moved[0])}: cash ${moved[1].cash > 0 ? '+' : '−'}${usd(Math.abs(moved[1].cash))}/mo.`);
    }
  }
  if (top_changed && topA) {
    const was = rb.evaluations.find((e) => e.listing_id === topA.listing_id)?.rank;
    causes.push(`New #1: ${nm(topA.listing_id)}${was ? ` (was #${was})` : ' (newly feasible)'}${topB ? ` — now ${usd(ra.evaluations.find((e) => e.listing_id === topB.listing_id)!.all_in_total - topA.all_in_total)}/mo cheaper all-in than ${nm(topB.listing_id)}` : ''}.`);
  } else if (topA) causes.push(`#1 stays ${nm(topA.listing_id)}.`);
  return { rank_changes, deltas, causes, top_changed };
}
