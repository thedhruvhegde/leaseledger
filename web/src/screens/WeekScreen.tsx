import { useEffect, useRef, useState } from 'react';
import { useApp } from '../store/app';
import { useBuildingMap, useBuildings, useDemoProfiles, useEvaluation, useListingMap, useParseSchedule, useTemplates } from '../api/hooks';
import { parseSchedule as localParse } from '../api/mockNlp';
import { CampusLegend, WeeklyGrid } from '../components/WeeklyGrid';
import { EventEditor } from '../components/EventEditor';
import { WeekPill } from '../components/WeekPill';
import { ConstraintsPanel } from '../components/ConstraintsPanel';
import { IconChevron, IconSparkle } from '../components/ui/Icons';
import { Callout, SectionTitle, Skeleton } from '../components/ui/Misc';
import { SyntheticBadge } from '../components/ui/Badge';
import type { ParseScheduleResult } from '../types';
import { usd } from '../lib/format';
import { splitName } from '../components/ui/Badge';

const EXAMPLE = `EECS 281 MWF 9-10:30 in BBB. Lab Tuesday 9 to noon in GG Brown. Ross class TTh 1-2:30. Gym at CCRB Mon/Wed 5:30-6:30. UgLi most weeknights until 1am. Café job in Kerrytown Saturdays 10-3.`;

export function WeekScreen() {
  const profile = useApp((s) => s.profile);
  const setProfile = useApp((s) => s.setProfile);
  const updateEvent = useApp((s) => s.updateEvent);
  const addEvent = useApp((s) => s.addEvent);
  const removeEvent = useApp((s) => s.removeEvent);
  const needsConfirm = useApp((s) => s.needsConfirm);
  const setNeedsConfirm = useApp((s) => s.setNeedsConfirm);
  const confirmEvent = useApp((s) => s.confirmEvent);
  const aiEnabled = useApp((s) => s.aiEnabled);
  const setScreen = useApp((s) => s.setScreen);
  const present = useApp((s) => s.present);
  const { data: buildings = [] } = useBuildings();
  const bmap = useBuildingMap();
  const { data: templates = [] } = useTemplates();
  const { data: demos = [] } = useDemoProfiles();
  const parse = useParseSchedule();
  const [text, setText] = useState('');
  const [sel, setSel] = useState<number | null>(null);
  const [parsed, setParsed] = useState<ParseScheduleResult | null>(null);
  const [demoId, setDemoId] = useState('');

  const applyParse = (r: ParseScheduleResult, append: boolean) => {
    const offset = append ? profile.events.length : 0;
    setProfile((p) => ({ ...p, events: append ? [...p.events, ...r.events] : r.events }));
    const nc: Record<number, string[]> = append ? { ...needsConfirm } : {};
    for (const n of r.needs_confirmation) (nc[n.event_index + offset] ??= []).push(n.reason);
    setNeedsConfirm(nc);
    setParsed(r);
    useApp.getState().setLastAiMode(r.mode);
  };

  const run = async (input: string = text) => {
    if (!input.trim()) return;
    try {
      const r = await parse.mutateAsync(input);
      applyParse(r, profile.events.length > 0);
    } catch {
      applyParse(localParse(input, buildings), profile.events.length > 0);
    }
  };

  const loadDemo = (id: string) => {
    const d = demos.find((x) => x.id === id);
    if (!d) return;
    setDemoId(id);
    setProfile(d.profile, 'load');
    setSel(null);
    setParsed(null);
  };

  const loadTemplate = (id: string) => {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    // Template = uncertain future schedule. Seed the grid with the first alternative of each slot (dashed) and use it for Monte Carlo.
    const seeded = t.slots.map((s) => ({ ...s[0], fixed: false, provenance: 'assumed' as const }));
    setProfile((p) => ({ ...p, template_id: t.id, events: [...p.events.filter((e) => e.fixed), ...seeded] }));
  };

  const selected = sel != null ? profile.events[sel] : undefined;

  // Arriving from the landing page's week pill: parse that text once.
  const weekDraft = useApp((s) => s.weekDraft);
  const consumed = useRef<string | null>(null);
  useEffect(() => {
    if (!weekDraft || consumed.current === weekDraft) return;
    consumed.current = weekDraft;
    useApp.getState().setWeekDraft(null);
    setText(weekDraft);
    void run(weekDraft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekDraft]);

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="min-w-0 space-y-5">
        <SectionTitle eyebrow="Step 1" title="Your week">
          Describe a normal week in plain English, or drag blocks on the grid. We price every home against <em>this</em> routine, not a single “distance to campus”.
        </SectionTitle>

        <div className="card p-4">
          <label htmlFor="describe" className="mb-3 flex items-center gap-2 font-display text-lg font-semibold"><IconSparkle size={16} /> Describe your week</label>
          <WeekPill id="describe" value={text} onChange={setText} onSubmit={() => void run()} pending={parse.isPending} placeholder={EXAMPLE} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button className="btn-outline" onClick={() => void run()} disabled={parse.isPending || !text.trim()}>
              {parse.isPending ? 'Reading…' : profile.events.length ? 'Add to my week' : 'Build my week'}
            </button>
            <button className="btn-ghost text-xs" onClick={() => setText(EXAMPLE)}>Use example text</button>
            <span className="text-xs text-faint">{aiEnabled ? 'AI parsing; every block keeps the exact words it came from.' : 'AI is off: using the deterministic pattern parser.'}</span>
            <span className="secondary-chrome mono ml-auto text-2xs text-faint">{text.length}/2000 · enter to read</span>
          </div>
          {parsed && (
            <div className="mt-3 space-y-2 animate-fade-in">
              <div className="text-xs text-muted">
                Found <b className="text-ink">{parsed.events.length}</b> block{parsed.events.length === 1 ? '' : 's'} ({parsed.mode} mode).
                {parsed.needs_confirmation.length > 0 && <> <b className="text-warn">{parsed.needs_confirmation.length}</b> need a quick check — look for <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-warn align-middle text-[9px] font-bold text-white">?</span>.</>}
              </div>
              {parsed.unparsed.length > 0 && (
                <Callout tone="warn" title="Couldn’t place these — add them on the grid:">
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                    {parsed.unparsed.map((u) => <li key={u.text}><span className="text-ink">“{u.text}”</span> — {u.reason}</li>)}
                  </ul>
                </Callout>
              )}
            </div>
          )}
        </div>

        <div className="card p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <select aria-label="Load demo profile" className="input w-auto py-1.5 text-sm" value={demoId} onChange={(e) => loadDemo(e.target.value)}>
              <option value="">Load demo profile…</option>
              {demos.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <select aria-label="Start from a template" className="input w-auto py-1.5 text-sm" value={profile.template_id ?? ''} onChange={(e) => loadTemplate(e.target.value)}>
              <option value="">Next semester unknown? Start from a template…</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            {profile.events.length > 0 && (
              <button className="btn-ghost text-xs" onClick={() => { setProfile((p) => ({ ...p, events: [], template_id: null })); setNeedsConfirm({}); setSel(null); }}>Clear grid</button>
            )}
            <div className="secondary-chrome ml-auto"><CampusLegend /></div>
          </div>
          {profile.template_id && (
            <div className="mb-3 text-xs text-muted">
              Dashed blocks come from the <b className="text-ink">{templates.find((t) => t.id === profile.template_id)?.name}</b> template (assumed, illustrative). “How sure are we?” samples its alternatives.
            </div>
          )}
          <div className="overflow-x-auto">
            <div className="min-w-[640px]">
              <WeeklyGrid
                events={profile.events}
                buildings={bmap}
                selected={sel}
                needsConfirm={needsConfirm}
                pxPerMin={present ? 0.62 : 0.56}
                onSelect={setSel}
                onChange={updateEvent}
                onDelete={(i) => { removeEvent(i); setSel(null); }}
                onAdd={(e) => { addEvent(e); setSel(profile.events.length); }}
              />
            </div>
          </div>
          {profile.events.length === 0 && (
            <p className="mt-3 text-center text-sm text-muted">Click any empty slot to add a block, type your week above, or load a demo profile.</p>
          )}
        </div>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-20 xl:self-start">
        {selected && sel != null && (
          <EventEditor
            key={sel}
            event={selected}
            buildings={buildings}
            confirmReasons={needsConfirm[sel]}
            onConfirm={() => confirmEvent(sel)}
            onChange={(patch) => updateEvent(sel, patch)}
            onDelete={() => { removeEvent(sel); setSel(null); }}
            onClose={() => setSel(null)}
          />
        )}
        <LivePreview onGo={() => setScreen('results')} />
        <div className="card p-4">
          <div className="mb-3 text-sm font-semibold">Constraints & what matters</div>
          <ConstraintsPanel />
        </div>
      </aside>
    </div>
  );
}

function LivePreview({ onGo }: { onGo: () => void }) {
  const { data, isLoading } = useEvaluation();
  const lmap = useListingMap();
  const top = (data?.evaluations ?? []).filter((e) => e.feasible).slice(0, 3);
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold">Right now, your week ranks</div>
        <button className="btn-ghost -mr-2 text-xs text-accent" onClick={onGo}>Full results <IconChevron size={14} /></button>
      </div>
      {isLoading && <div className="space-y-2"><Skeleton className="h-9" /><Skeleton className="h-9" /><Skeleton className="h-9" /></div>}
      {!data && !isLoading && <div className="text-sm text-muted">Add a block to your week (or load a demo) to see a ranking.</div>}
      {data && top.length === 0 && <div className="text-sm text-muted">No home fits your constraints yet.</div>}
      <ol className="space-y-1.5">
        {top.map((e) => {
          const l = lmap.get(e.listing_id);
          return (
            <li key={e.listing_id} className="flex items-center gap-2 rounded-lg bg-raised px-2.5 py-2">
              <span className="num w-5 text-sm font-bold text-accent">{e.rank}</span>
              <span className="min-w-0 flex-1 truncate text-sm" title={l?.name}>{splitName(l?.name ?? e.listing_id).title}</span>
              {l?.provenance === 'synthetic' && <SyntheticBadge className="secondary-chrome !text-[9px]" />}
              <span className="num text-sm font-semibold">{usd(e.all_in_total)}</span>
            </li>
          );
        })}
      </ol>
      <button className="btn-primary mt-3 w-full" onClick={onGo}>See what your week costs</button>
    </div>
  );
}
