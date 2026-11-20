import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '../store/app';
import { hasWeek, useBeforeEvaluation, useBuildings, useDemoProfiles, useDiff, useEvaluation, useListingMap, useListings } from '../api/hooks';
import { HomeCard } from '../components/HomeCard';
import { ComparePanel, HomeDetail } from '../components/HomeDetail';
import { AllFilters, BudgetFilter, FiltersSheetButton, HouseholdFilter, ModesFilter, SortSelect, WeekSummary, type SortKey } from '../components/SearchBar';
import { SplitBar } from '../components/ListingCard';
import { ErrorState, Skeleton } from '../components/ui/Misc';
import { IconChevron, IconInfo, IconX } from '../components/ui/Icons';
import { splitName } from '../components/ui/Badge';
import { Segmented } from '../components/ui/Controls';
import type { MapLine } from '../components/MapView';
import type { Anchor, Place, PricePin } from '../components/SearchMap';
import type { Campus, EvaluationResult, Infeasibility, Listing, ListingEvaluation, Profile } from '../types';
import { hours, titleCase, usd, usdRate } from '../lib/format';
import { legLines } from '../lib/legs';
import { useDesktop } from '../lib/media';
import { CATEGORIES, categoryOf, displayName } from '../lib/category';
import type { CategoryFilter } from '../store/app';

const SearchMap = lazy(() => import('../components/SearchMap'));

const CAMPUS_LABEL: Partial<Record<Campus, string>> = { central: 'Central Campus', north: 'North Campus', medical: 'Medical Campus', south: 'South Campus', downtown: 'Downtown' };
const rentOf = (x: ListingEvaluation) => x.ledger.find((y) => y.key === 'rent')?.usd_month ?? null;

function sortEvals(evals: ListingEvaluation[], key: SortKey): ListingEvaluation[] {
  const fit = (x: ListingEvaluation) => (x.feasible ? 0 : 1);
  const val: Record<SortKey, (x: ListingEvaluation) => number> = {
    best: (x) => x.rank ?? 999,
    allin: (x) => x.all_in_total,
    cash: (x) => x.cash_total,
    travel: (x) => x.commute?.weekly_min ?? 1e9,
    rent: (x) => rentOf(x) ?? 1e9,
  };
  return [...evals].sort((a, b) => fit(a) - fit(b) || val[key](a) - val[key](b));
}

/** Homes: the portal search-results layout — filter bar, ranked list on the left, price-pin map on the right. */
export function ResultsScreen() {
  const desktop = useDesktop();
  const { data, isLoading, error, refetch, isFetching } = useEvaluation();
  const before = useBeforeEvaluation();
  const diff = useDiff();
  const lmap = useListingMap();
  const { data: listings = [] } = useListings();
  const { data: buildings = [] } = useBuildings();
  const selected = useApp((s) => s.selected);
  const setSelected = useApp((s) => s.setSelected);
  const setScreen = useApp((s) => s.setScreen);
  const profile = useApp((s) => s.committed);
  const parsing = useApp((s) => s.parsing);
  const compare = useApp((s) => s.compare);
  const toggleCompare = useApp((s) => s.toggleCompare);
  const compareOpen = useApp((s) => s.compareOpen);
  const setCompareOpen = useApp((s) => s.setCompareOpen);
  const [sort, setSort] = useState<SortKey>('best');
  const [view, setView] = useState<'cards' | 'table'>('cards');
  const [hover, setHover] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'map'>('list');
  const pane = useRef<HTMLDivElement>(null);
  const listScroll = useRef(0);

  const category = useApp((s) => s.category);
  const allEvals = useMemo(() => data?.evaluations ?? [], [data]);
  const evals = useMemo(() => (category === 'all' ? allEvals : allEvals.filter((e) => categoryOf(lmap.get(e.listing_id)) === category)), [allEvals, category, lmap]);
  const counts = useMemo(() => {
    const c: Record<CategoryFilter, number> = { all: allEvals.length, apartments: 0, houses: 0, coops: 0 };
    for (const e of allEvals) c[categoryOf(lmap.get(e.listing_id))]++;
    return c;
  }, [allEvals, lmap]);
  const sorted = useMemo(() => sortEvals(evals, sort), [evals, sort]);
  const portalRank = useMemo(() => new Map((data?.baseline_ranking ?? []).map((id, i) => [id, i + 1])), [data]);
  const lines = useMemo(() => new Map(allEvals.map((e) => [e.listing_id, legLines(e)])), [allEvals]);
  const open = selected ? allEvals.find((e) => e.listing_id === selected) : undefined;
  const top = allEvals.find((e) => e.rank === 1);
  const lowest = useMemo(() => [...allEvals].filter((e) => rentOf(e) != null).sort((a, b) => rentOf(a)! - rentOf(b)!)[0], [allEvals]);
  const nFit = evals.filter((e) => e.feasible).length;

  // Map data
  // Price pins for the 12 best in view; the rest are small dots that open to a price on hover (portal convention).
  const pins: PricePin[] = useMemo(() => {
    const shown = new Set(sortEvals(evals, 'best').filter((e) => e.feasible).slice(0, 12).map((e) => e.listing_id));
    return evals.map((e) => {
      const l = lmap.get(e.listing_id);
      return { id: e.listing_id, lat: l?.lat ?? 0, lon: l?.lon ?? 0, rank: e.feasible ? e.rank ?? null : null, price: e.all_in_total, feasible: e.feasible, name: l?.name ?? e.listing_id, dot: !shown.has(e.listing_id) };
    }).filter((p) => p.lat !== 0);
  }, [evals, lmap]);
  const others = useMemo(() => {
    const ranked = new Set(evals.map((e) => e.listing_id));
    return listings.filter((l) => !ranked.has(l.id)).map((l) => ({ lat: l.lat, lon: l.lon, label: `${l.name} (not in this ranking)` }));
  }, [listings, evals]);
  const places: Place[] = useMemo(() => {
    const seen = new Map<string, Place>();
    const bm = new Map(buildings.map((b) => [b.id, b]));
    for (const ev of profile.events) {
      const b = ev.building_id ? bm.get(ev.building_id) : null;
      const p = b ? { lat: b.lat, lon: b.lon, label: `${b.name}: ${ev.label}` } : ev.point ? { lat: ev.point.lat, lon: ev.point.lon, label: ev.label } : null;
      if (p && !seen.has(`${p.lat},${p.lon}`)) seen.set(`${p.lat},${p.lon}`, p);
    }
    return Array.from(seen.values());
  }, [profile.events, buildings]);
  const anchors: Anchor[] = useMemo(() => {
    const acc = new Map<Campus, { lat: number; lon: number; n: number }>();
    for (const b of buildings) {
      if (!CAMPUS_LABEL[b.campus]) continue;
      const a = acc.get(b.campus) ?? { lat: 0, lon: 0, n: 0 };
      acc.set(b.campus, { lat: a.lat + b.lat, lon: a.lon + b.lon, n: a.n + 1 });
    }
    return Array.from(acc.entries()).map(([k, v]) => ({ lat: v.lat / v.n, lon: v.lon / v.n, label: CAMPUS_LABEL[k]! }));
  }, [buildings]);
  const firstInView = sorted.find((e) => e.feasible) ?? sorted[0];
  const routeId = hover ?? selected ?? firstInView?.listing_id ?? top?.listing_id ?? null;
  const routes: MapLine[] = useMemo(() => (routeId ? lines.get(routeId) ?? [] : []), [routeId, lines]);
  const focus = useMemo(() => {
    if (!open) return null;
    const l = lmap.get(open.listing_id);
    const pts: [number, number][] = (lines.get(open.listing_id) ?? []).flatMap((x) => x.coords);
    if (l) pts.push([l.lon, l.lat]);
    return pts;
  }, [open, lmap, lines]);
  const fitKey = `${evals.map((e) => e.listing_id).join('|')}#${places.length}#${selected ? 'd' : 'l'}`;

  const openHome = (id: string) => {
    if (pane.current && !selected) listScroll.current = pane.current.scrollTop;
    setCompareOpen(false);
    setSelected(id);
    if (pane.current) pane.current.scrollTop = 0;
  };
  const closeHome = () => {
    setSelected(null);
    setCompareOpen(false);
    requestAnimationFrame(() => { if (pane.current) pane.current.scrollTop = listScroll.current; });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && (useApp.getState().selected || useApp.getState().compareOpen)) closeHome(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // A selected id from elsewhere (e.g. portal screen) that is not in this ranking: drop it.
  useEffect(() => { if (data && selected && !open) setSelected(null); }, [data, selected, open, setSelected]);

  const noWeek = !hasWeek(profile) && !parsing;
  const listBody = noWeek ? <StartPanel /> : error && !data ? <div className="p-4"><ErrorState error={error} retry={() => void refetch()} /></div>
    : (isLoading || !data || parsing && !evals.length) ? <ListSkeleton reading={parsing} /> : (
    <ListView data={data} sorted={sorted} lmap={lmap} lines={lines} view={view} setView={setView} sort={sort} setSort={setSort}
      selected={selected} hover={hover} setHover={setHover} onOpen={openHome} compare={compare} toggleCompare={toggleCompare}
      deltas={diff.data?.deltas} beforeRank={(id) => before.data?.evaluations.find((e) => e.listing_id === id)?.rank ?? null}
      top={top} lowest={lowest} nFit={nFit} isFetching={isFetching} profile={profile} desktop={desktop} counts={counts} />
  );
  const detailBody = open && data ? <HomeDetail key={open.listing_id} e={open} l={lmap.get(open.listing_id)} result={data} onClose={closeHome} portalRank={portalRank.get(open.listing_id)} />
    : compareOpen && compare.length === 2 && data ? <ComparePanel a={compare[0]} b={compare[1]} result={data} onClose={closeHome} portalRank={portalRank} /> : null;
  const map = (
    <Suspense fallback={<div className="h-full w-full bg-raised" />}>
      <SearchMap pins={pins} others={others} places={places} anchors={anchors} routes={routes} activeId={selected} hoverId={hover}
        onHover={setHover} onOpen={openHome} fitKey={fitKey} focus={focus} />
    </Suspense>
  );

  if (desktop) {
    return (
      <div className="flex h-[calc(100dvh-57px)] flex-col">
        <FilterBar isFetching={isFetching} />
        <div className="flex min-h-0 flex-1">
          <div ref={pane} className="results-pane relative min-h-0 overflow-y-auto border-r border-line bg-surface">
            {detailBody ?? listBody}
            <CompareTray lmap={lmap} evals={allEvals} />
          </div>
          <div className="relative min-w-0 flex-1">
            {map}
            <MapLegend routeName={routeId ? displayName(lmap.get(routeId)?.name).building : null} hasPlaces={places.length > 0} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="sticky top-[57px] z-20 flex items-center gap-2 border-b border-line bg-bg px-3 py-2">
        <WeekSummary compact onClick={() => setScreen('week')} />
        <FiltersSheetButton />
      </div>
      {mobileView === 'list' ? <div ref={pane}>{listBody}</div> : (
        <div className="relative h-[calc(100dvh-57px-53px-64px)]">{map}</div>
      )}
      {!noWeek && (
        <button className="mobile-toggle fixed left-1/2 z-30 -translate-x-1/2 btn-primary h-10 px-5" onClick={() => setMobileView((v) => (v === 'list' ? 'map' : 'list'))}>
          {mobileView === 'list' ? 'Map' : 'List'}
        </button>
      )}
      <CompareTray lmap={lmap} evals={allEvals} mobile />
      {detailBody && (
        <div className="fixed inset-0 z-[55]" role="dialog" aria-modal="true" aria-label="Home details">
          <button className="absolute inset-0 bg-ink/30" aria-label="Close details" onClick={closeHome} />
          <div className="sheet absolute inset-x-0 bottom-0 max-h-[92dvh] overflow-y-auto rounded-t-2xl border-t border-line bg-surface animate-slide-up">
            <div className="flex justify-center pt-2"><span className="h-1 w-10 rounded-full bg-line-strong" aria-hidden /></div>
            {detailBody}
          </div>
        </div>
      )}
    </div>
  );
}

function FilterBar({ isFetching }: { isFetching: boolean }) {
  const setScreen = useApp((s) => s.setScreen);
  return (
    <div className="relative z-30 flex h-[52px] shrink-0 items-center gap-2 border-b border-line bg-bg px-4">
      <WeekSummary onClick={() => setScreen('week')} />
      <span className="mx-1 h-6 w-px bg-line" aria-hidden />
      <BudgetFilter />
      <HouseholdFilter />
      <ModesFilter />
      <AllFilters />
      <span className={`ml-auto text-[12px] text-faint transition-opacity ${isFetching ? 'opacity-100' : 'opacity-0'}`} aria-live="polite">{isFetching ? 'Updating…' : ''}</span>
    </div>
  );
}

function ListView({ data, sorted, lmap, lines, view, setView, sort, setSort, selected, hover, setHover, onOpen, compare, toggleCompare, deltas, beforeRank, top, lowest, nFit, profile, desktop, counts }: {
  data: EvaluationResult; sorted: ListingEvaluation[]; lmap: Map<string, Listing>; lines: Map<string, MapLine[]>; view: 'cards' | 'table'; setView: (v: 'cards' | 'table') => void;
  sort: SortKey; setSort: (s: SortKey) => void; selected: string | null; hover: string | null; setHover: (id: string | null) => void; onOpen: (id: string) => void;
  compare: string[]; toggleCompare: (id: string) => void; deltas?: Record<string, import('../types').DiffDelta>; beforeRank: (id: string) => number | null;
  top?: ListingEvaluation; lowest?: ListingEvaluation; nFit: number; isFetching: boolean; profile: Profile; desktop: boolean; counts: Record<CategoryFilter, number>;
}) {
  const setProfile = useApp((s) => s.setProfile);
  const category = useApp((s) => s.category);
  const cat = CATEGORIES.find((c) => c.id === category);
  const max = Math.max(1, ...sorted.map((e) => e.all_in_total));
  const showInsight = top && lowest && top.listing_id !== lowest.listing_id && lowest.all_in_total - top.all_in_total >= 10;
  return (
    <div className="px-4 pb-24 pt-4 sm:px-5">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h1 className="font-sans text-[1.125rem] font-semibold tracking-normal">Ann Arbor homes for your week</h1>
          <div className="num text-[13px] text-faint">
            <b className="font-semibold text-ink">{nFit}</b> of {sorted.length} fit · ranked by all-in monthly cost{data.value_of_time_used > 0 ? <> with time at {usdRate(data.value_of_time_used)}/h</> : <>, cash only</>}
            {' · '}<ScopeSelect />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SortSelect value={sort} onChange={setSort} />
          {desktop && <Segmented size="xs" label="View" value={view} onChange={setView} options={[{ value: 'cards', label: 'Cards' }, { value: 'table', label: 'Table' }]} />}
        </div>
      </div>
      <CategoryTabs counts={counts} />

      {data.infeasibility && <div className="mt-3"><InfeasibleBanner inf={data.infeasibility} profile={profile} onRelax={(p) => setProfile(p)} /></div>}
      {showInsight && category === 'all' && (
        <div className="mt-3 rounded-xl border border-line bg-raised px-4 py-3 text-[13px] leading-relaxed text-charcoal" data-testid="insight">
          <b className="font-semibold text-ink">Lowest rent isn’t the cheapest week.</b>{' '}
          {splitName(lmap.get(lowest!.listing_id)?.name).title} has the lowest rent{rentOf(lowest!) != null && <> (<span className="num">{usd(rentOf(lowest!))}</span>)</>} but {lowest!.feasible ? <>ranks #{lowest!.rank}</> : <>fails your constraints</>}: <b className="num font-semibold text-ink">{usd(lowest!.all_in_total - top!.all_in_total)}/mo</b> more all-in than #1.
        </div>
      )}
      <div className="mt-2"><Notes warnings={data.warnings.filter((w) => !w.startsWith('MOCK'))} /></div>

      {cat && <SectionHead title={cat.label} count={sorted.length} blurb={cat.blurb} />}
      {sorted.length === 0 && <div className="mt-4 rounded-xl border border-dashed border-line-strong px-4 py-6 text-center text-[13px] text-faint">No {cat?.label.toLowerCase()} in this ranking.</div>}
      {view === 'table' ? (
        <div className="mt-3"><DenseTable evals={sorted} lmap={lmap} max={max} selected={selected ?? undefined} onSelect={onOpen} /></div>
      ) : (
        <ol className="results-grid mt-3" aria-label="Ranked homes">
          {sorted.map((e) => (
            <li key={e.listing_id}>
              <HomeCard e={e} l={lmap.get(e.listing_id)} lines={lines.get(e.listing_id) ?? []} active={selected === e.listing_id} hovered={hover === e.listing_id}
                onOpen={() => onOpen(e.listing_id)} onHover={(on) => setHover(on ? e.listing_id : null)}
                inCompare={compare.includes(e.listing_id)} onCompare={() => toggleCompare(e.listing_id)}
                delta={deltas?.[e.listing_id]} before={beforeRank(e.listing_id)} lowestRent={e.listing_id === lowest?.listing_id && e.listing_id !== top?.listing_id} />
            </li>
          ))}
        </ol>
      )}
      <p className="mt-6 text-[12px] leading-relaxed text-faint">
        Prices are per person per month. All-in adds the value of your travel time and late-night exposure to the cash you pay; it is a ranking, not a bill.
        Not legal or financial advice. Synthetic listings are fictional and labeled. Photos appear only where the team has the right to show them; other homes show a street map.
      </p>
    </div>
  );
}

/** Category tabs with counts: All · Towers & apartments · Houses & rooms · Co-ops, plus which homes are ranked. */
function CategoryTabs({ counts }: { counts: Record<CategoryFilter, number> }) {
  const category = useApp((s) => s.category);
  const setCategory = useApp((s) => s.setCategory);
  const tabs: { id: CategoryFilter; label: string }[] = [{ id: 'all', label: 'All homes' }, ...CATEGORIES.map((c) => ({ id: c.id, label: c.label }))];
  return (
    <div className="mt-3 border-b border-line">
      <div role="tablist" aria-label="Home type" className="no-scrollbar -mb-px flex min-w-0 gap-1 overflow-x-auto">
        {tabs.map((t) => {
          const on = category === t.id;
          return (
            <button key={t.id} role="tab" aria-selected={on} onClick={() => setCategory(t.id)} disabled={t.id !== 'all' && counts[t.id] === 0}
              className={`cat-tab inline-flex h-10 shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 text-[13px] font-medium transition-colors disabled:opacity-40 ${on ? 'border-ink text-ink' : 'border-transparent text-faint hover:text-ink'}`}>
              {t.label}<span className={`num rounded-full px-1.5 text-[11px] leading-[18px] ${on ? 'bg-ink text-bg' : 'bg-soft text-charcoal'}`}>{counts[t.id]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ScopeSelect() {
  const scope = useApp((s) => s.scope);
  const setScope = useApp((s) => s.setScope);
  return (
    <select aria-label="Which homes to rank" value={scope} onChange={(e) => setScope(e.target.value as 'all' | 'shortlist')}
      className="cursor-pointer appearance-none bg-transparent pr-1 text-[13px] text-faint underline decoration-line-strong underline-offset-2 hover:text-ink">
      <option value="all">all observed homes</option>
      <option value="shortlist">demo shortlist</option>
    </select>
  );
}

function SectionHead({ title, count, blurb }: { title: string; count: number; blurb: string }) {
  return (
    <div className="mt-4 flex flex-wrap items-baseline gap-x-2">
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <span className="num text-[13px] text-faint">{count} home{count === 1 ? '' : 's'}</span>
      <p className="w-full text-[12.5px] text-faint">{blurb}</p>
    </div>
  );
}

function StartPanel() {
  const setScreen = useApp((s) => s.setScreen);
  const setProfile = useApp((s) => s.setProfile);
  const { data: demos = [] } = useDemoProfiles();
  return (
    <div className="px-5 py-10">
      <h1 className="text-[1.5rem] font-semibold">Start with your week</h1>
      <p className="mt-2 max-w-md text-[14px] text-charcoal">Homes are priced against your routine: classes, work, the library, the gym. Add a few blocks (or pick a program template) and the ranked list and price pins appear here.</p>
      <div className="mt-5 flex flex-wrap gap-2">
        <button className="btn-primary" onClick={() => setScreen('week')}>Describe your week</button>
        {demos.slice(0, 2).map((d) => <button key={d.id} className="btn-outline" onClick={() => setProfile(d.profile, 'load')}>Try “{d.name}”</button>)}
      </div>
    </div>
  );
}

function ListSkeleton({ reading }: { reading: boolean }) {
  return (
    <div className="px-5 pt-4">
      {reading && <div className="mb-3 text-[13px] text-charcoal" aria-live="polite">Reading your week and planning every trip…</div>}
      <Skeleton className="mb-3 h-6 w-64" />
      <div className="results-grid">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-72" />)}</div>
    </div>
  );
}

function CompareTray({ lmap, evals, mobile = false }: { lmap: Map<string, Listing>; evals: ListingEvaluation[]; mobile?: boolean }) {
  const compare = useApp((s) => s.compare);
  const toggle = useApp((s) => s.toggleCompare);
  const clear = useApp((s) => s.clearCompare);
  const compareOpen = useApp((s) => s.compareOpen);
  const setCompareOpen = useApp((s) => s.setCompareOpen);
  const setSelected = useApp((s) => s.setSelected);
  if (compare.length === 0 || compareOpen) return null;
  const ev = (id: string) => evals.find((e) => e.listing_id === id);
  return (
    <div className={`${mobile ? 'fixed inset-x-2 z-30 compare-tray-m' : 'sticky bottom-3 mx-4 sm:mx-5'} compare-tray rounded-2xl border border-line-strong bg-surface p-2`} role="region" aria-label="Compare tray">
      <div className={`flex gap-2 ${mobile ? 'flex-col' : 'items-center'}`}>
        <div className="grid min-w-0 flex-1 grid-cols-2 gap-1.5">
          {[0, 1].map((i) => {
            const id = compare[i];
            if (!id) return <div key={i} className="flex h-11 items-center justify-center rounded-xl border border-dashed border-line-strong px-2 text-[12px] text-faint">Add a second home</div>;
            const e = ev(id);
            const { building, plan } = displayName(lmap.get(id)?.name ?? id);
            return (
              <div key={id} className="flex h-11 min-w-0 items-center gap-2 rounded-xl bg-soft pl-2 pr-1">
                <span className="num inline-flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-surface px-1.5 text-[11px] font-semibold ring-1 ring-line">{e?.rank ? `#${e.rank}` : '–'}</span>
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-[12.5px] font-semibold">{building}</span>
                  <span className="num block truncate text-[11px] text-faint">{usd(e?.all_in_total)}/mo{plan ? ` · ${plan}` : ''}</span>
                </span>
                <button className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-faint hover:bg-line hover:text-ink" onClick={() => toggle(id)} aria-label={`Remove ${lmap.get(id)?.name ?? id} from compare`}><IconX size={13} /></button>
              </div>
            );
          })}
        </div>
        <div className={`flex shrink-0 items-center gap-1 ${mobile ? 'flex-row-reverse' : ''}`}>
          <button className={`btn-primary h-9 px-4 text-[13px] ${mobile ? 'flex-1' : ''}`} disabled={compare.length < 2} onClick={() => { setSelected(null); setCompareOpen(true); }}>Compare{compare.length === 2 ? ' 2 homes' : ''}</button>
          <button className="btn-ghost h-9 px-3 text-[12px]" onClick={clear}>Clear</button>
        </div>
      </div>
    </div>
  );
}

function MapLegend({ routeName, hasPlaces }: { routeName: string | null; hasPlaces: boolean }) {
  return (
    <div className="map-legend pointer-events-none absolute bottom-3 left-3 rounded-lg border border-line bg-surface/95 px-3 py-2 text-[11px] text-charcoal">
      {routeName && <div className="mb-1 font-medium text-ink">Routes from {routeName}</div>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1.5"><span className="h-[3px] w-5 rounded-full bg-bus" />Bus</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-0 w-5 border-t-2 border-dotted border-ink" />Walk</span>
        {hasPlaces && <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-ink bg-surface" />Your places</span>}
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full border-2 border-surface bg-charcoal ring-1 ring-line-strong" />More ranked homes</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-mute" />Not ranked</span>
      </div>
    </div>
  );
}

/** Engine warnings are assumptions to read, not alarms: one quiet disclosure. */
export function Notes({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <details className="disclosure w-fit max-w-full">
      <summary className="inline-flex items-center gap-1.5 rounded-full px-1 py-1 text-[12px] text-faint transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
        <IconInfo size={13} /> Assumptions &amp; notes ({warnings.length}) <IconChevron size={13} className="chev" />
      </summary>
      <ul className="mt-1 max-w-4xl space-y-1.5 rounded-xl border border-line bg-surface px-4 py-3 text-[13px] text-charcoal">
        {warnings.map((w) => <li key={w} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{w}</li>)}
      </ul>
    </details>
  );
}

export function InfeasibleBanner({ inf, profile, onRelax }: { inf: Infeasibility; profile: Profile; onRelax: (p: Profile) => void }) {
  const r = inf.minimal_relaxation;
  const label: Record<string, string> = { rent_cap: 'your rent cap', all_in_cap: 'your all-in cap', needs_parking: 'needing parking', pet: 'the pet requirement', max_single_trip_min: 'your longest-trip limit', bedrooms: 'the bedroom requirement' };
  return (
    <div role="alert" className="rounded-xl border border-bad/40 bg-bad/5 p-4">
      <div className="text-[14px] font-semibold text-ink">No home fits — {label[inf.binding_constraint] ?? titleCase(inf.binding_constraint)} is binding.</div>
      <div className="mt-1 text-[13px] text-charcoal">
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
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[560px] text-[13px]">
        <thead className="bg-raised text-left text-[12px] text-faint">
          <tr className="border-b border-line">
            <th className="px-3 py-2 font-medium">#</th><th className="px-3 py-2 font-medium">Home</th><th className="px-3 py-2 text-right font-medium">All-in</th><th className="px-3 py-2 text-right font-medium">Cash</th>
            <th className="px-3 py-2 text-right font-medium">h/wk</th><th className="px-3 py-2 text-right font-medium">Late</th><th className="w-24 px-3 py-2 font-medium">Split</th>
          </tr>
        </thead>
        <tbody className="num">
          {evals.map((e) => (
            <tr key={e.listing_id} onClick={() => onSelect(e.listing_id)} tabIndex={0} onKeyDown={(ev) => ev.key === 'Enter' && onSelect(e.listing_id)}
              className={`cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised ${selected === e.listing_id ? 'bg-soft' : ''} ${e.feasible ? '' : 'text-faint'}`}>
              <td className="px-3 py-2 font-semibold">{e.rank ?? '—'}</td>
              <td className="max-w-[16rem] truncate px-3 py-2 font-sans" title={e.violations.join(' ')}>{lmap.get(e.listing_id)?.name ?? e.listing_id}{!e.feasible && <span className="ml-1 text-bad">✕</span>}</td>
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
