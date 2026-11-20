import { useMemo, useState } from 'react';
import { hasWeek, useBuildingMap, useEvaluation, useListingMap } from '../api/hooks';
import { useApp } from '../store/app';
import { NoWeek } from '../components/NoWeek';
import { ErrorState, SectionTitle, Skeleton } from '../components/ui/Misc';
import { haversineKm, mostFrequentBuilding } from '../lib/geo';
import { usd } from '../lib/format';
import { ListingName, splitName } from '../components/ui/Badge';

const ROW = 46;

export function BaselineScreen() {
  const { data, isLoading, error, refetch } = useEvaluation();
  const lmap = useListingMap();
  const bmap = useBuildingMap();
  const events = useApp((s) => s.committed.events);
  const profile = useApp((s) => s.committed);
  const setSelected = useApp((s) => s.setSelected);
  const setScreen = useApp((s) => s.setScreen);
  const [hover, setHover] = useState<string | null>(null);
  const freq = mostFrequentBuilding(events);
  const fb = freq ? bmap.get(freq) : undefined;

  const { left, right } = useMemo(() => {
    if (!data) return { left: [] as string[], right: [] as string[] };
    const right = data.evaluations.map((e) => e.listing_id);
    const left = data.baseline_ranking.length ? data.baseline_ranking.filter((id) => right.includes(id)) : right;
    return { left, right };
  }, [data]);

  if (!hasWeek(profile)) return <NoWeek />;
  if (error && !data) return <ErrorState error={error} retry={() => void refetch()} />;
  if (isLoading || !data) return <Skeleton className="h-[36rem]" />;

  const evalOf = (id: string) => data.evaluations.find((e) => e.listing_id === id)!;
  const moved = left.filter((id, i) => right.indexOf(id) !== i).length;
  const portalTop = left[0];
  const portalTopRank = evalOf(portalTop)?.rank;
  const h = Math.max(left.length, right.length) * ROW;
  const rentOf = (id: string) => {
    const l = lmap.get(id);
    if (!l) return 0;
    return l.rent_basis === 'bed' ? l.rent : l.rent / Math.max(1, profile.household_size);
  };

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="Proof of value" title="Portal ranking vs. your-week ranking">
        Left: what a typical rental portal shows — sorted by rent plus straight-line distance to the one building you visit most{fb ? <> (<b className="text-ink">{fb.name}</b>)</> : ''}. Right: the same homes ranked by what your whole week costs.
      </SectionTitle>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="card p-4"><div className="label">Homes that change position</div><div className="num mt-1 text-3xl font-semibold">{moved} <span className="text-base text-faint">of {left.length}</span></div></div>
        <div className="card p-4"><div className="label">Portal’s #1 for you</div><div className="mt-1 text-base font-semibold"><ListingName name={lmap.get(portalTop)?.name} subClassName="text-sm font-normal" /></div><div className="text-sm text-muted">{portalTopRank ? <>ranks <b className="text-ink">#{portalTopRank}</b> for your week</> : <>doesn’t fit your constraints</>}</div></div>
        <div className="card p-4"><div className="label">Your-week #1</div><div className="mt-1 text-base font-semibold"><ListingName name={lmap.get(right[0])?.name} subClassName="text-sm font-normal" /></div><div className="text-sm text-muted">portal rank <b className="text-ink">#{left.indexOf(right[0]) + 1}</b></div></div>
      </div>
      <div className="card overflow-x-auto p-4 sm:p-6">
        <div className="grid min-w-[560px] grid-cols-[minmax(0,1fr)_minmax(60px,160px)_minmax(0,1fr)] gap-0">
          <div className="label mb-2">Portal-style (rent + distance)</div>
          <div />
          <div className="label mb-2 text-right">Your week (all-in)</div>
          <ol style={{ height: h }}>
            {left.map((id, i) => (
              <li key={id} style={{ height: ROW }} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}
                className={`flex items-center gap-2 border-b border-line/50 pr-2 text-sm transition-opacity ${hover && hover !== id ? 'opacity-40' : ''}`}>
                <span className="num w-6 font-bold text-muted">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate" title={lmap.get(id)?.name}>{splitName(lmap.get(id)?.name ?? id).title}</span>
                <span className="num shrink-0 text-xs text-muted">{usd(rentOf(id))}{fb && lmap.get(id) ? ` · ${haversineKm(lmap.get(id)!, fb).toFixed(1)} km` : ''}</span>
              </li>
            ))}
          </ol>
          <svg width="100%" height={h} viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" aria-hidden>
            {left.map((id, i) => {
              const j = right.indexOf(id);
              if (j < 0) return null;
              const y1 = i * ROW + ROW / 2;
              const y2 = j * ROW + ROW / 2;
              const same = i === j;
              const color = same ? 'rgb(var(--faint))' : j < i ? 'rgb(var(--good))' : 'rgb(var(--bad))';
              return (
                <path key={id} d={`M0 ${y1} C 50 ${y1}, 50 ${y2}, 100 ${y2}`} fill="none" stroke={color} strokeWidth={same ? 1.5 : 3}
                  vectorEffect="non-scaling-stroke" opacity={hover && hover !== id ? 0.12 : 0.9} strokeLinecap="round" />
              );
            })}
          </svg>
          <ol style={{ height: h }}>
            {right.map((id) => {
              const e = evalOf(id);
              return (
                <li key={id} style={{ height: ROW }} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}
                  className={`flex cursor-pointer items-center gap-2 border-b border-line/50 pl-2 text-sm transition-opacity ${hover && hover !== id ? 'opacity-40' : ''} ${e.feasible ? '' : 'text-faint'}`}
                  onClick={() => { setSelected(id); setScreen('results'); }}>
                  <span className="num w-6 font-bold text-accent">{e.rank ?? '✕'}</span>
                  <span className="min-w-0 flex-1 truncate" title={lmap.get(id)?.name}>{splitName(lmap.get(id)?.name ?? id).title}</span>
                  <span className="num shrink-0 text-xs text-muted">{usd(e.all_in_total)} · {((e.commute?.weekly_min ?? 0) / 60).toFixed(1)} h/wk</span>
                </li>
              );
            })}
          </ol>
        </div>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-good" />Moves up when your week counts</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-bad" />Moves down</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-faint" />Same place</span>
          <span>✕ = fails a hard constraint (portals usually don’t check)</span>
        </div>
        <p className="mt-3 text-xs text-faint">Why they differ: the portal sees one destination and a straight line. Your week has multi-stop days, waits that depend on the hour, late nights, winter walking, fees and utilities.</p>
      </div>
    </div>
  );
}
