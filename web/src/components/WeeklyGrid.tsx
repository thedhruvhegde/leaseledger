import { useCallback, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as RKeyboardEvent, PointerEvent as RPointerEvent } from 'react';
import type { Building, Campus, Day, Event } from '../types';
import { ALL_DAYS } from '../types';
import { DAY_SHORT, clock, snap } from '../lib/format';

export const GRID_START = 7 * 60; // 7:00
export const GRID_END = 26 * 60; // 2:00 next day
export const SNAP = 15;

export const CAMPUS_COLOR: Record<Campus | 'none', string> = {
  north: '37 99 235',
  central: '124 58 237',
  medical: '225 29 72',
  south: '5 150 105',
  downtown: '217 119 6',
  other: '71 85 105',
  none: '100 116 139',
};

export interface GridProps {
  events: Event[];
  buildings: Map<string, Building>;
  onChange?: (index: number, patch: Partial<Event>) => void;
  onAdd?: (e: Event) => void;
  onSelect?: (index: number | null) => void;
  onDelete?: (index: number) => void;
  selected?: number | null;
  needsConfirm?: Record<number, string[]>;
  pxPerMin?: number;
  readOnly?: boolean;
  label?: string;
}

type DragKind = 'move' | 'resize';
interface Drag {
  index: number;
  day: Day;
  kind: DragKind;
  startY: number;
  startX: number;
  orig: Event;
  moved: boolean;
}

/** Pure helper (unit-tested): apply a drag delta to an event, with snapping and bounds. */
export function applyDrag(e: Event, kind: DragKind, deltaMin: number, fromDay: Day, toDay: Day): Partial<Event> {
  const d = snap(deltaMin, SNAP);
  if (kind === 'resize') {
    const end = Math.min(GRID_END, Math.max(e.start_min + SNAP, snap(e.end_min + d, SNAP)));
    return { end_min: end };
  }
  const dur = e.end_min - e.start_min;
  const start = Math.min(GRID_END - dur, Math.max(GRID_START - 60, snap(e.start_min + d, SNAP)));
  const patch: Partial<Event> = { start_min: start, end_min: start + dur };
  if (toDay !== fromDay && !e.days.includes(toDay)) {
    const order = ALL_DAYS;
    patch.days = order.filter((x) => (x === toDay ? true : x === fromDay ? false : e.days.includes(x)));
  }
  return patch;
}

/**
 * Pure helper (unit-tested): calendar-style side-by-side layout for one day column. Events that overlap in time
 * (transitively, as a cluster) share the column width; each gets the first free lane. Returns index -> lane info.
 */
export function layoutDay(items: { i: number; start: number; end: number }[]): Map<number, { col: number; cols: number }> {
  const out = new Map<number, { col: number; cols: number }>();
  const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end || a.i - b.i);
  let cluster: { i: number; col: number }[] = [];
  let lanes: number[] = []; // end time of the last event in each lane
  let clusterEnd = -Infinity;
  const flush = () => {
    for (const c of cluster) out.set(c.i, { col: c.col, cols: lanes.length });
    cluster = [];
    lanes = [];
  };
  for (const it of sorted) {
    if (it.start >= clusterEnd) { flush(); clusterEnd = -Infinity; }
    let col = lanes.findIndex((end) => end <= it.start);
    if (col < 0) { col = lanes.length; lanes.push(it.end); } else lanes[col] = it.end;
    cluster.push({ i: it.i, col });
    clusterEnd = Math.max(clusterEnd, it.end);
  }
  flush();
  return out;
}

export function WeeklyGrid({ events, buildings, onChange, onAdd, onSelect, onDelete, selected = null, needsConfirm = {}, pxPerMin = 0.7, readOnly = false, label = 'Weekly schedule' }: GridProps) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [preview, setPreview] = useState<Partial<Event> | null>(null);
  const height = (GRID_END - GRID_START) * pxPerMin;
  const hours = useMemo(() => Array.from({ length: (GRID_END - GRID_START) / 60 + 1 }, (_, i) => GRID_START + i * 60), []);

  const colW = () => (bodyRef.current ? bodyRef.current.getBoundingClientRect().width / 7 : 100);

  const onPointerDown = (ev: RPointerEvent, index: number, day: Day, kind: DragKind) => {
    if (readOnly || ev.button !== 0) return;
    ev.stopPropagation();
    (ev.currentTarget as HTMLElement).setPointerCapture?.(ev.pointerId);
    setDrag({ index, day, kind, startY: ev.clientY, startX: ev.clientX, orig: events[index], moved: false });
  };

  const onPointerMove = (ev: RPointerEvent) => {
    if (!drag) return;
    const dy = (ev.clientY - drag.startY) / pxPerMin;
    const dx = ev.clientX - drag.startX;
    if (!drag.moved && Math.abs(ev.clientY - drag.startY) < 4 && Math.abs(dx) < 6) return;
    const di = Math.round(dx / colW());
    const fromIdx = ALL_DAYS.indexOf(drag.day);
    const toDay = drag.kind === 'move' ? ALL_DAYS[Math.min(6, Math.max(0, fromIdx + di))] : drag.day;
    setDrag({ ...drag, moved: true });
    setPreview(applyDrag(drag.orig, drag.kind, dy, drag.day, toDay));
  };

  const onPointerUp = () => {
    if (!drag) return;
    if (drag.moved && preview) onChange?.(drag.index, preview);
    else onSelect?.(drag.index);
    setDrag(null);
    setPreview(null);
  };

  const onEmptyClick = useCallback(
    (ev: React.MouseEvent<HTMLDivElement>, day: Day) => {
      if (readOnly || !onAdd) return;
      const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect();
      const m = snap(GRID_START + (ev.clientY - rect.top) / pxPerMin - 30, 30);
      const start = Math.max(GRID_START, Math.min(GRID_END - 60, m));
      onAdd({ label: 'New event', building_id: null, point: null, days: [day], start_min: start, end_min: start + 60, fixed: true, source_quote: null, provenance: 'user' });
    },
    [onAdd, pxPerMin, readOnly],
  );

  const onKey = (ev: RKeyboardEvent, index: number) => {
    const e = events[index];
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect?.(index); return; }
    if (readOnly) return;
    if (ev.key === 'Delete' || ev.key === 'Backspace') { ev.preventDefault(); onDelete?.(index); return; }
    const step = ev.key === 'ArrowUp' ? -SNAP : ev.key === 'ArrowDown' ? SNAP : 0;
    if (step) {
      ev.preventDefault();
      onChange?.(index, ev.shiftKey ? applyDrag(e, 'resize', step, e.days[0], e.days[0]) : applyDrag(e, 'move', step, e.days[0], e.days[0]));
    }
  };

  return (
    <div className="select-none" aria-label={label} role="group">
      {/* header */}
      <div className="grid grid-cols-[3rem_repeat(7,minmax(0,1fr))] border-b border-line pb-1.5">
        <div />
        {ALL_DAYS.map((d) => (
          <div key={d} className="text-center text-xs font-semibold uppercase tracking-wider text-muted">{DAY_SHORT[d]}</div>
        ))}
      </div>
      <div className="grid grid-cols-[3rem_1fr]" onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
        {/* hour labels */}
        <div className="relative" style={{ height }}>
          {hours.map((h) => (
            <div key={h} className="num absolute right-2 -translate-y-1/2 text-2xs text-faint" style={{ top: (h - GRID_START) * pxPerMin }}>
              {h === GRID_START ? '' : clock(h, { compact: true })}
            </div>
          ))}
        </div>
        <div ref={bodyRef} className="relative grid grid-cols-7" style={{ height }}>
          {/* hour lines */}
          {hours.map((h) => (
            <div key={h} aria-hidden className={`pointer-events-none absolute inset-x-0 border-t ${h === 22 * 60 ? 'border-night/40 border-dashed' : h === 24 * 60 ? 'border-line' : 'border-line/60'}`} style={{ top: (h - GRID_START) * pxPerMin }} />
          ))}
          <div aria-hidden className="pointer-events-none absolute inset-x-0 bg-night/[0.05]" style={{ top: (22 * 60 - GRID_START) * pxPerMin, bottom: 0 }} />
          <div aria-hidden className="pointer-events-none absolute right-1 text-2xs font-medium text-night/80" style={{ top: (22 * 60 - GRID_START) * pxPerMin + 2 }}>after 10 PM</div>
          {ALL_DAYS.map((day) => (
            <div key={day} className={`relative border-l border-line/60 ${readOnly ? '' : 'cursor-copy'}`} onClick={(ev) => { if (ev.target === ev.currentTarget) onEmptyClick(ev, day); }}
              data-testid={`grid-col-${day}`}>
              {(() => {
                const shown = events.map((e0, i) => (drag?.index === i && preview ? { ...e0, ...preview } : e0));
                const lanes = layoutDay(shown.flatMap((e, i) => (e.days.includes(day) ? [{ i, start: e.start_min, end: Math.max(e.end_min, e.start_min + 14 / pxPerMin) }] : [])));
                return events.map((_e0, i) => {
                const isDrag = drag?.index === i && preview;
                const e = shown[i];
                if (!e.days.includes(day)) return null;
                const lane = lanes.get(i) ?? { col: 0, cols: 1 };
                const narrow = lane.cols > 1;
                const top = (Math.max(GRID_START, e.start_min) - GRID_START) * pxPerMin;
                const h = Math.max(14, (Math.min(GRID_END, e.end_min) - Math.max(GRID_START, e.start_min)) * pxPerMin);
                const b = e.building_id ? buildings.get(e.building_id) : undefined;
                const color = CAMPUS_COLOR[b?.campus ?? 'none'];
                const nc = needsConfirm[i];
                const isSel = selected === i;
                const tip = [e.label, b?.name ?? (e.point ? 'Custom place' : 'No place yet'), `${clock(e.start_min)}–${clock(e.end_min)}`, e.source_quote ? `From your text: “${e.source_quote}”` : '', nc?.length ? `Needs confirmation: ${nc.join(', ')}` : ''].filter(Boolean).join('\n');
                return (
                  <div
                    key={i}
                    role="button"
                    tabIndex={0}
                    aria-label={`${e.label}, ${DAY_SHORT[day]} ${clock(e.start_min)} to ${clock(e.end_min)}${b ? ` at ${b.name}` : ''}${nc?.length ? ', needs confirmation' : ''}`}
                    aria-pressed={isSel}
                    title={tip}
                    data-testid="grid-event"
                    onPointerDown={(ev) => onPointerDown(ev, i, day, 'move')}
                    onKeyDown={(ev) => onKey(ev, i)}
                    className={`group absolute overflow-hidden rounded-md border-l-[3px] ${narrow ? 'px-1' : 'px-1.5'} py-0.5 text-left text-2xs leading-tight shadow-sm transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${readOnly ? '' : 'cursor-grab active:cursor-grabbing'} ${isSel ? 'ring-2 ring-accent' : ''} ${isDrag ? 'z-20 opacity-90 shadow-pop' : 'z-10'} ${!e.fixed ? 'border-dashed' : ''}`}
                    data-lane={`${lane.col + 1}/${lane.cols}`}
                    style={{ top, height: h, left: `calc(${(lane.col / lane.cols) * 100}% + 2px)`, width: `calc(${100 / lane.cols}% - 4px)`, background: `rgb(${color} / 0.16)`, borderLeftColor: `rgb(${color})`, color: 'rgb(var(--ink))' }}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <span className={narrow ? 'min-w-0 font-semibold [overflow-wrap:anywhere]' : 'truncate font-semibold'}>{e.label}</span>
                      {nc?.length ? <span className="mt-px inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-warn text-[9px] font-bold text-white" aria-hidden>?</span> : e.source_quote ? <span className="mt-px shrink-0 text-[9px] font-bold text-p-estimated" aria-hidden>AI</span> : null}
                    </div>
                    {h > 26 && !narrow && <div className="num truncate text-faint">{clock(e.start_min, { compact: true })}–{clock(e.end_min, { compact: true })}{b ? ` · ${b.aliases[0] ?? b.name}` : ''}</div>}
                    {!readOnly && (
                      <div
                        className="absolute inset-x-0 bottom-0 h-1.5 cursor-ns-resize opacity-0 group-hover:opacity-100"
                        style={{ background: `rgb(${color} / 0.5)` }}
                        onPointerDown={(ev) => onPointerDown(ev, i, day, 'resize')}
                        aria-hidden
                      />
                    )}
                  </div>
                );
                });
              })()}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CampusLegend() {
  const items: [Campus, string][] = [['north', 'North'], ['central', 'Central'], ['medical', 'Medical'], ['downtown', 'Downtown'], ['south', 'South / athletics']];
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
      {items.map(([c, l]) => (
        <span key={c} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: `rgb(${CAMPUS_COLOR[c]})` }} />{l}</span>
      ))}
      <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm border border-dashed border-faint" />Template (uncertain)</span>
      <span className="inline-flex items-center gap-1.5"><span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-warn text-[9px] font-bold text-white">?</span>Needs confirmation</span>
    </div>
  );
}
