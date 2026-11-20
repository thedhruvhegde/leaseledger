import { Suspense, lazy, useMemo, useState } from 'react';
import { useApp } from '../store/app';
import { NoWeek } from '../components/NoWeek';
import { hasWeek, useBeforeEvaluation, useBuildingMap, useDiff, useEvaluation, useListingMap } from '../api/hooks';
import { useFlip } from '../lib/flip';
import { ListingCard, SplitBar, TIME_FILL } from '../components/ListingCard';
import { TripList, WeekTimeline } from '../components/WeekTimeline';
import { WhyPanel } from '../components/WhyPanel';
import { ErrorState, SectionTitle, Skeleton } from '../components/ui/Misc';
import { IconChevron, IconInfo } from '../components/ui/Icons';
import { ListingSourceBadge, MealsBadge, splitName } from '../components/ui/Badge';
import { Segmented } from '../components/ui/Controls';
import type { MapLine, MapPoint } from '../components/MapView';
import type { EvaluationResult, Infeasibility, Listing, ListingEvaluation, Profile } from '../types';
import { hours, titleCase, usd, usdRate } from '../lib/format';
import { legLines } from '../lib/legs';

const MapView = lazy(() => import('../components/MapView'));

export function ResultsScreen() {
  const { data, isLoading, error, refetch, isFetching } = useEvaluation();
  const before = useBeforeEvaluation();
  const diff = useDiff();
  const lmap = useListingMap();
  const selected = useApp((s) => s.selected);
  const setSelected = useApp((s) => s.setSelected);
  const setProfile = useApp((s) => s.setProfile);
  const profile = useApp((s) => s.committed);
  const [view, setView] = useState<'cards' | 'table'>('cards');
  const order = (data?.evaluations ?? []).map((e) => e.listing_id).join('|');
  const flip = useFlip(order);
  const portalRank = useMemo(() => new Map((data?.baseline_ranking ?? []).map((id, i) => [id, i + 1])), [data]);

  if (!hasWeek(profile)) return <NoWeek />;
  if (error && !data) return <ErrorState error={error} retry={() => void refetch()} />;
  if (isLoading || !data) return <ResultsSkeleton />;

  const evals = data.evaluations;
  const max = Math.max(1, ...evals.map((e) => e.all_in_total));
  const sel = evals.find((e) => e.listing_id === selected) ?? evals.find((e) => e.feasible) ?? evals[0];
  const beforeRank = (id: string) => before.data?.evaluations.find((e) => e.listing_id === id)?.rank ?? null;
  const rentOf = (x: ListingEvaluation) => x.ledger.find((y) => y.key === 'rent')?.usd_month ?? null;
  const cheapestRent = [...evals].sort((a, b) => (rentOf(a) ?? 0) - (rentOf(b) ?? 0))[0];
  const top = evals.find((e) => e.rank === 1);

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="Step 2" title="What your week costs" right={
        <div className="flex items-center gap-2">
          {isFetching && <span className="text-xs text-faint animate-pulse2">Updating…</span>}
          <Segmented label="View" value={view} onChange={setView} options={[{ value: 'cards', label: 'Cards' }, { value: 'table', label: 'Table' }]} />
        </div>
      }>
        Ranked by all-in monthly cost: cash you pay plus the value of the hours your week spends getting around
        {data.value_of_time_used > 0 ? <> (at <b className="text-ink">{usdRate(data.value_of_time_used)}/h</b>)</> : <> — <b className="text-ink">cash only</b> right now</>}.
      </SectionTitle>

      {data.infeasibility && <InfeasibleBanner inf={data.infeasibility} profile={profile} onRelax={(p) => setProfile(p)} />}
      {top && cheapestRent && top.listing_id !== cheapestRent.listing_id && profile.events.length > 0 && cheapestRent.all_in_total - top.all_in_total >= 10 && (
        <div className="card flex flex-wrap items-baseline gap-x-4 gap-y-1 px-6 py-5" data-testid="insight">
          <span className="font-display text-2xl font-semibold text-ink">Lowest rent ≠ cheapest week.</span>
          <span className="text-base text-faint">
            <b className="font-semibold text-ink">{splitName(lmap.get(cheapestRent.listing_id)?.name).title}</b> has the lowest rent
            {rentOf(cheapestRent) != null && <> (<span className="num">{usd(rentOf(cheapestRent))}/mo</span>)</>}, but {cheapestRent.feasible ? <>ranks <b className="num font-semibold text-ink">#{cheapestRent.rank}</b> once your week is counted</> : <>fails your constraints</>}: <b className="num font-semibold text-ink">{usd(cheapestRent.all_in_total - top.all_in_total)}/mo</b> more all-in than #1.
          </span>
        </div>
      )}
      <Notes warnings={data.warnings.filter((w) => !w.startsWith('MOCK'))} />

      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,34rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,30rem)_minmax(0,1fr)]">
        <div className="min-w-0">
          {view === 'cards' ? (
            <ol className="space-y-2.5" aria-label="Ranked homes">
              {evals.map((e) => (
                <li key={e.listing_id} ref={flip(e.listing_id)} className="relative">
                  <ListingCard e={e} l={lmap.get(e.listing_id)} max={max} selected={sel?.listing_id === e.listing_id} onSelect={() => setSelected(e.listing_id)}
                    delta={diff.data?.deltas[e.listing_id]} before={beforeRank(e.listing_id)} portalRank={portalRank.get(e.listing_id)} />
                </li>
              ))}
            </ol>
          ) : (
            <DenseTable evals={evals} lmap={lmap} max={max} selected={sel?.listing_id} onSelect={setSelected} />
          )}
          <div className="secondary-chrome mt-3 flex flex-wrap gap-3 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-cash" />Cash</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full" style={{ background: TIME_FILL }} />Time &amp; late-night (not cash)</span>
          </div>
        </div>
        {sel && <Detail e={sel} result={data} l={lmap.get(sel.listing_id)} />}
      </div>
    </div>
  );
}

/** Engine warnings are assumptions to read, not alarms: one quiet disclosure. */
export function Notes({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <details className="disclosure w-fit max-w-full">
      <summary className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-sm text-muted transition-colors hover:border-faint/60 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
        <IconInfo size={14} /> Assumptions &amp; notes ({warnings.length}) <IconChevron size={14} className="chev" />
      </summary>
      <ul className="mt-2 max-w-4xl space-y-1.5 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">
        {warnings.map((w) => <li key={w} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{w}</li>)}
      </ul>
    </details>
  );
}

function ResultsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[30rem_1fr]">
      <div className="space-y-2.5">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
      <Skeleton className="h-[36rem]" />
    </div>
  );
}

export function InfeasibleBanner({ inf, profile, onRelax }: { inf: Infeasibility; profile: Profile; onRelax: (p: Profile) => void }) {
  const r = inf.minimal_relaxation;
  const label: Record<string, string> = { rent_cap: 'your rent cap', all_in_cap: 'your all-in cap', needs_parking: 'needing parking', pet: 'the pet requirement', max_single_trip_min: 'your longest-trip limit', bedrooms: 'the bedroom requirement' };
  return (
    <div role="alert" className="card border-bad/40 bg-bad/5 p-4">
      <div className="text-base font-semibold text-ink">No home fits — {label[inf.binding_constraint] ?? titleCase(inf.binding_constraint)} is binding.</div>
      <div className="mt-1 text-sm text-muted">
        {Object.entries(inf.eliminated).map(([k, n]) => `${label[k] ?? titleCase(k)} rules out ${n}`).join(' · ')}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {r.rent_cap != null && (
          <button className="btn-primary" onClick={() => onRelax({ ...profile, rent_cap: r.rent_cap })}>
            Raise rent cap to {usd(r.rent_cap)}{(inf.restores?.rent_cap ?? r.rent_cap_restores) ? `: restores ${inf.restores?.rent_cap ?? r.rent_cap_restores} home${(inf.restores?.rent_cap ?? r.rent_cap_restores) === 1 ? '' : 's'}` : ''}
          </button>
        )}
        {r.max_single_trip_min != null && (
          <button className="btn-outline" onClick={() => onRelax({ ...profile, max_single_trip_min: r.max_single_trip_min })}>Allow trips up to {Math.round(r.max_single_trip_min)} min{inf.restores?.max_single_trip_min ? `: restores ${inf.restores.max_single_trip_min} home${inf.restores.max_single_trip_min === 1 ? '' : 's'}` : ''}</button>
        )}
        {r.all_in_cap != null && <button className="btn-outline" onClick={() => onRelax({ ...profile, all_in_cap: r.all_in_cap })}>Raise all-in cap to {usd(r.all_in_cap)}{inf.restores?.all_in_cap ? `: restores ${inf.restores.all_in_cap} home${inf.restores.all_in_cap === 1 ? '' : 's'}` : ''}</button>}
      </div>
    </div>
  );
}

function DenseTable({ evals, lmap, max, selected, onSelect }: { evals: ListingEvaluation[]; lmap: Map<string, Listing>; max: number; selected?: string; onSelect: (id: string) => void }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <thead className="text-left text-2xs uppercase tracking-wider text-faint">
          <tr className="border-b border-line">
            <th className="px-3 py-2">#</th><th className="px-3 py-2">Home</th><th className="px-3 py-2 text-right">All-in</th><th className="px-3 py-2 text-right">Cash</th>
            <th className="px-3 py-2 text-right">h/wk</th><th className="px-3 py-2 text-right">Late</th><th className="w-24 px-3 py-2">Split</th>
          </tr>
        </thead>
        <tbody className="num">
          {evals.map((e) => (
            <tr key={e.listing_id} onClick={() => onSelect(e.listing_id)} tabIndex={0} onKeyDown={(ev) => ev.key === 'Enter' && onSelect(e.listing_id)}
              className={`cursor-pointer border-b border-line/60 hover:bg-raised ${selected === e.listing_id ? 'bg-accent-soft/60' : ''} ${e.feasible ? '' : 'text-faint'}`}>
              <td className="px-3 py-2 font-bold text-accent">{e.rank ?? '—'}</td>
              <td className="max-w-[14rem] truncate px-3 py-2 font-sans" title={e.violations.join(' ')}>{lmap.get(e.listing_id)?.name ?? e.listing_id}{!e.feasible && <span className="ml-1 text-bad">✕</span>}</td>
              <td className="px-3 py-2 text-right font-semibold">{usd(e.all_in_total)}</td>
              <td className="px-3 py-2 text-right">{usd(e.cash_total)}</td>
              <td className="px-3 py-2 text-right">{hours(e.commute?.weekly_min)}</td>
              <td className="px-3 py-2 text-right">{Math.round(e.commute?.late_night_outdoor_min ?? 0)}′</td>
              <td className="px-3 py-2"><SplitBar cash={e.cash_total} other={e.all_in_total - e.cash_total} max={max} height={6} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Detail({ e, result, l }: { e: ListingEvaluation; result: EvaluationResult; l?: Listing }) {
  const events = useApp((s) => s.committed.events);
  const bmap = useBuildingMap();
  const lmap = useListingMap();
  const [tab, setTab] = useState<'visual' | 'list'>('visual');
  const { points, lines } = useMemo(() => {
    const pts: MapPoint[] = [];
    const ls: MapLine[] = [];
    for (const [id, x] of lmap) if (id !== e.listing_id) pts.push({ id, lat: x.lat, lon: x.lon, label: x.name, kind: 'listing' });
    const seen = new Set<string>();
    for (const ev of events) {
      const b = ev.building_id ? bmap.get(ev.building_id) : null;
      const p = b ? { lat: b.lat, lon: b.lon, name: b.name } : ev.point ? { lat: ev.point.lat, lon: ev.point.lon, name: ev.label } : null;
      if (!p || seen.has(p.name)) continue;
      seen.add(p.name);
      pts.push({ id: p.name, lat: p.lat, lon: p.lon, label: `${p.name} — ${ev.label}`, kind: 'building' });
      if (l) {
        const usesBus = e.commute?.tours.some((t) => t.trips.some((tr) => tr.mode === 'bus' && tr.legs[tr.legs.length - 1]?.to_name === p.name));
        const usesBike = e.commute?.tours.some((t) => t.trips.some((tr) => tr.mode === 'bike' && tr.legs[tr.legs.length - 1]?.to_name === p.name));
        ls.push({ coords: [[l.lon, l.lat], [p.lon, p.lat]], kind: usesBus ? 'bus' : usesBike ? 'bike' : 'walk' });
      }
    }
    if (l) pts.push({ id: l.id, lat: l.lat, lon: l.lon, label: `Home: ${l.name}`, kind: 'home' });
    const exact = legLines(e);
    return { points: pts, lines: exact.length ? exact : ls };
  }, [e, l, events, bmap, lmap]);

  return (
    <div className="min-w-0 space-y-5">
      <div className="card p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="label">{e.feasible ? `#${e.rank} for your week` : 'Doesn’t fit your constraints'}</div>
            <h3 className="mt-1 text-[1.875rem] font-semibold leading-tight">{splitName(l?.name ?? e.listing_id).title}</h3>
            {splitName(l?.name).sub && <div className="text-base text-muted">{splitName(l?.name).sub}</div>}
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">
              {l?.address && <span>{l.address}</span>}
              {l?.neighborhood && <span>· {l.neighborhood}</span>}
              {l && <ListingSourceBadge l={l} />}
              {l && <MealsBadge l={l} />}
              {l?.source_url && <a className="text-ink underline underline-offset-2" href={l.source_url} target="_blank" rel="noreferrer">source</a>}
            </div>
          </div>
          <div className="text-right">
            <div className="mono text-4xl font-semibold">{usd(e.all_in_total)}<span className="text-sm font-normal text-faint">/mo</span></div>
            <div className="mono text-sm text-faint">{hours(e.commute?.weekly_min)} a week getting around</div>
          </div>
        </div>
        {l?.provenance === 'synthetic' && <div className="mt-3 rounded-md border border-p-synthetic/40 px-3 py-1.5 text-xs text-p-synthetic hatch-synthetic">Synthetic listing: a fictional home used to demonstrate the method. Not a real property, price, or availability.</div>}
        <div className="mt-6">
          <WhyPanel e={e} result={result} />
        </div>
      </div>

      {e.commute && (
        <div className="card p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-base font-semibold">Your week from here</div>
              <div className="num text-xs text-muted">
                {hours(e.commute.weekly_min)} door-to-door · {Math.round(e.commute.weekly_walk_min)} min walking · {Math.round(e.commute.weekly_wait_min)} min waiting · {Math.round(e.commute.weekly_in_vehicle_min)} min on buses · longest trip {Math.round(e.commute.max_single_trip_min)} min
              </div>
            </div>
            <Segmented size="xs" label="Timeline view" value={tab} onChange={setTab} options={[{ value: 'visual', label: 'Timeline' }, { value: 'list', label: 'Trip list' }]} />
          </div>
          {tab === 'visual' ? <WeekTimeline commute={e.commute} events={events} /> : <TripList commute={e.commute} />}
        </div>
      )}

      <div className="card p-4 sm:p-5">
        <div className="mb-3 text-base font-semibold">Map</div>
        <Suspense fallback={<Skeleton className="h-80" />}>
          <MapView points={points} lines={lines} height={340} ariaLabel={`Map of ${l?.name ?? 'home'} and your places`} />
        </Suspense>
      </div>
    </div>
  );
}
