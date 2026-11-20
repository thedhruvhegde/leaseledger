import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { currentRoute, navigate, type Route } from './lib/route';
import { resolveClient, watchLive } from './api/client';
import { SCREENS, useApp, type Screen } from './store/app';
import { useBuildings, useDemoProfiles, useDiff, useListingMap } from './api/hooks';
import { parseSchedule as localParse } from './api/mockNlp';
import { Header, Logo, TabBar } from './components/Header';
import { DiffDrawer } from './components/DiffDrawer';
import { WeekScreen } from './screens/WeekScreen';
import { ResultsScreen } from './screens/ResultsScreen';
import { RobustnessScreen } from './screens/RobustnessScreen';
import { BaselineScreen } from './screens/BaselineScreen';
import { GroupScreen } from './screens/GroupScreen';
import { AddListingScreen } from './screens/AddListingScreen';
import { MethodsScreen } from './screens/MethodsScreen';
import { PRODUCT_NAME, TAGLINE } from './brand';

const Landing = lazy(() => import('./landing/Landing'));

export function App() {
  const api = useApp((s) => s.api);
  const setApi = useApp((s) => s.setApi);
  const theme = useApp((s) => s.theme);
  const present = useApp((s) => s.present);

  useEffect(() => {
    let alive = true;
    let stop: (() => void) | undefined;
    void resolveClient().then(({ api, fellBack, health }) => {
      if (!alive) return;
      setApi(api, fellBack, health);
      if (fellBack) stop = watchLive((liveApi, h) => alive && setApi(liveApi, false, h));
    });
    return () => { alive = false; stop?.(); };
  }, [setApi]);

  const [route, setRoute] = useState<Route>(currentRoute);
  useEffect(() => {
    const on = () => setRoute(currentRoute());
    window.addEventListener('popstate', on);
    window.addEventListener('hashchange', on);
    return () => { window.removeEventListener('popstate', on); window.removeEventListener('hashchange', on); };
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('present', present && route === 'app');
  }, [theme, present, route]);

  if (!api) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg">
        <Logo />
        <div className="text-lg font-semibold">{PRODUCT_NAME}</div>
        <div className="text-sm text-muted">{TAGLINE}</div>
      </div>
    );
  }
  if (route === 'landing') {
    return (
      <Suspense fallback={<div className="min-h-screen bg-bg" />}>
        <Landing />
      </Suspense>
    );
  }
  return <Shell />;
}

function Shell() {
  const screen = useApp((s) => s.screen);
  const setScreen = useApp((s) => s.setScreen);
  const profile = useApp((s) => s.profile);
  const commit = useApp((s) => s.commit);
  const fellBack = useApp((s) => s.fellBack);
  const drawerOpen = useApp((s) => s.drawerOpen);
  const setDrawer = useApp((s) => s.setDrawer);
  const pinned = useApp((s) => s.pinned);
  const pin = useApp((s) => s.pin);
  const unpin = useApp((s) => s.unpin);
  const togglePresent = useApp((s) => s.togglePresent);
  const diff = useDiff();
  const names = useListingMap();
  const demos = useDemoProfiles();

  // ?demo=<id> preloads a demo profile (handy for rehearsals and screenshots)
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('demo');
    const d = id ? demos.data?.find((x) => x.id === id) : undefined;
    if (d) useApp.getState().setProfile(d.profile, 'load');
  }, [demos.data]);

  // Debounced commit: edits are instant in the UI, queries fire 150 ms after the last change.
  useEffect(() => {
    const t = setTimeout(commit, 150);
    return () => clearTimeout(t);
  }, [profile, commit]);

  // Hash routing + keyboard shortcuts (1–7 switch sections, P presentation mode)
  useEffect(() => {
    const fromHash = () => {
      const h = window.location.hash.replace('#', '') as Screen;
      if (SCREENS.some((s) => s.id === h)) setScreen(h);
    };
    fromHash();
    window.addEventListener('hashchange', fromHash);
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      const t = e.target as HTMLElement;
      if (t.closest('input, textarea, select, [contenteditable]') || e.metaKey || e.ctrlKey || e.altKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= SCREENS.length) setScreen(SCREENS[n - 1].id);
      if (e.key === 'p' || e.key === 'P') togglePresent();
      if (e.key === 'Escape') setDrawer(false);
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('hashchange', fromHash); window.removeEventListener('keydown', onKey); };
  }, [setScreen, togglePresent, setDrawer]);

  useEffect(() => {
    if (window.location.hash !== `#${screen}`) history.replaceState(null, '', `${window.location.pathname === '/' ? '/app' : window.location.pathname}${window.location.search}#${screen}`);
    window.scrollTo({ top: 0 });
  }, [screen]);

  // Landing hand-off: read the typed week once, then show the homes it ranks.
  const weekDraft = useApp((s) => s.weekDraft);
  const api = useApp((s) => s.api);
  const { data: buildings = [] } = useBuildings();
  const consumed = useRef<string | null>(null);
  useEffect(() => {
    if (!weekDraft || !api || consumed.current === weekDraft) return;
    consumed.current = weekDraft;
    const st = useApp.getState();
    st.setWeekDraft(null);
    st.setParsing(true);
    st.setScreen('results');
    void api.parseSchedule(weekDraft, st.aiEnabled).catch(() => localParse(weekDraft, buildings)).then((r) => {
      const s2 = useApp.getState();
      s2.setProfile((p) => ({ ...p, events: r.events }), 'load');
      const nc: Record<number, string[]> = {};
      for (const n of r.needs_confirmation) (nc[n.event_index] ??= []).push(n.reason);
      s2.setNeedsConfirm(nc);
      s2.setLastAiMode(r.mode);
      s2.setParsing(false);
    });
  }, [weekDraft, api, buildings]);

  const showDrawer = drawerOpen && (screen === 'week' || screen === 'results'); // never cover how-sure / portal screens

  const full = screen === 'results';
  return (
    <div className="min-h-screen bg-bg">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <Header />
      {!api && (
        <div role="status" className="border-b border-line bg-raised px-4 py-1.5 text-center text-[13px] text-charcoal">
          Connecting to the live server… the first visit after a quiet spell can take up to a minute.
        </div>
      )}
      {fellBack && (
        <div role="status" className="border-b border-line bg-raised px-4 py-1.5 text-center text-[13px] text-charcoal">
          Live server not reachable yet — showing sample data (simplified travel, synthetic listings). It reconnects automatically.
        </div>
      )}
      {full ? (
        <main id="main" className="app-main app-full"><ResultsScreen /></main>
      ) : (
        <>
          <main id="main" className="app-main mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:py-8">
            {screen === 'week' && <WeekScreen />}
            {screen === 'robustness' && <RobustnessScreen />}
            {screen === 'baseline' && <BaselineScreen />}
            {screen === 'group' && <GroupScreen />}
            {screen === 'add' && <AddListingScreen />}
            {screen === 'methods' && <MethodsScreen />}
          </main>
          <footer className="secondary-chrome app-foot mx-auto max-w-[1440px] border-t border-line px-4 py-6 text-[12px] text-faint sm:px-6">
            {PRODUCT_NAME} · Hack the Lease 2026 · Not legal or financial advice. Synthetic listings are fictional and labeled. <a className="underline decoration-line-strong underline-offset-2 hover:text-ink" href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}>About {PRODUCT_NAME}</a>
          </footer>
        </>
      )}
      <TabBar />
      <DiffDrawer diff={diff.data} loading={diff.isFetching} names={names} open={showDrawer} pinned={!!pinned} onClose={() => setDrawer(false)} onPin={pin} onUnpin={unpin} />
    </div>
  );
}
