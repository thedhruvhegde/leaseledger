/**
 * Marketing landing page ("/"). Every number on it is computed live from the API for the
 * north-engineer demo profile, or read from cited data (listings, GTFS feed manifest).
 * No photographs or illustrations: the product's own receipt, timelines and map are the pictures.
 * Style: paper-white, black ink, hairlines, pills; one inverted surface (the hero's #1 receipt).
 */
import { Suspense, lazy, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useApp } from '../store/app';
import { useBuildingMap, useDemoProfiles, useListingMap, useListings, useManifest } from '../api/hooks';
import { ListingCard, SplitBar, TIME_FILL } from '../components/ListingCard';
import { Receipt } from '../components/Receipt';
import { WeekTimeline } from '../components/WeekTimeline';
import { WeekPill } from '../components/WeekPill';
import { keyFacts } from '../components/WhyPanel';
import { humanize } from '../components/Breakeven';
import { Logo } from '../components/Header';
import { PROV_META, ProvenanceBadge, splitName } from '../components/ui/Badge';
import { Segmented } from '../components/ui/Controls';
import { Skeleton } from '../components/ui/Misc';
import { IconMoon, IconSun } from '../components/ui/Icons';
import { useFlip } from '../lib/flip';
import { LEG_COLOR, LEG_LABEL, legLines } from '../lib/legs';
import { DAY_SHORT, clock, daysLabel, hours, signedUsd, usd } from '../lib/format';
import { linkTo, navigate } from '../lib/route';
import { SCREENS } from '../store/app';
import { PRODUCT_NAME } from '../brand';
import type { DemoProfile, ListingEvaluation, Member, Provenance, Trip } from '../types';
import type { MapLine, MapPoint } from '../components/MapView';

const MapView = lazy(() => import('../components/MapView'));

const DEMO_ID = 'north-engineer';
const WEEKDAYS = ['M', 'T', 'W', 'R', 'F'] as const;
const TRY = '/app#week';
const SAMPLE = `/app?demo=${DEMO_ID}#results`;
const PLACEHOLDER = 'MWF 9 EECS · TTh 2:30 Ross · UgLi till 1am';

// ------------------------------------------------------------------ data

function useLandingData() {
  const api = useApp((s) => s.api)!;
  const demos = useDemoProfiles();
  const demo: DemoProfile | undefined = demos.data?.find((d) => d.id === DEMO_ID) ?? demos.data?.[0];
  const profile = demo?.profile;
  const ev = useQuery({ queryKey: ['landing-eval', api.kind, demo?.id], queryFn: () => api.evaluate(profile!, null), enabled: !!profile, staleTime: Infinity });
  const rob = useQuery({ queryKey: ['landing-rob', api.kind, demo?.id], queryFn: () => api.robustness(profile!, 2000, 42, null), enabled: !!profile, staleTime: Infinity });
  const evals = ev.data?.evaluations ?? [];
  const top = evals.find((e) => e.rank === 1);
  const rentOf = (x: ListingEvaluation) => x.ledger.find((y) => y.key === 'rent')?.usd_month ?? Infinity;
  const cheapest = [...evals].filter((e) => e.feasible).sort((a, b) => rentOf(a) - rentOf(b))[0];
  const groupMembers: Member[] | null = demos.data && demos.data.length >= 3
    ? demos.data.slice(0, 3).map((d, i) => ({ alias: `Roommate ${'ABC'[i]}`, profile: d.profile, budget_cap: [1100, 1000, 1200][i], room_values: null }))
    : null;
  const grp = useQuery({ queryKey: ['landing-group', api.kind], queryFn: () => api.group(groupMembers!, null), enabled: !!groupMembers, staleTime: Infinity });
  return { api, demo, demos: demos.data ?? [], ev, rob, top, cheapest, rentOf, grp };
}

type Feed = { label?: string; calendar_start?: string; calendar_end?: string; weekday_trips_in_week?: number; source?: string };

function useFeeds(): { um?: Feed; aaata?: Feed } {
  const { data } = useManifest();
  const feeds = ((data?.provider as { feeds?: Record<string, Feed> } | undefined)?.feeds) ?? {};
  return { um: feeds.UM, aaata: feeds.AAATA };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmtDate(iso?: string | null): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m) return iso;
  return d ? `${MONTHS[m - 1]} ${d}, ${y}` : `${MONTHS[m - 1]} ${y}`;
}
const n0 = (v: number) => v.toLocaleString('en-US');

// ------------------------------------------------------------------ page

export default function Landing() {
  const fellBack = useApp((s) => s.fellBack);
  const data = useLandingData();

  useEffect(() => {
    document.title = `${PRODUCT_NAME}: student housing priced by your week`;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest('input, textarea, select, [contenteditable]') || e.metaKey || e.ctrlKey || e.altKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= SCREENS.length) { e.preventDefault(); navigate(`/app#${SCREENS[n - 1].id}`); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); document.title = PRODUCT_NAME; };
  }, []);

  return (
    <div className="landing min-h-screen bg-bg text-ink">
      <a href="#hero" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">Skip to content</a>
      <Nav />
      {fellBack && (
        <div role="status" className="mono border-b border-line px-4 py-2 text-center text-sm text-charcoal">
          api offline · showing mock data · every listing below is synthetic
        </div>
      )}
      <main>
        <Hero d={data} />
        <Product d={data} />
        <How d={data} />
        <TwoDoors d={data} />
        <Sources />
        <Group d={data} />
        <Closing />
      </main>
      <Footer />
    </div>
  );
}

type D = ReturnType<typeof useLandingData>;

// ------------------------------------------------------------------ chrome

function Nav() {
  const theme = useApp((s) => s.theme);
  const toggleTheme = useApp((s) => s.toggleTheme);
  const links = [{ href: '#how', label: 'How it works' }, { href: '#sources', label: 'Sources' }, { href: '#group', label: 'Group Week' }];
  return (
    <header className="sticky top-0 z-50 h-14 border-b border-line bg-bg">
      <div className="ll-wrap flex h-full items-center gap-6">
        <a href="/" className="flex items-center gap-2 rounded-full" aria-label={`${PRODUCT_NAME} home`} onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0 }); }}>
          <Logo size={26} />
          <span className="font-display text-lg font-semibold">{PRODUCT_NAME}</span>
        </a>
        <nav aria-label="Page sections" className="hidden items-center gap-1 md:flex">
          {links.map((l) => <a key={l.href} href={l.href} className="rounded-full px-3 py-1.5 text-sm font-medium text-faint transition-colors hover:bg-soft hover:text-ink">{l.label}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <button className="btn-ghost w-9 px-0" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <IconSun /> : <IconMoon />}</button>
          <a href={SAMPLE} onClick={linkTo(SAMPLE)} className="btn-outline">Open the app</a>
        </div>
      </div>
    </header>
  );
}

function Section({ id, children, label }: { id: string; children: ReactNode; label: string }) {
  return (
    <section id={id} aria-labelledby={label} className="ll-section">
      {children}
    </section>
  );
}

/** Heading + prose in the narrow reading column. */
function Prose({ id, title, children, right }: { id: string; title: ReactNode; children?: ReactNode; right?: ReactNode }) {
  return (
    <div className="ll-col">
      <h2 id={id} className="ll-h2">{title}</h2>
      {children && <p className="mt-3 text-lg leading-relaxed text-faint">{children}</p>}
      {right && <div className="mt-6">{right}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ 1. hero

function Hero({ d }: { d: D }) {
  const { data: listings = [] } = useListings();
  const feeds = useFeeds();
  const setWeekDraft = useApp((s) => s.setWeekDraft);
  const [text, setText] = useState('');
  const observed = listings.filter((l) => l.provenance === 'observed');
  const obsDate = observed.map((l) => l.observed_on).filter(Boolean).sort().pop();
  const ends = [feeds.um?.calendar_end, feeds.aaata?.calendar_end].filter(Boolean).sort() as string[];
  const go = () => { setWeekDraft(text.trim()); navigate(TRY); };
  return (
    <section id="hero" className="ll-hero" aria-labelledby="hero-h">
      <div className="ll-col text-center">
        <div className="enter-fade flex justify-center"><Logo size={64} /></div>
        <h1 id="hero-h" className="ll-h1 mt-6">
          <span className="enter-rise block" style={{ animationDelay: '60ms' }}>Ann Arbor student housing,</span>
          <span className="enter-rise block" style={{ animationDelay: '140ms' }}>priced by your week</span>
        </h1>
        <p className="enter-fade mx-auto mt-4 max-w-[36rem] text-lg leading-relaxed text-faint" style={{ animationDelay: '380ms' }}>
          Type your week. {PRODUCT_NAME} plans every trip on the U-M and TheRide bus timetables and adds rent, utilities and travel time into one monthly cost per home.
        </p>
        <div className="enter-fade mx-auto mt-8 max-w-[36rem] text-left" style={{ animationDelay: '440ms' }}>
          <WeekPill size="lg" value={text} onChange={setText} onSubmit={go} placeholder={PLACEHOLDER} label="Describe your week" />
        </div>
        <p className="enter-fade mt-4 text-sm text-faint" style={{ animationDelay: '500ms' }}>
          <a href={SAMPLE} onClick={linkTo(SAMPLE)} className="ll-link text-ink">See a sample week</a>
          {observed.length > 0 && <span className="mono"> · {n0(observed.length)} listings observed {fmtDate(obsDate)}{ends.length > 0 && <> · timetables valid to {fmtDate(ends[0])}</>}</span>}
        </p>
      </div>
      <div className="enter-settle ll-wide mt-16" style={{ animationDelay: '200ms' }}>
        <HeroCompare d={d} />
      </div>
    </section>
  );
}

function HeroCompare({ d }: { d: D }) {
  const lmap = useListingMap();
  const { top, cheapest, ev, demo } = d;
  if (!top || !cheapest || !ev.data) return <Skeleton className="h-[26rem]" />;
  const same = top.listing_id === cheapest.listing_id;
  const cards = same ? [{ e: top, tag: 'cheapest week' }] : [{ e: cheapest, tag: 'lowest rent' }, { e: top, tag: 'cheapest week' }];
  return (
    <div>
      <div className="mb-6 text-center">
        <div className="font-display text-2xl font-semibold">{same ? 'The lowest rent is also the cheapest week.' : 'Lowest rent ≠ cheapest week.'}</div>
        {!same && (
          <p className="mt-1 text-base text-faint">
            {demo?.name}: {splitName(lmap.get(cheapest.listing_id)?.name).title} ranks <b className="mono font-semibold text-ink">#{cheapest.rank}</b> once the week is counted, <b className="mono font-semibold text-ink">{usd(cheapest.all_in_total - top.all_in_total)}/mo</b> more all-in.
          </p>
        )}
      </div>
      <div className={`grid gap-4 ${same ? 'mx-auto max-w-[34rem]' : 'md:grid-cols-2'}`}>
        {cards.map(({ e, tag }) => {
          const { title, sub } = splitName(lmap.get(e.listing_id)?.name);
          const look = tag === 'cheapest week';
          return (
            <div key={e.listing_id} className={`min-w-0 rounded-xl p-2 ${look ? 'surface-invert' : 'border border-line'}`}>
              <div className="flex items-baseline justify-between gap-3 px-3 pb-2 pt-3">
                <div className="min-w-0">
                  <div className="font-display text-xl font-semibold leading-snug">{title}</div>
                  {sub && <div className="text-sm text-faint">{sub}</div>}
                </div>
                <span className="tag shrink-0">#{e.rank} · {tag}</span>
              </div>
              <Receipt e={e} bands={false} showExcluded={false} className="border-transparent bg-transparent" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 2. the product, live

function Product({ d }: { d: D }) {
  const lmap = useListingMap();
  const [sort, setSort] = useState<'week' | 'rent'>('week');
  const [sel, setSel] = useState<string | null>(null);
  const evals = useMemo(() => (d.ev.data?.evaluations ?? []).filter((e) => e.feasible), [d.ev.data]);
  const list = useMemo(() => {
    const xs = [...evals];
    if (sort === 'rent') xs.sort((a, b) => d.rentOf(a) - d.rentOf(b));
    return xs.slice(0, 4);
  }, [evals, sort, d]);
  const flip = useFlip(list.map((e) => e.listing_id).join('|'), 600);
  const max = Math.max(1, ...evals.map((e) => e.all_in_total));
  const selected = evals.find((e) => e.listing_id === sel) ?? d.top;
  return (
    <Section id="product" label="product-h">
      <Prose id="product-h" title="Every home that fits your week, on one ledger"
        right={<Segmented label="Sort homes by" value={sort} onChange={setSort} options={[{ value: 'rent', label: 'Sort by rent' }, { value: 'week', label: 'Sort by your week' }]} />}>
        Sort it by rent, then by the week you live. The order changes.
      </Prose>
      <div className="ll-wide mt-10 overflow-hidden rounded-xl border border-line">
        {!d.ev.data ? <Skeleton className="m-4 h-[30rem]" /> : (
          <div className="grid lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
            <ol className="space-y-2 border-line p-3 sm:p-4 lg:border-r" aria-label="Homes">
              {list.map((e) => (
                <li key={e.listing_id} ref={flip(e.listing_id)} className="relative">
                  <ListingCard e={e} l={lmap.get(e.listing_id)} max={max} compact noInvert selected={selected?.listing_id === e.listing_id} onSelect={() => setSel(e.listing_id)} />
                </li>
              ))}
            </ol>
            {selected && <ProductDetail e={selected} d={d} />}
          </div>
        )}
      </div>
    </Section>
  );
}

function ProductDetail({ e, d }: { e: ListingEvaluation; d: D }) {
  const lmap = useListingMap();
  const api = d.api;
  const evals = d.ev.data!.evaluations;
  const other = e.rank === 1 ? evals.find((x) => x.rank === 2) : evals.find((x) => x.rank === 1);
  const cmp = useQuery({
    queryKey: ['landing-cmp', api.kind, d.demo?.id, e.listing_id, other?.listing_id],
    queryFn: () => api.compare(d.demo!.profile, e.listing_id, other!.listing_id),
    enabled: !!other && !!d.demo, staleTime: Infinity,
  });
  const { title, sub } = splitName(lmap.get(e.listing_id)?.name);
  const lines = (cmp.data?.line_diffs ?? []).filter((x) => Math.abs(x.delta) >= 1).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 3);
  const tone = (v: number) => (v > 0 ? 'text-bad' : 'text-good');
  return (
    <div className="min-w-0 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm text-faint">#{e.rank} for this week</div>
          <div className="font-display text-2xl font-semibold leading-tight">{title}</div>
          {sub && <div className="text-faint">{sub}</div>}
        </div>
        <div className="mono text-right text-sm text-faint">{hours(e.commute?.weekly_min)} a week<br />getting around</div>
      </div>
      <div className="mt-5 space-y-6">
        <Receipt e={e} />
        <div className="space-y-4">
          {other && (
            <div>
              <div className="mb-2 text-sm text-faint">vs <b className="font-semibold text-ink">#{other.rank} {splitName(lmap.get(other.listing_id)?.name).title}</b> (other minus this)</div>
              <div className="flex flex-wrap gap-1.5">
                <span className={`mono rounded-full border border-ink px-3 py-1 text-sm font-semibold ${tone(other.all_in_total - e.all_in_total)}`}>{signedUsd(other.all_in_total - e.all_in_total)}/mo all-in</span>
                {lines.map((x) => <span key={x.key} className="mono rounded-full bg-soft px-3 py-1 text-sm"><span className="text-faint">{x.label.replace(/\s*\(.*\)$/, '').toLowerCase()}</span> <b className={`font-medium ${tone(x.delta)}`}>{signedUsd(x.delta)}</b></span>)}
              </div>
            </div>
          )}
          <ul className="space-y-2">
            {keyFacts(e.explanation_facts, 2).map((f) => (
              <li key={f} className="flex gap-2.5 text-[0.9375rem] leading-relaxed text-charcoal"><span className="mt-[0.6rem] h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />{humanize(f, lmap)}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 3. how it works

function How({ d }: { d: D }) {
  return (
    <Section id="how" label="how-h">
      <Prose id="how-h" title="From a typed week to a ranked list">Four steps, all of them visible in the app.</Prose>
      <div className="ll-wide mt-10 grid gap-4 md:grid-cols-2">
        <HowCard title="Reads your week" body="Type it the way you would text a friend. Each class, shift and gym slot lands on a weekly grid."><WeekFragment d={d} /></HowCard>
        <HowCard title="Plans trips on real timetables" body="Walking, waits and transfers come from this term’s U-M and TheRide schedules."><TripFragment d={d} /></HowCard>
        <HowCard title="Prices time next to rent" body="Hours in transit get an hourly value you set, so a far, cheap room shows its full cost."><SplitFragment d={d} /></HowCard>
        <HowCard title="Tests the answer 2,000 times" body="Schedules, utility bills and the value of an hour are resampled to see if #1 holds."><SureFragment d={d} /></HowCard>
      </div>
    </Section>
  );
}

function HowCard({ title, body, children }: { title: string; body: string; children: ReactNode }) {
  return (
    <div className="flex flex-col rounded-xl border border-line p-2">
      <div className="flex h-[15.5rem] flex-col justify-center overflow-hidden rounded-lg bg-raised p-5" data-visual>{children}</div>
      <div className="px-4 pb-4 pt-5">
        <h3 className="font-display text-xl font-semibold">{title}</h3>
        <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-faint">{body}</p>
      </div>
    </div>
  );
}

function WeekFragment({ d }: { d: D }) {
  const bmap = useBuildingMap();
  const evs = d.demo?.profile.events.slice(0, 4) ?? [];
  if (!evs.length) return <Skeleton className="h-full" />;
  return (
    <ul className="space-y-1.5">
      {evs.map((e, i) => (
        <li key={i} className="rounded-lg border border-line bg-surface px-3 py-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-sm font-medium">{e.label}</span>
            <span className="mono shrink-0 text-xs text-faint">{daysLabel(e.days)}</span>
          </div>
          <div className="mono truncate text-xs text-faint">{clock(e.start_min)}–{clock(e.end_min)} · {e.building_id ? bmap.get(e.building_id)?.name ?? e.building_id : 'pinned place'}</div>
        </li>
      ))}
    </ul>
  );
}

function lastTrip(e: ListingEvaluation | undefined, day = 'M'): Trip | undefined {
  const t = e?.commute?.tours.find((x) => x.day === day);
  return t?.trips[t.trips.length - 1];
}

function TripRow({ name, t }: { name: string; t: Trip }) {
  const total = Math.max(1, t.arrive_min - t.depart_min);
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="truncate text-sm font-medium">{name}</span>
        <span className="mono shrink-0 text-sm font-semibold">{Math.round(t.total_min)} min</span>
      </div>
      <div className="relative h-7 overflow-hidden rounded-md bg-surface" role="img" aria-label={t.legs.map((l) => `${l.kind === 'bus' ? `bus ${l.route ?? ''}` : LEG_LABEL[l.kind]} ${Math.round(l.end_min - l.start_min)} min`).join(', ')}>
        {t.legs.map((l, i) => (
          <div key={i} className="absolute inset-y-0 flex items-center justify-center border-r border-surface text-[11px] font-semibold text-white"
            style={{ left: `${((l.start_min - t.depart_min) / total) * 100}%`, width: `${((l.end_min - l.start_min) / total) * 100}%`, background: LEG_COLOR[l.kind] }}>
            {l.kind === 'bus' && (l.end_min - l.start_min) / total > 0.07 ? l.route : ''}
          </div>
        ))}
      </div>
    </div>
  );
}

function TripFragment({ d }: { d: D }) {
  const lmap = useListingMap();
  const a = lastTrip(d.top);
  const b = lastTrip(d.cheapest);
  if (!a || !b || !d.top || !d.cheapest) return <Skeleton className="h-full" />;
  const dest = a.legs[0]?.from_name;
  return (
    <div className="space-y-4">
      <div className="mono text-xs text-faint">{DAY_SHORT.M} {clock(a.depart_min)}, home from {dest}</div>
      <TripRow name={splitName(lmap.get(d.top.listing_id)?.name).title} t={a} />
      {d.cheapest.listing_id !== d.top.listing_id && <TripRow name={splitName(lmap.get(d.cheapest.listing_id)?.name).title} t={b} />}
      <div className="flex flex-wrap gap-3 text-xs text-faint">
        {(['walk', 'wait', 'bus'] as const).map((k) => <span key={k} className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: LEG_COLOR[k] }} />{LEG_LABEL[k]}</span>)}
      </div>
    </div>
  );
}

function SplitFragment({ d }: { d: D }) {
  const lmap = useListingMap();
  const evals = (d.ev.data?.evaluations ?? []).filter((e) => e.feasible).slice(0, 4);
  if (!evals.length) return <Skeleton className="h-full" />;
  const max = Math.max(...evals.map((e) => e.all_in_total));
  return (
    <div className="space-y-3">
      {evals.map((e) => (
        <div key={e.listing_id}>
          <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
            <span className="truncate">{splitName(lmap.get(e.listing_id)?.name).title}</span>
            <span className="mono shrink-0 font-semibold">{usd(e.all_in_total)}</span>
          </div>
          <SplitBar cash={e.cash_total} other={e.all_in_total - e.cash_total} max={max} height={10} />
        </div>
      ))}
      <div className="flex gap-3 pt-1 text-xs text-faint">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-cash" />Cash</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: TIME_FILL }} />Valued time</span>
      </div>
    </div>
  );
}

function SureFragment({ d }: { d: D }) {
  const lmap = useListingMap();
  const r = d.rob.data;
  if (!r) return <Skeleton className="h-full" />;
  const ids = Object.keys(r.p_rank1).sort((a, b) => r.p_rank1[b] - r.p_rank1[a]);
  const top = ids[0];
  const k = Math.round(r.p_rank1[top] * 100);
  return (
    <div>
      <div role="img" aria-label={`${k} of 100 semesters`} className="grid w-fit grid-cols-10 gap-[3px]">
        {Array.from({ length: 100 }, (_, i) => (
          <svg key={i} width="15" height="16" viewBox="0 0 18 20" aria-hidden><path d="M9 1.5L1.5 8v10.5h15V8z" fill={i < k ? 'rgb(var(--ink))' : 'rgb(var(--line-strong))'} /></svg>
        ))}
      </div>
      <div className="mt-3 text-sm text-faint">
        <b className="mono font-semibold text-ink">{n0(Math.round(r.p_rank1[top] * r.samples))} of {n0(r.samples)}</b> sampled semesters keep {splitName(lmap.get(top)?.name).title} at #1.
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 4. two front doors

function TwoDoors({ d }: { d: D }) {
  const lmap = useListingMap();
  const bmap = useBuildingMap();
  const { top, cheapest, demo } = d;
  const events = demo?.profile.events ?? [];
  const pair = top && cheapest && top.listing_id !== cheapest.listing_id ? [top, cheapest] : top ? [top] : [];
  const dh = top && cheapest ? ((cheapest.commute?.weekly_min ?? 0) - (top.commute?.weekly_min ?? 0)) / 60 : 0;
  const dRent = top && cheapest ? d.rentOf(top) - d.rentOf(cheapest) : 0;
  const { points, lines } = useMemo(() => {
    const pts: MapPoint[] = [];
    const ls: MapLine[] = [];
    const seen = new Set<string>();
    for (const ev of events) {
      const b = ev.building_id ? bmap.get(ev.building_id) : null;
      if (!b || seen.has(b.id)) continue;
      seen.add(b.id);
      pts.push({ id: b.id, lat: b.lat, lon: b.lon, label: `${b.name}: ${ev.label}`, kind: 'building' });
      pair.forEach((e) => {
        const l = lmap.get(e.listing_id);
        if (!l) return;
        const bus = e.commute?.tours.some((t) => t.trips.some((tr) => tr.mode === 'bus' && tr.legs[tr.legs.length - 1]?.to_name === b.name));
        ls.push({ coords: [[l.lon, l.lat], [b.lon, b.lat]], kind: bus ? 'bus' : 'walk' });
      });
    }
    pair.forEach((e, i) => {
      const l = lmap.get(e.listing_id);
      if (l) pts.push({ id: l.id, lat: l.lat, lon: l.lon, label: l.name, kind: i === 0 ? 'home' : 'listing' });
    });
    const exact = pair.flatMap((e) => legLines(e));
    return { points: pts, lines: exact.length ? exact : ls };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, bmap, lmap, top?.listing_id, cheapest?.listing_id]);

  return (
    <Section id="week" label="week-h">
      {pair.length === 2 && dh > 0.5 ? (
        <Prose id="week-h" title={<>The lowest rent adds <span className="mono">{dh.toFixed(1)}</span> hours of travel a week</>}>
          It saves {usd(dRent)} a month in rent. Same schedule, both front doors, on this term’s timetable.
        </Prose>
      ) : (
        <Prose id="week-h" title="Your week from each front door" />
      )}
      <div className="ll-wide mt-10 grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          {pair.length === 0 && <Skeleton className="h-96" />}
          {pair.map((e, i) => e.commute && (
            <div key={e.listing_id} className="rounded-xl border border-line p-4 sm:p-5" data-visual>
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <span className="flex items-center gap-2 font-display text-lg font-semibold">
                  <span className={`h-3 w-3 rounded-full ${i === 0 ? 'bg-ink' : 'border-2 border-faint'}`} aria-hidden />
                  {splitName(lmap.get(e.listing_id)?.name).title}
                </span>
                <span className="mono text-sm text-faint"><b className="font-semibold text-ink">{hours(e.commute.weekly_min)}</b> a week door to door</span>
              </div>
              <WeekTimeline commute={e.commute} events={events} days={WEEKDAYS} legend={i === pair.length - 1} />
            </div>
          ))}
        </div>
        <div className="lg:col-span-5">
          <div className="h-[22rem] lg:h-full lg:min-h-[30rem]">
            <Suspense fallback={<Skeleton className="h-full" />}>
              <MapView points={points} lines={lines} height="100%" ariaLabel="Map of both homes and the week's buildings" />
            </Suspense>
          </div>
        </div>
      </div>
    </Section>
  );
}

// ------------------------------------------------------------------ 5. sources

function Sources() {
  const { data: listings = [] } = useListings();
  const feeds = useFeeds();
  const observed = listings.filter((l) => l.provenance === 'observed');
  const synthetic = listings.filter((l) => l.provenance === 'synthetic');
  const obsDate = observed.map((l) => l.observed_on).filter(Boolean).sort().pop();
  const rows: { k: string; v: ReactNode }[] = [];
  if (listings.length) rows.push({ k: 'Listings', v: <>{n0(observed.length)} observed {fmtDate(obsDate)} from search-result text; {n0(synthetic.length)} synthetic, labeled on every card</> });
  if (feeds.um) rows.push({ k: 'U-M buses', v: <>Timetable valid {fmtDate(feeds.um.calendar_start)} to {fmtDate(feeds.um.calendar_end)}{feeds.um.weekday_trips_in_week ? <>; {n0(feeds.um.weekday_trips_in_week)} weekday trips in the modeled week</> : null}</> });
  if (feeds.aaata) rows.push({ k: 'TheRide buses', v: <>Timetable valid {fmtDate(feeds.aaata.calendar_start)} to {fmtDate(feeds.aaata.calendar_end)}{feeds.aaata.weekday_trips_in_week ? <>; {n0(feeds.aaata.weekday_trips_in_week)} weekday trips</> : null}</> });
  rows.push({ k: 'Streets', v: <>Overture Maps segments, derived from OpenStreetMap (ODbL)</> });
  const kinds: Provenance[] = ['observed', 'estimated', 'assumed', 'computed', 'synthetic', 'user'];
  return (
    <Section id="sources" label="sources-h">
      <Prose id="sources-h" title="Every number says where it came from">Each line of the ledger carries one of six tags.</Prose>
      <div className="ll-col mt-8">
        <ul className="flex flex-wrap gap-2" aria-label="Provenance tags">
          {kinds.map((k) => (
            <li key={k} className="inline-flex items-center gap-2 rounded-full border border-line py-1 pl-1 pr-3 text-sm" title={PROV_META[k].desc}>
              <ProvenanceBadge p={k} compact />{PROV_META[k].label}
            </li>
          ))}
        </ul>
        <dl className="mt-8 border-t border-line">
          {rows.map((r) => (
            <div key={r.k} className="grid gap-1 border-b border-line py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
              <dt className="font-medium">{r.k}</dt>
              <dd className="mono text-[0.9375rem] leading-relaxed text-faint">{r.v}</dd>
            </div>
          ))}
        </dl>
        <a href="/app#methods" onClick={linkTo('/app#methods')} className="ll-link mt-6 inline-block text-base font-medium">Read the methods</a>
      </div>
    </Section>
  );
}

// ------------------------------------------------------------------ 6. group week

function Group({ d }: { d: D }) {
  const lmap = useListingMap();
  const g = d.grp.data;
  const id = g?.ranking[0];
  const split = g?.splits.find((s) => s.listing_id === id);
  const names = d.demos.slice(0, 3).map((x) => x.name);
  const travel = (alias: string) => {
    const f = split?.explanation_facts.find((x) => x.startsWith(`${alias} gets`));
    const m = f && /own travel cost from here \$([\d,.]+)\/mo/.exec(f);
    return m ? Number(m[1].replace(/,/g, '')) : null;
  };
  const maxEnvy = split ? Math.max(0, ...split.envy_matrix.flat()) : null;
  const name = splitName(split ? lmap.get(split.listing_id)?.name : '');
  return (
    <Section id="group" label="group-h">
      <Prose id="group-h" title="Group Week splits one lease by everyone’s week"
        right={<a href="/app#group" onClick={linkTo('/app#group')} className="btn-outline">Plan a group lease</a>}>
        Add each roommate’s schedule. It picks the home that is best for the worst-off roommate, assigns rooms and splits rent so nobody would rather swap.
      </Prose>
      <div className="ll-col mt-10 rounded-xl border border-line p-5 sm:p-6">
        {!split ? (d.grp.isLoading ? <Skeleton className="h-72" /> : <p className="text-sm text-faint">No shared home fits these three sample weeks.</p>) : (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="text-sm text-faint">Three sample weeks · best home for the worst-off roommate</div>
              {maxEnvy != null && <span className="tag">envy-free · max envy {usd(maxEnvy)}</span>}
            </div>
            <div className="mt-1 font-display text-2xl font-semibold">{name.title}</div>
            {name.sub && <div className="text-faint">{name.sub}</div>}
            <table className="mt-5 w-full text-left text-sm">
              <thead className="text-xs text-faint">
                <tr className="border-b border-line"><th className="py-2 pr-3 font-medium">Roommate</th><th className="py-2 pr-3 font-medium">Room</th><th className="py-2 pr-3 text-right font-medium">Rent</th><th className="py-2 text-right font-medium">Own travel</th></tr>
              </thead>
              <tbody className="mono">
                {Object.keys(split.assignment).map((alias, i) => (
                  <tr key={alias} className="border-b border-line last:border-0">
                    <td className="py-3 pr-3 font-sans"><div className="font-medium text-ink">{alias}</div><div className="text-xs text-faint">{names[i]}</div></td>
                    <td className="py-3 pr-3">{split.assignment[alias]}</td>
                    <td className="py-3 pr-3 text-right font-semibold">{usd(split.rent[alias])}</td>
                    <td className="py-3 text-right text-faint">{travel(alias) != null ? usd(travel(alias)) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Section>
  );
}

// ------------------------------------------------------------------ 7. close + footer

function Closing() {
  const setWeekDraft = useApp((s) => s.setWeekDraft);
  const [text, setText] = useState('');
  const go = () => { setWeekDraft(text.trim()); navigate(TRY); };
  return (
    <section className="ll-section" aria-labelledby="close-h">
      <div className="ll-col text-center">
        <h2 id="close-h" className="ll-h2">Type your week and see the ranking</h2>
        <p className="mt-3 text-lg text-faint">No account. Today’s listings, this term’s bus timetables.</p>
        <div className="mx-auto mt-8 max-w-[36rem] text-left">
          <WeekPill value={text} onChange={setText} onSubmit={go} placeholder={PLACEHOLDER} label="Describe your week" />
        </div>
        <p className="mt-5 text-sm text-faint">or <a href={SAMPLE} onClick={linkTo(SAMPLE)} className="ll-link text-ink">open the app with a sample week</a></p>
      </div>
    </section>
  );
}

function Footer() {
  const links = [
    { href: '/app#week', label: 'Your week' },
    { href: '/app#results', label: 'What your week costs' },
    { href: '/app#robustness', label: 'How sure are we?' },
    { href: '/app#group', label: 'Group Week' },
    { href: '/app#methods', label: 'Methods & sources' },
  ];
  return (
    <footer className="border-t border-line">
      <div className="ll-wrap flex flex-col gap-4 py-8 text-xs text-faint md:flex-row md:items-center md:justify-between">
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          {links.map((l) => <a key={l.href} href={l.href} onClick={linkTo(l.href)} className="py-1 hover:text-ink hover:underline">{l.label}</a>)}
        </nav>
        <p>© 2026 {PRODUCT_NAME} · Hack the Lease 2026 · Not legal or financial advice · Synthetic listings are labeled · Streets: Overture Maps / OSM (ODbL)</p>
      </div>
    </footer>
  );
}
