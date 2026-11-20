import type { Mode, Profile, Season } from '../types';
import { useApp } from '../store/app';
import { useEvaluation } from '../api/hooks';
import { Chip, NumberField, Segmented, Slider, Toggle } from './ui/Controls';
import { IconBike, IconBus, IconSnow, IconWalk } from './ui/Icons';
import { usd, usdRate } from '../lib/format';

export const PREFERENCES: { key: string; label: string }[] = [
  { key: 'in_unit_laundry', label: 'In-unit laundry' },
  { key: 'furnished', label: 'Furnished' },
  { key: 'gym', label: 'Gym' },
  { key: 'quiet', label: 'Quiet' },
  { key: 'study_rooms', label: 'Study rooms' },
  { key: 'yard', label: 'Yard / porch' },
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function ConstraintsPanel({ compact = false }: { compact?: boolean }) {
  const profile = useApp((s) => s.profile);
  const setProfile = useApp((s) => s.setProfile);
  const { data: evalRes } = useEvaluation();
  const up = (patch: Partial<Profile>) => setProfile((p) => ({ ...p, ...patch }));
  const toggleMode = (m: Mode) => {
    const has = profile.modes.includes(m);
    const modes = (['walk', 'bus', 'bike'] as Mode[]).filter((x) => (x === m ? !has : profile.modes.includes(x)));
    up({ modes: modes.length ? modes : ['walk'] });
  };
  const derivedVot = evalRes?.value_of_time_used ?? (profile.hourly_wage ?? 15) * 0.5;
  const vot = profile.value_of_time ?? derivedVot;

  return (
    <div className="space-y-5">
      <section aria-labelledby="c-money">
        <h3 id="c-money" className="label mb-2">Budget & household</h3>
        <NumberField label="Rent cap (per person)" prefix="$" suffix="/mo" value={profile.rent_cap} step={25} min={0} max={10000} width="w-36" onChange={(v) => up({ rent_cap: v })} />
        <NumberField label="People sharing the unit" value={profile.household_size} min={1} max={10} onChange={(v) => up({ household_size: Math.max(1, Math.min(10, Math.round(v))) })} />
        <Toggle label="I need parking" checked={profile.needs_parking} onChange={(v) => up({ needs_parking: v })} />
        <Toggle label="I have a pet" checked={profile.pet} onChange={(v) => up({ pet: v })} />
      </section>

      <section aria-labelledby="c-modes">
        <h3 id="c-modes" className="label mb-2">How you get around</h3>
        <div className="flex flex-wrap gap-1.5">
          <Chip active={profile.modes.includes('walk')} onClick={() => toggleMode('walk')}><IconWalk size={14} /> Walk</Chip>
          <Chip active={profile.modes.includes('bus')} onClick={() => toggleMode('bus')} title="U-M Blue Buses + TheRide"><IconBus size={14} /> Bus</Chip>
          <Chip active={profile.modes.includes('bike')} onClick={() => toggleMode('bike')}><IconBike size={14} /> Bike</Chip>
        </div>
      </section>

      <section aria-labelledby="c-time">
        <h3 id="c-time" className="label mb-2">What your time is worth</h3>
        <Slider
          label="Value of time"
          value={vot}
          min={0}
          max={40}
          step={0.5}
          onChange={(v) => up({ value_of_time: v })}
          format={(v) => (v === 0 ? 'Cash only' : `${usdRate(v)}/h`)}
          hint={
            <span className="block space-y-0.5">
              {(evalRes?.value_of_time_derivation ?? []).map((d) => <span key={d} className="block">{d}</span>)}
            </span>
          }
        />
        <div className="mt-1 flex items-center justify-between gap-2">
          <NumberField label="Your hourly wage" prefix="$" suffix="/h" value={profile.hourly_wage ?? 15} min={0} max={200} step={0.5} onChange={(v) => up({ hourly_wage: v })} />
        </div>
        {profile.value_of_time != null && (
          <button className="btn-ghost -ml-2 text-xs" onClick={() => up({ value_of_time: null })}>Use 50% of my wage instead</button>
        )}
        {!compact && (
          <>
            <Slider label="Late-night walking weight" value={profile.late_night_weight} min={0} max={5} step={0.25} onChange={(v) => up({ late_night_weight: v })}
              format={(v) => (v === 0 ? 'Ignore' : `${v.toFixed(2)}×`)} hint="How much you mind walking or waiting outdoors after 10 PM." />
            <Slider label={<span className="inline-flex items-center gap-1"><IconSnow size={14} /> Winter aversion</span>} value={profile.winter_aversion} min={0} max={3} step={0.25}
              onChange={(v) => up({ winter_aversion: v })} format={(v) => `${v.toFixed(2)}×`} hint="Scales the extra cost of walking in winter." />
          </>
        )}
      </section>

      <section aria-labelledby="c-season">
        <h3 id="c-season" className="label mb-2">Season</h3>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented<Season> label="Season" value={profile.season} onChange={(s) => up({ season: s, month: null })}
            options={[{ value: 'fall', label: 'Fall' }, { value: 'winter', label: 'Winter' }, { value: 'spring', label: 'Summer' }]} />
          <select aria-label="Month" className="input w-auto py-1 text-sm" value={profile.month ?? ''} onChange={(e) => {
            const m = e.target.value ? Number(e.target.value) : null;
            const season: Season = m == null ? profile.season : [12, 1, 2, 3].includes(m) ? 'winter' : [9, 10, 11].includes(m) ? 'fall' : 'spring';
            up({ month: m, season });
          }}>
            <option value="">Any month</option>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </div>
      </section>

      {!compact && (
        <section aria-labelledby="c-prefs">
          <h3 id="c-prefs" className="label mb-2">Nice to have</h3>
          <div className="flex flex-wrap gap-1.5">
            {PREFERENCES.map((p) => {
              const on = (profile.preferences[p.key] ?? 0) > 0;
              return (
                <Chip key={p.key} active={on} onClick={() => {
                  const prefs = { ...profile.preferences };
                  if (on) delete prefs[p.key];
                  else prefs[p.key] = 0.7;
                  up({ preferences: prefs });
                }}>{p.label}</Chip>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-faint">Preferences nudge the score slightly; they never override cost. Rent cap {usd(profile.rent_cap)} is a hard limit.</p>
        </section>
      )}
    </div>
  );
}
