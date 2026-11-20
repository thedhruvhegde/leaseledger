/**
 * Product homepage ("/"): a plain, credible front door in the portal convention — search field first, one real
 * screenshot of the results page, how it works in three steps, sources with live dates and counts, limits.
 * No hype copy, testimonials, invented stats or stock photos. Counts and dates come from the API.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { useApp } from '../store/app';
import { useDemoProfiles, useListings, useManifest } from '../api/hooks';
import { Logo } from '../components/Header';
import { PROV_META, ProvenanceBadge } from '../components/ui/Badge';
import { IconCalendar, IconMoon, IconSun } from '../components/ui/Icons';
import { linkTo, navigate } from '../lib/route';
import { SCREENS } from '../store/app';
import { PRODUCT_NAME } from '../brand';
import type { Provenance } from '../types';

const DEMO_ID = 'north-engineer';
const SAMPLE = `/app?demo=${DEMO_ID}#results`;
const PLACEHOLDER = 'MWF 9 EECS in BBB · TTh 2:30 Ross · UgLi till 1am';

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

export default function Landing() {
  const fellBack = useApp((s) => s.fellBack);
  useEffect(() => {
    document.title = `${PRODUCT_NAME}: Ann Arbor rentals ranked by your week`;
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
      {fellBack && <div role="status" className="border-b border-line bg-raised px-4 py-2 text-center text-[13px] text-charcoal">API offline: showing mock data. Every listing is synthetic.</div>}
      <main>
        <Hero />
        <Screenshot />
        <How />
        <Sources />
        <Limits />
      </main>
      <Footer />
    </div>
  );
}

function Nav() {
  const theme = useApp((s) => s.theme);
  const toggleTheme = useApp((s) => s.toggleTheme);
  const links = [{ href: '#how', label: 'How it works' }, { href: '#sources', label: 'Sources' }, { href: '/app#group', label: 'Group Week', app: true }, { href: '/app#methods', label: 'Methods', app: true }];
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-bg">
      <div className="ll-wrap flex h-14 items-center gap-6">
        <a href="/" className="flex items-center gap-2 rounded-full" aria-label={`${PRODUCT_NAME} home`} onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0 }); }}>
          <Logo size={24} />
          <span className="font-display text-[1.0625rem] font-semibold">{PRODUCT_NAME}</span>
        </a>
        <nav aria-label="Site" className="hidden items-center md:flex">
          {links.map((l) => <a key={l.href} href={l.href} onClick={l.app ? linkTo(l.href) : undefined} className="px-3 py-2 text-[13.5px] font-medium text-faint transition-colors hover:text-ink">{l.label}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <button className="btn-ghost h-8 w-8 px-0" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}</button>
          <a href="/app#results" onClick={linkTo('/app#results')} className="btn-outline h-9">Open the app</a>
        </div>
      </div>
    </header>
  );
}

function SearchField({ autoFocus = false }: { autoFocus?: boolean }) {
  const setWeekDraft = useApp((s) => s.setWeekDraft);
  const [text, setText] = useState('');
  const go = () => {
    if (!text.trim()) { navigate(SAMPLE); return; }
    setWeekDraft(text.trim());
    navigate('/app#results');
  };
  return (
    <form className="hero-search" role="search" onSubmit={(e) => { e.preventDefault(); go(); }}>
      <IconCalendar size={18} className="ml-1 shrink-0 text-faint" />
      <label htmlFor="hero-week" className="sr-only">Describe your week</label>
      <input id="hero-week" autoFocus={autoFocus} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder={PLACEHOLDER}
        className="min-w-0 flex-1 bg-transparent text-[15px] text-ink placeholder:text-faint focus:outline-none" autoComplete="off" />
      <button type="submit" className="btn-primary h-11 shrink-0 px-6 text-[14px]">See homes</button>
    </form>
  );
}

function Hero() {
  const { data: listings = [] } = useListings();
  const { data: demos = [] } = useDemoProfiles();
  const feeds = useFeeds();
  const observed = listings.filter((l) => l.provenance === 'observed');
  const obsDate = observed.map((l) => l.observed_on).filter(Boolean).sort().pop();
  const ends = [feeds.um?.calendar_end, feeds.aaata?.calendar_end].filter(Boolean).sort() as string[];
  return (
    <section id="hero" className="border-b border-line bg-raised" aria-labelledby="hero-h">
      <div className="ll-col py-16 text-center sm:py-20">
        <h1 id="hero-h" className="ll-h1">Ann Arbor rentals, ranked by what your week costs</h1>
        <p className="mx-auto mt-4 max-w-[34rem] text-[16px] leading-relaxed text-charcoal">
          Describe your classes, job and late nights. {PRODUCT_NAME} plans every trip on the bus timetables and adds the time to rent, utilities and fees, so each home has one monthly number.
        </p>
        <div className="mx-auto mt-8 max-w-[40rem]"><SearchField /></div>
        {demos.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-2 gap-y-2 text-[13px] text-faint">
            <span>Or start from a sample week:</span>
            {demos.map((d) => {
              const href = `/app?demo=${d.id}#results`;
              return <a key={d.id} href={href} onClick={linkTo(href)} className="rounded-full border border-line bg-surface px-3 py-1 text-charcoal transition-colors hover:border-ink hover:text-ink">{d.name}</a>;
            })}
          </div>
        )}
        {observed.length > 0 && (
          <p className="mt-6 text-[12px] text-faint">
            {n0(observed.length)} listings observed {fmtDate(obsDate)} · {n0(listings.length - observed.length)} synthetic, labeled{ends.length > 0 && <> · bus timetables valid to {fmtDate(ends[0])}</>}
          </p>
        )}
      </div>
    </section>
  );
}

function Screenshot() {
  return (
    <section className="ll-section" aria-labelledby="shot-h">
      <div className="ll-wide">
        <h2 id="shot-h" className="sr-only">The results page</h2>
        <figure>
          <a href={SAMPLE} onClick={linkTo(SAMPLE)} className="block overflow-hidden rounded-xl border border-line-strong bg-raised" aria-label="Open the results page for the sample week">
            <img src="/product-results.jpg" width={2160} height={1350} alt="The Lease Ledger results page: a ranked list of homes with all-in monthly prices on the left and a map with numbered price pins and the selected home's bus and walking routes on the right." className="block h-auto w-full" loading="lazy" />
          </a>
          <figcaption className="mt-3 text-[13px] text-faint">
            The results page for the sample week “North Campus engineer”. Prices are per person per month; all-in adds travel time to the cash you pay. Screenshot of the running app.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

function How() {
  const steps: { n: string; title: string; body: ReactNode }[] = [
    { n: '1', title: 'Describe your week', body: <>Type it the way you’d text a friend: “MWF 9 EECS in BBB, gym Mon/Wed, UgLi till 1am”. Each block keeps the words it came from, and you can drag it on a weekly grid.</> },
    { n: '2', title: 'Every trip is planned', body: <>For each home, every trip of your week is routed on the U-M Blue Bus and TheRide timetables and the street network: walking, waiting, riding, and the minutes you spend outside after 10 PM.</> },
    { n: '3', title: 'Homes ranked by all-in cost', body: <>Rent, utilities, fees and the value of your travel time become one monthly number per home, on a receipt you can read line by line. Compare two homes, or see how sure the ranking is.</> },
  ];
  return (
    <section id="how" className="ll-section" aria-labelledby="how-h">
      <div className="ll-wide">
        <h2 id="how-h" className="ll-h2">How it works</h2>
        <ol className="mt-8 grid gap-8 border-t border-line pt-8 md:grid-cols-3">
          {steps.map((s) => (
            <li key={s.n}>
              <div className="num flex h-7 w-7 items-center justify-center rounded-full border border-line-strong text-[13px] font-semibold">{s.n}</div>
              <h3 className="mt-4 text-[17px] font-semibold">{s.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-charcoal">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Sources() {
  const { data: listings = [] } = useListings();
  const feeds = useFeeds();
  const observed = listings.filter((l) => l.provenance === 'observed');
  const synthetic = listings.filter((l) => l.provenance === 'synthetic');
  const obsDate = observed.map((l) => l.observed_on).filter(Boolean).sort().pop();
  const rows: { k: string; v: ReactNode }[] = [];
  if (listings.length) rows.push({ k: 'Listings', v: <>{n0(observed.length)} observed {fmtDate(obsDate)} from public listing text; {n0(synthetic.length)} synthetic (fictional), labeled on every card. Availability is not verified.</> });
  if (feeds.um) rows.push({ k: 'U-M buses', v: <>GTFS timetable valid {fmtDate(feeds.um.calendar_start)} to {fmtDate(feeds.um.calendar_end)}{feeds.um.weekday_trips_in_week ? <>; {n0(feeds.um.weekday_trips_in_week)} weekday trips in the modeled week</> : null}.</> });
  if (feeds.aaata) rows.push({ k: 'TheRide buses', v: <>GTFS timetable valid {fmtDate(feeds.aaata.calendar_start)} to {fmtDate(feeds.aaata.calendar_end)}{feeds.aaata.weekday_trips_in_week ? <>; {n0(feeds.aaata.weekday_trips_in_week)} weekday trips</> : null}.</> });
  rows.push({ k: 'Streets & map', v: <>Overture Maps segments derived from OpenStreetMap (ODbL), served offline. Listing thumbnails are drawn from these streets; there are no photos.</> });
  const kinds: Provenance[] = ['observed', 'estimated', 'assumed', 'computed', 'synthetic', 'user'];
  return (
    <section id="sources" className="ll-section" aria-labelledby="sources-h">
      <div className="ll-wide grid gap-10 md:grid-cols-[18rem_1fr]">
        <div>
          <h2 id="sources-h" className="ll-h2">Sources</h2>
          <p className="mt-3 text-[14.5px] leading-relaxed text-charcoal">Every line of a receipt carries a tag saying where the number came from.</p>
          <ul className="mt-5 space-y-2" aria-label="Provenance tags">
            {kinds.map((k) => (
              <li key={k} className="flex items-center gap-2 text-[13px] text-charcoal" title={PROV_META[k].desc}>
                <ProvenanceBadge p={k} compact /><span className="font-medium text-ink">{PROV_META[k].label}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <dl className="border-t border-line">
            {rows.map((r) => (
              <div key={r.k} className="grid gap-1 border-b border-line py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
                <dt className="text-[14px] font-medium">{r.k}</dt>
                <dd className="text-[14px] leading-relaxed text-charcoal">{r.v}</dd>
              </div>
            ))}
          </dl>
          <a href="/app#methods" onClick={linkTo('/app#methods')} className="ll-link mt-5 inline-block text-[14px] font-medium">Methods, equations and assumptions</a>
        </div>
      </div>
    </section>
  );
}

function Limits() {
  return (
    <section className="ll-section" aria-labelledby="limits-h">
      <div className="ll-wide">
        <div className="grid gap-6 rounded-xl border border-line p-6 md:grid-cols-[18rem_1fr] md:p-8">
          <h2 id="limits-h" className="text-[1.25rem] font-semibold">What it doesn’t do</h2>
          <ul className="space-y-2 text-[14px] leading-relaxed text-charcoal">
            <li>It doesn’t list, rent or hold apartments. Listing facts are read from public text and may be out of date; check with the landlord.</li>
            <li>The all-in number is a way to rank homes, not a bill. Travel time is priced at a rate you can change, including zero.</li>
            <li>It covers Ann Arbor and its two bus systems only. It is not legal or financial advice.</li>
          </ul>
        </div>
        <div className="mt-12 flex flex-col items-center gap-4 text-center">
          <h2 className="text-[1.5rem] font-semibold">Start with your week</h2>
          <div className="w-full max-w-[40rem]"><SearchField /></div>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const links = [
    { href: '/app#results', label: 'Homes' },
    { href: '/app#week', label: 'Your week' },
    { href: '/app#robustness', label: 'How sure are we?' },
    { href: '/app#baseline', label: 'Portal vs. your week' },
    { href: '/app#group', label: 'Group Week' },
    { href: '/app#add', label: 'Add a listing' },
    { href: '/app#methods', label: 'Methods & sources' },
  ];
  return (
    <footer className="mt-[88px] border-t border-line">
      <div className="ll-wrap flex flex-col gap-4 py-8 text-[12px] text-faint md:flex-row md:items-center md:justify-between">
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          {links.map((l) => <a key={l.href} href={l.href} onClick={linkTo(l.href)} className="py-1 hover:text-ink hover:underline">{l.label}</a>)}
        </nav>
        <p>© 2026 {PRODUCT_NAME} · Hack the Lease 2026 · Not legal or financial advice · Streets: Overture Maps / OSM (ODbL)</p>
      </div>
    </footer>
  );
}
