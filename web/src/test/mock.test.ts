import { MOCK_BUILDINGS, MOCK_DEMO_PROFILES, MOCK_LISTINGS, MOCK_TEMPLATES } from '../api/mockData';
import { diff, evaluate, robustness, type EngineCtx } from '../api/mockEngine';
import { envyFreePrices, envyMatrix, group } from '../api/mockGroup';
import { extractListing, parseSchedule } from '../api/mockNlp';
import { humanize } from '../components/Breakeven';

const ctx: EngineCtx = { buildings: new Map(MOCK_BUILDINGS.map((b) => [b.id, b])), listings: MOCK_LISTINGS };
const maya = MOCK_DEMO_PROFILES[0].profile;

describe('mock fixtures', () => {
  it('labels every fixture listing synthetic', () => {
    expect(MOCK_LISTINGS.every((l) => l.provenance === 'synthetic')).toBe(true);
  });
});

describe('mock engine', () => {
  it('ranks feasible homes and keeps infeasible ones with reasons', () => {
    const r = evaluate(maya, ctx);
    const feas = r.evaluations.filter((e) => e.feasible);
    expect(feas[0].rank).toBe(1);
    expect(r.evaluations.find((e) => e.listing_id === 'syn-state-loft')!.violations[0]).toMatch(/above your/);
    expect(r.baseline_ranking).toHaveLength(MOCK_LISTINGS.length);
    for (const e of feas) expect(e.all_in_total).toBeCloseTo(e.ledger.reduce((s, l) => s + l.usd_month, 0), 6);
  });
  it('reports infeasibility with a minimal relaxation', () => {
    const r = evaluate({ ...maya, rent_cap: 500 }, ctx);
    expect(r.infeasibility?.binding_constraint).toBe('rent_cap');
    expect(r.infeasibility?.minimal_relaxation.rent_cap).toBeGreaterThan(500);
  });
  it('explains a schedule change in the diff', () => {
    const after = { ...maya, events: maya.events.map((e) => (e.label === 'Lab' ? { ...e, start_min: 480, end_min: 660 } : e)) };
    const d = diff(maya, after, ctx);
    expect(d.causes[0]).toMatch(/moved “Lab”/);
    expect(Object.keys(d.deltas)).toHaveLength(MOCK_LISTINGS.length);
  });
  it('runs 2,000-sample robustness quickly and deterministically', () => {
    const t = performance.now();
    const a = robustness(maya, ctx, MOCK_TEMPLATES, 2000, 42);
    const ms = performance.now() - t;
    const b = robustness(maya, ctx, MOCK_TEMPLATES, 2000, 42);
    expect(a.p_rank1).toEqual(b.p_rank1);
    const total = Object.values(a.p_rank1).reduce((s, v) => s + v, 0);
    expect(total).toBeCloseTo(1, 6);
    expect(ms).toBeLessThan(1500);
  });
});

describe('group split', () => {
  it('produces envy-free prices summing to the rent', () => {
    const v = [[500, 400, 300], [450, 450, 300], [420, 380, 350]];
    const assign = [0, 1, 2];
    const p = envyFreePrices(v, assign, 1200)!;
    expect(p.reduce((s, x) => s + x, 0)).toBeCloseTo(1200, 6);
    const E = envyMatrix(v, assign, p);
    expect(E.flat().every((x) => x <= 1e-6)).toBe(true);
  });
  it('ranks apartments for a group', () => {
    const members = [0, 1, 2].map((i) => ({ alias: `R${i}`, profile: maya, budget_cap: 1500 }));
    const g = group(members, ctx);
    expect(g.ranking.length).toBe(MOCK_LISTINGS.length);
    const best = g.splits.find((s) => s.listing_id === g.ranking[0])!;
    expect(best.envy_matrix.flat().every((x) => x <= 1e-6)).toBe(true);
  });
});

describe('regex parsers', () => {
  it('parses a typed week with exact source quotes', () => {
    const text = 'EECS 281 MWF 9-10:30 in BBB. Lab Tuesday 9 to noon in GG Brown. UgLi most weeknights until 1am.';
    const r = parseSchedule(text, MOCK_BUILDINGS);
    expect(r.events).toHaveLength(3);
    expect(r.events[0]).toMatchObject({ building_id: 'bbb', days: ['M', 'W', 'F'], start_min: 540, end_min: 630 });
    expect(r.events[1]).toMatchObject({ building_id: 'ggbrown', days: ['T'], start_min: 540, end_min: 720 });
    expect(r.events[2]).toMatchObject({ building_id: 'ugli', end_min: 1500 });
    for (const e of r.events) expect(text.includes(e.source_quote!)).toBe(true);
    expect(r.needs_confirmation.some((n) => n.event_index === 2)).toBe(true);
  });
  it('extracts listing facts with offsets and flags an over-cap application fee', () => {
    const text = '3 bedroom at 812 Packard St. $2,550/month. Heat included. Application fee: $75. No pets.';
    const r = extractListing(text);
    for (const f of r.facts) expect(text.slice(f.start, f.end)).toBe(f.quote);
    expect(r.facts.find((f) => f.field === 'rent')?.value).toBe(2550);
    expect(r.flags[0].advice).toMatch(/Student Legal Services/);
    expect(r.listing_patch.pets_allowed).toBe(false);
  });
  it('humanizes engine text', () => {
    expect(humanize('syn-a wins if value_of_time < 9.4', { 'syn-a': 'Kerrytown room' })).toBe('Kerrytown room wins if your time is worth under $9.40/h');
  });
});
