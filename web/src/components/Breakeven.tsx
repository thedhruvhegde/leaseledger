import type { Breakeven, Listing } from '../types';
import { usdRate } from '../lib/format';

/** Replace listing ids and parameter names in engine text with human words. */
export function humanize(text: string, names: Map<string, Listing> | Record<string, string>): string {
  let s = text;
  const entries: [string, string][] = names instanceof Map ? Array.from(names.entries()).map(([k, v]) => [k, v.name]) : Object.entries(names);
  entries.sort((a, b) => b[0].length - a[0].length);
  for (const [id, name] of entries) s = s.split(id).join(name);
  s = s.replace(/value_of_time\s*([<>])\s*(\d+(?:\.\d+)?)/g, (_, op: string, v: string) => `your time is worth ${op === '<' ? 'under' : 'over'} ${usdRate(Number(v))}/h`);
  s = s.replace(/value_of_time/g, 'value of time');
  return s;
}

export function breakevenSide(b: Breakeven): 'below' | 'above' | null {
  if (/<|under|below/.test(b.direction)) return 'below';
  if (/>|over|above/.test(b.direction)) return 'above';
  return null;
}

/** Number line for a value-of-time breakeven: shaded region = where B wins; marker = you. */
export function BreakevenLine({ b, vot, aName, bName }: { b: Breakeven; vot: number; aName: string; bName: string }) {
  const side = breakevenSide(b);
  const v = b.value;
  const max = Math.max(40, (v ?? 0) * 1.25, vot * 1.25);
  const x = (n: number) => `${(Math.max(0, Math.min(max, n)) / max) * 100}%`;
  const ticks = [0, 10, 20, 30, 40, 60, 80, 100, 150, 200].filter((t) => t <= max);
  if (v == null || side == null) {
    return <div className="rounded-lg bg-raised px-3 py-2 text-sm text-muted">On value of time alone, <b className="text-ink">{bName}</b> never overtakes <b className="text-ink">{aName}</b> in $0–$200/h.</div>;
  }
  const bWinsNow = side === 'below' ? vot < v : vot > v;
  const close = Math.abs(vot - v) / max < 0.12;
  return (
    <figure className="space-y-2" aria-label={`${bName} wins if your time is worth ${side === 'below' ? 'under' : 'over'} ${usdRate(v)} per hour; you are at ${usdRate(vot)} per hour`}>
      <figcaption className="text-sm text-ink">
        <b>{bName}</b> wins if your time is worth <b>{side === 'below' ? 'under' : 'over'} {usdRate(v)}/h</b>; you’re at <b>{usdRate(vot)}/h</b>
        {bWinsNow ? <span className="ml-1 text-good">(so it wins for you now)</span> : <span className="ml-1 text-muted">(so {aName} wins for you now)</span>}.
      </figcaption>
      <div className="relative mx-1 h-[3.75rem]">
        <div className="num absolute top-0 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-ink" style={{ left: x(v) }}>tie {usdRate(v)}{close && <span className="text-accent"> · you {usdRate(vot)}</span>}</div>
        {!close && <div className="num absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-full bg-accent px-2 text-xs font-semibold text-accent-ink" style={{ left: x(vot) }}>you {usdRate(vot)}</div>}
        <div className="absolute inset-x-0 top-[2.25rem] h-2 rounded-full bg-line-strong/60" />
        <div className="absolute top-[2.25rem] h-2 rounded-full" style={side === 'below' ? { left: 0, width: x(v), background: 'rgb(var(--ink))' } : { left: x(v), right: 0, background: 'rgb(var(--ink))' }} />
        <div className="absolute top-[1.5rem] h-[1.75rem] w-0.5 -translate-x-1/2 bg-ink" style={{ left: x(v) }} />
        <div className="absolute top-[1.85rem] h-5 w-5 -translate-x-1/2 rounded-full border-[3px] border-surface bg-accent" style={{ left: x(vot) }} title={`You: ${usdRate(vot)}/h`} />
      </div>
      <div className="relative mx-1 h-4" style={{ marginTop: 4 }}>
        {ticks.map((t) => <span key={t} className="num absolute -translate-x-1/2 text-2xs text-faint" style={{ left: x(t) }}>${t}</span>)}
      </div>
      <div className="flex flex-wrap gap-3 text-2xs text-muted">
        <span className="inline-flex items-center gap-1"><span className="h-2 w-4 rounded-full" style={{ background: 'rgb(var(--ink))' }} />{bName} wins</span>
        <span className="inline-flex items-center gap-1"><span className="h-2 w-4 rounded-full bg-line-strong/60" />{aName} wins</span>
      </div>
    </figure>
  );
}
