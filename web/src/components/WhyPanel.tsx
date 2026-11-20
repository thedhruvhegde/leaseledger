import type { EvaluationResult, ListingEvaluation, LineDiff, Listing } from '../types';
import { useCompare, useCounterfactual, useListingMap } from '../api/hooks';
import { useApp } from '../store/app';
import { BreakevenLine, humanize } from './Breakeven';
import { Receipt } from './Receipt';
import { Skeleton } from './ui/Misc';
import { IconChevron } from './ui/Icons';
import { ProvenanceLegend, splitName } from './ui/Badge';
import { LedgerChart } from './LedgerChart';
import { DAY_SHORT, duration, signedUsd, usd } from '../lib/format';

/** Order of preference for the (at most) three sentences shown before "Show all reasoning". */
const KEY_FACTS: RegExp[] = [/^Travel:/, /portal-style/i, /^Largest travel item/, /^Charge includes meals/, /^Co-op work shifts/, /outdoors after 22:00/];

export function keyFacts(facts: string[], n = 3): string[] {
  const out: string[] = [];
  for (const re of KEY_FACTS) {
    const f = facts.find((x) => re.test(x) && !out.includes(x));
    if (f) out.push(f);
    if (out.length >= n) break;
  }
  return out;
}

/** "Why this one?": receipt, a vs-#2 chip row, three key sentences, and the full reasoning behind a disclosure. */
export function WhyPanel({ e, result }: { e: ListingEvaluation; result: EvaluationResult }) {
  const lmap = useListingMap();
  const compareWith = useApp((s) => s.compareWith);
  const setCompareWith = useApp((s) => s.setCompareWith);
  const feasible = result.evaluations.filter((x) => x.feasible && x.listing_id !== e.listing_id);
  const other = compareWith && compareWith !== e.listing_id ? compareWith : (e.rank === 1 ? feasible[0]?.listing_id : result.evaluations.find((x) => x.rank === 1)?.listing_id) ?? null;
  const facts = keyFacts(e.explanation_facts);
  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <h4 className="mb-3 font-display text-xl font-semibold">Why this one?</h4>
        <Receipt e={e} size="lg" />
        <div className="secondary-chrome mt-3"><ProvenanceLegend inline /></div>
      </div>
      <div className="min-w-0 space-y-6">
        {other && (
          <VsRow a={e.listing_id} b={other} result={result} lmap={lmap}
            select={
              <select aria-label="Compare with" className="input w-auto max-w-[14rem] py-1 text-sm" value={other} onChange={(ev) => setCompareWith(ev.target.value || null)}>
                {result.evaluations.filter((x) => x.listing_id !== e.listing_id).map((x) => (
                  <option key={x.listing_id} value={x.listing_id}>{x.rank ? `#${x.rank} ` : ''}{lmap.get(x.listing_id)?.name ?? x.listing_id}</option>
                ))}
              </select>
            } />
        )}
        {facts.length > 0 && (
          <ul className="space-y-2.5" aria-label="Key reasons">
            {facts.map((f) => (
              <li key={f} className="flex gap-2.5 text-[0.9375rem] leading-relaxed text-charcoal"><span className="mt-[0.6rem] h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />{humanize(f, lmap)}</li>
            ))}
          </ul>
        )}
        <details className="disclosure rounded-xl border border-line">
          <summary className="flex items-center justify-between gap-2 rounded-xl px-4 py-3 text-sm font-medium text-ink hover:bg-raised">
            <span>Show all reasoning <span className="text-faint">({e.explanation_facts.length} facts, ledger bars{other ? ', side-by-side table' : ''})</span></span>
            <IconChevron className="chev text-faint" />
          </summary>
          <div className="space-y-6 border-t border-line p-4">
            <ul className="space-y-1.5">
              {e.explanation_facts.map((f) => (
                <li key={f} className="flex gap-2 text-sm text-charcoal"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{humanize(f, lmap)}</li>
              ))}
            </ul>
            <div>
              <div className="label mb-2">Monthly ledger, line by line</div>
              <LedgerChart e={e} />
            </div>
            {other && <Compare a={e.listing_id} b={other} vot={result.value_of_time_used} />}
          </div>
        </details>
      </div>
    </div>
  );
}

const shortLabel = (d: LineDiff) => d.label.replace(/\s*\(.*\)$/, '');

/** "#2 Hillcrest Manor, compared with this home": all-in delta chip + the largest line deltas (B − A, from /compare). */
export function VsRow({ a, b, result, lmap, select }: { a: string; b: string; result: EvaluationResult; lmap: Map<string, Listing>; select: React.ReactNode }) {
  const { data, isLoading } = useCompare(a, b);
  const be = result.evaluations.find((x) => x.listing_id === b);
  const ae = result.evaluations.find((x) => x.listing_id === a);
  const { title } = splitName(lmap.get(b)?.name ?? b);
  const allIn = be && ae ? { delta: be.all_in_total - ae.all_in_total } : null;
  const lines = (data?.line_diffs ?? []).filter((d) => d.key !== 'all_in' && d.key !== 'cash_total' && Math.abs(d.delta) >= 1)
    .sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta)).slice(0, 4);
  const tone = (v: number) => (Math.abs(v) < 0.5 ? 'text-faint' : v > 0 ? 'text-bad' : 'text-good');
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-faint">
          vs <span className="font-semibold text-ink">{be?.rank ? `#${be.rank} ` : ''}{title}</span> <span className="text-faint">(other minus this)</span>
        </div>
        <span className="secondary-chrome">{select}</span>
      </div>
      {isLoading || !data ? <Skeleton className="h-8" /> : (
        <div className="flex flex-wrap gap-1.5" aria-label="Differences, other home minus this one">
          {allIn && <span className={`num inline-flex items-center gap-1 rounded-full border border-ink px-3 py-1 text-[13px] font-semibold ${tone(allIn.delta)}`}>{signedUsd(allIn.delta)}/mo all-in</span>}
          {lines.map((d) => (
            <span key={d.key} className="num inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-[13px]">
              <span className="text-faint">{shortLabel(d).toLowerCase()}</span> <b className={`font-medium ${tone(d.delta)}`}>{signedUsd(d.delta)}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function Compare({ a, b, vot }: { a: string; b: string; vot: number }) {
  const { data, isLoading } = useCompare(a, b);
  const cf = useCounterfactual(a, b);
  const lmap = useListingMap();
  const an = lmap.get(a)?.name ?? a;
  const bn = lmap.get(b)?.name ?? b;
  if (isLoading || !data) return <div className="space-y-2"><Skeleton className="h-6" /><Skeleton className="h-24" /></div>;
  const votBe = data.breakevens.find((x) => x.parameter === 'value_of_time');
  const others = data.breakevens.filter((x) => x.parameter !== 'value_of_time');
  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-line">
        <table className="w-full text-sm">
          <thead className="bg-raised text-left text-xs text-muted">
            <tr><th className="px-3 py-2 font-medium">Line</th><th className="px-3 py-2 text-right font-medium"><span className="line-clamp-2">{splitName(an).title}</span></th><th className="px-3 py-2 text-right font-medium"><span className="line-clamp-2">{splitName(bn).title}</span></th><th className="px-3 py-2 text-right font-medium">B − A</th></tr>
          </thead>
          <tbody className="num">
            {data.line_diffs.map((d) => (
              <tr key={d.key} className={`border-t border-line ${d.key === 'all_in' ? 'bg-raised font-semibold' : ''}`}>
                <td className="px-3 py-1.5 font-sans text-ink">{d.label}</td>
                <td className="px-3 py-1.5 text-right">{usd(d.a)}</td>
                <td className="px-3 py-1.5 text-right">{usd(d.b)}</td>
                <td className={`px-3 py-1.5 text-right font-semibold ${Math.abs(d.delta) < 0.5 ? 'text-faint' : d.delta > 0 ? 'text-bad' : 'text-good'}`}>{signedUsd(d.delta)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.trip_diffs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.trip_diffs.map((t, i) => {
            const dm = Number(t.delta_min ?? 0);
            return (
              <span key={i} className="num rounded-md border border-line px-2 py-1 text-xs">
                <b>{t.day ? DAY_SHORT[t.day] : t.label}</b> {duration(Number(t.a_min ?? 0))} vs {duration(Number(t.b_min ?? 0))}
                <span className={`ml-1 font-semibold ${Math.abs(dm) < 1 ? 'text-faint' : dm > 0 ? 'text-bad' : 'text-good'}`}>{dm > 0 ? '+' : dm < 0 ? '−' : '±'}{Math.abs(Math.round(dm))}′</span>
              </span>
            );
          })}
        </div>
      )}
      {votBe && <BreakevenLine b={votBe} vot={vot} aName={splitName(an).title} bName={splitName(bn).title} aFull={an} bFull={bn} />}
      <ul className="space-y-1 text-sm text-muted">
        {others.map((x) => <li key={x.parameter}>• {humanize(x.direction, lmap)}</li>)}
        {(cf.data?.alternative_changes ?? []).map((x) => <li key={x}>• {humanize(x, lmap)}</li>)}
        {data.facts.map((f) => <li key={f}>• {humanize(f, lmap)}</li>)}
      </ul>
    </div>
  );
}
