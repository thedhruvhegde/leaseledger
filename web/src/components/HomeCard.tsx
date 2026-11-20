import { memo } from 'react';
import type { DiffDelta, Listing, ListingEvaluation } from '../types';
import { ListingVisual } from './Photo';
import { RankMove, DeltaChips } from './ListingCard';
import { IconCheck, IconPlus } from './ui/Icons';
import { TYPE_WORD, displayName } from '../lib/category';
import { hours, usd } from '../lib/format';
import type { MapLine } from './MapView';


export function factsLine(l?: Listing): string {
  if (!l) return '';
  const parts = [
    l.bedrooms === 0 ? 'Studio' : `${l.bedrooms} bd`,
    l.baths != null ? `${l.baths} ba` : null,
    l.sqft ? `${l.sqft.toLocaleString()} sqft` : null,
    TYPE_WORD[l.building_type] || null,
  ];
  return parts.filter(Boolean).join(' · ');
}

/** One quiet line of provenance for a card: "Observed · search text · Nov 20" or "Synthetic (fictional)". */
export function SourceLine({ l }: { l?: Listing }) {
  if (!l) return null;
  if (l.provenance === 'synthetic') {
    return <span className="inline-flex min-w-0 items-center truncate rounded-full border border-dashed border-line-strong px-1.5 text-[11px] leading-4 text-faint hatch-synthetic" title="Fictional listing created for this demo. Not a real property, price or availability.">Synthetic · fictional</span>;
  }
  const how = l.verification === 'search_extract' ? 'search text' : l.verification === 'user_verified' ? 'verified by you' : 'listing page';
  const d = l.observed_on ? new Date(`${l.observed_on}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null;
  return <span className="min-w-0 truncate text-[11px] text-faint" title="Read from a dated public source. Availability not verified.">Observed · {how}{d ? ` · ${d}` : ''}</span>;
}

/**
 * Listing card in the portal convention: picture slot on top (a licensed photo, else the generated street map),
 * price first, the week facts, the building and plan, the home facts and a quiet source line.
 * The whole card opens the detail; Compare is a small toggle on the picture.
 */
export const HomeCard = memo(function HomeCard({ e, l, lines, active, hovered, onOpen, onHover, inCompare, onCompare, delta, before, lowestRent, layout = 'vertical' }: {
  e: ListingEvaluation; l?: Listing; lines: MapLine[]; active: boolean; hovered: boolean; onOpen: () => void; onHover: (on: boolean) => void;
  inCompare: boolean; onCompare: () => void; delta?: DiffDelta; before?: number | null; lowestRent?: boolean; layout?: 'vertical' | 'row';
}) {
  const { building, plan } = displayName(l?.name ?? e.listing_id);
  const c = e.commute;
  const row = layout === 'row';
  return (
    <article
      className={`home-card group relative flex h-full overflow-hidden rounded-xl border bg-surface transition-colors ${row ? 'flex-row' : 'flex-col'} ${active ? 'border-ink' : hovered ? 'border-line-strong' : 'border-line'} ${e.feasible ? '' : 'is-out'}`}
      onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)}
    >
      <div className={`relative shrink-0 ${row ? 'w-36 self-stretch' : 'aspect-[16/10] w-full border-b border-line'}`}>
        <ListingVisual l={l} lines={lines} className="absolute inset-0" />
        <span className={`num pointer-events-none absolute left-2 top-2 inline-flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-xs font-semibold ${e.feasible ? (e.rank === 1 ? 'bg-ink text-bg' : 'bg-surface text-ink ring-1 ring-line') : 'bg-surface text-faint ring-1 ring-line'}`}>
          {e.feasible ? `#${e.rank}` : 'Doesn’t fit'}
        </span>
        <button type="button" onClick={onCompare} aria-pressed={inCompare} aria-label={`${inCompare ? 'Remove from' : 'Add to'} compare: ${l?.name ?? e.listing_id}`}
          className={`compare-toggle absolute right-2 top-2 z-10 inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-[12px] font-medium ring-1 transition-colors ${inCompare ? 'bg-ink text-bg ring-ink' : 'bg-surface/95 text-charcoal ring-line hover:text-ink hover:ring-line-strong'}`}>
          {inCompare ? <IconCheck size={13} /> : <IconPlus size={13} />} Compare
        </button>
      </div>
      <div className="flex min-w-0 flex-1 flex-col px-3 pb-2.5 pt-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <div className="num text-[1.25rem] font-semibold leading-tight tracking-tight text-ink">
            {usd(e.all_in_total)}<span className="ml-0.5 text-xs font-normal text-faint">/mo all-in</span>
          </div>
          <RankMove before={before} after={e.rank} />
        </div>
        <div className="num mt-0.5 truncate text-[12.5px] text-charcoal">
          <span title="Cash you pay per month (rent, utilities, fees)">{usd(e.cash_total)} cash</span>
          <span className="mx-1.5 text-mute" aria-hidden>·</span>
          <span title="Door-to-door travel per week">{hours(c?.weekly_min)}/wk travel</span>
          <span className="mx-1.5 text-mute" aria-hidden>·</span>
          <span title="Minutes per week walking or waiting outdoors after 10 PM">{Math.round(c?.late_night_outdoor_min ?? 0)} min late</span>
        </div>
        <h3 className="mt-2 truncate font-sans text-[14.5px] font-semibold leading-snug tracking-normal text-ink" title={l?.name}>
          <button type="button" onClick={onOpen} aria-pressed={active} className="text-left after:absolute after:inset-0 after:content-[''] focus-visible:outline-none">
            {building}
          </button>
        </h3>
        <div className="truncate text-[13px] text-charcoal" title={plan ?? undefined}>{plan ?? factsLine(l)}</div>
        <div className="truncate text-[12.5px] text-faint">{[plan ? factsLine(l) : null, l?.neighborhood].filter(Boolean).join(' · ')}</div>
        {!e.feasible && e.violations[0] && <div className="mt-1 truncate text-[12px] text-bad" title={e.violations.join(' ')}>{e.violations[0]}</div>}
        {delta && <div className="relative mt-1.5"><DeltaChips d={delta} /></div>}
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <SourceLine l={l} />
          {lowestRent && <span className="shrink-0 text-[11px] font-medium text-charcoal">Lowest rent</span>}
        </div>
      </div>
    </article>
  );
});
