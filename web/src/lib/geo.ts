import type { Event } from '../types';

export function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const r = 6371;
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((b.lon - a.lon) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

/** Building the student visits most often per week (by event-days). */
export function mostFrequentBuilding(events: Event[]): string | null {
  const c = new Map<string, number>();
  for (const e of events) if (e.building_id) c.set(e.building_id, (c.get(e.building_id) ?? 0) + e.days.length);
  let best: string | null = null;
  let n = -1;
  for (const [k, v] of c) if (v > n) { best = k; n = v; }
  return best;
}
