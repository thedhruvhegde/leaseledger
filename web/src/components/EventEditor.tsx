import { useId, useMemo, useState } from 'react';
import type { Building, Day, Event } from '../types';
import { ALL_DAYS } from '../types';
import { DAY_SHORT, hhmm, parseHhmm } from '../lib/format';
import { ProvenanceBadge } from './ui/Badge';
import { IconAlert, IconCheck, IconTrash, IconX } from './ui/Icons';
import { CAMPUS_COLOR } from './WeeklyGrid';

export function matchBuildings(buildings: Building[], q: string): Building[] {
  const s = q.trim().toLowerCase();
  if (!s) return buildings;
  const score = (b: Building) => {
    const hay = [b.name, b.id, ...b.aliases].map((x) => x.toLowerCase());
    if (hay.some((h) => h === s)) return 0;
    if (hay.some((h) => h.startsWith(s))) return 1;
    if (hay.some((h) => h.includes(s))) return 2;
    return 9;
  };
  return buildings.map((b) => ({ b, s: score(b) })).filter((x) => x.s < 9).sort((a, b) => a.s - b.s || a.b.name.localeCompare(b.b.name)).map((x) => x.b);
}

export function BuildingSelect({ buildings, value, onChange }: { buildings: Building[]; value: string | null | undefined; onChange: (id: string) => void }) {
  const id = useId();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const cur = buildings.find((b) => b.id === value);
  const list = useMemo(() => matchBuildings(buildings, q).slice(0, 8), [buildings, q]);
  const pick = (b: Building) => { onChange(b.id); setQ(''); setOpen(false); };
  return (
    <div className="relative">
      <label htmlFor={id} className="label">Place</label>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        className="input mt-1"
        placeholder={cur ? cur.name : 'Search buildings — try “BBB”, “UgLi”, “Ross”'}
        value={q}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setHi(0); }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(list.length - 1, h + 1)); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(0, h - 1)); }
          else if (e.key === 'Enter' && list[hi]) { e.preventDefault(); pick(list[hi]); }
          else if (e.key === 'Escape') setOpen(false);
        }}
      />
      {cur && !q && (
        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted">
          <span className="h-2 w-2 rounded-sm" style={{ background: `rgb(${CAMPUS_COLOR[cur.campus]})` }} />
          {cur.name} · <span className="capitalize">{cur.campus}</span>
        </div>
      )}
      {open && list.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="absolute z-40 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-line bg-surface p-1 shadow-pop">
          {list.map((b, i) => (
            <li key={b.id} role="option" aria-selected={i === hi}
              onMouseDown={(e) => { e.preventDefault(); pick(b); }}
              onMouseEnter={() => setHi(i)}
              className={`flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm ${i === hi ? 'bg-accent-soft text-ink' : 'text-ink'}`}>
              <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: `rgb(${CAMPUS_COLOR[b.campus]})` }} />
              <span className="truncate">{b.name}</span>
              {b.aliases.length > 0 && <span className="ml-auto truncate text-xs text-faint">{b.aliases.slice(0, 2).join(', ')}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function EventEditor({ event, buildings, onChange, onDelete, onClose, confirmReasons, onConfirm }: {
  event: Event; buildings: Building[]; onChange: (patch: Partial<Event>) => void; onDelete: () => void; onClose: () => void;
  confirmReasons?: string[]; onConfirm?: () => void;
}) {
  const lid = useId();
  const toggleDay = (d: Day) => {
    const has = event.days.includes(d);
    const days = ALL_DAYS.filter((x) => (x === d ? !has : event.days.includes(x)));
    if (days.length) onChange({ days });
  };
  return (
    <div className="card animate-fade-in p-4" role="dialog" aria-label={`Edit ${event.label}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Edit block</span>
          <ProvenanceBadge p={event.provenance} />
          {!event.fixed && <span className="chip text-2xs">template</span>}
        </div>
        <button className="btn-ghost px-1.5" onClick={onClose} aria-label="Close editor"><IconX /></button>
      </div>
      {confirmReasons && confirmReasons.length > 0 && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 p-2 text-xs">
          <IconAlert className="mt-px shrink-0 text-warn" />
          <div className="flex-1 text-muted">
            <div className="font-semibold text-ink">Please confirm</div>
            {confirmReasons.map((r) => <div key={r}>{r}</div>)}
          </div>
          {onConfirm && <button className="btn-outline px-2 py-1 text-xs" onClick={onConfirm}><IconCheck size={14} /> Looks right</button>}
        </div>
      )}
      {event.source_quote && (
        <blockquote className="mb-3 border-l-2 border-p-estimated/60 pl-2 text-xs italic text-muted">“{event.source_quote}”</blockquote>
      )}
      <div className="space-y-3">
        <div>
          <label htmlFor={lid} className="label">Label</label>
          <input id={lid} className="input mt-1" value={event.label} onChange={(e) => onChange({ label: e.target.value })} />
        </div>
        <BuildingSelect buildings={buildings} value={event.building_id} onChange={(id) => onChange({ building_id: id, point: null })} />
        <div>
          <div className="label mb-1">Days</div>
          <div className="flex flex-wrap gap-1">
            {ALL_DAYS.map((d) => (
              <button key={d} type="button" aria-pressed={event.days.includes(d)} onClick={() => toggleDay(d)}
                className={`h-8 w-11 rounded-full border text-xs font-semibold transition-colors ${event.days.includes(d) ? 'border-accent bg-accent text-accent-ink' : 'border-line text-muted hover:text-ink'}`}>
                {DAY_SHORT[d]}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <TimeInput label="Arrive by" value={event.start_min} onChange={(v) => v < event.end_min && onChange({ start_min: v })} />
          <TimeInput label="Leave at" value={event.end_min} onChange={(v) => v > event.start_min && onChange({ end_min: v })} />
        </div>
        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={!event.fixed} onChange={(e) => onChange({ fixed: !e.target.checked })} className="accent-[rgb(var(--accent))]" />
            Not sure yet (treat as uncertain)
          </label>
          <button className="btn-ghost text-bad hover:text-bad" onClick={onDelete}><IconTrash size={14} /> Remove</button>
        </div>
      </div>
    </div>
  );
}

function TimeInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input id={id} type="time" step={900} className="input num mt-1" value={hhmm(value)}
        onChange={(e) => { const v = parseHhmm(e.target.value); if (v != null) onChange(v); }} />
      {value >= 1440 && <div className="mt-0.5 text-2xs text-faint">after midnight</div>}
    </div>
  );
}
