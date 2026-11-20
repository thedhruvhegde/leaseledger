import { useEffect, useState } from 'react';
import { useBuildingMap, useBuildings, useGroup, useListingMap, useTemplates } from '../api/hooks';
import { useApp } from '../store/app';
import { WeeklyGrid } from '../components/WeeklyGrid';
import { EventEditor } from '../components/EventEditor';
import { Callout, EmptyState, ErrorState, SectionTitle, Skeleton } from '../components/ui/Misc';
import { ListingName, ListingSourceBadge, splitName } from '../components/ui/Badge';
import { IconCheck, IconPlus, IconTrash } from '../components/ui/Icons';
import { DEFAULT_PROFILE } from '../api/mockData';
import type { GroupSplit, Member, ScheduleTemplate } from '../types';
import { usd } from '../lib/format';
import { humanize } from '../components/Breakeven';

const ALIASES = ['Roommate A', 'Roommate B', 'Roommate C', 'Roommate D', 'Roommate E', 'Roommate F'];

function fromTemplate(t: ScheduleTemplate | undefined) {
  return t ? t.slots.map((s) => ({ ...s[0], fixed: true, provenance: 'assumed' as const })) : [];
}

export function GroupScreen() {
  const members = useApp((s) => s.members);
  const setMembers = useApp((s) => s.setMembers);
  const mine = useApp((s) => s.committed);
  const { data: templates = [] } = useTemplates();
  const { data, isLoading, error, refetch, isFetching } = useGroup(members);
  const lmap = useListingMap();
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    if (members.length === 0 && templates.length) {
      const caps = [1100, 1000, 1200];
      setMembers([0, 1, 2].map((i) => ({
        alias: ALIASES[i],
        budget_cap: caps[i],
        room_values: null,
        profile: { ...DEFAULT_PROFILE, events: i === 0 && mine.events.length ? mine.events : fromTemplate(templates[i % templates.length]) },
      })));
    }
  }, [members.length, templates, mine.events, setMembers]);

  const update = (i: number, m: Partial<Member>) => setMembers((ms) => ms.map((x, j) => (j === i ? { ...x, ...m } : x)));
  const ranking = data?.ranking ?? [];
  const selected = data?.splits.find((s) => s.listing_id === (sel ?? ranking[0]));

  return (
    <div className="space-y-5">
      <SectionTitle title="Group Week">
        Everyone’s week counts. We pick the apartment that’s best for the <b className="text-ink">worst-off</b> roommate, assign rooms, and split rent so that <b className="text-ink">nobody would rather swap</b> their room-and-rent with anyone else (envy-free). Aliases only — no names needed.
      </SectionTitle>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-3">
        {members.map((m, i) => (
          <MemberCard key={i} m={m} i={i} templates={templates} onChange={(p) => update(i, p)}
            onRemove={members.length > 2 ? () => setMembers((ms) => ms.filter((_, j) => j !== i)) : undefined}
            onUseMine={() => update(i, { profile: { ...m.profile, events: mine.events } })} />
        ))}
        {members.length < 6 && (
          <button className="card flex min-h-[10rem] items-center justify-center gap-2 border-dashed text-sm font-medium text-muted hover:text-ink"
            onClick={() => setMembers((ms) => [...ms, { alias: ALIASES[ms.length] ?? `Roommate ${ms.length + 1}`, budget_cap: 1100, room_values: null, profile: { ...DEFAULT_PROFILE, events: fromTemplate(templates[ms.length % Math.max(1, templates.length)]) } }])}>
            <IconPlus /> Add roommate
          </button>
        )}
      </div>

      {error && !data ? <ErrorState error={error} retry={() => void refetch()} /> : isLoading || !data ? <Skeleton className="h-80" /> : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-base font-semibold">Apartments for {members.length}</div>
              {isFetching && <span className="animate-pulse2 text-xs text-faint">Updating…</span>}
            </div>
            <ol className="space-y-1.5">
              {ranking.map((id, k) => {
                const s = data.splits.find((x) => x.listing_id === id)!;
                const tooSmall = !s.feasible && s.envy_matrix.length === 0;
                return (
                  <li key={id}>
                    <button onClick={() => setSel(id)} aria-pressed={selected?.listing_id === id}
                      className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${selected?.listing_id === id ? 'border-accent bg-accent-soft/60' : 'border-line hover:bg-raised'} ${s.feasible ? '' : 'opacity-60'}`}>
                      <span className="num w-5 font-bold text-accent">{s.feasible ? k + 1 : '—'}</span>
                      <span className="min-w-0 flex-1 truncate" title={lmap.get(id)?.name}>{splitName(lmap.get(id)?.name ?? id).title}</span>
                      <span className="num text-xs text-muted">{tooSmall ? 'too small' : s.feasible ? `worst-off ${usd(s.maximin_utility)}` : 'over budget'}</span>
                    </button>
                  </li>
                );
              })}
            </ol>
            <p className="mt-3 text-xs text-faint">Ranked by the worst-off roommate’s surplus: room value − rent share − their own commute cost (USD-equiv/mo).</p>
          </div>
          {selected ? <SplitDetail s={selected} members={members} /> : <EmptyState title="Pick an apartment" />}
        </div>
      )}
      {data?.warnings.filter((w) => !w.startsWith('MOCK')).map((w) => <Callout key={w} tone="warn">{w}</Callout>)}
    </div>
  );
}

function MemberCard({ m, i, templates, onChange, onRemove, onUseMine }: {
  m: Member; i: number; templates: ScheduleTemplate[]; onChange: (p: Partial<Member>) => void; onRemove?: () => void; onUseMine: () => void;
}) {
  const bmap = useBuildingMap();
  const { data: buildings = [] } = useBuildings();
  const [sel, setSel] = useState<number | null>(null);
  const setEvents = (events: Member['profile']['events']) => onChange({ profile: { ...m.profile, events } });
  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-soft text-xs font-bold text-accent">{String.fromCharCode(65 + i)}</span>
        <input aria-label="Alias" className="input py-1 text-sm font-semibold" value={m.alias} maxLength={24} onChange={(e) => onChange({ alias: e.target.value || `Roommate ${i + 1}` })} />
        {onRemove && <button className="btn-ghost px-1.5" onClick={onRemove} aria-label={`Remove ${m.alias}`}><IconTrash size={14} /></button>}
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <label className="flex items-center gap-1 text-muted">Max rent
          <span className="flex items-center rounded-md border border-line px-1.5"><span className="text-faint">$</span>
            <input aria-label={`${m.alias} budget cap`} type="number" className="num w-16 bg-transparent py-1 text-right text-ink focus:outline-none" value={m.budget_cap ?? ''} step={25}
              onChange={(e) => onChange({ budget_cap: e.target.value ? Number(e.target.value) : null })} />
          </span>
        </label>
        <select aria-label="Quick template" className="input w-auto py-1 text-xs" value="" onChange={(e) => { const t = templates.find((x) => x.id === e.target.value); if (t) setEvents(fromTemplate(t)); }}>
          <option value="">Quick template…</option>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button className="btn-ghost px-1.5 py-0.5 text-xs" onClick={onUseMine}>Use my week</button>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[420px]">
          <WeeklyGrid events={m.profile.events} buildings={bmap} pxPerMin={0.2} selected={sel} onSelect={setSel} label={`${m.alias} weekly schedule`}
            onChange={(k, patch) => setEvents(m.profile.events.map((e, j) => (j === k ? { ...e, ...patch } : e)))}
            onDelete={(k) => { setEvents(m.profile.events.filter((_, j) => j !== k)); setSel(null); }} />
        </div>
      </div>
      {sel != null && m.profile.events[sel] && (
        <div className="mt-2">
          <EventEditor event={m.profile.events[sel]} buildings={buildings} onClose={() => setSel(null)}
            onChange={(patch) => setEvents(m.profile.events.map((e, j) => (j === sel ? { ...e, ...patch } : e)))}
            onDelete={() => { setEvents(m.profile.events.filter((_, j) => j !== sel)); setSel(null); }} />
        </div>
      )}
    </div>
  );
}

export function EnvyMatrix({ E, aliases }: { E: number[][]; aliases: string[] }) {
  const max = Math.max(1, ...E.flat().map(Math.abs));
  const ok = E.every((row, p) => row.every((v, q) => p === q || v <= 1e-6));
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <div className="text-sm font-semibold">Envy matrix</div>
        {ok ? <span className="inline-flex items-center gap-1 rounded-full bg-good/15 px-2 py-0.5 text-xs font-bold text-good" data-testid="envy-free"><IconCheck size={12} /> envy-free</span>
          : <span className="rounded-full bg-bad/15 px-2 py-0.5 text-xs font-bold text-bad">not envy-free</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="num border-separate border-spacing-1 text-xs" aria-label="Envy matrix: how much each roommate (row) would prefer another's room and rent (column); zero or negative means no envy">
          <thead><tr><th className="text-left text-2xs font-medium text-faint">row envies →</th>{aliases.map((a) => <th key={a} className="max-w-[5rem] truncate px-1 text-2xs font-semibold text-muted">{a}</th>)}</tr></thead>
          <tbody>
            {E.map((row, p) => (
              <tr key={p}>
                <th className="max-w-[6rem] truncate pr-2 text-left text-2xs font-semibold text-muted">{aliases[p]}</th>
                {row.map((v, q) => {
                  const a = Math.min(1, Math.abs(v) / max);
                  const bg = p === q ? 'rgb(var(--line) / 0.5)' : v <= 1e-6 ? `rgb(var(--good) / ${0.12 + 0.45 * a})` : `rgb(var(--bad) / ${0.2 + 0.6 * a})`;
                  return <td key={q} className="h-10 w-16 rounded-md text-center font-semibold text-ink" style={{ background: bg }} title={p === q ? 'self' : `${aliases[p]} values ${aliases[q]}'s deal ${v <= 0 ? `${usd(-v)} less` : `${usd(v)} more`} than their own`}>{p === q ? '—' : usd(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-1 text-2xs text-faint">E[p][q] = how much p would gain by taking q’s room at q’s rent. All ≤ $0 ⇒ nobody wants to swap.</div>
    </div>
  );
}

function SplitDetail({ s, members }: { s: GroupSplit; members: Member[] }) {
  const lmap = useListingMap();
  const l = lmap.get(s.listing_id);
  const aliases = members.map((m) => m.alias);
  const tooSmall = s.envy_matrix.length === 0;
  return (
    <div className="card space-y-5 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="label">{s.feasible ? 'Fair split' : 'Doesn’t work yet'}</div>
          <div className="text-xl font-semibold tracking-tight"><ListingName name={l?.name ?? s.listing_id} subClassName="text-base font-normal" /></div>
          {l && <div className="mt-1"><ListingSourceBadge l={l} /></div>}
        </div>
        {s.maximin_utility != null && <div className="text-right"><div className="label">Worst-off roommate</div><div className="num text-2xl font-bold">{usd(s.maximin_utility)}<span className="text-xs text-faint">/mo surplus</span></div></div>}
      </div>
      {tooSmall ? <Callout tone="warn">{s.explanation_facts.join(' ')}</Callout> : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-2xs uppercase tracking-wider text-faint"><tr className="border-b border-line"><th className="py-2 pr-3">Roommate</th><th className="py-2 pr-3">Room</th><th className="py-2 pr-3 text-right">Rent share</th><th className="py-2 pr-3 text-right">Surplus</th><th className="py-2 text-right">Budget</th></tr></thead>
              <tbody className="num">
                {members.map((m) => {
                  const over = s.relaxation[m.alias];
                  return (
                    <tr key={m.alias} className="border-b border-line/60">
                      <td className="py-2 pr-3 font-sans font-semibold">{m.alias}</td>
                      <td className="py-2 pr-3 font-sans">{s.assignment[m.alias]}</td>
                      <td className="py-2 pr-3 text-right text-base font-semibold">{usd(s.rent[m.alias])}</td>
                      <td className="py-2 pr-3 text-right">{usd(s.utility[m.alias])}</td>
                      <td className={`py-2 text-right ${over ? 'font-semibold text-bad' : 'text-muted'}`}>{over ? `+${usd(over)} needed` : m.budget_cap != null ? `≤ ${usd(m.budget_cap)} ✓` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <EnvyMatrix E={s.envy_matrix} aliases={aliases} />
            <div className="space-y-3">
              <div className="rounded-lg border border-line p-3">
                <div className="label mb-1">vs. splitting rent equally</div>
                <div className="num text-sm text-ink">Equal split: someone envies another’s room by up to <b className="text-bad">{usd(s.equal_split_max_envy)}/mo</b>.</div>
                <div className="num text-sm text-ink">This split: max envy <b className="text-good">{usd(Math.max(0, ...s.envy_matrix.flat()))}</b>.</div>
              </div>
              {Object.keys(s.relaxation).length > 0 && (
                <Callout tone="warn" title="To make it work">
                  {Object.entries(s.relaxation).map(([a, v]) => <div key={a}>{a}: raise max rent by <b>{usd(v)}</b></div>)}
                </Callout>
              )}
              <ul className="space-y-1 text-sm text-muted">
                {s.explanation_facts.map((f) => <li key={f}>• {humanize(f, lmap)}</li>)}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
