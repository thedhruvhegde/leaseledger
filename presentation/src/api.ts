// Live API with per-request fallback to the cached snapshot (public/snapshot.json).
import { keyOf, runPlan } from './requests.js';
import demoProfilesFile from '../../data/templates/demo_profiles.json';

const qs = new URLSearchParams(location.search);
/** API base: same-origin /api (Vite proxies it to :8000). Override with ?api=http://host:8000/api. */
export const API_BASE = (qs.get('api') ?? '/api').replace(/\/$/, '');
/** ?offline forces snapshot mode (rehearsal of the no-network path). */
const FORCE_OFFLINE = qs.has('offline');

export type Source = 'live' | 'snapshot' | 'missing';
type Snapshot = { captured_at: string; responses: Record<string, unknown> };

let snapshot: Snapshot | null = null;
let apiUp = false;
const listeners = new Set<() => void>();
export const status = { mode: 'connecting' as 'connecting' | 'live' | 'snapshot' | 'mixed' | 'none', capturedAt: '', live: 0, cached: 0, missing: 0 };

export function onStatus(fn: () => void) { listeners.add(fn); fn(); }
const emit = () => listeners.forEach((f) => f());
function recompute() {
  status.mode = status.missing && !status.live && !status.cached ? 'none'
    : status.cached && status.live ? 'mixed' : status.cached ? 'snapshot' : status.live ? 'live' : status.mode;
  emit();
}

async function loadSnapshot() {
  try {
    const r = await fetch('./snapshot.json', { cache: 'no-cache' });
    if (r.ok) { snapshot = await r.json(); status.capturedAt = snapshot!.captured_at; }
  } catch { /* no snapshot shipped */ }
}

async function probe(): Promise<boolean> {
  if (FORCE_OFFLINE) return false;
  try {
    const r = await fetch(API_BASE + '/health', { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch { return false; }
}

/** One request: live first (if the API answered the probe), snapshot second. */
export async function call<T = any>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<{ data: T; source: Source; ms: number }> {
  const key = keyOf(method, path, body);
  const t0 = performance.now();
  if (apiUp) {
    try {
      const r = await fetch(API_BASE + path, {
        method,
        headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(12000),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const data = (await r.json()) as T;
      status.live++; recompute();
      return { data, source: 'live', ms: performance.now() - t0 };
    } catch (e) {
      console.warn(`[deck] live ${method} ${path} failed (${e}); using snapshot`);
    }
  }
  const cached = snapshot?.responses[key];
  if (cached !== undefined) { status.cached++; recompute(); return { data: cached as T, source: 'snapshot', ms: performance.now() - t0 }; }
  status.missing++; recompute();
  throw new Error(`no live answer and no snapshot for ${method} ${path}`);
}

export type Plan = Record<string, any>;
export const plan: Plan = {};
const planListeners = new Set<(name: string) => void>();
export function onPlan(fn: (name: string) => void) { planListeners.add(fn); }

export async function start() {
  await loadSnapshot();
  apiUp = await probe();
  if (!apiUp) { status.mode = snapshot ? 'snapshot' : 'none'; emit(); }
  // keep probing so the indicator recovers when the API comes back
  setInterval(async () => { const up = await probe(); if (up !== apiUp) { apiUp = up; emit(); } }, 10000);
  const g = (demoProfilesFile as any).group;
  const group = g ? { members: g.members, listing_ids: g.listing_ids ?? null } : null;
  await runPlan(async (m: string, p: string, b?: unknown) => (await call(m as 'GET' | 'POST', p, b)).data, group, (name: string, data: unknown) => {
    plan[name] = data;
    planListeners.forEach((f) => f(name));
  });
  plan.__done = true;
  planListeners.forEach((f) => f('__done'));
}
export const isApiUp = () => apiUp;

// ---------- helpers over EvaluationResult ----------
export type Evaluation = {
  listing_id: string; feasible: boolean; rank: number; score: number; all_in_total: number; cash_total: number;
  ledger: { key: string; label: string; usd_month: number; low: number; high: number; provenance: string; in_cash_total: boolean }[];
  commute: { weekly_min: number; weekly_generalized_min: number; weekly_walk_min: number; weekly_wait_min: number; weekly_in_vehicle_min: number; late_night_outdoor_min: number };
};
export const ranked = (ev: any): Evaluation[] => (ev?.evaluations ?? []).filter((e: Evaluation) => e.feasible).sort((a: Evaluation, b: Evaluation) => a.rank - b.rank);

export function listingName(id: string): string {
  const l = plan.listings?.listings?.find((x: any) => x.id === id);
  return l?.name ?? id;
}
export function listing(id: string): any { return plan.listings?.listings?.find((x: any) => x.id === id); }
export function profile(id: string): any { return plan.demoProfiles?.find((d: any) => d.id === id); }

/** Listing name as a data-bound span (names like "1006 Packard St" contain digits from the API). */
export const lname = (id: string) => `<span class="lname" data-src="api:GET /listings name">${String(listingName(id)).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)}</span>`;

/** Compact listing name for tables: "University Towers - 2BR shared (up to 4 people)" -> "University Towers · 2BR shared". */
export function shortName(id: string): string {
  const n = String(listingName(id));
  const [base, ...rest] = n.split(' - ');
  if (!rest.length) return n.replace(/^Synthetic: /, 'Synth: ');
  const tail = rest.join(' - ').replace(/\s*\(.*?\)\s*/g, ' ').trim().split(/\s+/).slice(0, 2).join(' ');
  return `${base} · ${tail}`;
}
export const sname = (id: string) => `<span class="lname" data-src="api:GET /listings name">${shortName(id).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)}</span>`;
