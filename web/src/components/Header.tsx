import { useState } from 'react';
import { PRODUCT_NAME } from '../brand';
import { navigate } from '../lib/route';
import { SCREENS, useApp, type Screen } from '../store/app';
import { useListings } from '../api/hooks';
import { ProvenanceLegend } from './ui/Badge';
import { IconBook, IconCalendar, IconGauge, IconLayers, IconMoon, IconPlus, IconPresent, IconReceipt, IconSparkle, IconSun, IconSwap, IconUsers } from './ui/Icons';

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
  const aiTone = aiMode === 'off' ? 'text-mute' : 'text-charcoal';

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg">
      <div className="mx-auto flex max-w-[1800px] items-center gap-3 px-4 py-2.5 sm:px-6">
        <a href="/" className="flex shrink-0 items-center gap-2 rounded-full" onClick={(e) => { e.preventDefault(); navigate('/'); }} aria-label={`${PRODUCT_NAME} home`}>
          <Logo />
          <span className="font-display text-lg font-semibold text-ink sm:text-xl">{PRODUCT_NAME}</span>
        </a>
        <nav aria-label="Sections" className="no-scrollbar hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto lg:flex">
          {SCREENS.map((s, i) => (
            <button key={s.id} onClick={() => setScreen(s.id)} aria-current={screen === s.id ? 'page' : undefined}
              title={`${s.label} (press ${i + 1})`}
              className={`relative h-9 whitespace-nowrap rounded-full px-3.5 text-sm font-medium transition-colors ${screen === s.id ? 'bg-soft text-ink' : 'text-faint hover:bg-soft hover:text-ink'}`}>
              {present ? s.short : s.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {synthetic > 0 && (
            <span className="mono hidden h-8 items-center rounded-full border border-dashed border-line-strong px-3 text-xs text-charcoal hatch-synthetic sm:inline-flex"
              title={`${synthetic} of ${listings.length} listings are synthetic (fictional) demo data`}>
              synthetic {synthetic}/{listings.length}
            </span>
          )}
          <button onClick={() => setAiEnabled(!aiEnabled)} className={`secondary-chrome mono inline-flex h-8 items-center gap-1 rounded-full bg-soft px-3 text-xs ${aiTone}`}
            title={`AI parsing: ${aiMode}. Click to turn AI ${aiEnabled ? 'off' : 'on'} — everything still works with the offline parser.`} aria-pressed={aiEnabled}>
            <IconSparkle size={12} /> ai · {aiMode}
          </button>
          <div className="relative">
            <button className="btn-ghost w-9 px-0" onClick={() => setLegend((v) => !v)} aria-expanded={legend} aria-label="Provenance legend" title="What the O/E/A/C/S/U badges mean"><IconLayers /></button>
            {legend && (
              <div className="absolute right-0 top-10 z-50 w-72 rounded-xl border border-line-strong bg-surface p-1" onMouseLeave={() => setLegend(false)}>
                <div className="px-3 pt-2 text-xs font-semibold">Where numbers come from</div>
                <ProvenanceLegend />
              </div>
            )}
          </div>
          <button className="btn-ghost w-9 px-0" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <IconSun /> : <IconMoon />}</button>
          <button className={`btn-ghost w-9 px-0 ${present ? 'text-accent' : ''}`} onClick={togglePresent} aria-pressed={present} aria-label="Presentation mode" title="Presentation mode: larger type, less chrome (P)"><IconPresent /></button>
          {kind === 'mock' && <span className="secondary-chrome mono hidden rounded-full border border-dashed border-line-strong px-3 py-1 text-xs md:inline">mock data</span>}
        </div>
      </div>
    </header>
  );
}

const TAB_ICON: Record<Screen, (p: { size?: number }) => JSX.Element> = {
  week: IconCalendar, results: IconReceipt, robustness: IconGauge, baseline: IconSwap, group: IconUsers, add: IconPlus, methods: IconBook,
};

/** Phone: the seven screens as a bottom tab bar (thumb reach), above the home indicator. */
export function TabBar() {
  const screen = useApp((s) => s.screen);
  const setScreen = useApp((s) => s.setScreen);
  return (
    <nav aria-label="Sections" className="tabbar fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg lg:hidden">
      <div className="grid grid-cols-7">
        {SCREENS.map((s) => {
          const Icon = TAB_ICON[s.id];
          const on = screen === s.id;
          return (
            <button key={s.id} onClick={() => setScreen(s.id)} aria-current={on ? 'page' : undefined} aria-label={s.label}
              className={`flex min-h-[56px] flex-col items-center justify-center gap-1 text-[10.5px] font-medium transition-colors ${on ? 'text-ink' : 'text-faint'}`}>
              <span className={`flex h-7 w-11 items-center justify-center rounded-full transition-colors ${on ? 'bg-soft' : ''}`}><Icon size={18} /></span>
              {s.short}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
