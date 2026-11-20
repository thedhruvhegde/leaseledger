import type { LegKind, ListingEvaluation } from '../types';
import type { MapLine } from '../components/MapView';

export const LEG_COLOR: Record<LegKind, string> = {
  walk: 'rgb(var(--walk))',
  wait: 'rgb(var(--wait))',
  bus: 'rgb(var(--bus))',
  bike: 'rgb(var(--bike))',
};
export const LEG_LABEL: Record<LegKind, string> = { walk: 'Walk', wait: 'Wait', bus: 'Bus', bike: 'Bike' };

/** Real leg geometry from the engine (TripLeg.path, (lat, lon)) as map lines, deduplicated across days. */
export function legLines(e: ListingEvaluation | undefined): MapLine[] {
  const out: MapLine[] = [];
  const seen = new Set<string>();
  for (const t of e?.commute?.tours ?? []) {
    for (const tr of t.trips) {
      for (const l of tr.legs) {
        const p = l.path;
        if (!p || p.length < 2) continue;
        const key = `${l.kind}|${l.route ?? ''}|${p[0].join(',')}|${p[p.length - 1].join(',')}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ coords: p.map(([lat, lon]) => [lon, lat] as [number, number]), kind: l.kind, exact: true, label: l.kind === 'bus' && l.route ? l.route : null });
      }
    }
  }
  return out;
}
