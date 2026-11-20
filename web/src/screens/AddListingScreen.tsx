import { Suspense, lazy, useMemo, useState } from 'react';
import { useAddListing, useExtractListing } from '../api/hooks';
import { extractListing as localExtract } from '../api/mockNlp';
import { useApp } from '../store/app';
import { Callout, SectionTitle, Skeleton } from '../components/ui/Misc';
import { ProvenanceBadge } from '../components/ui/Badge';
import { IconAlert, IconCheck, IconPin } from '../components/ui/Icons';
import type { ExtractListingResult, ExtractedFact, Listing } from '../types';
import { titleCase } from '../lib/format';

const MapView = lazy(() => import('../components/MapView'));

const EXAMPLE = `Sunny 3 bedroom, 1.5 bath upper flat at 812 Packard St. $2,550/month for the unit. Heat included; tenant pays DTE electric. Shared laundry in basement. Application fee: $75 per applicant. Admin fee $150. Free parking for one car. Cats ok. Available August 25, 2027. 12-month lease. Built in 1924.`;

export function AddListingScreen() {
  const [text, setText] = useState('');
  const [res, setRes] = useState<ExtractListingResult | null>(null);
  const [hi, setHi] = useState<number | null>(null);
  const [pos, setPos] = useState<{ lat: number; lon: number } | null>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [done, setDone] = useState<string | null>(null);
  const setScreen = useApp((s) => s.setScreen);
  const setSelected = useApp((s) => s.setSelected);
  const extract = useExtractListing();
  const add = useAddListing();

  const run = async () => {
    setDone(null);
    try { setRes(await extract.mutateAsync(text)); } catch { setRes(localExtract(text)); }
  };

  const patch = res?.listing_patch ?? {};
  const canAdd = !!res && pos != null && typeof patch.rent === 'number';

  const submit = async () => {
    if (!res || !pos) return;
    const today = new Date().toISOString().slice(0, 10);
    const l: Listing = {
      id: `custom-${Date.now().toString(36)}`,
      name: name.trim() || (typeof patch.address === 'string' ? patch.address : 'My pasted listing'),
      address: (patch.address as string | undefined) ?? null,
      lat: pos.lat, lon: pos.lon, neighborhood: 'Added by you',
      provenance: 'observed', verification: 'user_verified', source_url: url.trim() || 'pasted by user (no URL)', observed_on: today,
      rent: Number(patch.rent), rent_basis: patch.rent_basis === 'bed' ? 'bed' : 'unit', rent_is_range: false,
      bedrooms: typeof patch.bedrooms === 'number' ? patch.bedrooms : 1, baths: patch.baths ?? null, sqft: patch.sqft ?? null, rooms: [],
      fees: patch.fees ?? [], utilities_included: patch.utilities_included ?? [], building_type: patch.building_type ?? 'other',
      year_built: patch.year_built ?? null, heating: patch.heating ?? 'unknown', furnished: patch.furnished ?? null, in_unit_laundry: patch.in_unit_laundry ?? null,
      parking_monthly: patch.parking_monthly ?? null, pets_allowed: patch.pets_allowed ?? null, lease_term_months: patch.lease_term_months ?? 12,
      lease_start: null, amenities: [], notes: 'Added from pasted text; facts extracted with quotes.', board_included: false,
    };
    const saved = await add.mutateAsync(l);
    setDone(saved.id);
  };

  return (
    <div className="space-y-5">
      <SectionTitle eyebrow="Your own find" title="Add a listing">
        Paste a listing’s text. We pull out the facts that matter — every one linked to the exact words it came from — flag things worth checking, and add it to your ranking.
      </SectionTitle>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="space-y-4">
          <div className="card p-4">
            <label htmlFor="ltext" className="text-sm font-semibold">Listing text</label>
            <textarea id="ltext" className="input mt-2 min-h-[150px] leading-relaxed" value={text} placeholder={EXAMPLE} onChange={(e) => { setText(e.target.value); setRes(null); }} maxLength={6000} />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button className="btn-primary" disabled={!text.trim() || extract.isPending} onClick={() => void run()}>{extract.isPending ? 'Reading…' : 'Extract facts'}</button>
              <button className="btn-ghost text-xs" onClick={() => { setText(EXAMPLE); setRes(null); }}>Use example (fictional)</button>
              {res && <span className="text-xs text-faint">{res.mode} mode · {res.facts.length} facts</span>}
            </div>
          </div>
          {res && (
            <div className="card p-4">
              <div className="label mb-2">Where each fact came from</div>
              <Highlighted text={text} facts={res.facts} hi={hi} setHi={setHi} />
            </div>
          )}
          {res && res.flags.length > 0 && (
            <div className="space-y-2">
              {res.flags.map((f, i) => (
                <div key={i} className="card flex gap-3 border-warn/40 bg-warn/5 p-3">
                  <IconAlert className="mt-0.5 shrink-0 text-warn" />
                  <div className="text-sm"><div className="font-semibold text-ink">{f.rule}</div><div className="text-muted">{f.advice}</div></div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="space-y-4">
          {res ? (
            <div className="card p-4">
              <div className="label mb-2">Extracted facts</div>
              <ul className="divide-y divide-line">
                {res.facts.map((f, i) => (
                  <li key={i} onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)} className={`flex items-center gap-2 py-1.5 text-sm ${hi === i ? 'bg-accent-soft/50' : ''}`}>
                    <span className="w-40 shrink-0 text-muted">{titleCase(f.field)}</span>
                    <span className="num font-semibold text-ink">{String(f.value)}</span>
                    <ProvenanceBadge p="observed" compact className="ml-auto" />
                  </li>
                ))}
              </ul>
              {res.not_stated.length > 0 && (
                <div className="mt-3 text-xs text-muted"><b className="text-ink">Not stated</b> (ask the landlord; we’ll estimate meanwhile): {res.not_stated.map(titleCase).join(', ')}</div>
              )}
            </div>
          ) : <Skeleton className="h-40 opacity-50" />}
          <div className="card p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><IconPin size={16} /> Click the map to place it</div>
            <Suspense fallback={<Skeleton className="h-72" />}>
              <MapView height={300} schematic={false} onPick={(lat, lon) => setPos({ lat, lon })} points={pos ? [{ id: 'pick', lat: pos.lat, lon: pos.lon, label: 'New listing', kind: 'pick' }] : []} ariaLabel="Click to place the listing" />
            </Suspense>
            <div className="num mt-1 text-xs text-faint">{pos ? `${pos.lat.toFixed(5)}, ${pos.lon.toFixed(5)}` : 'No location yet'}</div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <input aria-label="Listing name" className="input" placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
              <input aria-label="Source URL" className="input" placeholder="Source URL (recommended)" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
            <button className="btn-primary mt-3 w-full" disabled={!canAdd || add.isPending} onClick={() => void submit()}>
              {add.isPending ? 'Adding…' : !res ? 'Extract facts first' : typeof patch.rent !== 'number' ? 'Rent not found in text' : !pos ? 'Place it on the map' : 'Add to my ranking'}
            </button>
            {done && (
              <div className="mt-3"><Callout tone="good" title={<span className="inline-flex items-center gap-1"><IconCheck size={14} /> Added — it’s in your ranking now.</span>}>
                <button className="btn-outline mt-2" onClick={() => { setSelected(done); setScreen('results'); }}>See where it ranks</button>
              </Callout></div>
            )}
            {add.isError && <div className="mt-2 text-xs text-bad">Couldn’t add: {String(add.error)}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Highlighted({ text, facts, hi, setHi }: { text: string; facts: ExtractedFact[]; hi: number | null; setHi: (i: number | null) => void }) {
  const parts = useMemo(() => {
    const ordered = facts.map((f, i) => ({ ...f, i })).filter((f) => f.start >= 0 && f.end <= text.length && f.end > f.start).sort((a, b) => a.start - b.start);
    const out: { t: string; i: number | null }[] = [];
    let cur = 0;
    for (const f of ordered) {
      if (f.start < cur) continue;
      if (f.start > cur) out.push({ t: text.slice(cur, f.start), i: null });
      out.push({ t: text.slice(f.start, f.end), i: f.i });
      cur = f.end;
    }
    if (cur < text.length) out.push({ t: text.slice(cur), i: null });
    return out;
  }, [text, facts]);
  return (
    <p className="whitespace-pre-wrap text-sm leading-7 text-ink">
      {parts.map((p, k) => p.i == null ? <span key={k}>{p.t}</span> : (
        <mark key={k} tabIndex={0} onMouseEnter={() => setHi(p.i)} onMouseLeave={() => setHi(null)} onFocus={() => setHi(p.i)} onBlur={() => setHi(null)}
          title={`${titleCase(facts[p.i].field)}: ${String(facts[p.i].value)}`}
          className={`rounded px-0.5 text-ink transition-colors ${hi === p.i ? 'bg-accent/30 ring-1 ring-accent' : 'bg-p-observed/15'}`}>{p.t}</mark>
      ))}
    </p>
  );
}

