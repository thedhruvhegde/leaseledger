import type { Listing, Provenance } from '../../types';
import { PROVENANCES } from '../../types';

export const PROV_META: Record<Provenance, { label: string; glyph: string; code: string; desc: string }> = {
  observed: { label: 'Observed', glyph: 'O', code: 'obs', desc: 'Read from a dated public source (listing page, timetable, NOAA).' },
  estimated: { label: 'Estimated', glyph: 'E', code: 'est', desc: 'Model output from observed inputs (e.g. utility band, AI-parsed block).' },
  assumed: { label: 'Assumed', glyph: 'A', code: 'asm', desc: 'An explicit assumption you can change (e.g. value of time share).' },
  computed: { label: 'Computed', glyph: 'C', code: 'cmp', desc: 'Deterministic arithmetic from the above.' },
  synthetic: { label: 'Synthetic', glyph: 'S', code: 'syn', desc: 'Fictional demo data, not a real listing or price.' },
  user: { label: 'You', glyph: 'U', code: 'you', desc: 'Entered or confirmed by you.' },
};

/** Provenance as a small mono command-tag pill: "obs", "est", "asm", "cmp", "syn", "you". */
export function ProvenanceBadge({ p, compact = false, className = '' }: { p: Provenance; compact?: boolean; className?: string }) {
  const m = PROV_META[p];
  const syn = p === 'synthetic' ? 'border border-dashed border-line-strong hatch-synthetic' : '';
  return (
    <span className={`tag ${syn} ${className}`} title={`${m.label}: ${m.desc}`} aria-label={`Provenance: ${m.label}`}>
      <span aria-hidden>{m.code}</span>
      {!compact && <span className="font-sans text-faint">{m.label.toLowerCase()}</span>}
    </span>
  );
}

export function SyntheticBadge({ className = '' }: { className?: string }) {
  return (
    <span className={`tag border border-dashed border-ink/50 font-medium text-ink hatch-synthetic ${className}`}
      title="Fictional listing created for this demo. Not a real property, price or availability.">
      synthetic listing
    </span>
  );
}

export function ProvenanceLegend({ inline = false }: { inline?: boolean }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 ${inline ? '' : 'p-3'}`} aria-label="Provenance legend">
      {PROVENANCES.map((p) => (
        <span key={p} className="inline-flex items-center gap-1.5 text-xs text-faint" title={PROV_META[p].desc}>
          <ProvenanceBadge p={p} compact /> {PROV_META[p].label}
        </span>
      ))}
    </div>
  );
}

const VERIF: Record<string, { label: string; code: string; tip: string }> = {
  search_extract: { label: 'Observed · search text', code: 'obs · search', tip: 'Copied from search-engine text for the cited URL; the page itself was not loaded. Availability not verified.' },
  page_fetched: { label: 'Observed · page read', code: 'obs · page', tip: 'Read from the listing page on the observation date. Availability not verified.' },
  user_verified: { label: 'Verified by you', code: 'verified', tip: 'You checked these facts against the listing yourself.' },
};

/** Listing-level source tag: "obs · search 11-20", or "synthetic listing". */
export function ListingSourceBadge({ l, className = '', compact = false }: { l: Listing; className?: string; compact?: boolean }) {
  if (l.provenance === 'synthetic') return <SyntheticBadge className={className} />;
  const v = VERIF[l.verification ?? 'page_fetched'] ?? VERIF.page_fetched;
  const date = l.observed_on ? `, ${l.observed_on}` : '';
  const md = l.observed_on ? l.observed_on.slice(5) : '';
  return (
    <span className={`tag ${className}`} title={`${v.label}${date}. ${v.tip}${l.source_url ? ` Source: ${l.source_url}` : ''}`}>
      {v.code}{md && <span className={compact ? 'text-faint' : 'text-faint'}>{compact ? md : l.observed_on}</span>}
    </span>
  );
}

/** Long listing names ("ICC Escher House - single room (co-op)") split into a title and a subtitle on the first " - ". */
export function splitName(name: string | undefined | null): { title: string; sub: string | null } {
  const n = name ?? '';
  const i = n.indexOf(' - ');
  if (i < 0) return { title: n, sub: null };
  return { title: n.slice(0, i), sub: n.slice(i + 3) };
}

export function ListingName({ name, className = '', subClassName = '' }: { name: string | undefined | null; className?: string; subClassName?: string }) {
  const { title, sub } = splitName(name);
  return (
    <span className="block min-w-0">
      <span className={`block ${className}`}>{title}</span>
      {sub && <span className={`block text-muted ${subClassName}`}>{sub}</span>}
    </span>
  );
}

export function MealsBadge({ l }: { l: Listing }) {
  if (!l.board_included) return null;
  return <span className="tag" title="Co-op charge includes food (board). Compare against rent + your grocery spend.">meals incl.</span>;
}
