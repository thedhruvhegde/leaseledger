// Every API request the deck makes, in one place.
// Shared by the browser deck (src/api.ts) and the Node snapshot script (scripts/snapshot.mjs),
// so a cached snapshot is keyed exactly like the live request it stands in for.
// Plain ES module on purpose: Node runs it without a build step.

/** Profiles used on each chapter (ids from GET /api/demo-profiles). */
export const PROFILE = {
  hook: 'north-engineer',
  robustness: 'north-engineer',
  surfaceA: 'north-engineer',
  surfaceB: 'ross-kerrytown-job',
};

/**
 * Demo flips. ONLY changes listed in execution/demo-flips.md. The deck evaluates on the API's DEFAULT listing set
 * (data/listings/demo_set.json — exactly what the app shows); the snapshot script re-verifies every flip there.
 * `expect` is the documented new #1; the snapshot script warns loudly if the live engine disagrees.
 * Numbers in labels are request parameters and are rendered from these fields, never typed into slide copy.
 */
export const FLIPS = [
  {
    id: 'vot',
    profile: 'north-engineer',
    verb: 'Value my time at',
    patch: { value_of_time: 20 },
    expect: 'university-towers-2br',
  },
  {
    id: 'hospital',
    profile: 'late-night-studio',
    verb: 'Add a hospital shift',
    addEvent: { label: 'Hospital shift', building_id: 'uhosp', days: ['T', 'R'], start_min: 420, end_min: 720, fixed: true, provenance: 'user' },
    expect: 'university-towers-2br',
    knifeEdge: true,
  },
  {
    id: 'coops',
    profile: 'north-engineer',
    verb: 'Exclude co-ops',
    patch: { excluded_building_types: ['coop'] },
    expect: 'university-towers-2br',
  },
];

/**
 * Advanced-math requests (/api/advanced/*; appendix chapter). Default listing set, like everything else.
 * `music` is the decision-relevant EVPI case from ledger/engine/advanced/README.md: template
 * 'music-artdesign-north' with no fixed classes and time valued at MUSIC_VOT; it is shown only if the API answers.
 */
export const MUSIC_TEMPLATE = 'music-artdesign-north';
export const MUSIC_VOT = 20;
export const ADVANCED = [
  { key: 'adv:evpi', path: '/advanced/evpi', body: (P) => ({ profile: P['north-engineer'] }) },
  { key: 'adv:evpiMusic', path: '/advanced/evpi', body: (P) => ({ profile: musicProfile(P['north-engineer']) }) },
  { key: 'adv:risk', path: '/advanced/risk', body: (P) => ({ profile: P['north-engineer'] }) },
  { key: 'adv:sensitivity', path: '/advanced/sensitivity', body: (P) => ({ profile: P['ross-kerrytown-job'] }) },
  { key: 'adv:profile', path: '/advanced/profile', body: (P) => ({ profile: P['north-engineer'] }) },
];
export function musicProfile(base) {
  const p = { events: [], template_id: MUSIC_TEMPLATE, value_of_time: MUSIC_VOT };
  for (const k of ['modes', 'rent_cap', 'household_size', 'season', 'month']) p[k] = base[k];
  return p;
}

export const ROBUSTNESS_SAMPLES = 2000;
export const ROBUSTNESS_SEED = 42;

// ---------- keys ----------
export function stable(v) {
  if (Array.isArray(v)) return '[' + v.map(stable).join(',') + ']';
  if (v && typeof v === 'object') {
    return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stable(v[k])).join(',') + '}';
  }
  return JSON.stringify(v ?? null);
}
function fnv(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, '0');
}
export function keyOf(method, path, body) {
  return `${method} ${path} ${body === undefined ? '' : fnv(stable(body))}`;
}

export function applyFlip(profile, flip) {
  const p = JSON.parse(JSON.stringify(profile));
  if (flip.patch) Object.assign(p, flip.patch);
  if (flip.addEvent) p.events = [...p.events, flip.addEvent];
  return p;
}

/**
 * Run the deck's whole request plan with `call(method, path, body)` -> data (throws on failure).
 * `group` is the demo group request ({members, listing_ids}) from data/templates/demo_profiles.json.
 * Returns {[name]: data}. Failures are recorded as undefined so one bad call never blanks the deck.
 */
/** @param {(m: string, p: string, b?: unknown) => Promise<any>} call @param {any} group @param {(name: string, data: any) => void} [onResult] */
export async function runPlan(call, group, onResult = (_n, _d) => {}) {
  const out = {};
  const get = async (name, method, path, body) => {
    try { out[name] = await call(method, path, body); } catch (e) { out[name] = undefined; }
    onResult(name, out[name]);
    return out[name];
  };
  const [profiles, listings] = await Promise.all([
    get('demoProfiles', 'GET', '/demo-profiles'),
    get('listings', 'GET', '/listings'),
    get('methods', 'GET', '/methods'),
    get('manifest', 'GET', '/manifest'),
  ]);
  if (!profiles || !listings) return out;
  const P = Object.fromEntries(profiles.map((d) => [d.id, d.profile]));

  // one evaluation per demo profile on the API's default listing set (what the app shows)
  await Promise.all(Object.keys(P).map((id) => get(`eval:${id}`, 'POST', '/evaluate', { profile: P[id] })));

  // scripted flips: after-evaluation + engine diff
  await Promise.all(FLIPS.map(async (f) => {
    const after = applyFlip(P[f.profile], f);
    await Promise.all([
      get(`flip:${f.id}`, 'POST', '/evaluate', { profile: after }),
      get(`diff:${f.id}`, 'POST', '/diff', { before: P[f.profile], after }),
    ]);
  }));

  // robustness + breakevens between the top two
  const rp = PROFILE.robustness;
  const ev = out[`eval:${rp}`];
  const jobs = [get('robustness', 'POST', '/robustness', { profile: P[rp], samples: ROBUSTNESS_SAMPLES, seed: ROBUSTNESS_SEED })];
  if (ev) {
    const top = ev.evaluations.filter((e) => e.feasible).sort((a, b) => a.rank - b.rank);
    if (top.length > 1) jobs.push(get('compare', 'POST', '/compare', { profile: P[rp], a: top[0].listing_id, b: top[1].listing_id }));
  }
  if (group) jobs.push(get('group', 'POST', '/group', group));
  // the hook's two homes (lowest rent vs cheapest week) with every trip leg's geometry: cover map + hook maps
  const hk = out[`eval:${PROFILE.hook}`];
  if (hk) {
    const feas = hk.evaluations.filter((e) => e.feasible).sort((a, b) => a.rank - b.rank);
    const rent = (e) => e.ledger.find((x) => x.key === 'rent')?.usd_month ?? Infinity;
    const cheap = [...feas].sort((a, b) => rent(a) - rent(b))[0];
    if (cheap && feas[0] && cheap.listing_id !== feas[0].listing_id) {
      jobs.push(get('routes', 'POST', '/compare', { profile: P[PROFILE.hook], a: feas[0].listing_id, b: cheap.listing_id }));
    }
  }
  await Promise.all(jobs);

  // advanced math (appendix); failures leave the chapter in its "pending" state
  await Promise.all(ADVANCED.map((a) => get(a.key, 'POST', a.path, a.body(P))));
  return out;
}
