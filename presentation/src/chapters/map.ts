// "Same city, different identity, different map": two students' travel-cost surfaces (presentation/data/surface-*.geojson)
// drawn over the Ann Arbor street basemap, cross-fading between them. Each layer is shaded by the cell's percentile WITHIN
// that student's own surface (light = their cheapest cells), so the morph shows where each student should look.
import type { Chapter } from '../deck';
import { html, said, esc, fmt, num, reducedMotion, eyebrow, ROMAN } from '../lib';
import { surfaces, placeholder, requiredData, F } from '../facts';
import { PROFILE } from '../requests.js';

type Base = { bounds: { west: number; east: number; south: number; north: number }; width: number; height: number; major: string; minor: string; service: string; campus: { id: string; name: string; x: number; y: number }[] };
let base: Base | null = null;
const loaded: Record<string, any> = {};
const VALUE_KEYS = ['usd_month', 'all_in', 'all_in_usd', 'cost', 'value', 'weekly_min'];
let timer = 0;
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
  numeral: 'VII',
  gist: 'Two students, two cost surfaces',
  budget: 15,
  render() {
    const P = pair();
    const ready = P.length === 2 && P.every((s) => loaded[s.name]) && base;
    let body: string, side = '';
    if (P.length < requiredData.surfaces_min) {
      body = placeholder(`data/${requiredData.surface_glob} (${P.length} student surfaces found)`, 'cost-surface map: two students’ travel-cost surfaces over Ann Arbor');
    } else if (!ready) {
      body = html`<div class="img-ph"><span class="micro">Loading map</span></div>`;
    } else {
      const [A, B] = P.map((s) => loaded[s.name]);
      const kA = valueKey(A)!, kB = valueKey(B)!;
      const b = base!;
      body = html`<svg class="city" viewBox="0 0 ${b.width} ${b.height}" role="img" aria-label="Travel-cost surfaces of two students">
          <rect width="${b.width}" height="${b.height}" fill="var(--bg2)"/>
          ${layer(A, kA, b, 'sa on')}${layer(B, kB, b, 'sb')}
          <path d="${b.minor}" class="st-minor"/><path d="${b.major}" class="st-major"/>
          ${b.campus.map((c) => `<circle cx="${c.x}" cy="${c.y}" r="4.5" class="bld"><title>${esc(c.name)}</title></circle>`).join('')}
        </svg>`;
      const q = (fc: any) => fc.properties?.usd_month_p10_p50_p90 as number[] | undefined;
      side = html`
        <div class="m-who">${P.map((s, i) => {
          const fc = loaded[s.name], qq = q(fc);
          return html`<button class="m-tab agenda-row ${i ? '' : 'on'}" data-i="${i}"><span class="an">${ROMAN[i]}</span><span class="m-t"><span class="m-name">${esc(fc.properties?.name ?? s.id)}</span>${qq ? html`<span class="m-q micro">typical travel cost ${num(`${fmt(qq[0], 'usd')}–${fmt(qq[2], 'usd')}/mo`, `facts:${s.name} usd_month p10–p90`)}</span>` : ''}</span></button>`;
        })}</div>
        <div class="m-legend"><span class="micro">their cheapest</span><span class="ramp">${STEPS.map((c) => `<i style="background:${c}"></i>`).join('')}</span><span class="micro">most expensive</span></div>
        <div class="stats m-stats">
          <div><span class="fig">${F('surface_rank_corr_north_vs_ross')}</span><span class="cap">rank correlation between the two maps (Spearman ρ)</span></div>
          <div><span class="fig">${F('surface_cheapest_decile_overlap', { suffix: '%' })}</span><span class="cap">of one student’s cheapest tenth of the city is also the other’s</span></div>
        </div>
        ${A.properties?.caveat ? html`<p class="micro m-cav">${said(A.properties.caveat, 'facts:surface caveat')}</p>` : ''}`;
    }
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'Same city, different identity')}
      <h2 class="enter" style="--i:1">Same city, different identity, <em>different map.</em></h2>
      <div class="map-grid grow">
        <figure class="map-plate enter" style="--i:2">
          <div class="map-box">${body}</div>
          <figcaption class="micro">Plate II · Ann Arbor · monthly travel cost per cell, each student’s own week</figcaption>
        </figure>
        <div class="map-side enter" style="--i:3">
          <p class="sub" style="margin:0">Every cell of Ann Arbor, priced for one student’s own week — the monthly value of the time it would cost them to live there.</p>
          ${side}
        </div>
      </div>`;
  },
  mount(el) {
    const P = pair();
    if (P.length >= 2 && !(P.every((s) => loaded[s.name]) && base)) load().then(() => el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
    el.querySelectorAll<HTMLElement>('.m-tab').forEach((t) => t.addEventListener('click', (e) => { e.stopPropagation(); clearInterval(timer); show(el, Number(t.dataset.i)); }));
  },
  enter(el) {
    clearInterval(timer);
    let i = 0;
    show(el, 0);
    if (!reducedMotion()) timer = window.setInterval(() => { i = 1 - i; show(el, i); }, 3500);
  },
  leave() { clearInterval(timer); },
  notes() {
    return `<p><b>VII · Same city (15 s).</b> The map cross-fades between the North Campus engineer and the Ross student with a Kerrytown job every few seconds (click a name to hold one). Each map is shaded within that student's own range: light = their cheapest places.</p>
      <p>Line: "Same city, different identity, different map — rank correlation only ~0.4, and only ~28% of one student's cheapest tenth is the other's." Travel cost only, no rent; 250 m cells.</p>`;
  },
};

function show(el: HTMLElement, i: number) {
  el.querySelector('.sa')?.classList.toggle('on', i === 0);
  el.querySelector('.sb')?.classList.toggle('on', i === 1);
  el.querySelectorAll('.m-tab').forEach((t, k) => t.classList.toggle('on', k === i));
}
