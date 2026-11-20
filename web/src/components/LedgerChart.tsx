import type { LedgerLine, ListingEvaluation } from '../types';
import { ProvenanceBadge } from './ui/Badge';
import { usd } from '../lib/format';
import { TIME_FILL } from './ListingCard';

/** One row per ledger line: bar for the point estimate, whisker for low–high, provenance chip. Non-cash lines hatched. */
export function LedgerChart({ e }: { e: ListingEvaluation }) {
  const cash = e.ledger.filter((l) => l.in_cash_total);
  const non = e.ledger.filter((l) => !l.in_cash_total);
  const max = Math.max(1, ...e.ledger.map((l) => Math.max(l.high, l.usd_month)));
  return (
    <div>
      <div className="space-y-1.5">
        {cash.map((l) => <Row key={l.key} l={l} max={max} />)}
      </div>
      <div className="my-2 flex items-baseline justify-between border-t border-line pt-2">
        <span className="text-sm font-semibold">Cash per month</span>
        <span className="num text-sm"><b className="text-base font-semibold">{usd(e.cash_total)}</b> <span className="text-faint">range {usd(e.cash_low)}–{usd(e.cash_high)}</span></span>
      </div>
      {non.length > 0 && (
        <>
          <div className="label mb-1.5 mt-3">Not cash: what the commute costs you</div>
          <div className="space-y-1.5">
            {non.map((l) => <Row key={l.key} l={l} max={max} hatched />)}
          </div>
        </>
      )}
      <div className="mt-2 flex items-baseline justify-between border-t border-line pt-2">
        <span className="text-sm font-semibold">All-in (cash + valued time)</span>
        <span className="num text-lg font-semibold">{usd(e.all_in_total)}<span className="text-xs font-medium text-faint">/mo</span></span>
      </div>
    </div>
  );
}

function Row({ l, max, hatched = false }: { l: LedgerLine; max: number; hatched?: boolean }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  const color = 'rgb(var(--cash))';
  const band = l.high - l.low > 0.5;
  return (
    <div className="group grid grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)_4.5rem] items-center gap-2 text-sm sm:grid-cols-[minmax(0,12.5rem)_minmax(0,1fr)_5rem]" title={l.note}>
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="leading-snug text-ink">{l.label}</span>
        <ProvenanceBadge p={l.provenance} compact />
      </div>
      <div className="relative h-4" aria-hidden>
        <div className="absolute inset-y-1 left-0 rounded-sm" style={{ width: pct(l.usd_month), background: hatched ? TIME_FILL : color, opacity: 0.9 }} />
        {band && (
          <>
            <div className="absolute top-1/2 h-px bg-ink/70" style={{ left: pct(l.low), width: `calc(${pct(l.high)} - ${pct(l.low)})` }} />
            <div className="absolute top-0.5 h-3 w-px bg-ink/70" style={{ left: pct(l.low) }} />
            <div className="absolute top-0.5 h-3 w-px bg-ink/70" style={{ left: pct(l.high) }} />
          </>
        )}
      </div>
      <div className="num text-right">
        <div className="font-semibold text-ink">{usd(l.usd_month)}</div>
        {band && <div className="text-2xs text-faint">{usd(l.low)}–{usd(l.high)}</div>}
      </div>
      {l.note && <div className="col-span-3 -mt-1 hidden text-2xs text-faint group-hover:block">{l.note}</div>}
    </div>
  );
}
