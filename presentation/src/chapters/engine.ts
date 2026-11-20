// "The engine": the whole pipeline as one vertical diagram — timetables → Connection Scan → day tours →
// generalized cost → monthly ledger → Monte Carlo + closed-form breakeven → envy-free maximin LP.
// Every constant inside an equation is read from GET /methods params (or /manifest, /robustness) at render time,
// so the KaTeX is data-bound too; the right column carries one measured number per stage.
import type { Chapter } from '../deck';
import { plan } from '../api';
import { html, num, esc, fmt } from '../lib';
import { citeTag } from '../citations';
import { tex } from './how';

const MP = 'api:GET /methods params';
/** A parameter row from GET /methods ({key, value, low, high, provenance, source}). */
export const param = (key: string): any => (plan.methods?.params ?? []).find((p: any) => p.key === key);
export const pv = (key: string): number | undefined => param(key)?.value;
/** Trim trailing zeros: 1.75 → "1.75", 10 → "10", 0.50 → "0.5". */
export const g = (x: number | undefined, d = 2) => (x == null ? '?' : String(Number(x.toFixed(d))));

type Stage = { name: string; cite?: string; sub?: string; eq: () => string; stat: () => string };

const STAGES: Stage[] = [
  {
    name: 'Connection Scan', cite: 'csa',
    eq: () => String.raw`LV[u] \leftarrow \max\!\big(LV[u],\ d_c\big)\quad\text{if } a_c \le LA[x]`,
    stat: () => {
      const lb = plan.manifest?.provider?.labels, step = plan.manifest?.provider?.params?.slot_step_min;
      if (!lb) return '';
      return html`${num(fmt(lb.scans, 'int'), 'api:GET /manifest provider.labels.scans')} backward scans, one per building × ${num(step + '-min', 'api:GET /manifest provider.params.slot_step_min')} slot · <b>${num(lb.ms_per_scan.toFixed(2) + ' ms', 'api:GET /manifest provider.labels.ms_per_scan')}</b> each`;
    },
  },
  {
    name: 'Day tours', cite: 'kobus',
    eq: () => String.raw`G_{\mathrm{day}} = \textstyle\sum_i \min\!\big\{\,G(e_i\!\to\!e_{i+1}),\ \ G(e_i\!\to\!H) + G(H\!\to\!e_{i+1})\,\big\}`,
    stat: () => html`home only if the gap leaves <b>${num(g(pv('schedule.home_return_min_gap')) + ' min', MP + ' schedule.home_return_min_gap')}</b> there`,
  },
  {
    name: 'Felt minutes', cite: 'abrantes',
    eq: () => String.raw`G = t_{\mathrm{ride}} + \varphi(m)\big(${g(pv('time_multipliers.walk'))}\,t_{\mathrm{walk}} + ${g(pv('time_multipliers.wait'))}\,t_{\mathrm{wait}}\big) + ${g(pv('time_multipliers.transfer_penalty_min'))}\,n_{\mathrm{xfer}} + ${g(pv('time_multipliers.schedule_delay_early_per_min'))}\,t_{\mathrm{early}}`,
    stat: () => {
      // expected January snow factor: 1 + (b − 1) · snow-cover days / 31 (NOAA normals)
      const b = pv('weather.bad_day_walk_multiplier'), sd = pv('weather.monthly_snow_cover_days.1');
      if (b == null || sd == null) return '';
      return html`<b>${num('φ(Jan) = ' + (1 + (b - 1) * sd / 31).toFixed(2), 'derived: GET /methods weather.bad_day_walk_multiplier × NOAA snow-cover days / 31')}</b> from NOAA snow-cover days`;
    },
  },
  {
    name: 'Monthly ledger', cite: 'usdot',
    eq: () => String.raw`\text{all-in} = \text{cash} + v\,\tfrac{G_{\mathrm{week}}}{60}\,\omega + \text{late night} + v\,h_{\mathrm{co\text{-}op}}\,\omega`,
    stat: () => html`<b>${num(fmt(pv('value_of_time.default_vot_usd_h') ?? 0, 'usdh'), MP + ' value_of_time.default_vot_usd_h')}</b> default · ${num('ω = ' + g(pv('calendar.weeks_per_month'), 3), MP + ' calendar.weeks_per_month')} wk/mo`,
  },
  {
    name: 'How sure', sub: 'seeded Monte Carlo, closed form',
    eq: () => String.raw`\hat p_\ell = \tfrac{1}{S}\textstyle\sum_{s}\mathbf{1}\!\left[\ell = \arg\min_j \mathrm{score}_j(\theta_s)\right]\qquad v^{*} = \Delta\,\text{cash}\,/\,\Delta\,\text{hours}`,
    stat: () => {
      const r = plan.robustness;
      if (!r?.samples) return '';
      return html`<b>${num(fmt(r.samples, 'int'), 'api:POST /robustness samples')}</b> sampled semesters · the breakeven needs no simulation`;
    },
  },
  {
    name: 'Roommates', cite: 'gal',
    eq: () => String.raw`\max_{\pi}\ \min_p\ u_p\quad\text{s.t.}\ \ u_p = W_{p\sigma(p)} - \pi_{\sigma(p)} \ge W_{p\sigma(q)} - \pi_{\sigma(q)},\ \ \textstyle\sum_r \pi_r = R`,
    stat: () => html`envy-free, worst-off roommate <b>best off</b> · one LP`,
  },
];

export const engine: Chapter = {
  id: 'engine',
  title: 'The engine',
  budget: 22,
  deps: ['methods', 'manifest', 'robustness'],
  render() {
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">The engine, <em>end to end.</em></h2>
      <ol class="en-flow grow" style="--n:${STAGES.length}">
        ${STAGES.map((s, i) => html`<li class="en-row enter" style="--i:${i + 2}">${i < STAGES.length - 1 ? html`<i class="en-line"></i>` : ''}
            <div class="en-name"><i class="en-dot"></i><div><span>${esc(s.name)}</span>${s.cite ? html`<div class="en-cite">${citeTag(s.cite)}</div>` : s.sub ? html`<div class="en-cite"><span class="cite">${esc(s.sub)}</span></div>` : ''}</div></div>
            <div class="en-body"><div class="en-eq" data-src="${MP}">${tex(s.eq(), false)}</div><div class="en-stat">${s.stat()}</div></div>
          </li>`)}
      </ol>`;
  },
  notes() {
    const lb = plan.manifest?.provider?.labels;
    return `<p><b>The engine (22 s) — attention to detail.</b> Read it top to bottom; don't read the equations aloud.</p>
      <p>1 · Connection Scan (Dibbelt et al. 2018), run <i>backwards</i>: for every campus building and every 5-minute arrive-by slot one pass over the day's connections gives, for every stop, the latest time you can board and still make it. Adding the walk from each apartment gives door-to-door minutes for <b>every home at once</b>${lb ? ` — ${lb.scans.toLocaleString('en-US')} scans at ${lb.ms_per_scan} ms each` : ''}.</p>
      <p>2 · Day tours: home → events → home; go home between events only when that is cheaper in felt minutes and leaves at least ${g(pv('schedule.home_return_min_gap'))} min at home (Kobus et al. 2015).</p>
      <p>3 · Generalized cost: ride minutes 1×, walk and wait ${g(pv('time_multipliers.walk'))}× (Wardman meta-analysis), ×φ(month) on snow-cover days (NOAA), +${g(pv('time_multipliers.transfer_penalty_min'))} min per transfer, ${g(pv('time_multipliers.schedule_delay_early_per_min'))}× for timetable-forced early arrival (Small 1982).</p>
      <p>4 · Monthly ledger: cash (rent, fees, seasonal utilities, insurance, parking, minus the meal offset) + hours × value of time (USDOT: half the wage) + late-night outdoor minutes + co-op work hours. ω = weeks per month.</p>
      <p>5 · How sure: ${plan.robustness?.samples ?? 2000} seeded draws over every declared range (log-uniform value of time); p̂ = share of semesters each home wins. Because score = K + v·T is linear in v, the breakeven v* = Δcash / Δhours is exact — no simulation needed.</p>
      <p>6 · Roommates: welfare-maximising room assignment (Hungarian), then an LP (HiGHS) for the envy-free rent split that maximises the worst-off roommate's utility (Gal et al. 2017). Not strategy-proof (Dufton & Larson 2011) — on the Limits slide.</p>`;
  },
};
