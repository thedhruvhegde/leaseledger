import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource, Map as MlMap, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useApp } from '../store/app';

export interface MapPoint { id: string; lat: number; lon: number; label: string; kind: 'home' | 'listing' | 'building' | 'pick' }
/** coords are [lon, lat]. `exact` = real geometry (street path / bus stops); otherwise a straight schematic line. */
export interface MapLine { coords: [number, number][]; kind: 'walk' | 'bus' | 'bike' | 'wait'; exact?: boolean; label?: string | null }

const css = (name: string) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  return v ? `rgb(${v.split(/\s+/).join(',')})` : '#888';
};

let basemapCache: Promise<GeoJSON.FeatureCollection | null> | null = null;
function loadBasemap() {
  basemapCache ??= fetch('/basemap.geojson').then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return basemapCache;
}

function style(dark: boolean): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'bg', type: 'background', paint: { 'background-color': dark ? '#12151c' : '#f3f4f6' } }],
  };
}

const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });

/** Offline MapLibre map: local Overture-derived street basemap, no tile servers. */
export function MapView({ points, lines = [], onPick, height = 320, center, schematic = true, ariaLabel = 'Map' }: {
  points: MapPoint[]; lines?: MapLine[]; onPick?: (lat: number, lon: number) => void; height?: number | string;
  center?: [number, number]; schematic?: boolean; ariaLabel?: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const theme = useApp((s) => s.theme);
  const pickRef = useRef(onPick);
  const labels = useRef<maplibregl.Marker[]>([]);
  pickRef.current = onPick;

  useEffect(() => {
    if (!el.current) return;
    let m: MlMap;
    try {
      m = new maplibregl.Map({
        container: el.current,
        style: style(theme === 'dark'),
        center: center ? [center[1], center[0]] : [-83.735, 42.281],
        zoom: 12.6,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        preserveDrawingBuffer: true,
      });
    } catch {
      setFailed(true);
      return;
    }
    map.current = m;
    if (import.meta.env.DEV) (window as unknown as { __map?: MlMap }).__map = m;
    m.on('error', (e) => console.warn('map error', e.error?.message ?? e));
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Streets: Overture Maps / OSM (ODbL)' }));
    m.on('load', async () => {
      const bm = await loadBasemap();
      if (bm && m.getStyle()) {
        m.addSource('base', { type: 'geojson', data: bm });
        const ink = theme === 'dark' ? ['#2a3140', '#3a4356', '#4b566e'] : ['#e3e6eb', '#d1d5db', '#b8bec8'];
        m.addLayer({ id: 'paths', type: 'line', source: 'base', filter: ['==', ['get', 'k'], 'path'], paint: { 'line-color': ink[0], 'line-width': 0.6, 'line-dasharray': [2, 1.5] } });
        m.addLayer({ id: 'service', type: 'line', source: 'base', filter: ['==', ['get', 'k'], 'service'], paint: { 'line-color': ink[0], 'line-width': 0.7 } });
        m.addLayer({ id: 'minor', type: 'line', source: 'base', filter: ['==', ['get', 'k'], 'minor'], paint: { 'line-color': ink[1], 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.6, 15, 2.2] } });
        m.addLayer({ id: 'major', type: 'line', source: 'base', filter: ['==', ['get', 'k'], 'major'], paint: { 'line-color': ink[2], 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.2, 15, 4] } });
      }
      m.addSource('lines', { type: 'geojson', data: fc([]) });
      const lineColor = ['match', ['get', 'kind'], 'bus', css('bus'), 'bike', css('bike'), 'wait', css('wait'), css('walk')] as unknown as string;
      // Solid: exact bus/bike geometry. Dashed: walking paths and straight schematic fallbacks.
      m.addLayer({ id: 'lines', type: 'line', source: 'lines', filter: ['==', ['get', 'dashed'], false], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: {
        'line-color': lineColor, 'line-width': 4, 'line-opacity': 0.9 } });
      m.addLayer({ id: 'lines-dashed', type: 'line', source: 'lines', filter: ['==', ['get', 'dashed'], true], layout: { 'line-join': 'round' }, paint: {
        'line-color': lineColor, 'line-width': 2.5, 'line-opacity': 0.9, 'line-dasharray': [1.6, 1.2] } });
      m.addSource('pts', { type: 'geojson', data: fc([]) });
      m.addLayer({ id: 'pts-listing', type: 'circle', source: 'pts', filter: ['==', ['get', 'kind'], 'listing'], paint: { 'circle-radius': 4, 'circle-color': css('faint'), 'circle-stroke-width': 1, 'circle-stroke-color': '#fff' } });
      m.addLayer({ id: 'pts-building', type: 'circle', source: 'pts', filter: ['==', ['get', 'kind'], 'building'], paint: { 'circle-radius': 6, 'circle-color': css('surface'), 'circle-stroke-width': 2.5, 'circle-stroke-color': css('ink') } });
      m.addLayer({ id: 'pts-home', type: 'circle', source: 'pts', filter: ['any', ['==', ['get', 'kind'], 'home'], ['==', ['get', 'kind'], 'pick']], paint: { 'circle-radius': 9, 'circle-color': css('accent'), 'circle-stroke-width': 3, 'circle-stroke-color': '#fff' } });
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
      for (const layer of ['pts-listing', 'pts-building', 'pts-home']) {
        m.on('mouseenter', layer, (e) => {
          const f = e.features?.[0];
          if (!f) return;
          m.getCanvas().style.cursor = 'pointer';
          pop.setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number]).setText(String(f.properties?.label ?? '')).addTo(m);
        });
        m.on('mouseleave', layer, () => { m.getCanvas().style.cursor = ''; pop.remove(); });
      }
      m.on('click', (e) => pickRef.current?.(e.lngLat.lat, e.lngLat.lng));
      setReady(true);
    });
    return () => { m.remove(); map.current = null; setReady(false); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, schematic]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource('pts') as GeoJSONSource | undefined)?.setData(fc(points.map((p) => ({ type: 'Feature', properties: { kind: p.kind, label: p.label, id: p.id }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } }))));
    (m.getSource('lines') as GeoJSONSource | undefined)?.setData(fc(lines.map((l) => ({ type: 'Feature', properties: { kind: l.kind, dashed: !l.exact || l.kind === 'walk' }, geometry: { type: 'LineString', coordinates: l.coords } }))));
    // Route labels as HTML markers (offline: no glyph server for symbol layers). One label per route.
    labels.current.forEach((mk) => mk.remove());
    labels.current = [];
    const seenRoutes = new Set<string>();
    for (const l of lines) {
      if (!l.label || seenRoutes.has(l.label) || l.coords.length < 2) continue;
      seenRoutes.add(l.label);
      const mid = l.coords[Math.floor(l.coords.length / 2)];
      const el = document.createElement('div');
      el.className = 'map-route-label';
      el.textContent = l.label;
      labels.current.push(new maplibregl.Marker({ element: el }).setLngLat(mid).addTo(m));
    }
    m.resize();
    const focus = points.filter((p) => p.kind !== 'listing' || points.length < 12);
    if (focus.length >= 2) {
      const b = new maplibregl.LngLatBounds();
      focus.forEach((p) => b.extend([p.lon, p.lat]));
      m.fitBounds(b, { padding: 40, maxZoom: 15, duration: 400 });
    } else if (focus.length === 1) m.easeTo({ center: [focus[0].lon, focus[0].lat], duration: 400 });
  }, [points, lines, ready]);

  if (failed) return <div className="flex items-center justify-center rounded-lg bg-raised text-sm text-muted" style={{ height }}>Map unavailable in this browser (WebGL off).</div>;
  return (
    <div className="relative overflow-hidden rounded-lg border border-line" style={{ height }}>
      <div ref={el} className="h-full w-full" role="region" aria-label={ariaLabel} />
      {schematic && lines.some((l) => !l.exact) && (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded-full bg-surface/90 px-2.5 py-0.5 text-2xs text-muted">Straight lines are schematic, not exact routes</div>
      )}
    </div>
  );
}

export default MapView;
