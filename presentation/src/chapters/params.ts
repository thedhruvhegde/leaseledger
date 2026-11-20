// "What every home is ranked on": the parameter ledger. Nine rows, each read from GET /methods params
// (value, low–high band, provenance, source). Nothing here is typed in: values, ranges and the study count come
// from the API (the snapshot stands in when it is down); sources are author-year chips from citations.ts.
import type { Chapter } from '../deck';
import { plan } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, esc } from '../lib';
import { citeTag } from '../citations';
import { param, g } from './engine';

const MP = 'api:GET /methods params';
type Row = { key: string; label: string; fmt: (x: number) => string; src: () => string };

const usd = (x: number) => '$' + (Number.isInteger(x) ? String(x) : x.toFixed(2));

const ROWS: Row[] = [
  { key: 'value_of_time.default_vot_usd_h', label: 'Value of time', fmt: (x) => usd(x) + '/h',
    src: () => {
      const f = param('value_of_time.fraction_of_wage')?.value, w = param('value_of_time.default_student_wage_usd_h')?.value;
      return html`${f != null && w != null ? html`${num(g(f) + ' × ' + usd(w) + ' wage', `${MP} value_of_time.fraction_of_wage × default_student_wage_usd_h`)} · ` : ''}${citeTag('usdot')}`;
    } },
  { key: 'time_multipliers.walk', label: 'Walk & wait', fmt: (x) => g(x) + '×', src: () => html`${citeTag('abrantes')} · meta-analyses` },
  { key: 'time_multipliers.transfer_penalty_min', label: 'Each transfer', fmt: (x) => '+' + g(x) + ' min', src: () => citeTag('garcia') },
  { key: 'time_multipliers.schedule_delay_early_per_min', label: 'Early arrival', fmt: (x) => g(x) + '×', src: () => citeTag('small') },
  { key: 'weather.bad_day_walk_multiplier', label: 'Snow-day walk', fmt: (x) => g(x) + '×', src: () => html`× snow-cover days · ${citeTag('noaa')}` },
  { key: 'late_night.usd_per_outdoor_min', label: 'Late-night outdoors', fmt: (x) => usd(x) + '/min', src: () => html`no study prices it` },
  { key: 'engine.coop_labor_hours_week', label: 'Co-op work shifts', fmt: (x) => g(x) + ' h/wk', src: () => html`when a listing doesn’t say` },
  { key: 'engine.food_offset_usd_person_month', label: 'Meals included', fmt: (x) => usd(x) + '/mo', src: () => html`grocery offset` },
  { key: 'gas_usd_per_therm', label: 'Heating gas', fmt: (x) => usd(x) + '/therm', src: () => html`× degree days × intensity · ${citeTag('eia')}` },
];

const range = (r: Row, p: any) => {
  if (p.low == null || p.high == null || p.low === p.high) return '';
  const a = r.fmt(p.low), b = r.fmt(p.high).replace(/^\+/, '');
  // drop the shared unit on the low end: "1.5–2×", "$4.80–$15/h"
  const unit = b.match(/[^\d.]*$/)?.[0] ?? '';
  return (unit && a.endsWith(unit) ? a.slice(0, a.length - unit.length) : a) + '–' + b;
};

const CRIT: Record<string, string> = { cash: 'cash', time: 'weekly hours', late_night: 'late-night minutes', fit: 'fit' };

export const params: Chapter = {
  id: 'params',
  title: 'What every home is ranked on',
  budget: 14,
  deps: ['methods', `eval:${PROFILE.hook}`],
  render() {
    const crit = Object.keys(plan[`eval:${PROFILE.hook}`]?.manifest?.weighted_criteria_view?.weights ?? {});
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">What every home is <em>ranked on.</em></h2>
      <table class="pl enter" style="--i:2">
        <thead><tr><th>parameter</th><th class="r">value</th><th class="r">range</th><th>basis</th><th>source</th></tr></thead>
        <tbody>
          ${ROWS.map((r) => {
            const p = param(r.key);
            if (!p) return '';
            const rg = range(r, p);
            return html`<tr class="pl-${esc(p.provenance)}">
              <td class="pl-name">${esc(r.label)}</td>
              <td class="r pl-v">${num(r.fmt(p.value), `${MP} ${r.key}.value`)}</td>
              <td class="r pl-rg">${rg ? num(rg, `${MP} ${r.key}.low/high`) : ''}</td>
              <td class="pl-prov"><i></i>${esc(p.provenance)}</td>
              <td class="pl-src">${r.src()}</td>
            </tr>`;
          })}
        </tbody>
      </table>
      ${crit.length ? html`<p class="pl-crit enter" style="--i:3">Ranked on ${crit.map((k) => html`<b>${esc(CRIT[k] ?? k)}</b>`).join(' · ')}</p>` : ''}`;
  },
  notes() {
    const row = (k: string) => { const p = param(k); return p ? `${p.value} [${p.low}–${p.high}], ${p.provenance}` : '—'; };
    return `<p><b>What every home is ranked on (14 s).</b> Point at the basis column: observed, estimated or assumed — we say which.</p>
      <p>Value of time ${row('value_of_time.default_vot_usd_h')} = 0.5 × $15 student wage (USDOT 2016 guidance: half the wage for local personal travel). It is the dominant input — the app shows hours first and lets you set it, and the breakeven says where it would flip.</p>
      <p>Walk &amp; wait ${row('time_multipliers.walk')} (Abrantes &amp; Wardman 2011 UK meta-analysis, below 2; a newer worldwide meta-analysis by Wardman et al. of 606 studies supports 1.5–1.75, exact citation still to confirm; USDOT would say 2.0). Transfer ${row('time_multipliers.transfer_penalty_min')} min (García-Martínez 2018, scaled down for short campus transfers). Early arrival ${row('time_multipliers.schedule_delay_early_per_min')} (Small 1982). Snow-day walk ${row('weather.bad_day_walk_multiplier')}, weighted by NOAA 1991–2020 snow-cover days (21 of 31 January days).</p>
      <p>Assumed, and labelled so: late-night $/outdoor minute ${row('late_night.usd_per_outdoor_min')}, co-op shifts ${row('engine.coop_labor_hours_week')} h/wk, meals offset ${row('engine.food_offset_usd_person_month')} $/mo. Utilities = NOAA heating degree days × EIA RECS intensity by building type × gas/electric price (${row('gas_usd_per_therm')} $/therm).</p>
      <p>Every range above is what the Monte Carlo samples. Besides the dollar total, the app shows the four criteria separately (cash, weekly hours, late-night minutes, fit) and the Pareto front, so nobody has to trust our weights.</p>`;
  },
};
