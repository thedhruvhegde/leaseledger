// Evidence files from presentation/data/ (filled by the evidence agent).
// Missing evidence renders as a loud PLACEHOLDER in dev; `npm run build` refuses to ship it.
import required from './required-data.json';
import { esc } from './lib';

const jsonFiles = import.meta.glob('../data/*.json', { eager: true, import: 'default' }) as Record<string, any>;
const geoFiles = import.meta.glob('../data/*.geojson', { query: '?url', import: 'default', eager: true }) as Record<string, string>;

const byName = (rec: Record<string, any>) => Object.fromEntries(Object.entries(rec).map(([k, v]) => [k.split('/').pop()!, v]));
const J = byName(jsonFiles);
const G = byName(geoFiles);

export const facts: any = J[required.facts_file] ?? null;
export const interviews: any = J['interviews.json'] ?? null;

/** Surface files as [{name, label, url}] sorted by name. */
export const surfaces = Object.entries(G)
  .filter(([n]) => /^surface-.*\.geojson$/.test(n))
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([name, url]) => ({ name, id: name.replace(/^surface-|\.geojson$/g, ''), url }));

/** Look up a fact by key in any of the shapes we accept: {facts:{k:..}}, {facts:[{id|key:k}]}, {k:..}. */
export function getFact(key: string): any {
  if (!facts) return undefined;
  const pools = [facts.facts, facts.sections, facts];
  for (const p of pools) {
    if (!p) continue;
    if (Array.isArray(p)) {
      const hit = p.find((x: any) => x && (x.id === key || x.key === key || x.name === key));
      if (hit !== undefined) return hit;
    } else if (typeof p === 'object' && key in p) return p[key];
  }
  return undefined;
}

/** Rows of a tabular section (array of objects, or {rows:[...]}), or null. */
export function rowsOf(key: string): { rows: any[]; meta: any } | null {
  const v = getFact(key);
  if (!v) return null;
  if (Array.isArray(v)) return { rows: v, meta: {} };
  if (Array.isArray(v.rows)) return { rows: v.rows, meta: v };
  if (typeof v === 'object') {
    // {label: value} map -> rows
    const rows = Object.entries(v).filter(([k]) => !['source', 'note', 'title'].includes(k)).map(([k, x]) => (typeof x === 'object' ? { name: k, ...(x as object) } : { name: k, value: x }));
    return { rows, meta: v };
  }
  return null;
}

/** A fact as a data-bound span: value (+unit) formatted; placeholder if absent. */
export function F(id: string, opts: { unit?: boolean; digits?: number; prefix?: string; suffix?: string } = {}): string {
  const f = getFact(id);
  if (f === undefined || f.value === undefined) return placeholderInline(id);
  const v = f.value;
  let t: string;
  if (typeof v === 'number') t = (opts.digits != null ? v.toFixed(opts.digits) : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-US') : String(v));
  else if (Array.isArray(v)) t = v.join('–');
  else if (v && typeof v === 'object') t = Object.entries(v).map(([k, x]) => `${x} ${k}`).join(', ');
  else t = String(v);
  t = (opts.prefix ?? '') + t + (opts.suffix ?? '');
  if (opts.unit && f.unit) t += ' ' + f.unit;
  return `<span class="num" data-src="facts:${esc(id)}" title="${esc((f.how ?? '') + (f.caveat ? ' — ' + f.caveat : ''))}">${esc(t)}</span>`;
}
/** "95% CI a–b" for a fact with ci95, else ''. */
export function CI(id: string, suffix = ''): string {
  const f = getFact(id);
  if (!f?.ci95) return '';
  return `<span class="num ci" data-src="facts:${esc(id)}.ci95">95% CI ${esc(f.ci95[0])}–${esc(f.ci95[1])}${esc(suffix)}</span>`;
}
export const factVal = (id: string): any => getFact(id)?.value;
function placeholderInline(id: string) { missing.add(id); return `<span class="ph-inline" data-missing="${esc(id)}">⟨missing fact: ${esc(id)}⟩</span>`; }

export const missing = new Set<string>();
export function placeholder(what: string, why: string): string {
  missing.add(what);
  return `<div class="ph" data-missing="${esc(what)}"><b>PLACEHOLDER</b><span>${esc(what)}</span><small>${esc(why)} — waiting for presentation/data/. The production build fails until this resolves.</small></div>`;
}

export const requiredData = required;
