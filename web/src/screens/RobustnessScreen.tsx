import { useState } from 'react';
import { hasWeek, useEvaluation, useListingMap, useRobustness, useTemplates } from '../api/hooks';
import { NoWeek } from '../components/NoWeek';
import { useApp } from '../store/app';
import { Callout, EmptyState, ErrorState, SectionTitle, Skeleton } from '../components/ui/Misc';
import { Segmented } from '../components/ui/Controls';
import { BreakevenLine, humanize } from '../components/Breakeven';
import { frequency, per100, usd, usdRate } from '../lib/format';
import { splitName } from '../components/ui/Badge';
import { IconChevron } from '../components/ui/Icons';
import type { Listing, RobustnessResult } from '../types';

export function IconArray({ share, label }: { share: number; label: string }) {
  const k = per100(share);
  return (
    <div role="img" aria-label={label} className="grid w-fit grid-cols-10 gap-1">
      {Array.from({ length: 100 }, (_, i) => (
        <svg key={i} width="28" height="30" viewBox="0 0 18 20" aria-hidden>
          <path d="M9 1.5L1.5 8v10.5h15V8z" fill={i < k ? 'rgb(var(--accent))' : 'rgb(var(--line))'} />
        </svg>
      ))}
    </div>
  );
}

export function RobustnessScreen() {
  const [samples, setSamples] = useState(2000);
  const { data, isLoading, error, refetch, isFetching } = useRobustness(samples, 42);
  const ev = useEvaluation();
  const lmap = useListingMap();
  const profile = useApp((s) => s.profile);
  const setProfile = useApp((s) => s.setProfile);
  const { data: templates = [] } = useTemplates();
  if (!hasWeek(profile)) return <NoWeek />;
  if (error && !data) return <ErrorState error={error} retry={() => void refetch()} />;
  const vot = ev.data?.value_of_time_used ?? 7.5;
  const vr = profile.value_of_time_range ?? [Math.round(vot * 0.5 * 2) / 2, Math.max(1, Math.round(vot * 2 * 2) / 2)];
  const tpl = templates.find((t) => t.id === profile.template_id);

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="Step 3" title="How sure are we?" right={
        <div className="flex items-center gap-2">
          {isFetching && <span className="animate-pulse2 text-xs text-faint">Sampling…</span>}
          <Segmented label="Number of plausible semesters" value={String(samples)} onChange={(v) => setSamples(Number(v))}
            options={[{ value: '500', label: '500' }, { value: '2000', label: '2,000' }, { value: '5000', label: '5,000' }]} />
        </div>
      }>
        You don’t know next semester’s schedule, your utility bills, or exactly what an hour is worth to you. We replay your choice across thousands of plausible semesters drawn from the ranges below and count how often each home comes out cheapest.
      </SectionTitle>

      <div className="card grid gap-4 p-4 md:grid-cols-3">
        <div>
          <div className="label mb-1">Value of time range (assumed)</div>
          <div className="flex items-center gap-2 text-sm">
            <input aria-label="Lowest value of time" type="number" className="input num w-20 py-1" value={vr[0]} min={0} max={vr[1]} step={0.5}
              onChange={(e) => setProfile((p) => ({ ...p, value_of_time_range: [Number(e.target.value), vr[1]] }))} />
            <span className="text-faint">to</span>
            <input aria-label="Highest value of time" type="number" className="input num w-20 py-1" value={vr[1]} min={vr[0]} max={200} step={0.5}
              onChange={(e) => setProfile((p) => ({ ...p, value_of_time_range: [vr[0], Number(e.target.value)] }))} />
            <span className="text-faint">$/h</span>
          </div>
        </div>
        <div>
          <div className="label mb-1">Utilities (estimated)</div>
          <div className="text-sm text-ink">0.75× to 1.35× each home’s estimate</div>
        </div>
        <div>
          <div className="label mb-1">Next semester’s schedule</div>
          <div className="text-sm text-ink">{tpl ? <>Sampled from <b>{tpl.name}</b> (assumed template) + your fixed blocks</> : <>Fixed — pick a template on “Your week” to sample it</>}</div>
        </div>
      </div>

      {isLoading || !data ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
      ) : Object.keys(data.p_rank1).length === 0 ? (
        <EmptyState title="Nothing to sample">No home fits your constraints. Relax a constraint on the results page.</EmptyState>
      ) : (
        <RobustBody data={data} lmap={lmap} vot={vot} />
      )}
    </div>
  );
}

function RobustBody({ data, lmap, vot }: { data: RobustnessResult; lmap: Map<string, Listing>; vot: number }) {
  const ids = Object.keys(data.p_rank1).sort((a, b) => data.p_rank1[b] - data.p_rank1[a] || data.rank_quantiles[a][1] - data.rank_quantiles[b][1]);
  const top = ids[0];
  const nm = (id: string) => lmap.get(id)?.name ?? id;
  const n = data.samples;
  const maxRank = Math.max(...ids.map((id) => data.rank_quantiles[id][2]), 2);
  const costs = ids.map((id) => data.cost_quantiles[id]);
  const cMin = Math.min(...costs.map((c) => c[0]));
  const cMax = Math.max(...costs.map((c) => c[2]));
  const cx = (v: number) => `${((v - cMin) / Math.max(1, cMax - cMin)) * 100}%`;
  const votBe = data.breakevens.find((b) => b.parameter === 'value_of_time' && b.value != null) ?? data.breakevens.find((b) => b.parameter === 'value_of_time');

  return (
    <>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="card p-5">
          <div className="text-2xl font-semibold leading-snug tracking-tight sm:text-3xl">
            In <span className="mono text-ink underline decoration-2 underline-offset-4">{frequency(data.p_rank1[top], n)}</span> plausible semesters, <span className="text-ink">{splitName(nm(top)).title}</span> is the cheapest week for you.
          </div>
          <div className="mt-5 grid items-start gap-6 2xl:grid-cols-[auto_minmax(0,1fr)]">
          <div>
            <IconArray share={data.p_rank1[top]} label={`${per100(data.p_rank1[top])} of 100 semesters`} />
            <div className="mt-2 text-sm text-muted">Each house = 1 in 100 semesters. <b className="text-ink">{per100(data.p_rank1[top])} of 100</b> filled.</div>
          </div>
          <div className="min-w-0 border-t border-line pt-4 2xl:border-l 2xl:border-t-0 2xl:pl-6 2xl:pt-0">
            <div className="mb-3 text-base font-semibold">How often each home is #1</div>
            <ul className="space-y-2">
              {ids.map((id) => (
                <li key={id} className="grid grid-cols-[minmax(0,10rem)_1fr_6.5rem] items-center gap-3 text-sm">
                  <span className="truncate" title={nm(id)}>{splitName(nm(id)).title}</span>
                  <div className="h-3 rounded-full bg-line/50"><div className="h-3 rounded-full bg-accent transition-[width] duration-500" style={{ width: `${data.p_rank1[id] * 100}%` }} /></div>
                  <span className="num text-right text-xs"><b className="text-ink">{Math.round(data.p_rank1[id] * n).toLocaleString('en-US')}</b> <span className="text-faint">of {n.toLocaleString('en-US')}</span></span>
                </li>
              ))}
            </ul>
          </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="label mb-2">What could flip it</div>
          <ul className="space-y-2">
            {data.drivers.slice(0, 2).map((d) => <li key={d} className="flex gap-2.5 text-base leading-relaxed text-ink"><span className="mt-[0.6rem] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{humanize(d, lmap)}</li>)}
          </ul>
          {votBe && <div className="mt-6"><BreakevenLine b={votBe} vot={vot} aName={splitName(nm(votBe.a)).title} bName={splitName(nm(votBe.b)).title} /></div>}
          <details className="disclosure mt-5 rounded-xl border border-line">
            <summary className="flex items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-sm font-medium text-ink hover:bg-raised">
              <span>Show every input tested <span className="text-muted">({data.drivers.length - Math.min(2, data.drivers.length) + data.breakevens.filter((b) => b !== votBe).length})</span></span>
              <IconChevron className="chev text-muted" />
            </summary>
            <ul className="space-y-1.5 border-t border-line p-3 text-sm text-muted">
              {data.drivers.slice(2).map((d) => <li key={d} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{humanize(d, lmap)}</li>)}
              {[...new Set(data.breakevens.filter((b) => b !== votBe).map((b) => humanize(b.direction, lmap)))].map((t) => <li key={t} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{t}</li>)}
            </ul>
          </details>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="card p-5">
          <div className="mb-1 text-base font-semibold">Rank range</div>
          <div className="mb-3 text-xs text-muted">Bar = 10th to 90th percentile rank; dot = median. Shorter bar = more predictable.</div>
          <ul className="space-y-2">
            {ids.map((id) => {
              const [p10, p50, p90] = data.rank_quantiles[id];
              const x = (r: number) => `${((r - 1) / Math.max(1, maxRank - 1)) * 100}%`;
              return (
                <li key={id} className="grid grid-cols-[minmax(0,11rem)_1fr_4.5rem] items-center gap-3 text-sm">
                  <span className="truncate" title={nm(id)}>{splitName(nm(id)).title}</span>
                  <div className="relative h-4">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-line" />
                    <div className="absolute top-1 h-2 rounded-full bg-accent/35" style={{ left: x(p10), width: `calc(${x(p90)} - ${x(p10)} + 0.5rem)` }} />
                    <div className="absolute top-0.5 h-3 w-3 -translate-x-0 rounded-full bg-accent ring-2 ring-surface" style={{ left: x(p50) }} />
                  </div>
                  <span className="num text-right text-xs text-muted">#{p10}–#{p90}</span>
                </li>
              );
            })}
          </ul>
          <div className="num mt-1 flex justify-between pl-[12rem] pr-[5.5rem] text-2xs text-faint"><span>#1</span><span>#{maxRank}</span></div>
        </div>

      <div className="card p-5">
        <div className="mb-1 text-base font-semibold">All-in cost fan</div>
        <div className="mb-3 text-xs text-muted">P10 · P50 · P90 of all-in monthly cost across sampled semesters (USD-equivalent per person).</div>
        <ul className="space-y-2.5">
          {ids.map((id) => {
            const [a, b, c] = data.cost_quantiles[id];
            return (
              <li key={id} className="grid grid-cols-[minmax(0,11rem)_1fr_9rem] items-center gap-3 text-sm">
                <span className="truncate" title={nm(id)}>{splitName(nm(id)).title}</span>
                <div className="relative h-5">
                  <div className="absolute top-1 h-3 rounded-sm" style={{ left: cx(a), width: `calc(${cx(c)} - ${cx(a)})`, background: 'linear-gradient(90deg, rgb(var(--accent) / 0.15), rgb(var(--accent) / 0.45), rgb(var(--accent) / 0.15))' }} />
                  <div className="absolute top-0 h-5 w-0.5 bg-accent" style={{ left: cx(b) }} />
                </div>
                <span className="num text-right text-xs"><span className="text-faint">{usd(a)}</span> · <b className="text-ink">{usd(b)}</b> · <span className="text-faint">{usd(c)}</span></span>
              </li>
            );
          })}
        </ul>
        <div className="num mt-2 flex justify-between pl-[12rem] pr-[10rem] text-2xs text-faint"><span>{usd(cMin)}</span><span>{usd(cMax)}</span></div>
      </div>
      </div>

      <Callout tone="info">
        Monte Carlo over <b>declared input ranges</b> only, not arbitrary priority weights. {n.toLocaleString('en-US')} samples, seed {data.seed}.
        <span className="num ml-1 text-xs">Standard error of the #1 share: ±{(data.mc_standard_error * 100).toFixed(1)} percentage points (±{Math.round(data.mc_standard_error * n)} of {n.toLocaleString('en-US')}).</span>
        <span className="ml-1 text-xs">Current value of time {usdRate(vot)}/h.</span>
      </Callout>
    </>
  );
}
