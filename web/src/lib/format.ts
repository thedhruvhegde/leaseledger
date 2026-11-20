import type { Day } from '../types';

const usd0 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "$1,240" (rounded). Negative zero is normalised. */
export function usd(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const r = Math.round(v);
  return usd0.format(r === 0 ? 0 : r);
}

/** "$9.40" for rates. */
export function usdRate(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return usd2.format(v);
}

/** Signed money delta: "+$42", "−$18", "±$0". Uses a real minus sign for legibility. */
export function signedUsd(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  const r = Math.round(v);
  if (r === 0) return '±$0';
  return `${r > 0 ? '+' : '−'}${usd0.format(Math.abs(r))}`;
}

/** Signed plain number with unit: signed(1.25,'h',1) -> "+1.3 h". */
export function signed(v: number, unit = '', digits = 0): string {
  const f = Number(v.toFixed(digits));
  const s = Math.abs(f).toFixed(digits);
  const u = unit ? (unit.startsWith('/') || unit === '%' ? unit : ` ${unit}`) : '';
  if (f === 0) return `±${s}${u}`;
  return `${f > 0 ? '+' : '−'}${s}${u}`;
}

/** 135 -> "2 h 15 min", 45 -> "45 min", 0 -> "0 min". */
export function duration(min: number | null | undefined): string {
  if (min == null || !Number.isFinite(min)) return '—';
  const m = Math.round(min);
  if (Math.abs(m) < 60) return `${m} min`;
  const h = Math.trunc(m / 60);
  const r = Math.abs(m % 60);
  return r === 0 ? `${h} h` : `${h} h ${r} min`;
}

/** minutes -> hours with one decimal: 412 -> "6.9 h". */
export function hours(min: number | null | undefined, digits = 1): string {
  if (min == null || !Number.isFinite(min)) return '—';
  return `${(min / 60).toFixed(digits)} h`;
}

/** Minutes after service-day midnight -> "9:05 AM". Values >= 1440 wrap ("1:00 AM"). */
export function clock(min: number, opts: { compact?: boolean } = {}): string {
  const m = ((Math.round(min) % 1440) + 1440) % 1440;
  const h24 = Math.floor(m / 60);
  const mm = m % 60;
  const ampm = h24 < 12 ? 'AM' : 'PM';
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  if (opts.compact) return mm === 0 ? `${h12}${ampm === 'AM' ? 'a' : 'p'}` : `${h12}:${String(mm).padStart(2, '0')}${ampm === 'AM' ? 'a' : 'p'}`;
  return `${h12}:${String(mm).padStart(2, '0')} ${ampm}`;
}

/** "9:00" 24h for inputs. */
export function hhmm(min: number): string {
  const m = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

/** Parse "09:30" -> 570. Hours before 06:00 are treated as after midnight (service day): "01:00" -> 1500. */
export function parseHhmm(s: string, lateCutoffHour = 6): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const mm = Number(m[2]);
  if (h > 23 || mm > 59) return null;
  const v = h * 60 + mm;
  return h < lateCutoffHour ? v + 1440 : v;
}

export const DAY_SHORT: Record<Day, string> = { M: 'Mon', T: 'Tue', W: 'Wed', R: 'Thu', F: 'Fri', S: 'Sat', U: 'Sun' };
export const DAY_LONG: Record<Day, string> = { M: 'Monday', T: 'Tuesday', W: 'Wednesday', R: 'Thursday', F: 'Friday', S: 'Saturday', U: 'Sunday' };

/** ["M","W","F"] -> "Mon, Wed, Fri"; all weekdays -> "Weekdays"; all -> "Every day". */
export function daysLabel(days: Day[]): string {
  const order: Day[] = ['M', 'T', 'W', 'R', 'F', 'S', 'U'];
  const s = order.filter((d) => days.includes(d));
  if (s.length === 7) return 'Every day';
  if (s.length === 5 && !s.includes('S') && !s.includes('U')) return 'Weekdays';
  if (s.length === 2 && s.includes('S') && s.includes('U')) return 'Weekends';
  return s.map((d) => DAY_SHORT[d]).join(', ');
}

/** Frequency format (Gigerenzer): 0.656 of 2000 -> "1,312 of 2,000". */
export function frequency(share: number, n: number): string {
  const k = Math.round(share * n);
  return `${k.toLocaleString('en-US')} of ${n.toLocaleString('en-US')}`;
}

/** Natural frequency per 100 for icon arrays. */
export function per100(share: number): number {
  return Math.max(0, Math.min(100, Math.round(share * 100)));
}

export function ordinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Snap minutes to a grid step (default 15). */
export function snap(min: number, step = 15): number {
  return Math.round(min / step) * step;
}

export function pluralize(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
