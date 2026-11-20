import type { LedgerLine, ListingEvaluation } from '../types';
import { PROV_META } from './ui/Badge';
import { usd } from '../lib/format';

const SHORT: Record<string, string> = {
  rent: 'rent',
  utilities: 'utilities (est.)',
  insurance: 'renters insurance',
  food_offset: 'meals offset',
  transport_cash: 'bus fares',
  time_value: 'travel time',
  late_night: 'late-night outdoors',
  member_labor: 'co-op work shifts',
  amenity_gap: 'missing preferences',
};
const short = (l: LedgerLine) => SHORT[l.key] ?? l.label.replace(/\s*\(.*\)$/, '').toLowerCase();

/**
 * Split the non-cash ledger lines into the ones the engine adds to the all-in total and the ones it reports
 * beside it. Purely from API fields: the included set is whichever makes cash + lines = all_in_total.
 */
export function receiptLines(e: ListingEvaluation): { included: LedgerLine[]; excluded: LedgerLine[] } {
  const non = e.ledger.filter((l) => !l.in_cash_total && Math.abs(l.usd_month) >= 0.5);
  const target = e.all_in_total - e.cash_total;
  const sum = non.reduce((a, l) => a + l.usd_month, 0);
  if (Math.abs(sum - target) <= 1.5) return { included: non, excluded: [] };
  for (const x of non) {
    if (Math.abs(sum - x.usd_month - target) <= 1.5) return { included: non.filter((y) => y !== x), excluded: [x] };
  }
  return { included: non, excluded: [] };
}

const b0 = (v: number) => usd(v).replace('$', '').replace('-', '−');
const band = (lo: number, hi: number) => `${b0(lo)}…${b0(hi)}`;

function Row({ label, value, l, bands, op, strong = false }: { label: string; value: number; l?: LedgerLine; bands: boolean; op?: string; strong?: boolean }) {
  const hasBand = !!l && l.high - l.low > 0.5;
  return (
    <div className={`flex items-baseline ${strong ? 'font-semibold text-ink' : 'text-ink'}`} title={l?.note || undefined}>
      <span className="w-[2ch] shrink-0 text-faint" aria-hidden>{op ?? ''}</span>
      <span className="truncate">{label}</span>
      {l && <span className="ml-1.5 shrink-0 text-[0.85em] text-mute" title={`${PROV_META[l.provenance].label}: ${PROV_META[l.provenance].desc}`}>{PROV_META[l.provenance].code}</span>}
      <span className="leader" aria-hidden />
      <span className="shrink-0 text-right">{usd(value).replace('-', '−')}</span>
      {bands && <span className="w-[12ch] shrink-0 text-right text-[0.85em] text-mute">{hasBand ? band(l!.low, l!.high) : ''}</span>}
    </div>
  );
}

/**
 * The ledger as a receipt: JetBrains Mono, dotted leaders, tabular numbers, low–high bands in mute gray,
 * a rule above the all-in total. Every number is an API ledger field.
 */
export function Receipt({ e, title, bands = true, size = 'md', className = '', showExcluded = true }: {
  e: ListingEvaluation; title?: string; bands?: boolean; size?: 'md' | 'lg'; className?: string; showExcluded?: boolean;
}) {
  const { included, excluded } = receiptLines(e);
  const cash = e.ledger.filter((l) => l.in_cash_total && Math.abs(l.usd_month) >= 0.5);
  const text = size === 'lg' ? 'text-[0.9375rem] leading-7' : 'text-[0.8125rem] leading-6';
  return (
    <div className={`mono rounded-xl border border-line bg-surface p-4 sm:p-5 ${text} ${className}`} role="group" aria-label={`All-in monthly cost breakdown${title ? ` for ${title}` : ''}`}>
      <div className="mb-2 flex items-baseline justify-between gap-3 text-faint">
        <span className="truncate">{title ? `receipt · ${title}` : 'receipt · per person / month'}</span>
        {bands && <span className="shrink-0 text-[0.85em] text-mute">low–high</span>}
      </div>
      {cash.map((l) => <Row key={l.key} label={short(l)} value={l.usd_month} l={l} bands={bands} />)}
      <div className="my-1 border-t border-dashed border-line-strong" />
      <Row label="cash you pay" value={e.cash_total} bands={false} strong />
      {included.map((l) => <Row key={l.key} label={short(l)} value={l.usd_month} l={l} bands={bands} op="+" />)}
      <div className="mt-2 border-t-2 border-ink pt-2">
        <div className={`flex items-baseline font-semibold ${size === 'lg' ? 'text-xl' : 'text-lg'}`}>
          <span className="w-[2ch] shrink-0 text-faint" aria-hidden>=</span>
          <span className="whitespace-nowrap">all-in<span className="text-[0.6em] font-normal text-faint"> /mo</span></span>
          <span className="leader" aria-hidden />
          <span>{usd(e.all_in_total)}</span>
          {bands && <span className="w-[12ch] shrink-0" />}
        </div>
      </div>
      {showExcluded && excluded.length > 0 && (
        <div className="mt-2 text-[0.85em] text-faint">not in all-in: {excluded.map((l) => `${short(l)} ${usd(l.usd_month)}`).join(', ')}</div>
      )}
    </div>
  );
}
