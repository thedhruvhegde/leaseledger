import type { Building, Event } from '../types';

const COURSE = /\b([A-Za-z]{2,6})\s?-?(\d{3}[A-Za-z]?)\b/;

/** Short place tag: the shortest all-caps-ish alias ("BBB", "UGLI", "CCRB"), else the first word of the name. */
export function shortPlace(b?: Building): string {
  if (!b) return '';
  const cands = [...b.aliases, b.name].filter((a) => a && a.length <= 8 && !/\s/.test(a));
  cands.sort((x, y) => x.length - y.length);
  return cands[0] ?? b.name.split(/\s+/)[0];
}

/**
 * Compact label for narrow blocks: course code + room ("EECS 281 · BBB"), or the label's first words without the
 * "in/at <place>" tail ("gym · CCRB"). The full label stays in the tooltip.
 */
export function compactLabel(e: Pick<Event, 'label'>, b?: Building): string {
  const place = shortPlace(b);
  const m = COURSE.exec(e.label);
  let head: string;
  if (m && !/^(room|rm|bus|route)$/i.test(m[1])) head = `${m[1].toUpperCase()} ${m[2].toUpperCase()}`;
  else {
    head = e.label.replace(/\s+(in|at|@)\s+.*$/i, '').trim();
    if (b) for (const a of [b.name, ...b.aliases]) head = head.replace(new RegExp(`\\b${a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i'), '').trim();
    head = head.split(/\s+/).slice(0, 2).join(' ');
  }
  if (!head) return place || e.label;
  return place && !head.toLowerCase().includes(place.toLowerCase()) ? `${head} · ${place}` : head;
}

/** Label candidates from longest to shortest: full, "EECS 281 · BBB", "EECS 281", "281" / first word. */
export function labelCandidates(e: Pick<Event, 'label'>, b?: Building): string[] {
  const full = e.label;
  const compact = compactLabel(e, b);
  const head = compact.split(' · ')[0];
  const m = COURSE.exec(e.label);
  const tiny = m ? m[2].toUpperCase() : head.split(/\s+/)[0];
  return Array.from(new Set([full, compact, head, tiny].filter(Boolean)));
}

/** The longest candidate that fits `px` at ~`charPx` per character (plus padding); '' if none fits. */
export function fitLabel(cands: string[], px: number, charPx = 5.6, pad = 8): string {
  return cands.find((c) => c.length * charPx + pad <= px) ?? '';
}
