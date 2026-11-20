import { useRef, useState, type ReactNode } from 'react';
import { useApp } from '../store/app';
import type { EvaluationResult, Listing, ListingEvaluation } from '../types';
import { Receipt } from './Receipt';
import { TripList, WeekTimeline } from './WeekTimeline';
import { Compare, VsRow, keyFacts } from './WhyPanel';
import { humanize } from './Breakeven';
import { LedgerChart } from './LedgerChart';
import { MapThumb } from './MapThumb';
import { Gallery, ListingVisual } from './Photo';
import { photosOf } from '../lib/photos';
import { categoryLabel, categoryOf, displayName } from '../lib/category';
import { ProvenanceLegend, splitName } from './ui/Badge';
import { Segmented } from './ui/Controls';
import { IconChevron, IconX } from './ui/Icons';
import { SourceLine, factsLine } from './HomeCard';
import { hours, usd, usdRate } from '../lib/format';
import { legLines } from '../lib/legs';
import { useListingMap } from '../api/hooks';

const SECTIONS = [
  { id: 'receipt', label: 'Monthly cost' },
  { id: 'why', label: 'Why this one' },
  { id: 'week', label: 'Your week' },
  { id: 'facts', label: 'Facts' },
  { id: 'sources', label: 'Sources' },
] as const;

function Section({ id, title, aside, children }: { id: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section id={`d-${id}`} className="scroll-mt-14 border-t border-line px-5 py-6 sm:px-6" aria-labelledby={`d-${id}-h`}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 id={`d-${id}-h`} className="text-[1.125rem] font-semibold">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="min-w-0 py-3 pr-4 sm:px-4 sm:first:pl-0">
      <div className="text-[12px] text-faint">{label}</div>
      <div className="num mt-0.5 text-[1.0625rem] font-semibold text-ink">{value}</div>
      {sub && <div className="num text-[11px] text-faint">{sub}</div>}
    </div>
  );
}

/** Listing detail in the portal convention: header with price and actions, section tabs, then sections. */
export function HomeDetail({ e, l, result, onClose, portalRank }: { e: ListingEvaluation; l?: Listing; result: EvaluationResult; onClose: () => void; portalRank?: number }) {
  const events = useApp((s) => s.committed.events);
  const inCompare = useApp((s) => s.compare.includes(e.listing_id));
  const toggleCompare = useApp((s) => s.toggleCompare);
  const setScreen = useApp((s) => s.setScreen);
  const lmap = useListingMap();
  const [tab, setTab] = useState<'visual' | 'list'>('visual');
  const root = useRef<HTMLDivElement>(null);
  const { building: title, plan: sub } = displayName(l?.name ?? e.listing_id);
  const c = e.commute;
  const facts = keyFacts(e.explanation_facts, 4);
  const feasible = result.evaluations.filter((x) => x.feasible && x.listing_id !== e.listing_id);
  const compareWith = useApp((s) => s.compareWith);
  const setCompareWith = useApp((s) => s.setCompareWith);
  const other = compareWith && compareWith !== e.listing_id ? compareWith : (e.rank === 1 ? feasible[0]?.listing_id : result.evaluations.find((x) => x.rank === 1)?.listing_id) ?? null;
  const jump = (id: string) => root.current?.querySelector(`#d-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <div ref={root} className="min-h-full bg-surface">
      <div className="sticky top-0 z-20 flex items-center gap-1 border-b border-line bg-surface/95 px-3 backdrop-blur-sm">
        <button className="btn-ghost h-11 gap-1 px-2 text-[13px] text-ink" onClick={onClose}>
          <IconChevron size={15} className="rotate-180" /> All homes
        </button>
        <nav aria-label="Sections of this home" className="no-scrollbar ml-2 flex min-w-0 flex-1 gap-0.5 overflow-x-auto">
          {SECTIONS.map((s) => (
            <button key={s.id} onClick={() => jump(s.id)} className="h-11 shrink-0 whitespace-nowrap border-b-2 border-transparent px-2.5 text-[13px] text-faint hover:border-line-strong hover:text-ink">{s.label}</button>
          ))}
        </nav>
        <button className="btn-ghost w-9 px-0 lg:hidden" onClick={onClose} aria-label="Close details"><IconX /></button>
      </div>

      {l && photosOf(l).length > 0 ? <Gallery l={l} />
        : l && <MapThumb lat={l.lat} lon={l.lon} lines={legLines(e)} label={l.name} className="h-44 border-b border-line lg:hidden" />}

      <header className="px-5 pb-5 pt-5 sm:px-6">
        <div className="flex flex-col gap-x-6 gap-y-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <div className="text-[13px] text-faint">{e.feasible ? <>Ranked <b className="font-semibold text-ink">#{e.rank}</b> for your week{portalRank ? <> · a typical portal would rank it #{portalRank}</> : null}</> : 'Doesn’t fit your constraints'}</div>
            <h2 className="mt-1 text-[1.625rem] font-semibold leading-tight">{title}</h2>
            {sub && <div className="text-[15px] text-charcoal">{sub}</div>}
            <div className="mt-1 text-[13px] text-faint">{[l?.address?.replace(/, Ann Arbor, MI$/, ''), l?.neighborhood, l ? categoryLabel(categoryOf(l)) : null].filter(Boolean).join(' · ')}</div>
          </div>
          <div className="sm:text-right">
            <div className="num text-[2rem] font-semibold leading-none tracking-tight">{usd(e.all_in_total)}<span className="ml-1 text-sm font-normal text-faint">/mo all-in</span></div>
            <div className="num mt-1 text-[13px] text-faint">{usd(e.cash_total)} cash ({usd(e.cash_low)}–{usd(e.cash_high)})</div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button className={inCompare ? 'btn-primary h-8 text-[13px]' : 'btn-outline h-8 text-[13px]'} onClick={() => toggleCompare(e.listing_id)} aria-pressed={inCompare}>
            {inCompare ? 'In compare' : 'Add to compare'}
          </button>
          {l?.source_url && <a className="btn-outline h-8 text-[13px]" href={l.source_url} target="_blank" rel="noreferrer">Listing source ↗</a>}
          <button className="btn-ghost h-8 text-[13px]" onClick={() => setScreen('robustness')}>How sure is this rank?</button>
          <span className="ml-auto"><SourceLine l={l} /></span>
        </div>
        {l?.provenance === 'synthetic' && (
          <div className="mt-3 rounded-lg border border-dashed border-line-strong px-3 py-2 text-[12px] text-charcoal hatch-synthetic">Synthetic listing: a fictional home used to demonstrate the method. Not a real property, price, or availability.</div>
        )}
        {!e.feasible && e.violations.length > 0 && (
          <ul className="mt-3 space-y-0.5 text-[13px] text-bad">{e.violations.map((v) => <li key={v}>✕ {v}</li>)}</ul>
        )}
        <div className="mt-4 grid grid-cols-2 divide-line border-y border-line sm:grid-cols-4 sm:divide-x">
          <Stat label="Travel per week" value={hours(c?.weekly_min)} sub={c ? `${Math.round(c.weekly_walk_min)} min walking` : undefined} />
          <Stat label="Out after 10 PM" value={`${Math.round(c?.late_night_outdoor_min ?? 0)} min`} sub="walking or waiting, per week" />
          <Stat label="Longest trip" value={`${Math.round(c?.max_single_trip_min ?? 0)} min`} sub="door to door" />
          <Stat label="Home" value={factsLine(l) || '—'} sub={l?.rent_basis === 'bed' ? 'rent is per bed' : 'rent is per unit'} />
        </div>
      </header>

      <Section id="receipt" title="Monthly cost" aside={<span className="text-[12px] text-faint">per person · low–high bands in gray</span>}>
        <Receipt e={e} size="md" className="max-w-[40rem]" />
        <p className="mt-3 text-[12px] text-faint">
          {result.value_of_time_used > 0 ? <>Travel time is valued at {usdRate(result.value_of_time_used)}/h; it is not cash you pay. </> : <>Cash only: time is not priced right now. </>}
          Change it under All filters.
        </p>
      </Section>

      <Section id="why" title="Why this one">
        {facts.length > 0 && (
          <ul className="mb-5 space-y-2" aria-label="Key reasons">
            {facts.map((f) => <li key={f} className="flex gap-2.5 text-[14px] leading-relaxed text-charcoal"><span className="mt-[0.55rem] h-1 w-1 shrink-0 rounded-full bg-ink" />{humanize(f, lmap)}</li>)}
          </ul>
        )}
        {other && (
          <VsRow a={e.listing_id} b={other} result={result} lmap={lmap}
            select={
              <select aria-label="Compare with" className="h-8 max-w-[15rem] rounded-full border border-line bg-surface px-3 text-[13px]" value={other} onChange={(ev) => setCompareWith(ev.target.value || null)}>
                {result.evaluations.filter((x) => x.listing_id !== e.listing_id).map((x) => (
                  <option key={x.listing_id} value={x.listing_id}>{x.rank ? `#${x.rank} ` : ''}{splitName(lmap.get(x.listing_id)?.name ?? x.listing_id).title}</option>
                ))}
              </select>
            } />
        )}
        <details className="disclosure mt-5 rounded-xl border border-line">
          <summary className="flex items-center justify-between gap-2 rounded-xl px-4 py-2.5 text-[13px] font-medium text-ink hover:bg-raised">
            <span>All reasoning <span className="font-normal text-faint">({e.explanation_facts.length} facts, ledger bars{other ? ', side-by-side table' : ''})</span></span>
            <IconChevron size={15} className="chev text-faint" />
          </summary>
          <div className="space-y-6 border-t border-line p-4">
            <ul className="space-y-1.5">{e.explanation_facts.map((f) => <li key={f} className="flex gap-2 text-[13px] text-charcoal"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{humanize(f, lmap)}</li>)}</ul>
            <div><div className="mb-2 text-[12px] font-medium text-faint">Monthly ledger, line by line</div><LedgerChart e={e} /></div>
            {other && <Compare a={e.listing_id} b={other} vot={result.value_of_time_used} />}
          </div>
        </details>
      </Section>

      {c && (
        <Section id="week" title="Your week from here" aside={<Segmented size="xs" label="Timeline view" value={tab} onChange={setTab} options={[{ value: 'visual', label: 'Timeline' }, { value: 'list', label: 'Trip list' }]} />}>
          <div className="num mb-3 text-[12px] text-faint">
            {hours(c.weekly_min)} door to door · {Math.round(c.weekly_walk_min)} min walking · {Math.round(c.weekly_wait_min)} min waiting · {Math.round(c.weekly_in_vehicle_min)} min on buses
          </div>
          {tab === 'visual' ? <WeekTimeline commute={c} events={events} /> : <TripList commute={c} />}
        </Section>
      )}

      <Section id="facts" title="Listing facts">
        <ListingFacts l={l} />
      </Section>

      <Section id="sources" title="Sources">
        <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-2 text-[13px]">
          <dt className="text-faint">Listing</dt>
          <dd className="min-w-0 text-charcoal">
            {l?.provenance === 'synthetic' ? 'Synthetic (fictional) demo listing.' : <>Observed{l?.observed_on ? ` on ${l.observed_on}` : ''}{l?.verification === 'search_extract' ? ' from search-engine text for the cited URL (page not loaded)' : l?.verification === 'user_verified' ? ', verified by you' : ' from the listing page'}. Availability not verified.</>}
            {l?.source_url && <> <a className="break-all text-ink underline underline-offset-2" href={l.source_url} target="_blank" rel="noreferrer">{l.source_url}</a></>}
          </dd>
          <dt className="text-faint">Trips</dt>
          <dd className="text-charcoal">Planned on the U-M Blue Bus and TheRide GTFS timetables and the street network (Overture/OSM).</dd>
          <dt className="text-faint">Value of time</dt>
          <dd className="text-charcoal">{result.value_of_time_derivation.length ? result.value_of_time_derivation.join(' ') : `${usdRate(result.value_of_time_used)}/h`}</dd>
        </dl>
        <div className="mt-4 border-t border-line pt-3">
          <div className="mb-1 text-[12px] font-medium text-faint">Tags on the receipt</div>
          <ProvenanceLegend inline />
        </div>
      </Section>
    </div>
  );
}

const UTIL: Record<string, string> = { heat: 'Heat', electric: 'Electric', water: 'Water', gas: 'Gas', internet: 'Internet', trash: 'Trash' };

function ListingFacts({ l }: { l?: Listing }) {
  if (!l) return null;
  const yn = (v: boolean | null | undefined) => (v == null ? 'Not stated' : v ? 'Yes' : 'No');
  const rows: [string, ReactNode][] = [
    ['Rent', <>{usd(l.rent)}{l.rent_is_range && l.rent_low && l.rent_high ? ` (${usd(l.rent_low)}–${usd(l.rent_high)})` : ''} per {l.rent_basis === 'bed' ? 'bed' : 'unit'}</>],
    ['Bedrooms / baths', `${l.bedrooms === 0 ? 'Studio' : l.bedrooms} / ${l.baths ?? '—'}`],
    ['Size', l.sqft ? `${l.sqft.toLocaleString()} sqft` : 'Not stated'],
    ['Utilities included', l.utilities_included.length ? l.utilities_included.map((u) => UTIL[u] ?? u).join(', ') : 'None stated'],
    ['Fees', l.fees.length ? l.fees.map((f) => `${f.label} ${usd(f.amount)} ${f.period === 'once' ? 'once' : f.period === 'annual' ? '/yr' : '/mo'}`).join(' · ') : 'None stated'],
    ['Furnished', yn(l.furnished)],
    ['In-unit laundry', yn(l.in_unit_laundry)],
    ['Parking', l.parking_monthly != null ? `${usd(l.parking_monthly)}/mo` : 'Not stated'],
    ['Pets', yn(l.pets_allowed)],
    ['Lease', [l.lease_term_months ? `${l.lease_term_months} months` : null, l.lease_start ? `from ${l.lease_start}` : null].filter(Boolean).join(' ') || 'Not stated'],
  ];
  if (l.board_included) rows.push(['Meals', 'Charge includes meals (co-op board)']);
  if (l.member_labor_hours_week) rows.push(['Co-op work', `${l.member_labor_hours_week} h/week`]);
  if (l.amenities.length) rows.push(['Amenities', l.amenities.join(', ')]);
  return (
    <>
      <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 border-b border-line py-2 text-[13px]">
            <dt className="text-faint">{k}</dt><dd className="num text-right text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {l.notes && <p className="mt-3 text-[13px] text-charcoal">{l.notes}</p>}
    </>
  );
}

/** Compare tray destination: two homes side by side, line by line, with trip differences and the breakeven. */
export function ComparePanel({ a, b, result, onClose, portalRank }: { a: string; b: string; result: EvaluationResult; onClose: () => void; portalRank: Map<string, number> }) {
  const lmap = useListingMap();
  const setScreen = useApp((s) => s.setScreen);
  const toggle = useApp((s) => s.toggleCompare);
  const ev = (id: string) => result.evaluations.find((x) => x.listing_id === id);
  return (
    <div className="min-h-full bg-surface">
      <div className="sticky top-0 z-20 flex items-center gap-2 border-b border-line bg-surface/95 px-3 backdrop-blur-sm">
        <button className="btn-ghost h-11 gap-1 px-2 text-[13px] text-ink" onClick={onClose}><IconChevron size={15} className="rotate-180" /> All homes</button>
        <div className="text-[13px] font-semibold">Compare 2 homes</div>
      </div>
      <div className="grid grid-cols-2 gap-3 px-5 pt-5 sm:px-6">
        {[a, b].map((id, i) => {
          const e = ev(id);
          const l = lmap.get(id);
          return (
            <div key={id} className="overflow-hidden rounded-xl border border-line">
              <div className="relative aspect-[16/9] border-b border-line"><ListingVisual l={l} lines={legLines(e)} className="absolute inset-0" /></div>
              <div className="p-3">
                <div className="text-[11px] font-medium text-faint">Home {i === 0 ? 'A' : 'B'} · {e?.rank ? `#${e.rank} for your week` : 'doesn’t fit'}{portalRank.get(id) ? ` · portal #${portalRank.get(id)}` : ''}</div>
                <div className="mt-0.5 truncate text-[14px] font-semibold">{splitName(l?.name ?? id).title}</div>
                <div className="num mt-1 text-[1.25rem] font-semibold">{usd(e?.all_in_total)}<span className="text-xs font-normal text-faint">/mo all-in</span></div>
                <div className="num text-[12px] text-faint">{usd(e?.cash_total)} cash · {hours(e?.commute?.weekly_min)}/wk</div>
                <button className="mt-2 text-[12px] text-faint underline underline-offset-2 hover:text-ink" onClick={() => toggle(id)}>Remove</button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="px-5 py-6 sm:px-6">
        <h3 className="mb-3 text-[1.125rem] font-semibold">Line by line</h3>
        <Compare a={a} b={b} vot={result.value_of_time_used} />
        <div className="mt-6 rounded-xl border border-line p-4 text-[13px] text-charcoal">
          A typical portal sorts by rent and distance to one building. <button className="font-medium text-ink underline underline-offset-2" onClick={() => setScreen('baseline')}>See the portal ranking next to your week’s</button>.
        </div>
      </div>
    </div>
  );
}
