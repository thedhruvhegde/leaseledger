/**
 * MOCK Group Week: welfare-maximizing room assignment + envy-free prices (difference constraints,
 * Bellman-Ford), choosing the midpoint of the two extreme envy-free price vectors to protect the
 * worst-off roommate. Labeled mock in the UI; the API's maximin LP replaces this in live mode.
 */
import type { GroupResult, GroupSplit, Listing, Member } from '../types';
import { evaluateOne, valueOfTime, type EngineCtx } from './mockEngine';
import { usd } from '../lib/format';

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296;
}

export function roomsOf(l: Listing): { id: string; sqft: number; private_bath: boolean }[] {
  if (l.rooms.length) return l.rooms.map((r) => ({ id: String(r.id), sqft: Number(r.sqft ?? 130), private_bath: !!r.private_bath }));
  const n = Math.max(1, l.bedrooms);
  return Array.from({ length: n }, (_, i) => ({ id: `room ${i + 1}`, sqft: 150 - i * 12, private_bath: i === 0 && (l.baths ?? 1) > 1 }));
}

function permutations(n: number): number[][] {
  if (n === 0) return [[]];
  const out: number[][] = [];
  const rec = (cur: number[], used: boolean[]) => {
    if (cur.length === n) { out.push([...cur]); return; }
    for (let i = 0; i < n; i++) if (!used[i]) { used[i] = true; cur.push(i); rec(cur, used); cur.pop(); used[i] = false; }
  };
  rec([], Array(n).fill(false));
  return out;
}

/** Envy-free prices for a fixed assignment: p[a_i] - p[a_j] <= v_i(a_i) - v_i(a_j). Returns null if a negative cycle exists. */
export function envyFreePrices(values: number[][], assign: number[], total: number): number[] | null {
  const n = assign.length;
  // node k = room assigned to member k. constraint x_i <= x_j + (v_i(a_i) - v_i(a_j)) : edge j -> i
  const solve = (sign: 1 | -1): number[] | null => {
    const dist = Array(n).fill(0);
    for (let it = 0; it < n; it++) {
      let changed = false;
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const w = values[i][assign[i]] - values[i][assign[j]];
        if (sign === 1) {
          if (dist[j] + w < dist[i] - 1e-9) { dist[i] = dist[j] + w; changed = true; }
        } else if (-dist[i] + w < -dist[j] - 1e-9) { dist[j] = dist[i] - w; changed = true; }
      }
      if (!changed) return dist;
    }
    return null;
  };
  const lo = solve(1);
  const hi = solve(-1);
  if (!lo || !hi) return null;
  const norm = (p: number[]) => { const s = p.reduce((a, b) => a + b, 0); return p.map((x) => x + (total - s) / n); };
  const a = norm(lo);
  const b = norm(hi);
  return a.map((x, i) => (x + b[i]) / 2);
}

export function envyMatrix(values: number[][], assign: number[], prices: number[]): number[][] {
  const n = assign.length;
  return Array.from({ length: n }, (_, p) => Array.from({ length: n }, (_, q) => (p === q ? 0 : values[p][assign[q]] - prices[q] - (values[p][assign[p]] - prices[p]))));
}

export function group(members: Member[], ctx: EngineCtx, listingIds?: string[] | null): GroupResult {
  const n = members.length;
  const listings = (listingIds?.length ? ctx.listings.filter((l) => listingIds.includes(l.id)) : ctx.listings);
  const splits: GroupSplit[] = [];
  const warnings: string[] = ['MOCK mode: room values are derived from room size, private bath and a per-person taste term; commute costs use the simplified travel model.'];
  for (const l of listings) {
    const rooms = roomsOf(l);
    if (rooms.length < n) {
      splits.push({ listing_id: l.id, feasible: false, assignment: {}, rent: {}, utility: {}, envy_matrix: [], maximin_utility: null, equal_split_max_envy: null, relaxation: {}, explanation_facts: [`${rooms.length} bedroom${rooms.length === 1 ? '' : 's'} for ${n} people.`] });
      continue;
    }
    const total = l.rent_basis === 'bed' ? l.rent * n : l.rent;
    const avg = rooms.reduce((s, r) => s + r.sqft, 0) / rooms.length;
    const base = total / n;
    // values[i][r]: willingness to pay (USD/mo) for room r — explicit if member gave room_values
    const values = members.map((m) =>
      rooms.map((r) => m.room_values?.[r.id] ?? base * (0.78 + 0.22 * (r.sqft / avg)) + (r.private_bath ? 55 : 0) + (hash(`${m.alias}|${r.id}`) - 0.5) * 50 + 40),
    );
    const commuteCost = members.map((m) => {
      const e = evaluateOne(l, { ...m.profile, household_size: n }, ctx);
      return e.ledger.find((x) => x.key === 'time_value')?.usd_month ?? 0;
    });
    // best assignment over the first n rooms permutations (rooms.length may exceed n: choose subset by perms of indices)
    let best: number[] | null = null;
    let bestW = -Infinity;
    const idx = rooms.map((_, i) => i);
    const combos = permutations(Math.min(rooms.length, 7)).map((p) => p.slice(0, n));
    const seen = new Set<string>();
    for (const c of combos) {
      const k = c.join(',');
      if (seen.has(k)) continue;
      seen.add(k);
      const w = c.reduce((s, r, i) => s + values[i][r], 0);
      if (w > bestW) { bestW = w; best = c; }
    }
    void idx;
    const assign = best!;
    const prices = envyFreePrices(values, assign, total) ?? Array(n).fill(total / n);
    const E = envyMatrix(values, assign, prices);
    const utility: Record<string, number> = {};
    const rent: Record<string, number> = {};
    const assignment: Record<string, string> = {};
    const relaxation: Record<string, number> = {};
    members.forEach((m, i) => {
      rent[m.alias] = Math.round(prices[i] * 100) / 100;
      utility[m.alias] = values[i][assign[i]] - prices[i] - commuteCost[i];
      assignment[m.alias] = rooms[assign[i]].id;
      if (m.budget_cap != null && prices[i] > m.budget_cap) relaxation[m.alias] = Math.ceil(prices[i] - m.budget_cap);
    });
    let eqEnvy = 0;
    for (let p = 0; p < n; p++) for (let q = 0; q < n; q++) if (p !== q) eqEnvy = Math.max(eqEnvy, values[p][assign[q]] - values[p][assign[p]]);
    const feasible = Object.keys(relaxation).length === 0;
    const mm = Math.min(...Object.values(utility));
    const worst = members[Object.values(utility).indexOf(mm)].alias;
    const facts = [
      `Total rent ${usd(total)}/mo split ${members.map((m) => `${m.alias} ${usd(rent[m.alias])}`).join(', ')}.`,
      `Envy-free: no one would swap their room-and-rent for anyone else's (max envy ${usd(Math.max(...E.flat()))}).`,
      `An equal split would leave someone envying another room by up to ${usd(eqEnvy)}/mo.`,
      `Worst-off roommate here is ${worst} once their commute is counted.`,
    ];
    if (!feasible) facts.push(`Over budget: ${Object.entries(relaxation).map(([a, v]) => `${a} needs +${usd(v)}`).join(', ')}.`);
    void valueOfTime;
    splits.push({ listing_id: l.id, feasible, assignment, rent, utility, envy_matrix: E, maximin_utility: mm, equal_split_max_envy: eqEnvy, relaxation, explanation_facts: facts });
  }
  const ranking = [...splits]
    .sort((a, b) => Number(b.feasible) - Number(a.feasible) || (b.maximin_utility ?? -1e9) - (a.maximin_utility ?? -1e9))
    .map((s) => s.listing_id);
  if (!splits.some((s) => s.feasible)) warnings.push('No apartment fits everyone’s budget — see the budget increases each roommate would need.');
  return { splits, ranking, warnings };
}
