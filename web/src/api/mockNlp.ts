/**
 * Offline "regex mode" parsers used by the MOCK layer (and conceptually by the API's AI-off fallback).
 * Every event keeps an exact substring of the input as its source_quote.
 */
import type { Building, Day, Event, ExtractListingResult, ExtractedFact, ListingFlag, ParseScheduleResult } from '../types';

// ---------------------------------------------------------------- schedule
const DAY_WORDS: [RegExp, Day[]][] = [
  [/\bweek\s?nights?\b/i, ['M', 'T', 'W', 'R']],
  [/\bweekdays?\b/i, ['M', 'T', 'W', 'R', 'F']],
  [/\bweekends?\b/i, ['S', 'U']],
  [/\b(daily|every\s?day)\b/i, ['M', 'T', 'W', 'R', 'F', 'S', 'U']],
  [/\bmon(day)?s?\b/i, ['M']],
  [/\btue(s|sday)?s?\b/i, ['T']],
  [/\bwed(nesday)?s?\b/i, ['W']],
  [/\bthu(rs|rsday)?s?\b/i, ['R']],
  [/\bfri(day)?s?\b/i, ['F']],
  [/\bsat(urday)?s?\b/i, ['S']],
  [/\bsun(day)?s?\b/i, ['U']],
];

/** Compact codes: MWF, TTh, TuTh, TR, MW, MTWR, MTWThF. */
const COMPACT = /\b((?:M|Tu|T|W|Th|R|F|Sa|Su)(?:\/?(?:M|Tu|T|W|Th|R|F|Sa|Su)){1,6})\b/;

function compactDays(code: string): Day[] | null {
  const toks = code.replace(/\//g, '').match(/Tu|Th|Sa|Su|M|T|W|R|F/g);
  if (!toks || toks.join('') !== code.replace(/\//g, '')) return null;
  const map: Record<string, Day> = { M: 'M', Tu: 'T', T: 'T', W: 'W', Th: 'R', R: 'R', F: 'F', Sa: 'S', Su: 'U' };
  const ds = toks.map((t) => map[t]);
  return Array.from(new Set(ds));
}

export function parseDays(s: string): { days: Day[]; spans: [number, number][] } {
  const days = new Set<Day>();
  const spans: [number, number][] = [];
  const c = COMPACT.exec(s);
  if (c) {
    const d = compactDays(c[1]);
    if (d && (d.length > 1 || c[1].length > 1)) {
      d.forEach((x) => days.add(x));
      spans.push([c.index, c.index + c[1].length]);
    }
  }
  for (const [re, ds] of DAY_WORDS) {
    const g = new RegExp(re.source, 'gi');
    let m: RegExpExecArray | null;
    while ((m = g.exec(s))) {
      ds.forEach((x) => days.add(x));
      spans.push([m.index, m.index + m[0].length]);
    }
  }
  // ranges like "Mon-Thu" / "Mon to Fri"
  const rng = /\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s*(?:-|–|to|through)\s*(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b/i.exec(s);
  if (rng) {
    const order: Day[] = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
    const idx = (w: string) => ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].indexOf(w.toLowerCase());
    const a = idx(rng[1]);
    const b = idx(rng[2]);
    if (a >= 0 && b >= a) for (let i = a; i <= b; i++) days.add(order[i]);
  }
  const order: Day[] = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
  return { days: order.filter((d) => days.has(d)), spans };
}

function toMin(h: number, m: number, suf: string | undefined, isEnd: boolean, startMin?: number): number {
  let hh = h % 12;
  const s = suf?.toLowerCase();
  if (s?.startsWith('p')) hh += 12;
  else if (s?.startsWith('a')) {
    if (h === 12) hh = 0;
  } else if (h === 12) hh = 12;
  else if (h >= 1 && h <= 6 && !isEnd) hh = h + 12; // "2" without am/pm -> 2 PM
  else hh = h;
  let v = hh * 60 + m;
  if (s?.startsWith('a') && hh < 6) v += 1440; // after midnight belongs to the service day
  if (isEnd && startMin != null) {
    while (v <= startMin && v + 720 <= startMin + 900) v += 720;
    if (v <= startMin) v += 1440;
  }
  return v;
}

const TIME = String.raw`(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|a|p)?`;
const RANGE = new RegExp(String.raw`\b(?:from\s+)?${TIME}\s*(?:-|–|—|to|until|till)\s*${TIME}`, 'i');
const UNTIL = new RegExp(String.raw`\b(?:until|till|til)\s+${TIME}`, 'i');
const AT = new RegExp(String.raw`\b(?:at|@)\s+${TIME}`, 'i');
const BARE = /\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?|\b(\d{1,2})\s*(am|pm)\b/i;
const NOON = /\bnoon\b/i;
const MIDNIGHT = /\bmidnight\b/i;

export function parseTimes(raw: string): { start?: number; end?: number; spans: [number, number][]; missing?: 'start' | 'end' } {
  const s = raw.replace(NOON, '12pm').replace(MIDNIGHT, '12am');
  const r = RANGE.exec(s);
  if (r) {
    let suf1 = r[3];
    const suf2 = r[6];
    const h1 = Number(r[1]);
    const h2 = Number(r[4]);
    if (!suf1 && suf2 && h1 <= h2 && h2 !== 12) suf1 = suf2; // "9-11am"
    const start = toMin(h1, Number(r[2] ?? 0), suf1, false);
    const end = toMin(h2, Number(r[5] ?? 0), suf2, true, start);
    if (end > start && h1 <= 24 && h2 <= 24) return { start, end, spans: [[r.index, r.index + r[0].length]] };
  }
  const u = UNTIL.exec(s);
  if (u) {
    const end = toMin(Number(u[1]), Number(u[2] ?? 0), u[3] ?? (Number(u[1]) <= 4 ? 'am' : undefined), true, 1080);
    return { start: Math.max(420, Math.min(end - 120, 1200)), end, spans: [[u.index, u.index + u[0].length]], missing: 'start' };
  }
  const a = AT.exec(s);
  if (a) {
    const start = toMin(Number(a[1]), Number(a[2] ?? 0), a[3], false);
    return { start, end: start + 60, spans: [[a.index, a.index + a[0].length]], missing: 'end' };
  }
  const bare = BARE.exec(s);
  if (bare) {
    const start = bare[1] ? toMin(Number(bare[1]), Number(bare[2] ?? 0), bare[3], false) : toMin(Number(bare[4]), 0, bare[5], false);
    return { start, end: start + 60, spans: [[bare.index, bare.index + bare[0].length]], missing: 'end' };
  }
  return { spans: [] };
}

export function findBuilding(s: string, buildings: Building[]): { b: Building; span: [number, number] } | null {
  let best: { b: Building; span: [number, number]; len: number } | null = null;
  const prep = (i: number) => /\b(in|at)\s+$/i.test(s.slice(Math.max(0, i - 4), i));
  for (const b of buildings) {
    for (const alias of [b.name, b.id, ...b.aliases]) {
      if (alias.length < 2) continue;
      const esc = alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const re = new RegExp(`(^|[^A-Za-z])(${esc})(?![A-Za-z])`, alias.length <= 3 && alias === alias.toUpperCase() ? '' : 'i');
      const m = re.exec(s);
      if (m) {
        const st = m.index + m[1].length;
        const sc = alias.length + (prep(st) ? 10 : 0);
        if (!best || sc > best.len) best = { b, span: [st, st + m[2].length], len: sc };
      }
    }
  }
  return best ? { b: best.b, span: best.span } : null;
}

function splitClauses(text: string): [number, number][] {
  const out: [number, number][] = [];
  const re = /[^\n;.]+(?:\.(?=\d)[^\n;.]*)*/g; // keep "10.30"
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    // further split on ", and " / " and then " / ", plus "
    const chunk = m[0];
    const parts = chunk.split(/,\s*(?:and\s+|plus\s+|then\s+)|\s+and then\s+|,\s+(?=[A-Z])/);
    const off = m.index;
    let cursor = 0;
    for (const p of parts) {
      const i = chunk.indexOf(p, cursor);
      cursor = i + p.length;
      const lead = p.length - p.trimStart().length;
      const t = p.trim();
      if (t.length >= 3) out.push([off + i + lead, off + i + lead + t.length]);
    }
  }
  return out;
}

const FILLER = /\b(in|at|on|the|from|every|each|most|usually|i have|i've got|i work|my|a|an|and|with|until|till|@|class|s)\b/gi;

export function parseSchedule(text: string, buildings: Building[]): ParseScheduleResult {
  const events: Event[] = [];
  const unparsed: ParseScheduleResult['unparsed'] = [];
  const needs: ParseScheduleResult['needs_confirmation'] = [];
  for (const [a, z] of splitClauses(text)) {
    const clause = text.slice(a, z);
    const bld = findBuilding(clause, buildings);
    const t = parseTimes(clause);
    const d = parseDays(clause);
    if (!bld) {
      if (t.start != null || d.days.length) unparsed.push({ text: clause, reason: 'No known campus building or place — add it in the grid.' });
      continue;
    }
    if (t.start == null || t.end == null) {
      unparsed.push({ text: clause, reason: 'No time found — drag a block onto the grid.' });
      continue;
    }
    // label: remove recognised spans
    const spans = [...t.spans, ...d.spans, bld.span].sort((x, y) => x[0] - y[0]);
    let label = '';
    let cur = 0;
    for (const [s0, s1] of spans) {
      if (s0 > cur) label += clause.slice(cur, s0) + ' ';
      cur = Math.max(cur, s1);
    }
    label += clause.slice(cur);
    label = label.replace(FILLER, ' ').replace(/[,:()–-]+/g, ' ').replace(/\s+/g, ' ').trim();
    if (label.length < 2) label = bld.b.name;
    label = label[0].toUpperCase() + label.slice(1);
    const idx = events.length;
    const days = d.days.length ? d.days : (['M', 'T', 'W', 'R', 'F'] as Day[]);
    if (!d.days.length) needs.push({ event_index: idx, field: 'days', reason: 'No days found — assumed weekdays.' });
    if (t.missing) needs.push({ event_index: idx, field: t.missing === 'start' ? 'start_min' : 'end_min', reason: t.missing === 'start' ? 'Only an end time was given — start guessed.' : 'Only a start time was given — assumed 1 hour.' });
    events.push({ label, building_id: bld.b.id, point: null, days, start_min: t.start, end_min: t.end, fixed: true, source_quote: clause, provenance: 'estimated' });
  }
  return { events: events.slice(0, 40), unparsed, needs_confirmation: needs, mode: 'regex' };
}

// ---------------------------------------------------------------- listing extraction
interface Rule { field: string; re: RegExp; value: (m: RegExpExecArray) => string | number | boolean }

const money = (s: string) => Number(s.replace(/[,$]/g, ''));

const RULES: Rule[] = [
  { field: 'rent', re: /\$\s?([\d,]{3,6})(?:\.\d{2})?\s*(?:\/|per|a)\s*(?:month|mo)\b(?:\s*(?:\/|per)\s*(?:bed|person|room))?/i, value: (m) => money(m[1]) },
  { field: 'rent_basis', re: /\b(per\s+(?:bed|person|room)|\/\s*(?:bed|person)|by the room|individual leases?)\b/i, value: () => 'bed' },
  { field: 'bedrooms', re: /\b(\d{1,2})\s*(?:-|\s)?(?:bed(?:room)?s?|br|bd)\b/i, value: (m) => Number(m[1]) },
  { field: 'bedrooms', re: /\bstudio\b/i, value: () => 0 },
  { field: 'baths', re: /\b(\d(?:\.5)?)\s*(?:-|\s)?(?:bath(?:room)?s?|ba)\b/i, value: (m) => Number(m[1]) },
  { field: 'sqft', re: /\b([\d,]{3,5})\s*(?:sq\.?\s*ft|sqft|square feet)\b/i, value: (m) => money(m[1]) },
  { field: 'address', re: /\b(\d{2,5}\s+(?:[NSEW]\.?\s+)?[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Ct|Court|Dr|Drive|Pl|Place|Way|Pkwy|Parkway))\b\.?/, value: (m) => m[1] },
  { field: 'heat_included', re: /\bheat(?:ing)?\s+(?:is\s+)?included\b|\bincludes?\s+(?:[a-z, ]+\s)?heat\b/i, value: () => true },
  { field: 'water_included', re: /\bwater\s+(?:is\s+)?included\b|\bincludes?\s+(?:[a-z, ]+\s)?water\b/i, value: () => true },
  { field: 'internet_included', re: /\b(?:internet|wi-?fi)\s+(?:is\s+)?included\b|\bincludes?\s+(?:[a-z, ]+\s)?(?:internet|wi-?fi)\b/i, value: () => true },
  { field: 'tenant_pays_utilities', re: /\btenants?\s+pays?\s+(?:all\s+)?(?:utilities|gas|electric(?:ity)?|DTE)\b/i, value: () => true },
  { field: 'application_fee', re: /\bapplication\s+fee(?:\s+(?:is|of))?\s*:?\s*\$\s?([\d,]+)/i, value: (m) => money(m[1]) },
  { field: 'admin_fee', re: /\badmin(?:istration|istrative)?\s+fee(?:\s+(?:is|of))?\s*:?\s*\$\s?([\d,]+)/i, value: (m) => money(m[1]) },
  { field: 'amenity_fee', re: /\bamenity\s+fee(?:\s+(?:is|of))?\s*:?\s*\$\s?([\d,]+)/i, value: (m) => money(m[1]) },
  { field: 'pre_tenancy_fee', re: /\b(holding|waitlist|wait-list|move-in|preparation|option)\s+fee\b/i, value: (m) => m[1].toLowerCase() },
  { field: 'security_deposit', re: /\b(?:security\s+)?deposit(?:\s+(?:is|of))?\s*:?\s*\$\s?([\d,]+)/i, value: (m) => money(m[1]) },
  { field: 'parking_monthly', re: /\bparking\s*(?:is|:)?\s*\$\s?(\d+)\s*(?:\/|per\s*)?\s*(?:mo|month)/i, value: (m) => Number(m[1]) },
  { field: 'parking_monthly', re: /\bfree\s+parking\b|\bparking\s+included\b/i, value: () => 0 },
  { field: 'pets_allowed', re: /\bno\s+pets\b|\bpets?\s+not\s+allowed\b/i, value: () => false },
  { field: 'pets_allowed', re: /\bpets?\s+(?:allowed|welcome|ok|friendly)\b|\b(?:cat|dog)[- ]friendly\b/i, value: () => true },
  { field: 'in_unit_laundry', re: /\bin[- ]unit\s+(?:laundry|washer)\b|\bwasher\s*(?:\/|and|&)\s*dryer\s+in\s+(?:unit|apartment)\b/i, value: () => true },
  { field: 'in_unit_laundry', re: /\b(?:shared|coin|on-site|basement)\s+laundry\b/i, value: () => false },
  { field: 'furnished', re: /\bunfurnished\b/i, value: () => false },
  { field: 'furnished', re: /\b(?:fully\s+)?furnished\b/i, value: () => true },
  { field: 'lease_start', re: /\b(?:available|move[- ]in|lease\s+starts?)\s*:?\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s*\d{4})?|\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)/i, value: (m) => m[1] },
  { field: 'lease_term_months', re: /\b(\d{1,2})[- ]month\s+lease\b/i, value: (m) => Number(m[1]) },
  { field: 'heating', re: /\b(gas|electric|baseboard|steam|radiator|heat pump)\s+heat(?:ing)?\b/i, value: (m) => ({ gas: 'gas', electric: 'electric_resistance', baseboard: 'electric_resistance', steam: 'steam', radiator: 'steam', 'heat pump': 'heat_pump' } as Record<string, string>)[m[1].toLowerCase()] ?? 'unknown' },
  { field: 'year_built', re: /\bbuilt\s+(?:in\s+)?(1[89]\d\d|20\d\d)\b/i, value: (m) => Number(m[1]) },
];

const IMPORTANT = ['rent', 'bedrooms', 'address', 'utilities', 'fees', 'parking_monthly', 'pets_allowed', 'lease_start', 'heating', 'in_unit_laundry'];

export function extractListing(text: string): ExtractListingResult {
  const facts: ExtractedFact[] = [];
  const seen = new Set<string>();
  for (const r of RULES) {
    if (seen.has(r.field) && !['bedrooms'].includes(r.field)) continue;
    const m = r.re.exec(text);
    if (!m || seen.has(r.field)) continue;
    seen.add(r.field);
    facts.push({ field: r.field, value: r.value(m), quote: m[0], start: m.index, end: m.index + m[0].length });
  }
  const has = (f: string) => facts.some((x) => x.field === f);
  const get = (f: string) => facts.find((x) => x.field === f);
  const flags: ListingFlag[] = [];
  const app = get('application_fee');
  if (app && Number(app.value) > 50) flags.push({ rule: 'Ann Arbor §8:532 caps application fees at $50 (effective Jan 26, 2025)', fact_field: 'application_fee', advice: `Listed application fee ${'$'}${app.value} exceeds $50 — verify with Student Legal Services before paying. Not legal advice.` });
  const pre = get('pre_tenancy_fee');
  if (pre) flags.push({ rule: 'Ann Arbor §8:532 bans pre-tenancy fees (holding, waitlist, move-in, preparation, option)', fact_field: 'pre_tenancy_fee', advice: `The listing mentions a ${pre.value} fee — verify with Student Legal Services. Not legal advice.` });
  if (get('admin_fee') || get('amenity_fee')) flags.push({ rule: 'Mandatory tenancy fees (admin/amenity) were addressed by ORD-26-04 (details not verified)', fact_field: get('admin_fee') ? 'admin_fee' : 'amenity_fee', advice: 'Ask whether the fee is mandatory and include it in your all-in cost. Verify current rules with Student Legal Services. Not legal advice.' });
  const not_stated = IMPORTANT.filter((f) => {
    if (f === 'utilities') return !has('heat_included') && !has('water_included') && !has('internet_included') && !has('tenant_pays_utilities');
    if (f === 'fees') return !has('application_fee') && !has('admin_fee') && !has('amenity_fee');
    return !has(f);
  });
  const patch: Record<string, unknown> = { provenance: 'observed' };
  const num = (f: string) => (get(f) ? Number(get(f)!.value) : undefined);
  if (has('rent')) patch.rent = num('rent');
  patch.rent_basis = has('rent_basis') ? 'bed' : 'unit';
  if (has('bedrooms')) patch.bedrooms = num('bedrooms');
  if (has('baths')) patch.baths = num('baths');
  if (has('sqft')) patch.sqft = num('sqft');
  if (has('address')) patch.address = String(get('address')!.value);
  const inc: string[] = [];
  if (has('heat_included')) inc.push('heat');
  if (has('water_included')) inc.push('water');
  if (has('internet_included')) inc.push('internet');
  patch.utilities_included = inc;
  const fees: unknown[] = [];
  for (const [f, label, period] of [['application_fee', 'Application fee', 'once'], ['admin_fee', 'Admin fee', 'once'], ['amenity_fee', 'Amenity fee', 'monthly']] as const) {
    const x = get(f);
    if (x) fees.push({ label, amount: Number(x.value), period, per: 'unit', provenance: 'observed', quote: x.quote });
  }
  patch.fees = fees;
  if (has('parking_monthly')) patch.parking_monthly = num('parking_monthly');
  if (has('pets_allowed')) patch.pets_allowed = get('pets_allowed')!.value;
  if (has('in_unit_laundry')) patch.in_unit_laundry = get('in_unit_laundry')!.value;
  if (has('furnished')) patch.furnished = get('furnished')!.value;
  if (has('heating')) patch.heating = get('heating')!.value;
  if (has('year_built')) patch.year_built = num('year_built');
  if (has('lease_term_months')) patch.lease_term_months = num('lease_term_months');
  return { facts: facts.sort((a, b) => a.start - b.start), not_stated, flags, listing_patch: patch, mode: 'regex' };
}
