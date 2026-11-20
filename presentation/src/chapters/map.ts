// "Same city, different identity, different map": two students' travel-cost surfaces (presentation/data/surface-*.geojson)
// drawn over the Ann Arbor street basemap, cross-fading between them. Each layer is shaded by the cell's percentile WITHIN
// that student's own surface (light = their cheapest cells), so the morph shows where each student should look.
import type { Chapter } from '../deck';
import { html, esc, tag } from '../lib';
import { surfaces, placeholder, requiredData, F } from '../facts';
import { PROFILE } from '../requests.js';

type Base = { bounds: { west: number; east: number; south: number; north: number }; width: number; height: number; major: string; minor: string; service: string; campus: { id: string; name: string; x: number; y: number }[] };
let base: Base | null = null;
const loaded: Record<string, any> = {};
const VALUE_KEYS = ['usd_month', 'all_in', 'all_in_usd', 'cost', 'value', 'weekly_min'];
/** Five-step stone→ink ramp (Cartesian: no gradients; tones only). */
const STEPS = ['#E8E2D8', '#CFC7BB', '#A89F93', '#6E675F', '#2E2B28'];

/** The two student surfaces to morph between (never the delta surface). */
const pair = () => {
  const plain = surfaces.filter((s) => !/delta|diff/.test(s.id));
  const a = plain.find((s) => s.id === PROFILE.surfaceA) ?? plain[0];
  const b = plain.find((s) => s.id === PROFILE.surfaceB && s !== a) ?? plain.find((s) => s !== a);
  return [a, b].filter(Boolean) as typeof surfaces;
};

async function load() {
  if (!base) base = await fetch('./basemap-paths.json').then((r) => r.json()).catch(() => null);
  for (const s of pair()) if (!loaded[s.name]) loaded[s.name] = await fetch(s.url).then((r) => r.json()).catch(() => null);
}
const valueKey = (fc: any): string | null => {
  const props = fc?.features?.[0]?.properties ?? {};
  return VALUE_KEYS.find((k) => typeof props[k] === 'number') ?? Object.keys(props).find((k) => typeof props[k] === 'number' && !/lat|lon/.test(k)) ?? null;
};

function layer(fc: any, key: string, b: Base, cls: string) {
  const { west, east, south, north } = b.bounds;
  const px = (lon: number) => ((lon - west) / (east - west)) * b.width;
  const py = (lat: number) => ((north - lat) / (north - south)) * b.height;
  const vals = fc.features.map((f: any) => f.properties?.[key]).filter((v: any) => typeof v === 'number').sort((x: number, y: number) => x - y);
  const pct = (v: number) => { let lo = 0, hi = vals.length; while (lo < hi) { const m = (lo + hi) >> 1; if (vals[m] < v) lo = m + 1; else hi = m; } return lo / Math.max(1, vals.length - 1); };
  // stone (cheapest for this student) → ink (most expensive), in five quiet steps
  const shade = (v: number) => STEPS[Math.min(STEPS.length - 1, Math.floor(pct(v) * STEPS.length))];
  const ring = (r: number[][]) => 'M' + r.map(([x, y]) => `${px(x).toFixed(1)} ${py(y).toFixed(1)}`).join('L') + 'Z';
  const out = fc.features.map((f: any) => {
    const v = f.properties?.[key];
    const g = f.geometry;
    if (typeof v !== 'number' || !g) return '';
    if (g.type === 'Polygon') return `<path d="${g.coordinates.map(ring).join('')}" fill="${shade(v)}"/>`;
    if (g.type === 'MultiPolygon') return `<path d="${g.coordinates.map((p: any) => p.map(ring).join('')).join('')}" fill="${shade(v)}"/>`;
    return '';
  }).join('');
  return `<g class="surf ${cls}">${out}</g>`;
}

export const map: Chapter = {
  id: 'map',
  title: 'Same city, different map',
  budget: 15,
  render() {
    const P = pair();
    const ready = P.length === 2 && P.every((s) => loaded[s.name]) && base;
    let body: string;
    if (P.length < requiredData.surfaces_min) {
      body = placeholder(`data/${requiredData.surface_glob} (${P.length} student surfaces found)`, 'cost-surface map: two students’ travel-cost surfaces over Ann Arbor');
    } else if (!ready) {
      body = html`<div class="mp-maps"><div class="img-ph mp-ph"></div><div class="img-ph mp-ph"></div></div>`;
    } else {
      const b = base!;
      body = html`<div class="mp-maps">${P.map((s, i) => {
        const fc = loaded[s.name];
        return html`<figure class="mp-fig enter" style="--i:${2 + i}">
          <div class="plate-img mp-plate"><svg class="city" viewBox="0 0 ${b.width} ${b.height}" role="img" aria-label="Travel-cost surface">
            <rect width="${b.width}" height="${b.height}" fill="var(--bg2)"/>
            ${layer(fc, valueKey(fc)!, b, 'on')}
            <path d="${b.major}" class="st-major"/>
          </svg></div>
          <figcaption>${esc(fc.properties?.name ?? s.id)}</figcaption>
        </figure>`;
      })}</div>`;
    }
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">Same city. <em>Different map.</em></h2>
      <div class="mp-grid grow">
        ${body}
        <div class="mp-side enter" style="--i:4">
          <div class="hero md">${F('surface_cheapest_decile_overlap', { digits: 0, suffix: '%' })}</div>
          <div class="hero-cap">of one student’s <b>cheapest tenth</b> of the city is also the other’s</div>
          <div class="mp-legend"><span>cheap</span><span class="ramp">${STEPS.map((c) => `<i style="background:${c}"></i>`).join('')}</span><span>costly</span></div>
          ${tag('travel cost only')}
        </div>
      </div>`;
  },
  mount(el) {
    const P = pair();
    if (P.length >= 2 && !(P.every((s) => loaded[s.name]) && base)) load().then(() => el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
  },
  notes() {
    return `<p><b>VII · Same city (15 s).</b> Left: the North Campus engineer. Right: the Ross student with a Kerrytown job. Every 250 m cell of Ann Arbor priced for that student's own week (travel cost only, no rent); each map is shaded within that student's own range, light = their cheapest places.</p>
      <p>Line: "Same city, different identity, different map — only ~28% of one student's cheapest tenth is the other's; rank correlation between the maps is only ~0.4."</p>
      <p>Caveat if asked: schedule = demo profile events + first template alternative per slot; scheduled GTFS times, no delays; homes inside a cell can differ.</p>`;
  },
};
