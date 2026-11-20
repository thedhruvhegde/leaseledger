#!/usr/bin/env node
// Capture every API response the deck uses into public/snapshot.json (offline fallback).
// Usage: npm run snapshot            (API at http://localhost:8000/api)
//        API=http://127.0.0.1:8101/api npm run snapshot
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runPlan, keyOf, FLIPS } from '../src/requests.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const API = (process.env.API ?? 'http://localhost:8000/api').replace(/\/$/, '');

const responses = {};
// Drop bulky fields the deck never reads (trip geometry, per-evaluation provider manifests).
function prune(path, d) {
  if (path === '/evaluate' && d?.evaluations) {
    for (const e of d.evaluations) if (e.commute?.tours) {
      e.commute.n_trips = e.commute.tours.reduce((n, t) => n + (t.trips?.length ?? 0), 0);
      delete e.commute.tours;
    }
    if (d.manifest) { delete d.manifest.provider; delete d.manifest.params; }
  }
  if (path === '/manifest' && d?.provider) delete d.provider.late_night;
  if (path === '/advanced/profile' && d) {
    const keep = ['t', 'tau', 'route', 'cliffs', 'mean_tau', 'integral_tau', 'sd_tau', 'building_id', 'day', 'event_label', 'event_start', 'listing_id', 'listing_name', 'buffer_min'];
    const slim = (x) => Object.fromEntries(Object.entries(x).filter(([k]) => keep.includes(k)));
    return { ...slim(d), series: (d.series ?? []).map(slim) };
  }
  return d;
}
let failures = 0;
async function call(method, path, body) {
  const t0 = performance.now();
  const res = await fetch(API + path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(60000),
  });
  const ms = Math.round(performance.now() - t0);
  if (!res.ok) {
    if (path.startsWith('/advanced/')) { console.warn(`  skip ${method} ${path} -> ${res.status} (advanced endpoint; appendix stays pending)`); throw new Error(String(res.status)); }
    failures++;
    console.error(`  FAIL ${method} ${path} -> ${res.status} ${(await res.text()).slice(0, 200)}`);
    throw new Error(String(res.status));
  }
  const data = await res.json();
  responses[keyOf(method, path, body)] = prune(path, structuredClone(data));
  console.log(`  ok   ${method.padEnd(4)} ${path.padEnd(16)} ${String(ms).padStart(5)} ms`);
  return data;
}

const health = await fetch(API + '/health', { signal: AbortSignal.timeout(5000) }).then((r) => r.json()).catch(() => null);
if (!health) {
  console.error(`API not reachable at ${API}. Start it first: make api   (repo root)`);
  process.exit(1);
}
console.log(`API ${API}: provider=${health.provider} warmup=${health.warmup?.state}`);
const demo = JSON.parse(readFileSync(resolve(root, '../data/templates/demo_profiles.json'), 'utf8'));
const group = demo.group ? { members: demo.group.members, listing_ids: demo.group.listing_ids ?? null } : null;
const out = await runPlan(call, group);

// Verify the scripted flips still flip the way execution/demo-flips.md documents.
let drift = 0;
for (const f of FLIPS) {
  const before = out[`eval:${f.profile}`], after = out[`flip:${f.id}`];
  if (!before || !after) { console.error(`  flip ${f.id}: missing responses`); drift++; continue; }
  const top = (r) => r.evaluations.filter((e) => e.feasible).sort((a, b) => a.rank - b.rank)[0]?.listing_id;
  const a = top(before), b = top(after);
  const ok = b === f.expect && a !== b;
  if (!ok) drift++;
  console.log(`  flip ${f.id.padEnd(9)} ${a} -> ${b} ${ok ? '(as documented)' : `!! expected ${f.expect}`}`);
}

const snap = { captured_at: new Date().toISOString(), api: API, health, responses };
const file = resolve(root, 'public/snapshot.json');
writeFileSync(file, JSON.stringify(snap));
console.log(`wrote ${file}: ${Object.keys(responses).length} responses, ${(JSON.stringify(snap).length / 1e6).toFixed(1)} MB`);
if (failures || drift) {
  console.error(`${failures} failed request(s), ${drift} flip(s) not as documented — fix before presenting.`);
  process.exit(2);
}
