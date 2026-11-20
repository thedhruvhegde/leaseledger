import type { DiffDelta, Listing, ListingEvaluation } from '../types';
import { ListingSourceBadge, MealsBadge, splitName } from './ui/Badge';
import { IconArrowDown, IconArrowUp, IconClock, IconMoon } from './ui/Icons';
import { hours, signed, signedUsd, usd } from '../lib/format';

export const TIME_FILL = 'repeating-linear-gradient(135deg, rgb(var(--time)) 0 2px, rgb(var(--time) / 0.35) 2px 5px)';

export function SplitBar({ cash, other, max, height = 8 }: { cash: number; other: number; max: number; height?: number }) {
  const w = (v: number) => `${Math.max(0, (v / Math.max(1, max)) * 100)}%`;
  return (
    <div className="flex w-full overflow-hidden rounded-full bg-soft" style={{ height }} role="img" aria-label={`Cash ${usd(cash)}, time and late-night ${usd(other)}`}>
      <div className="bg-cash transition-[width] duration-500" style={{ width: w(cash) }} />
      <div className="transition-[width] duration-500" style={{ width: w(other), background: TIME_FILL }} />
    </div>
  );
}

export function RankMove({ before, after }: { before: number | null | undefined; after: number | null | undefined }) {
  if (before == null || after == null || before === after) return null;
  const up = after < before;
  return (
    <span className={`mono inline-flex items-center gap-0.5 rounded-full bg-soft px-1.5 py-px text-2xs font-semibold ${up ? 'text-good' : 'text-bad'}`} aria-label={`Rank ${up ? 'up' : 'down'} from ${before} to ${after}`}>
      {up ? <IconArrowUp size={11} /> : <IconArrowDown size={11} />}
      {Math.abs(before - after)}
    </span>
  );
}

export function DeltaChips({ d }: { d: DiffDelta }) {
  const chip = (label: string, v: number, txt: string) => (
    <span key={label} className={`mono rounded-full bg-soft px-2 py-px text-2xs font-medium ${Math.abs(v) < 0.5 ? 'text-faint' : v > 0 ? 'text-bad' : 'text-good'}`}>{txt}</span>
  );
  return (
    <span className="inline-flex flex-wrap gap-1">
      {chip('all', d.all_in, `${signedUsd(d.all_in)} all-in`)}
      {Math.abs(d.time_h) >= 0.05 && chip('time', d.time_h * 60, `${signed(d.time_h, 'h', 1)}/wk`)}
      {Math.abs(d.cash) >= 0.5 && chip('cash', d.cash, `${signedUsd(d.cash)} cash`)}
      {Math.abs(d.late_night) >= 1 && chip('late', d.late_night, `${signed(d.late_night, 'min', 0)} late`)}
    </span>
  );
}

export function ListingCard({ e, l, max, selected, onSelect, delta, before, portalRank, compact = false, noInvert = false }: {
  e: ListingEvaluation; l?: Listing; max: number; selected: boolean; onSelect: () => void;
  delta?: DiffDelta; before?: number | null; portalRank?: number; compact?: boolean; noInvert?: boolean;
}) {
  const compactNoInvert = noInvert;
  const other = e.all_in_total - e.cash_total;
  const c = e.commute;
  const { title, sub } = splitName(l?.name ?? e.listing_id);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${e.feasible ? `Rank ${e.rank}` : 'Not feasible'}: ${l?.name ?? e.listing_id}, ${usd(e.all_in_total)} per month all-in`}
      className={`lift group w-full rounded-xl border p-3 text-left sm:p-4 ${e.rank === 1 && !compactNoInvert ? 'surface-invert border-transparent' : 'bg-surface'} ${selected ? (e.rank === 1 && !compactNoInvert ? 'outline outline-2 outline-offset-2 outline-ink' : 'border-ink') : e.rank === 1 && !compactNoInvert ? '' : 'border-line'} ${e.feasible ? '' : 'opacity-60'}`}
    >
      <div className="flex items-start gap-3">
        <div className={`mono flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-base font-semibold ${e.feasible ? (e.rank === 1 ? 'bg-accent text-accent-ink' : 'bg-soft text-ink') : 'bg-soft text-faint'}`}>
          {e.feasible ? e.rank : '—'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <span className="min-w-0">
              <span className="block font-display text-[1.0625rem] font-semibold leading-snug text-ink">{title}</span>
              {sub && <span className="block text-sm leading-snug text-faint">{sub}</span>}
            </span>
            <RankMove before={before} after={e.rank} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-faint">
            <span>{l?.neighborhood ?? 'Ann Arbor'}</span>
            {l && <ListingSourceBadge l={l} compact />}
            {l && <MealsBadge l={l} />}
            {e.pareto && e.feasible && !compact && <span className="secondary-chrome tag" title="Pareto-optimal: no other home is better on cash, time and late-night at once">pareto</span>}
            {portalRank != null && !compact && <span className="secondary-chrome text-faint">· portal #{portalRank}</span>}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="mono text-2xl font-semibold text-ink">{usd(e.all_in_total)}<span className="text-xs font-normal text-faint">/mo</span></div>
          <div className="mono text-xs text-faint">{usd(e.cash_total)} cash</div>
        </div>
      </div>
      <div className="mt-3">
        <SplitBar cash={e.cash_total} other={other} max={max} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-faint">
        <span className="num inline-flex items-center gap-1"><IconClock size={13} /> <b className="font-semibold text-ink">{hours(c?.weekly_min)}</b>/wk travel</span>
        <span className="num inline-flex items-center gap-1"><IconMoon size={13} /> <b className="font-semibold text-ink">{Math.round(c?.late_night_outdoor_min ?? 0)} min</b> out after 10 PM</span>
        {!compact && <span className="num secondary-chrome">time &amp; late-night <b className="font-semibold text-ink">{usd(other)}</b></span>}
        {delta && <span className="ml-auto"><DeltaChips d={delta} /></span>}
      </div>
      {!e.feasible && e.violations.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-bad">
          {e.violations.map((v) => <li key={v}>✕ {v}</li>)}
        </ul>
      )}
    </button>
  );
}
