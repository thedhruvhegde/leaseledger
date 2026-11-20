import { useState } from 'react';
import { PRODUCT_NAME } from '../brand';
import { navigate } from '../lib/route';
import { SCREENS, useApp, type Screen } from '../store/app';
import { useListings } from '../api/hooks';
import { ProvenanceLegend } from './ui/Badge';
import { IconBook, IconCalendar, IconGauge, IconHome, IconLayers, IconMoon, IconMore, IconPlus, IconPresent, IconSparkle, IconSun, IconSwap, IconUsers } from './ui/Icons';

/** Our mark: a house outline whose roofline is a bus-route polyline with three stops. Stroke-only, ink. */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-ink">
      <path d="M3.5 16 L10 9.5 L14 12 L19 5.5 L23 9 L28.5 16" strokeWidth="2" />
      <circle cx="10" cy="9.5" r="1.6" strokeWidth="1.6" fill="rgb(var(--bg))" />
      <circle cx="19" cy="5.5" r="1.6" strokeWidth="1.6" fill="rgb(var(--bg))" />
      <circle cx="23" cy="9" r="1.6" strokeWidth="1.6" fill="rgb(var(--bg))" />
      <path d="M7 14v13.5h18V14" strokeWidth="2" />
      <path d="M13.5 27.5v-6.5h5v6.5" strokeWidth="1.8" />
    </svg>
  );
}

export function Header() {
  const screen = useApp((s) => s.screen);
  const setScreen = useApp((s) => s.setScreen);
  const theme = useApp((s) => s.theme);
  const toggleTheme = useApp((s) => s.toggleTheme);
  const present = useApp((s) => s.present);
  const togglePresent = useApp((s) => s.togglePresent);
  const aiEnabled = useApp((s) => s.aiEnabled);
  const setAiEnabled = useApp((s) => s.setAiEnabled);
  const lastAiMode = useApp((s) => s.lastAiMode);
  const health = useApp((s) => s.health);
  const kind = useApp((s) => s.api?.kind);
  const { data: listings = [] } = useListings();
  const [legend, setLegend] = useState(false);
  const synthetic = listings.filter((l) => l.provenance === 'synthetic').length;
  const aiMode = !aiEnabled ? 'off' : lastAiMode ?? (typeof health?.ai_mode === 'string' ? health.ai_mode : typeof health?.llm_mode === 'string' ? health.llm_mode : 'regex');

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg">
      <div className="flex h-14 items-center gap-2 px-4 lg:px-5">
        <a href="/" className="mr-3 flex shrink-0 items-center gap-2 rounded-full" onClick={(e) => { e.preventDefault(); navigate('/'); }} aria-label={`${PRODUCT_NAME} home`}>
          <Logo size={24} />
          <span className="font-display text-[1.0625rem] font-semibold text-ink">{PRODUCT_NAME}</span>
        </a>
        <nav aria-label="Sections" className="no-scrollbar hidden min-w-0 flex-1 items-center overflow-x-auto lg:flex">
          {SCREENS.map((s, i) => (
            <button key={s.id} onClick={() => setScreen(s.id)} aria-current={screen === s.id ? 'page' : undefined}
              title={`${s.label} (press ${i + 1})`}
              className={`nav-link ${screen === s.id ? 'is-current' : ''}`}>
              {present ? s.short : s.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-1">
          {synthetic > 0 && (
            <span className="hidden h-7 items-center rounded-full border border-dashed border-line-strong px-2.5 text-[11px] text-faint hatch-synthetic xl:inline-flex"
              title={`${synthetic} of ${listings.length} listings are synthetic (fictional) demo data`}>
              {synthetic}/{listings.length} synthetic
            </span>
          )}
          <button onClick={() => setAiEnabled(!aiEnabled)} className="secondary-chrome hidden h-7 items-center gap-1 rounded-full px-2.5 text-[11px] text-faint hover:bg-soft hover:text-ink sm:inline-flex"
            title={`AI parsing: ${aiMode}. Click to turn AI ${aiEnabled ? 'off' : 'on'} — everything still works with the offline parser.`} aria-pressed={aiEnabled}>
            <IconSparkle size={12} /> AI {aiMode}
          </button>
          <div className="relative">
            <button className="btn-ghost h-8 w-8 px-0" onClick={() => setLegend((v) => !v)} aria-expanded={legend} aria-label="Where numbers come from" title="Where numbers come from"><IconLayers size={16} /></button>
            {legend && (
              <div className="absolute right-0 top-10 z-50 w-72 rounded-xl border border-line-strong bg-surface p-1" onMouseLeave={() => setLegend(false)}>
                <div className="px-3 pt-2 text-xs font-semibold">Where numbers come from</div>
                <ProvenanceLegend />
              </div>
            )}
          </div>
          <button className="btn-ghost h-8 w-8 px-0" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}</button>
          <button className={`btn-ghost hidden h-8 w-8 px-0 sm:inline-flex ${present ? 'text-ink' : ''}`} onClick={togglePresent} aria-pressed={present} aria-label="Presentation mode" title="Presentation mode: larger type, less chrome (P)"><IconPresent size={16} /></button>
          {kind === 'mock' && <span className="secondary-chrome hidden rounded-full border border-dashed border-line-strong px-2.5 py-0.5 text-[11px] md:inline">mock data</span>}
        </div>
      </div>
    </header>
  );
}

const TAB_ICON: Record<Screen, (p: { size?: number }) => JSX.Element> = {
  week: IconCalendar, results: IconHome, robustness: IconGauge, baseline: IconSwap, group: IconUsers, add: IconPlus, methods: IconBook,
};
const PRIMARY: Screen[] = ['results', 'week', 'robustness', 'group'];

/** Phone: four primary sections + More (portal comparison, add a listing, methods) as a bottom tab bar. */
export function TabBar() {
  const screen = useApp((s) => s.screen);
  const setScreen = useApp((s) => s.setScreen);
  const [more, setMore] = useState(false);
  const inMore = !PRIMARY.includes(screen);
  const tab = (id: Screen) => {
    const s = SCREENS.find((x) => x.id === id)!;
    const Icon = TAB_ICON[id];
    const on = screen === id;
    return (
      <button key={id} onClick={() => { setMore(false); setScreen(id); }} aria-current={on ? 'page' : undefined} aria-label={s.label}
        className={`flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${on ? 'text-ink' : 'text-faint'}`}>
        <Icon size={20} />{s.short}
      </button>
    );
  };
  return (
    <>
      {more && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setMore(false)}>
          <div className="absolute inset-0 bg-ink/20" />
          <div className="tabbar-more absolute inset-x-2 rounded-xl border border-line-strong bg-surface p-1" onClick={(e) => e.stopPropagation()} role="menu">
            {SCREENS.filter((s) => !PRIMARY.includes(s.id)).map((s) => {
              const Icon = TAB_ICON[s.id];
              return (
                <button key={s.id} role="menuitem" onClick={() => { setMore(false); setScreen(s.id); }} className={`flex h-12 w-full items-center gap-3 rounded-lg px-3 text-left text-[15px] ${screen === s.id ? 'bg-soft font-medium' : ''}`}>
                  <Icon size={18} />{s.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
      <nav aria-label="Sections" className="tabbar fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg lg:hidden">
        <div className="grid grid-cols-5">
          {PRIMARY.map(tab)}
          <button onClick={() => setMore((v) => !v)} aria-expanded={more} aria-label="More sections"
            className={`flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${inMore || more ? 'text-ink' : 'text-faint'}`}>
            <IconMore size={20} />More
          </button>
        </div>
      </nav>
    </>
  );
}
