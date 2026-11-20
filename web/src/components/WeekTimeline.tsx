import type { CommuteSummary, Day, Event, Trip } from '../types';
import { ALL_DAYS } from '../types';
import { DAY_SHORT, clock, duration } from '../lib/format';
import { LEG_COLOR, LEG_LABEL } from '../lib/legs';
import { fitLabel, labelCandidates } from '../lib/label';
import { useEffect, useRef, useState } from 'react';
import { useBuildingMap } from '../api/hooks';

const T0 = 6 * 60;
const T1 = 26 * 60;

/** Per-day horizontal strip: grey event blocks + colored trip legs (walk / wait / bus / bike) with route labels. */
export function WeekTimeline({ commute, events, days = ALL_DAYS, legend = true }: { commute: CommuteSummary; events: Event[]; days?: readonly Day[]; legend?: boolean }) {
  const pct = (m: number) => `${((Math.max(T0, Math.min(T1, m)) - T0) / (T1 - T0)) * 100}%`;
  const w = (a: number, b: number) => `${(Math.max(0, Math.min(T1, b) - Math.max(T0, a)) / (T1 - T0)) * 100}%`;
  const ticks = [6, 9, 12, 15, 18, 21, 24].map((h) => h * 60);
  const bmap = useBuildingMap();
  // measure the strip so each block shows the longest label that fits (full → "EECS 281 · BBB" → "EECS 281" → "281")
  const stripRef = useRef<HTMLDivElement>(null);
  const [stripPx, setStripPx] = useState(480);
  useEffect(() => {
    const el = stripRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setStripPx(el.getBoundingClientRect().width || 480));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div>
     <div className="-mx-1 overflow-x-auto px-1"><div className="min-w-[640px]">
      <div className="grid grid-cols-[2.5rem_1fr_4.5rem] items-end gap-2 pb-1">
        <div />
        <div ref={stripRef} className="relative h-4">
          {ticks.map((t) => (
            <span key={t} className="num absolute -translate-x-1/2 text-2xs text-faint" style={{ left: pct(t) }}>{clock(t, { compact: true })}</span>
          ))}
        </div>
        <div className="text-right text-2xs font-medium text-faint">Door to door</div>
      </div>
      <div className="space-y-1.5">
        {days.map((d) => {
          const tour = commute.tours.find((t) => t.day === d);
          const evs = events.filter((e) => e.days.includes(d));
          return (
            <div key={d} className="grid grid-cols-[2.5rem_1fr_4.5rem] items-center gap-2">
              <div className="text-xs font-semibold text-muted">{DAY_SHORT[d]}</div>
              <div className="relative h-7 rounded-md bg-raised">
                {ticks.map((t) => <div key={t} className="absolute inset-y-0 w-px bg-line/70" style={{ left: pct(t) }} aria-hidden />)}
                <div className="absolute inset-y-0 bg-night/[0.07]" style={{ left: pct(22 * 60), right: 0 }} aria-hidden />
                {evs.map((e, i) => {
                  const b = e.building_id ? bmap.get(e.building_id) : undefined;
                  const full = `${e.label}${b ? ` · ${b.name}` : ''} · ${clock(e.start_min)}–${clock(e.end_min)}`;
                  const px = ((Math.min(T1, e.end_min) - Math.max(T0, e.start_min)) / (T1 - T0)) * stripPx;
                  const text = fitLabel(labelCandidates(e, b), px, 5.6, 7);
                  return (
                    <div key={i} className="absolute inset-y-1 overflow-hidden whitespace-nowrap rounded-sm border border-line bg-surface/90 px-[3px] font-mono text-[9.5px] leading-5 text-muted" style={{ left: pct(e.start_min), width: w(e.start_min, e.end_min) }} title={full} aria-label={full}>
                      {text}
                    </div>
                  );
                })}
                {tour?.trips.map((t, i) => <TripStrip key={i} t={t} pct={pct} w={w} />)}
              </div>
              <div className="num text-right text-xs font-semibold text-ink">{tour ? duration(tour.total_min) : <span className="text-faint">—</span>}</div>
            </div>
          );
        })}
      </div>
     </div></div>
      {legend && <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
        {(['walk', 'wait', 'bus', 'bike'] as const).map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm" style={{ background: LEG_COLOR[k] }} />{LEG_LABEL[k]}</span>
        ))}
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm border border-line bg-surface" />Your event</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-night/20" />After 10 PM</span>
      </div>}
    </div>
  );
}

function TripStrip({ t, pct, w }: { t: Trip; pct: (m: number) => string; w: (a: number, b: number) => string }) {
  const bus = t.legs.find((l) => l.kind === 'bus');
  const title = `${clock(t.depart_min)} → ${clock(t.arrive_min)} · ${Math.round(t.total_min)} min${bus ? ` · ${bus.agency === 'AAATA' ? 'TheRide' : 'U-M'} ${bus.route}` : ''}${t.note ? `\n${t.note}` : ''}`;
  return (
    <div className="absolute inset-y-0" style={{ left: pct(t.depart_min), width: w(t.depart_min, t.arrive_min), minWidth: 3 }} title={title}>
      {t.legs.map((l, i) => (
        <div key={i} className="absolute inset-y-[5px] flex items-center justify-center overflow-hidden rounded-[3px] text-[9px] font-bold leading-none text-white"
          style={{
            left: `${((l.start_min - t.depart_min) / Math.max(1, t.arrive_min - t.depart_min)) * 100}%`,
            width: `${((l.end_min - l.start_min) / Math.max(1, t.arrive_min - t.depart_min)) * 100}%`,
            background: LEG_COLOR[l.kind],
          }}>
          {l.kind === 'bus' && l.route ? l.route : ''}
        </div>
      ))}
    </div>
  );
}

/** Text list of trips for one day — screen-reader friendly and precise. */
export function TripList({ commute }: { commute: CommuteSummary }) {
  return (
    <div className="space-y-3">
      {commute.tours.map((d) => (
        <div key={d.day}>
          <div className="label mb-1">{DAY_SHORT[d.day]} · {duration(d.total_min)}{d.home_returns ? ` · ${d.home_returns} trip${d.home_returns > 1 ? 's' : ''} home mid-day` : ''}</div>
          <ul className="space-y-1">
            {d.trips.map((t, i) => (
              <li key={i} className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="num w-28 shrink-0 text-muted">{clock(t.depart_min)}–{clock(t.arrive_min)}</span>
                {t.legs.map((l, j) => (
                  <span key={j} className="num inline-flex items-center gap-1 rounded px-1.5 py-px font-medium text-white" style={{ background: LEG_COLOR[l.kind] }}>
                    {l.kind === 'bus' ? `${l.route ?? 'Bus'}` : LEG_LABEL[l.kind]} {Math.round(l.end_min - l.start_min)}′
                  </span>
                ))}
                <span className="text-faint">→ {t.legs[t.legs.length - 1]?.to_name ?? ''}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
