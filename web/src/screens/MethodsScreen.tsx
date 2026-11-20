import { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useManifest, useMethods } from '../api/hooks';
import { useApp } from '../store/app';
import { ErrorState, SectionTitle, Skeleton } from '../components/ui/Misc';
import { ProvenanceBadge, ProvenanceLegend } from '../components/ui/Badge';
import type { MethodsResult, Provenance } from '../types';
import { PROVENANCES } from '../types';

function Tex({ latex }: { latex: string }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, { displayMode: true, throwOnError: false, output: 'html' });
    } catch {
      return latex;
    }
  }, [latex]);
  return <div className="overflow-x-auto py-1 text-ink" dangerouslySetInnerHTML={{ __html: html }} />;
}

const isProv = (p: unknown): p is Provenance => typeof p === 'string' && (PROVENANCES as string[]).includes(p);

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string => (v == null ? '' : typeof v === 'string' ? v : typeof v === 'number' || typeof v === 'boolean' ? String(v) : JSON.stringify(v));

const STATIC_LIMITS = [
  'Travel times use one representative service day per feed; real buses run late, early, or not at all on holidays.',
  'Utility bands are estimates from building type, heating fuel and weather normals — not your bills.',
  'Listings are curated public extracts (dated) or synthetic; we make no availability claims.',
  'Schedule templates are illustrative, not registrar data.',
  'Legal flags are prompts to verify with U-M Student Legal Services — not legal advice.',
];

/** Accept both our proposed MethodsResult shape and the API's {engine_readme, params, data_sources} shape. */
export function normaliseMethods(raw: unknown): MethodsResult {
  const m: Obj = isObj(raw) ? raw : {};
  const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
  const sources = arr(m.sources ?? m.data_sources).filter(isObj).map((x) => ({
    name: str(x.name) || str(x.kind), kind: str(x.kind).replace(/_/g, ' '),
    date: str(x.date), valid: str(x.valid) || (isObj(x.detail) ? [str(x.detail.valid_from), str(x.detail.valid_to)].filter(Boolean).join(' → ') : ''),
    url: str(x.url) || undefined, license: str(x.license) || undefined,
    note: str(x.note) || (isObj(x.detail) ? '' : str(x.detail)) + (Array.isArray(x.hosts) ? ` (${(x.hosts as unknown[]).map(str).join(', ')})` : ''),
  }));
  const assumptions = arr(m.assumptions ?? m.params).filter(isObj).map((x) => {
    const lo = typeof x.low === 'number' ? x.low : undefined;
    const hi = typeof x.high === 'number' ? x.high : undefined;
    const range = Array.isArray(x.range) ? (x.range as [number, number]) : lo != null && hi != null ? ([lo, hi] as [number, number]) : null;
    return {
      key: str(x.key), label: str(x.label) || str(x.key).replace(/[._]/g, ' '), value: typeof x.value === 'number' ? x.value : str(x.value),
      unit: str(x.unit) || undefined, range, provenance: (isProv(x.provenance) ? x.provenance : 'assumed') as Provenance, source: str(x.source) || undefined,
    };
  });
  let equations = arr(m.equations).filter(isObj).map((x) => ({ name: str(x.title ?? x.name), latex: str(x.latex), explanation: str(x.meaning ?? x.explanation) }));
  const readme = isObj(m.engine_readme) ? m.engine_readme : null;
  if (!equations.length && readme) {
    equations = arr(readme.sections).filter(isObj).filter((sec) => arr(sec.equations).length > 0).slice(0, 12).map((sec) => ({
      name: str(sec.title), latex: arr(sec.equations).map(str).slice(0, 4).join('\n'), explanation: str(sec.summary),
    }));
  }
  const limits = arr(m.limitations).map(str);
  if (readme) for (const sec of arr(readme.sections).filter(isObj)) if (/limit|caveat|not claim/i.test(str(sec.title)) && str(sec.summary)) limits.push(str(sec.summary));
  return { sources, assumptions, equations, limitations: limits.length ? limits : STATIC_LIMITS };
}

/** Render LaTeX when it looks like LaTeX; otherwise show the formula as code (engine README formulas may be plain text). */
function Formula({ src }: { src: string }) {
  const lines = src.split('\n');
  const looksTex = /\\[a-zA-Z]+|\^\{|_\{/.test(src);
  if (looksTex) return <Tex latex={lines.length > 1 ? `\\begin{gathered}${lines.join(' \\\\ ')}\\end{gathered}` : src} />;
  return <pre className="my-2 overflow-x-auto rounded-md bg-raised p-3 font-mono text-xs leading-relaxed text-ink">{lines.join('\n')}</pre>;
}

export function MethodsScreen() {
  const methods = useMethods();
  const manifest = useManifest();
  const kind = useApp((s) => s.api?.kind);
  if (methods.error && !methods.data) return <ErrorState error={methods.error} retry={() => void methods.refetch()} />;
  if (!methods.data) return <Skeleton className="h-[40rem]" />;
  const m = normaliseMethods(methods.data);
  const mf = manifest.data;
  return (
    <div className="space-y-6">
      <SectionTitle title="Methods & sources">
        Every number in {kind === 'mock' ? 'this (mock) session' : 'the app'} is tagged with where it came from. Here are the data sources, the assumptions you can change, the equations, and what we can’t claim.
      </SectionTitle>
      <div className="card"><ProvenanceLegend /></div>

      <section className="card p-5">
        <h3 className="h-section mb-3">Data sources</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-2xs uppercase tracking-wider text-faint"><tr className="border-b border-line"><th className="py-2 pr-3">Source</th><th className="py-2 pr-3">Kind</th><th className="py-2 pr-3">Date / validity</th><th className="py-2">Notes</th></tr></thead>
            <tbody>
              {m.sources.map((s, i) => (
                <tr key={i} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3 font-semibold text-ink">{s.url ? <a className="text-accent hover:underline" href={s.url} target="_blank" rel="noreferrer">{s.name}</a> : s.name}</td>
                  <td className="py-2 pr-3 text-muted">{s.kind}</td>
                  <td className="num py-2 pr-3 text-muted">{[s.date, s.valid].filter(Boolean).join(' · ') || '—'}{s.license ? <div className="text-2xs text-faint">{s.license}</div> : null}</td>
                  <td className="py-2 text-muted">{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {mf && (
          <div className="mt-4 rounded-lg bg-raised p-3">
            <div className="label mb-1">Run manifest {mf.engine_version ? `· engine ${mf.engine_version}` : ''}</div>
            {mf.warning && <div className="mb-1 text-xs font-semibold text-warn">{mf.warning}</div>}
            <ul className="num space-y-0.5 text-xs text-muted">
              {(mf.feeds ?? []).map((f, i) => <li key={i}><b className="text-ink">{f.name}</b> — valid {f.valid_from ?? '?'} → {f.valid_to ?? '?'}{f.used_service_date ? ` · service day used: ${f.used_service_date}` : ''}</li>)}
            </ul>
          </div>
        )}
      </section>

      <section className="card p-5">
        <h3 className="h-section mb-3">Assumptions (with ranges)</h3>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {m.assumptions.map((a) => (
            <div key={a.key} className="flex items-start justify-between gap-3 rounded-lg border border-line p-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-ink">{a.label}</div>
                {a.source && <div className="text-xs text-faint">{a.source}</div>}
              </div>
              <div className="shrink-0 text-right">
                <div className="num text-sm font-semibold">{String(a.value)} <span className="text-xs font-normal text-faint">{a.unit}</span></div>
                {a.range && <div className="num text-2xs text-faint">range {a.range[0]}–{a.range[1]}</div>}
                {isProv(a.provenance) && <ProvenanceBadge p={a.provenance} className="mt-1" />}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h3 className="h-section mb-3">Equations</h3>
        <div className="space-y-4">
          {m.equations.map((e) => (
            <div key={e.name} className="rounded-lg border border-line p-4">
              <div className="text-sm font-semibold text-ink">{e.name}</div>
              <Formula src={e.latex} />
              <div className="text-sm text-muted">{e.explanation}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h3 className="h-section mb-3">Limitations — what we can’t claim</h3>
        <ul className="space-y-1.5">
          {m.limitations.map((l) => <li key={l} className="flex gap-2 text-sm text-ink"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />{l}</li>)}
        </ul>
        <p className="mt-3 text-xs text-faint">Legal flags are prompts to verify with U-M Student Legal Services — not legal advice.</p>
      </section>
    </div>
  );
}
