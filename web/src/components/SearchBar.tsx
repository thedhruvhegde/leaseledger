import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../store/app';
import type { Mode, Profile } from '../types';
import { NumberField, Toggle } from './ui/Controls';
import { ConstraintsPanel } from './ConstraintsPanel';
import { IconBike, IconBus, IconCalendar, IconChevron, IconWalk, IconX } from './ui/Icons';
import { DAY_SHORT, usd } from '../lib/format';
import { useBuildingMap } from '../api/hooks';

export type SortKey = 'best' | 'allin' | 'cash' | 'travel' | 'rent';
export const SORTS: { value: SortKey; label: string }[] = [
  { value: 'best', label: 'Best for your week' },
  { value: 'allin', label: 'All-in: low to high' },
  { value: 'cash', label: 'Cash: low to high' },
  { value: 'travel', label: 'Least travel' },
  { value: 'rent', label: 'Rent: low to high' },
];

/** Pill that opens a small popover, the portal "filter dropdown" convention. Esc / outside click closes. */
export function FilterPill({ label, value, active, children, wide = false, align = 'left' }: {
  label: string; value?: ReactNode; active?: boolean; children: ReactNode; wide?: boolean; align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); setOpen(false); btn.current?.focus(); } };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button ref={btn} type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}
        className={`filter-pill ${active ? 'is-set' : ''} ${open ? 'is-open' : ''}`}>
        <span className={value ? 'text-faint' : ''}>{label}</span>
        {value && <span className="num font-medium text-ink">{value}</span>}
        <IconChevron size={13} className={`text-faint transition-transform ${open ? '-rotate-90' : 'rotate-90'}`} />
      </button>
      {open && (
        <div id={id} role="dialog" aria-label={label}
          className={`absolute top-[calc(100%+6px)] z-50 rounded-xl border border-line-strong bg-surface p-4 animate-fade-in ${wide ? 'w-[26rem] max-h-[70vh] overflow-y-auto' : 'w-72'} ${align === 'right' ? 'right-0' : 'left-0'}`}>
          {children}
          <div className="mt-3 flex justify-end border-t border-line pt-3">
            <button className="btn-primary h-8 px-4 text-[13px]" onClick={() => { setOpen(false); btn.current?.focus(); }}>Done</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** "Your week" summary: the search field of this product. */
export function WeekSummary({ onClick, compact = false }: { onClick: () => void; compact?: boolean }) {
  const profile = useApp((s) => s.profile);
  const parsing = useApp((s) => s.parsing);
  const needs = Object.keys(useApp((s) => s.needsConfirm)).length;
  const bmap = useBuildingMap();
  const days = (['M', 'T', 'W', 'R', 'F', 'S', 'U'] as const).filter((d) => profile.events.some((e) => e.days.includes(d)));
  const places = new Set(profile.events.map((e) => (e.building_id ? bmap.get(e.building_id)?.name ?? e.building_id : e.label)));
  const span = days.length === 0 ? '' : days.length === 1 ? DAY_SHORT[days[0]] : `${DAY_SHORT[days[0]]}–${DAY_SHORT[days[days.length - 1]]}`;
  const text = parsing ? 'Reading your week…'
    : profile.events.length === 0 ? (profile.template_id ? 'Template week' : 'Describe your week')
    : `${profile.events.length} block${profile.events.length === 1 ? '' : 's'} · ${span} · ${places.size} place${places.size === 1 ? '' : 's'}`;
  return (
    <button type="button" onClick={onClick} className={`week-summary ${compact ? 'min-w-0 flex-1' : 'w-[22rem]'}`} title="Edit your week">
      <IconCalendar size={16} className="shrink-0 text-ink" />
      <span className="min-w-0 flex-1 truncate text-left">
        {!compact && <span className="mr-2 font-semibold text-ink">Your week</span>}
        <span className={profile.events.length || parsing ? 'text-charcoal' : 'text-faint'}>{text}</span>
      </span>
      {needs > 0 && <span className="rounded-full bg-soft px-1.5 text-[11px] font-medium text-ink" title="Blocks to confirm">{needs} to check</span>}
      <span className="shrink-0 text-[12px] font-medium text-ink underline decoration-line-strong underline-offset-2">Edit</span>
    </button>
  );
}

function useProfilePatch() {
  const setProfile = useApp((s) => s.setProfile);
  return (patch: Partial<Profile>) => setProfile((p) => ({ ...p, ...patch }));
}

export function BudgetFilter() {
  const p = useApp((s) => s.profile);
  const up = useProfilePatch();
  return (
    <FilterPill label="Budget" value={`≤ ${usd(p.rent_cap)}`} active>
      <div className="mb-2 text-[13px] font-semibold">Rent per person</div>
      <NumberField label="Rent cap" prefix="$" suffix="/mo" value={p.rent_cap} step={25} min={0} max={10000} width="w-36" onChange={(v) => up({ rent_cap: v })} />
      <NumberField label="All-in cap (optional)" prefix="$" suffix="/mo" value={p.all_in_cap ?? 0} step={25} min={0} max={10000} width="w-36" onChange={(v) => up({ all_in_cap: v > 0 ? v : null })} />
      <p className="mt-2 text-[12px] text-faint">The rent cap is a hard limit. The all-in cap also counts time and late-night costs; 0 means none.</p>
    </FilterPill>
  );
}

export function HouseholdFilter() {
  const p = useApp((s) => s.profile);
  const up = useProfilePatch();
  const set = p.household_size > 1 || p.bedrooms_min > 0 || p.needs_parking || p.pet;
  const v = `${p.household_size} ${p.household_size === 1 ? 'person' : 'people'}${p.bedrooms_min ? ` · ${p.bedrooms_min}+ bd` : ''}${p.needs_parking ? ' · parking' : ''}${p.pet ? ' · pet' : ''}`;
  return (
    <FilterPill label="Household" value={v} active={set}>
      <NumberField label="People sharing" value={p.household_size} min={1} max={10} onChange={(n) => up({ household_size: Math.max(1, Math.min(10, Math.round(n))) })} />
      <NumberField label="Bedrooms, at least" value={p.bedrooms_min} min={0} max={6} onChange={(n) => up({ bedrooms_min: Math.max(0, Math.min(6, Math.round(n))) })} />
      <Toggle label="I need parking" checked={p.needs_parking} onChange={(b) => up({ needs_parking: b })} />
      <Toggle label="I have a pet" checked={p.pet} onChange={(b) => up({ pet: b })} />
    </FilterPill>
  );
}

const MODE_META: Record<Mode, { label: string; Icon: (p: { size?: number }) => JSX.Element }> = {
  walk: { label: 'Walk', Icon: IconWalk }, bus: { label: 'Bus', Icon: IconBus }, bike: { label: 'Bike', Icon: IconBike },
};

export function ModesFilter() {
  const p = useApp((s) => s.profile);
  const up = useProfilePatch();
  const toggle = (m: Mode) => {
    const has = p.modes.includes(m);
    const modes = (['walk', 'bus', 'bike'] as Mode[]).filter((x) => (x === m ? !has : p.modes.includes(x)));
    up({ modes: modes.length ? modes : ['walk'] });
  };
  return (
    <FilterPill label="Getting around" value={p.modes.map((m) => MODE_META[m].label).join(' + ')} active>
      <div className="mb-2 text-[13px] font-semibold">Modes you’ll use</div>
      <div className="flex gap-1.5">
        {(['walk', 'bus', 'bike'] as Mode[]).map((m) => {
          const { label, Icon } = MODE_META[m];
          const on = p.modes.includes(m);
          return (
            <button key={m} type="button" aria-pressed={on} onClick={() => toggle(m)}
              className={`inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full border text-[13px] font-medium transition-colors ${on ? 'border-ink bg-ink text-bg' : 'border-line-strong text-charcoal hover:border-ink'}`}>
              <Icon size={15} /> {label}
            </button>
          );
        })}
      </div>
      <div className="mt-3">
        <NumberField label="Longest single trip" suffix="min" value={p.max_single_trip_min ?? 0} min={0} max={120} step={5} onChange={(n) => up({ max_single_trip_min: n > 0 ? n : null })} />
        <p className="text-[12px] text-faint">Buses: U-M Blue Buses and TheRide timetables. 0 = no limit.</p>
      </div>
    </FilterPill>
  );
}

export function AllFilters() {
  return (
    <FilterPill label="All filters" wide align="right">
      <ConstraintsPanel />
    </FilterPill>
  );
}

export function SortSelect({ value, onChange }: { value: SortKey; onChange: (v: SortKey) => void }) {
  return (
    <label className="inline-flex items-center gap-1.5 text-[13px] text-faint">
      Sort
      <select value={value} onChange={(e) => onChange(e.target.value as SortKey)}
        className="h-8 rounded-full border border-line bg-surface pl-3 pr-7 text-[13px] font-medium text-ink focus:border-ink focus:outline-none">
        {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
    </label>
  );
}

/** Phone: one "Filters" pill opening a full-screen sheet with every control. */
export function FiltersSheetButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="filter-pill shrink-0" onClick={() => setOpen(true)}>Filters</button>
      {open && (
        <div className="fixed inset-0 z-[60] flex flex-col bg-bg" role="dialog" aria-label="Filters">
          <div className="flex h-14 items-center justify-between border-b border-line px-4">
            <div className="text-base font-semibold">Filters</div>
            <button className="btn-ghost w-10 px-0" onClick={() => setOpen(false)} aria-label="Close filters"><IconX /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-4"><ConstraintsPanel /></div>
          <div className="border-t border-line p-3"><button className="btn-primary h-11 w-full" onClick={() => setOpen(false)}>Show homes</button></div>
        </div>
      )}
    </>
  );
}
