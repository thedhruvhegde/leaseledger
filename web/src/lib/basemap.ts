import type maplibregl from 'maplibre-gl';
/**
 * Offline basemap (Overture/OSM-derived street lines in /basemap.geojson) shared by the MapLibre maps and the
 * SVG listing thumbnails. One fetch per session; a bbox index makes thumbnail clipping cheap.
 */
import { useEffect, useState } from 'react';

export type RoadKind = 'major' | 'minor' | 'service' | 'path';
export interface Road { k: RoadKind; coords: [number, number][]; bbox: [number, number, number, number] }

let cache: Promise<GeoJSON.FeatureCollection | null> | null = null;
export function loadBasemap(): Promise<GeoJSON.FeatureCollection | null> {
  cache ??= fetch('/basemap.geojson').then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return cache;
}

let roadsCache: Promise<Road[]> | null = null;
export function loadRoads(): Promise<Road[]> {
  roadsCache ??= loadBasemap().then((fc) => {
    const out: Road[] = [];
    for (const f of fc?.features ?? []) {
      if (f.geometry.type !== 'LineString') continue;
      const coords = f.geometry.coordinates as [number, number][];
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const [x, y] of coords) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      out.push({ k: (f.properties?.k ?? 'minor') as RoadKind, coords, bbox: [x0, y0, x1, y1] });
    }
    return out;
  });
  return roadsCache;
}

export function useRoads(): Road[] | null {
  const [roads, setRoads] = useState<Road[] | null>(null);
  useEffect(() => {
    let alive = true;
    void loadRoads().then((r) => alive && setRoads(r));
    return () => { alive = false; };
  }, []);
  return roads;
}

/** Map palette, light and dark: desaturated so pins and routes carry the colour. */
export const MAP_INK = {
  light: { bg: '#f0f0ed', casing: '#d3d3cd', road: '#ffffff', major: '#ffffff', majorCasing: '#c2c2bb', path: '#d0d0ca' },
  dark: { bg: '#141414', casing: '#262626', road: '#2b2b2b', major: '#3a3a3a', majorCasing: '#1f1f1f', path: '#2a2a2a' },
};

/** Street layers (casing + fill, like a printed street map) for a MapLibre map whose style has loaded. */
export async function addStreetLayers(m: import('maplibre-gl').Map, dark: boolean): Promise<void> {
  const bm = await loadBasemap();
  if (!bm || !m.getStyle()) return;
  const c = dark ? MAP_INK.dark : MAP_INK.light;
  const w = (a: number, b: number) => ['interpolate', ['exponential', 1.6], ['zoom'], 11, a, 16, b] as unknown as number;
  m.addSource('base', { type: 'geojson', data: bm });
  const k = (v: string) => ['==', ['get', 'k'], v] as unknown as maplibregl.FilterSpecification;
  m.addLayer({ id: 'paths', type: 'line', source: 'base', filter: k('path'), minzoom: 13.5, paint: { 'line-color': c.path, 'line-width': 0.8, 'line-dasharray': [2, 1.5] } });
  m.addLayer({ id: 'service', type: 'line', source: 'base', filter: k('service'), paint: { 'line-color': c.casing, 'line-width': w(0.4, 2) } });
  m.addLayer({ id: 'minor-case', type: 'line', source: 'base', filter: k('minor'), layout: { 'line-join': 'round' }, paint: { 'line-color': c.casing, 'line-width': w(1.4, 8) } });
  m.addLayer({ id: 'major-case', type: 'line', source: 'base', filter: k('major'), layout: { 'line-join': 'round' }, paint: { 'line-color': c.majorCasing, 'line-width': w(2.6, 12) } });
  m.addLayer({ id: 'minor', type: 'line', source: 'base', filter: k('minor'), layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': c.road, 'line-width': w(0.6, 6) } });
  m.addLayer({ id: 'major', type: 'line', source: 'base', filter: k('major'), layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': c.major, 'line-width': w(1.6, 9.5) } });
}
