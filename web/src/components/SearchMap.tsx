import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource, Map as MlMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useApp } from '../store/app';
import { MAP_INK, addStreetLayers } from '../lib/basemap';
import { usd } from '../lib/format';
import type { MapLine } from './MapView';

export interface PricePin { id: string; lat: number; lon: number; rank: number | null; price: number; feasible: boolean; name: string; /** shown as a small dot until hovered/selected (keeps a 60-home map legible) */ dot?: boolean }
export interface Place { lat: number; lon: number; label: string }
export interface Anchor { lat: number; lon: number; label: string }

const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });
const css = (name: string) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  return v ? `rgb(${v.split(/\s+/).join(',')})` : '#888';
};

/**
 * The results map: offline street basemap, campus anchors, your places, every other listing as a gray dot,
 * numbered all-in price pins for ranked homes, and the selected home's real week routes.
 */
export default function SearchMap({ pins, others, places, anchors, routes, activeId, hoverId, onHover, onOpen, fitKey, focus }: {
  pins: PricePin[]; others: { lat: number; lon: number; label: string }[]; places: Place[]; anchors: Anchor[]; routes: MapLine[];
  activeId: string | null; hoverId: string | null; onHover: (id: string | null) => void; onOpen: (id: string) => void;
  fitKey: string; focus: [number, number][] | null;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const markers = useRef(new Map<string, { m: maplibregl.Marker; el: HTMLButtonElement }>());
  const extra = useRef<maplibregl.Marker[]>([]);
  const routeLabels = useRef<maplibregl.Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const theme = useApp((s) => s.theme);
  const cb = useRef({ onHover, onOpen });
  cb.current = { onHover, onOpen };

  useEffect(() => {
    if (!el.current) return;
    let m: MlMap;
    const dark = theme === 'dark';
    try {
      m = new maplibregl.Map({
        container: el.current,
        style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': dark ? MAP_INK.dark.bg : MAP_INK.light.bg } }] },
        center: [-83.73, 42.28], zoom: 12.8, attributionControl: false, dragRotate: false, pitchWithRotate: false, preserveDrawingBuffer: true,
      });
    } catch {
      setFailed(true);
      return;
    }
    map.current = m;
    m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Streets: Overture Maps / OSM (ODbL)' }), window.innerWidth < 640 ? 'top-left' : 'bottom-right');
    const zoomClass = () => el.current?.classList.toggle('z-low', m.getZoom() < 13.4);
    m.on('zoomend', zoomClass);
    m.on('load', async () => {
      await addStreetLayers(m, dark);
      m.addSource('others', { type: 'geojson', data: fc([]) });
      m.addLayer({ id: 'others', type: 'circle', source: 'others', paint: { 'circle-radius': 3.5, 'circle-color': css('mute'), 'circle-stroke-width': 1, 'circle-stroke-color': dark ? '#000' : '#fff' } });
      m.addSource('routes', { type: 'geojson', data: fc([]) });
      // one home: colour by mode; two homes (compare): colour by home, A blue / B orange, with a legend
      const color = ['case', ['==', ['get', 'home'], 'a'], css('cmp-a'), ['==', ['get', 'home'], 'b'], css('cmp-b'),
        ['match', ['get', 'kind'], 'bus', css('bus'), 'bike', css('bike'), 'wait', css('wait'), css('ink')]] as unknown as string;
      m.addLayer({ id: 'route-case', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'bus'], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': dark ? '#000' : '#fff', 'line-width': 8 } });
      m.addLayer({ id: 'route-bus', type: 'line', source: 'routes', filter: ['!=', ['get', 'kind'], 'walk'], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': color, 'line-width': 4.5 } });
      m.addLayer({ id: 'route-walk', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'walk'], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': color, 'line-width': 2.5, 'line-opacity': 0.8, 'line-dasharray': [0.6, 1.8] } });
      m.addSource('places', { type: 'geojson', data: fc([]) });
      m.addLayer({ id: 'places', type: 'circle', source: 'places', paint: { 'circle-radius': 5.5, 'circle-color': dark ? '#111' : '#fff', 'circle-stroke-width': 2.5, 'circle-stroke-color': css('ink') } });
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: 'll-pop' });
      for (const layer of ['places', 'others']) {
        m.on('mouseenter', layer, (e) => {
          const f = e.features?.[0];
          if (!f) return;
          pop.setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number]).setText(String(f.properties?.label ?? '')).addTo(m);
        });
        m.on('mouseleave', layer, () => pop.remove());
      }
      setReady(true);
    });
    const mk = markers.current;
    return () => { mk.clear(); m.remove(); map.current = null; setReady(false); };
  }, [theme]);

  // Static layers: other listings, your places, campus anchors
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const pt = (lat: number, lon: number, label: string): GeoJSON.Feature => ({ type: 'Feature', properties: { label }, geometry: { type: 'Point', coordinates: [lon, lat] } });
    (m.getSource('others') as GeoJSONSource | undefined)?.setData(fc(others.map((o) => pt(o.lat, o.lon, o.label))));
    (m.getSource('places') as GeoJSONSource | undefined)?.setData(fc(places.map((o) => pt(o.lat, o.lon, o.label))));
    extra.current.forEach((x) => x.remove());
    extra.current = anchors.map((a) => {
      const d = document.createElement('div');
      d.className = 'map-anchor';
      d.textContent = a.label;
      return new maplibregl.Marker({ element: d }).setLngLat([a.lon, a.lat]).addTo(m);
    });
  }, [others, places, anchors, ready]);

  // Price pins (HTML buttons so they are focusable and readable)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const keep = new Set(pins.map((p) => p.id));
    for (const [id, x] of markers.current) if (!keep.has(id)) { x.m.remove(); markers.current.delete(id); }
    for (const p of pins) {
      let x = markers.current.get(p.id);
      if (!x) {
        const b = document.createElement('button');
        b.type = 'button';
        b.addEventListener('mouseenter', () => cb.current.onHover(p.id));
        b.addEventListener('mouseleave', () => cb.current.onHover(null));
        b.addEventListener('focus', () => cb.current.onHover(p.id));
        b.addEventListener('blur', () => cb.current.onHover(null));
        b.addEventListener('click', (ev) => { ev.stopPropagation(); cb.current.onOpen(p.id); });
        x = { el: b, m: new maplibregl.Marker({ element: b, anchor: 'center' }).setLngLat([p.lon, p.lat]).addTo(m) };
        markers.current.set(p.id, x);
      }
      x.m.setLngLat([p.lon, p.lat]);
      // keep MapLibre's own marker classes (they position the element); replace only ours
      const own = Array.from(x.el.classList).filter((c) => c.startsWith('maplibregl-'));
      x.el.className = [...own, 'price-pin', p.feasible ? '' : 'is-out', p.dot ? 'is-dot' : ''].filter(Boolean).join(' ');
      x.el.innerHTML = `${p.rank != null ? `<span class="pin-rank">${p.rank}</span>` : ''}<span>${usd(p.price)}</span>`;
      x.el.setAttribute('aria-label', `${p.rank != null ? `Rank ${p.rank}, ` : 'Does not fit, '}${p.name}, ${usd(p.price)} a month all-in`);
      x.el.style.zIndex = String(p.dot ? 1 : p.rank != null ? 200 - p.rank : 2);
    }
  }, [pins, ready]);

  // Active / hover state
  useEffect(() => {
    for (const [id, x] of markers.current) {
      const on = id === activeId || id === hoverId;
      x.el.classList.toggle('is-active', on);
      x.el.setAttribute('aria-pressed', String(id === activeId));
      const base = Number(x.el.style.zIndex) % 1000;
      x.el.style.zIndex = String(on ? 1000 + base : base);
    }
  }, [activeId, hoverId, pins]);


  // Routes for the selected (or hovered) home
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource('routes') as GeoJSONSource | undefined)?.setData(fc(routes.map((l) => ({ type: 'Feature', properties: { kind: l.kind, home: l.home ?? '' }, geometry: { type: 'LineString', coordinates: l.coords } }))));
    routeLabels.current.forEach((x) => x.remove());
    routeLabels.current = [];
    const seen = new Set<string>();
    for (const l of routes) {
      const key = `${l.home ?? ''}${l.label}`;
      if (!l.label || seen.has(key) || l.coords.length < 2) continue;
      seen.add(key);
      const d = document.createElement('div');
      d.className = `map-route-label${l.home ? ` is-${l.home}` : ''}`;
      d.textContent = l.home ? `${l.home.toUpperCase()} · ${l.label}` : l.label;
      routeLabels.current.push(new maplibregl.Marker({ element: d }).setLngLat(l.coords[Math.floor(l.coords.length / 2)]).addTo(m));
    }
  }, [routes, ready]);

  // Fit: all homes + places when the result set changes; the selected home's routes when one opens
  const fit = useRef<(animate: boolean) => void>(() => {});
  fit.current = (animate: boolean) => {
    const m = map.current;
    if (!m || !ready) return;
    const pts: [number, number][] = focus && focus.length ? focus : [...pins.map((p) => [p.lon, p.lat] as [number, number]), ...places.map((p) => [p.lon, p.lat] as [number, number])];
    if (pts.length === 0) return;
    const b = new maplibregl.LngLatBounds();
    pts.forEach((p) => b.extend(p));
    m.resize();
    const w = el.current?.clientWidth ?? 800;
    const pad = w < 600 ? { top: 40, bottom: 80, left: 24, right: 56 } : { top: 70, bottom: 110, left: 80, right: 150 };
    m.fitBounds(b, { padding: pad, maxZoom: 15.2, duration: animate ? 500 : 0 });
    el.current?.classList.toggle('z-low', m.getZoom() < 13.4);
  };
  useEffect(() => {
    fit.current(!!focus);
  }, [fitKey, ready, focus]);

  // Refit (without animation) when the container changes size, e.g. on first layout or window resize.
  useEffect(() => {
    const m = map.current;
    if (!m || !el.current) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    let last = el.current.clientWidth;
    const ro = new ResizeObserver(() => {
      m.resize();
      const w = el.current?.clientWidth ?? last;
      if (Math.abs(w - last) < 2) return;
      last = w;
      clearTimeout(t);
      t = setTimeout(() => fit.current(false), 120);
    });
    ro.observe(el.current);
    return () => { ro.disconnect(); clearTimeout(t); };
  }, [ready]);

  if (failed) return <div className="flex h-full items-center justify-center bg-raised text-sm text-faint">Map unavailable in this browser (WebGL off). Every fact on the map is also in the list.</div>;
  return <div ref={el} className="h-full w-full" role="region" aria-label="Map of ranked homes, your places and the selected home's routes" />;
}
