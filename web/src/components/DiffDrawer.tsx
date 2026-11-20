import { useState } from 'react';
import type { DiffResult, Listing } from '../types';
import { useFlip } from '../lib/flip';
import { DeltaChips, RankMove } from './ListingCard';
import { IconChevron, IconPin, IconX } from './ui/Icons';
import { Segmented } from './ui/Controls';
import { humanize } from './Breakeven';
import { splitName } from './ui/Badge';

export interface DiffDrawerProps {
  diff: DiffResult | undefined;
  loading?: boolean;
  names: Map<string, Listing>;
  open: boolean;
  pinned: boolean;
  onClose: () => void;
  onPin: () => void;
  onUnpin: () => void;
}

/** "What changed" drawer: causes, animated rank movement (FLIP), per-listing delta chips, before/after snapshot toggle. */
export function DiffDrawer({ diff, loading, names, open, pinned, onClose, onPin, onUnpin }: DiffDrawerProps) {
  const [view, setView] = useState<'after' | 'before'>('after');
  const ranked = (diff?.rank_changes ?? []).filter((r) => r.before != null || r.after != null);
  const key = (r: { before: number | null; after: number | null }) => (view === 'after' ? r.after : r.before) ?? 999;
  const ordered = [...ranked].sort((a, b) => key(a) - key(b)).slice(0, 8);
  const flip = useFlip(`${view}|${ordered.map((r) => r.listing_id).join(',')}`, 500);
  if (!open) return null;
  return (
    <aside
      role="complementary"
      aria-label="What changed"
      aria-live="polite"
      className="drawer fixed inset-x-2 z-40 max-h-[62vh] sm:max-h-[72vh] animate-slide-up overflow-y-auto rounded-xl border border-line-strong bg-surface sm:inset-x-auto sm:bottom-4 sm:right-4 sm:w-[28rem]"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-line bg-surface px-4 py-3">
        <div>
          <div className="font-display text-xl font-semibold">What changed</div>
          <div className="text-xs text-muted">{pinned ? 'Compared with your pinned snapshot' : 'Compared with before your last edit'}</div>
        </div>
        <div className="flex items-center gap-1">
          <button className={`btn-ghost px-2 text-xs ${pinned ? 'text-accent' : ''}`} onClick={pinned ? onUnpin : onPin} aria-pressed={pinned} title={pinned ? 'Unpin snapshot' : 'Pin the current state as the comparison baseline'}>
            <IconPin size={14} /> {pinned ? 'Pinned' : 'Pin now'}
          </button>
          <button className="btn-ghost px-1.5" onClick={onClose} aria-label="Close what changed"><IconX /></button>
        </div>
      </div>
      <div className="space-y-4 p-4">
        {loading && !diff && <div className="text-sm text-muted">Recomputing…</div>}
        {diff && (
          <>
            <div className={`rounded-xl px-4 py-2.5 text-lg font-semibold font-display ${diff.top_changed ? 'border-2 border-ink text-ink' : 'bg-soft text-ink'}`} data-testid="diff-headline">
              {diff.top_changed ? 'Your #1 changed.' : 'Your #1 held.'}
            </div>
            <ul className="space-y-1.5" aria-label="Causes">
              {diff.causes.slice(0, 3).map((c) => (
                <li key={c} className="flex gap-2.5 text-sm leading-relaxed text-ink"><span className="mt-[0.55rem] h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />{humanize(c, names)}</li>
              ))}
            </ul>
            {diff.causes.length > 3 && (
              <details className="disclosure">
                <summary className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><IconChevron size={14} className="chev" />{diff.causes.length - 3} more</summary>
                <ul className="mt-1.5 space-y-1.5">
                  {diff.causes.slice(3).map((c) => <li key={c} className="flex gap-2.5 text-sm text-muted"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />{humanize(c, names)}</li>)}
                </ul>
              </details>
            )}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <div className="label">Ranking</div>
                <Segmented size="xs" label="Snapshot" value={view} onChange={setView} options={[{ value: 'before', label: 'Before' }, { value: 'after', label: 'After' }]} />
              </div>
              <ol className="space-y-1">
                {ordered.map((r) => {
                  const d = diff.deltas[r.listing_id];
                  const rank = view === 'after' ? r.after : r.before;
                  return (
                    <li key={r.listing_id} ref={flip(r.listing_id)} className="relative rounded-xl border border-line bg-surface px-3 py-2" data-testid="diff-row">
                      <div className="flex items-center gap-2">
                        <span className="mono w-6 text-base font-semibold text-ink">{rank ?? '—'}</span>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={names.get(r.listing_id)?.name}>{splitName(names.get(r.listing_id)?.name ?? r.listing_id).title}</span>
                        {view === 'after' && <RankMove before={r.before} after={r.after} />}
                      </div>
                      {d && view === 'after' && <div className="mt-1 pl-8"><DeltaChips d={d} /></div>}
                    </li>
                  );
                })}
              </ol>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
