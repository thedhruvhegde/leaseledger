#!/usr/bin/env node
// Turn web/public/basemap.geojson (3.7 MB, street lines) into a compact projected SVG path file
// for the deck's map: public/basemap-paths.json. Runs before dev/build; skips when up to date.
import { readFileSync, writeFileSync, statSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const src = resolve(root, '../web/public/basemap.geojson');
const campusSrc = resolve(root, '../web/public/campus.geojson');
const out = resolve(root, 'public/basemap-paths.json');

if (!existsSync(src)) {
  console.warn(`prep-basemap: ${src} not found; map chapter will draw without streets`);
  process.exit(0);
}
if (existsSync(out) && statSync(out).mtimeMs > statSync(src).mtimeMs && statSync(out).mtimeMs > statSync(new URL(import.meta.url)).mtimeMs) {
  process.exit(0);
}

// Map window: central Ann Arbor + North Campus (all listings and buildings sit inside it).
const BOUNDS = { west: -83.775, east: -83.69, south: 42.245, north: 42.31 };
const W = 1000;
const kx = Math.cos(((BOUNDS.north + BOUNDS.south) / 2) * Math.PI / 180);
const H = Math.round((W * (BOUNDS.north - BOUNDS.south)) / ((BOUNDS.east - BOUNDS.west) * kx));
const px = (lon) => ((lon - BOUNDS.west) / (BOUNDS.east - BOUNDS.west)) * W;
const py = (lat) => ((BOUNDS.north - lat) / (BOUNDS.north - BOUNDS.south)) * H;

const g = JSON.parse(readFileSync(src, 'utf8'));
const layers = { major: [], minor: [], service: [] };
for (const f of g.features) {
  const k = f.properties?.k;
  if (!(k in layers) || f.geometry?.type !== 'LineString') continue;
  const cs = f.geometry.coordinates;
  if (!cs.some(([x, y]) => x >= BOUNDS.west && x <= BOUNDS.east && y >= BOUNDS.south && y <= BOUNDS.north)) continue;
  let d = '', last = '';
  cs.forEach(([x, y], i) => {
    const p = `${px(x).toFixed(1)} ${py(y).toFixed(1)}`;
    if (p === last) return;
    d += (i === 0 ? 'M' : 'L') + p;
    last = p;
  });
  layers[k].push(d);
}
const campus = existsSync(campusSrc)
  ? JSON.parse(readFileSync(campusSrc, 'utf8')).features.map((f) => ({
      id: f.properties.id, name: f.properties.name, campus: f.properties.campus,
      x: +px(f.geometry.coordinates[0]).toFixed(1), y: +py(f.geometry.coordinates[1]).toFixed(1),
    }))
  : [];
const res = { bounds: BOUNDS, width: W, height: H, major: layers.major.join(''), minor: layers.minor.join(''), service: layers.service.join(''), campus };
writeFileSync(out, JSON.stringify(res));
console.log(`prep-basemap: wrote ${out} (${(JSON.stringify(res).length / 1e6).toFixed(2)} MB, ${W}x${H})`);
