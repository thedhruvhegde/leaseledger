import { memo, useMemo } from 'react';
import { MAP_INK, useRoads, type Road } from '../lib/basemap';
import type { MapLine } from './MapView';
import { useApp } from '../store/app';

const W = 320;
const H = 200;
const HALF_M = 460; // half the thumbnail width in metres

/**
 * Listing thumbnail without photos: the streets around the home, drawn from the offline basemap, with the
 * home's own week routes (street walk paths and bus legs from the engine) and a home marker. Never a picture of
 * the building; it is labelled as a map for screen readers.
 */
export const MapThumb = memo(function MapThumb({ lat, lon, lines = [], label, className = '', chips = true }: {
  lat: number; lon: number; lines?: MapLine[]; label: string; className?: string; chips?: boolean;
}) {
  const roads = useRoads();
  const dark = useApp((s) => s.theme === 'dark');
  const c = dark ? MAP_INK.dark : MAP_INK.light;
  const proj = useMemo(() => {
    const kx = Math.cos((lat * Math.PI) / 180) * 111320;
    const ky = 110540;
    const s = W / 2 / HALF_M;
    return (x: number, y: number): [number, number] => [W / 2 + (x - lon) * kx * s, H / 2 - (y - lat) * ky * s];
  }, [lat, lon]);

  const streets = useMemo(() => {
    if (!roads) return null;
    const dLon = (HALF_M * 1.1) / (Math.cos((lat * Math.PI) / 180) * 111320);
    const dLat = (HALF_M * 1.1 * (H / W)) / 110540;
    const box = [lon - dLon, lat - dLat, lon + dLon, lat + dLat];
    const pick = (k: Road['k']) => roads
      .filter((r) => r.k === k && r.bbox[2] >= box[0] && r.bbox[0] <= box[2] && r.bbox[3] >= box[1] && r.bbox[1] <= box[3])
      .map((r) => 'M' + r.coords.map(([x, y]) => proj(x, y).map((v) => v.toFixed(1)).join(' ')).join('L'))
      .join('');
    return { major: pick('major'), minor: pick('minor'), service: pick('service') };
  }, [roads, lat, lon, proj]);

  const routes = useMemo(() => lines.map((l) => ({ kind: l.kind, label: l.label, d: 'M' + l.coords.map(([x, y]) => proj(x, y).map((v) => v.toFixed(1)).join(' ')).join('L') })), [lines, proj]);
  const busLabels = Array.from(new Set(lines.filter((l) => l.kind === 'bus' && l.label).map((l) => l.label as string))).slice(0, 3);

  return (
    <div className={`relative overflow-hidden ${className}`} style={{ background: c.bg }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className="block h-full w-full" role="img" aria-label={`Map: streets around ${label}${busLabels.length ? `, with your bus route ${busLabels.join(', ')}` : ''}`}>
        {streets && (
          <g fill="none" strokeLinecap="round" strokeLinejoin="round">
            <path d={streets.service} stroke={c.casing} strokeWidth={0.8} />
            <path d={streets.minor} stroke={c.casing} strokeWidth={4.2} />
            <path d={streets.major} stroke={c.majorCasing} strokeWidth={7} />
            <path d={streets.minor} stroke={c.road} strokeWidth={2.8} />
            <path d={streets.major} stroke={c.major} strokeWidth={5.4} />
          </g>
        )}
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          {routes.filter((r) => r.kind !== 'bus').map((r, i) => (
            <path key={`w${i}`} d={r.d} stroke={r.kind === 'bike' ? 'rgb(var(--bike))' : 'rgb(var(--ink))'} strokeWidth={2} strokeDasharray={r.kind === 'walk' ? '1 4' : undefined} opacity={0.75} />
          ))}
          {routes.filter((r) => r.kind === 'bus').map((r, i) => (
            <g key={`b${i}`}>
              <path d={r.d} stroke={c.road} strokeWidth={6.5} />
              <path d={r.d} stroke="rgb(var(--bus))" strokeWidth={3.5} />
            </g>
          ))}
        </g>
        <circle cx={W / 2} cy={H / 2} r={9} fill="rgb(var(--ink))" stroke={c.road} strokeWidth={3} />
        <path d={`M${W / 2 - 4} ${H / 2 + 0.5} L${W / 2} ${H / 2 - 3.5} L${W / 2 + 4} ${H / 2 + 0.5} M${W / 2 - 2.6} ${H / 2 - 0.5} V${H / 2 + 3.5} H${W / 2 + 2.6} V${H / 2 - 0.5}`} fill="none" stroke={c.road} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      {chips && busLabels.length > 0 && (
        <div className="pointer-events-none absolute bottom-2 left-2 flex gap-1">
          {busLabels.map((b) => <span key={b} className="map-route-label !static">{b}</span>)}
        </div>
      )}
    </div>
  );
});
