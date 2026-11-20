// Ink route maps over the offline Ann Arbor street basemap (public/basemap-paths.json, made by scripts/prep-basemap.mjs).
// Geometry comes from the API: POST /compare returns every trip leg of a home's week with its `path` ([lat, lon] pairs),
// so every line drawn here is a leg the engine actually routed on the real timetable.
import { esc } from './lib';

export type Base = {
  bounds: { west: number; east: number; south: number; north: number };
  width: number; height: number; major: string; minor: string; service: string;
  campus: { id: string; name: string; x: number; y: number }[];
};
let basePromise: Promise<Base | null> | null = null;
export let base: Base | null = null;
/** Load the basemap once; resolves null when it is missing (maps then draw routes only). */
export function loadBase(): Promise<Base | null> {
  basePromise ??= fetch('./basemap-paths.json').then((r) => (r.ok ? r.json() : null)).catch(() => null).then((b) => (base = b));
  return basePromise;
}

const proj = (b: Base) => {
  const { west, east, south, north } = b.bounds;
  return (lat: number, lon: number): [number, number] => [((lon - west) / (east - west)) * b.width, ((north - lat) / (north - south)) * b.height];
};

export type Leg = { kind: string; path?: [number, number][] | null; route?: string | null };
/** All legs of an evaluation that carries commute.tours (POST /compare a|b). */
export const legsOf = (ev: any): Leg[] =>
  (ev?.commute?.tours ?? []).flatMap((t: any) => (t.trips ?? []).flatMap((tr: any) => tr.legs ?? [])).filter((l: Leg) => l.path && l.path.length > 1);

/** Unique leg geometries projected to basemap units, buses first. */
export function projectLegs(b: Base, legs: Leg[]) {
  const P = proj(b);
  const seen = new Set<string>();
  const out: { d: string; kind: 'bus' | 'walk'; x0: number; y0: number; x1: number; y1: number }[] = [];
  for (const l of legs) {
    const pts = l.path!.map(([la, lo]) => P(la, lo));
    const d = 'M' + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join('L');
    if (seen.has(d)) continue;
    seen.add(d);
    const [x0, y0] = pts[0], [x1, y1] = pts[pts.length - 1];
    out.push({ d, kind: l.kind === 'bus' ? 'bus' : 'walk', x0, y0, x1, y1 });
  }
  return out.sort((a, c) => (a.kind === c.kind ? 0 : a.kind === 'walk' ? -1 : 1));
}

/** Bounding box (basemap units) of a set of evaluations' legs. */
export function bboxOf(b: Base, evs: any[]) {
  const P = proj(b);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const ev of evs) for (const l of legsOf(ev)) for (const [la, lo] of l.path!) {
    const [x, y] = P(la, lo);
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  return { x0, y0, x1, y1 };
}

/** The home point = first point of the first leg of the week (every tour starts at home). */
export function homeOf(b: Base, ev: any): [number, number] | null {
  const l = legsOf(ev)[0];
  return l ? proj(b)(l.path![0][0], l.path![0][1]) : null;
}

/** SVG markup for one home's week of routes (draw-on animated via CSS: .rt path, --k stagger). */
export function routeLayer(b: Base, ev: any, cls = '', stagger = 40): string {
  const legs = projectLegs(b, legsOf(ev));
  const ends = new Map<string, [number, number]>();
  const home = homeOf(b, ev);
  const near = (x: number, y: number, p: [number, number] | null) => !!p && Math.hypot(x - p[0], y - p[1]) < 3;
  const busEnds = legs.filter((l) => l.kind === 'bus').flatMap((l) => [[l.x0, l.y0], [l.x1, l.y1]] as [number, number][]);
  legs.forEach((l) => {
    if (l.kind !== 'walk' || near(l.x1, l.y1, home) || busEnds.some((p) => near(l.x1, l.y1, p))) return;
    ends.set(`${Math.round(l.x1)},${Math.round(l.y1)}`, [l.x1, l.y1]);
  });
  return `<g class="rt ${esc(cls)}">
    ${legs.map((l, i) => `<path d="${l.d}" pathLength="1" class="rt-${l.kind}" style="--k:${i};--st:${stagger}ms"/>`).join('')}
    ${[...ends.values()].map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.2" class="rt-dest"/>`).join('')}
    ${home ? `<circle cx="${home[0].toFixed(1)}" cy="${home[1].toFixed(1)}" r="9" class="rt-home-ring"/><circle cx="${home[0].toFixed(1)}" cy="${home[1].toFixed(1)}" r="4.5" class="rt-home"/>` : ''}
  </g>`;
}

/** Street layers. */
export const streets = (b: Base, minor = true) =>
  `${minor ? `<path d="${b.minor}" class="st-minor"/>` : ''}<path d="${b.major}" class="st-major"/>`;
