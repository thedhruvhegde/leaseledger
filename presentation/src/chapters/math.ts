// Appendix (press A, or the link on "How sure are we"): the math under the hood, all from /api/advanced/*.
// (a) Sobol total-order indices with 90% CIs   (ross-kerrytown-job: University Towers vs its runner-up)
// (b) τ(t) sawtooth from the #1 home, with shaded ∫τ dt and bus "cliffs"   (north-engineer)
// (c) CVaR "safe" pick vs expected-cost pick and the price of safety   (north-engineer)
// (d) EVPI of knowing next semester: $0 for the stock demos (stated honestly) + the music-template case if the API answers.
// Formulas are the definitions in ledger/engine/advanced/README.md; every number is from the API response.
import type { Chapter } from '../deck';
import { plan, sname } from '../api';
import { MUSIC_VOT } from '../requests.js';
import { html, num, said, esc, fmt, eyebrow } from '../lib';
import { tex } from './how';

const S = 'api:POST /advanced/sensitivity', PR = 'api:POST /advanced/profile', RK = 'api:POST /advanced/risk', EV = 'api:POST /advanced/evpi';
const EQ = {
  sobol: String.raw`S_{T,i} = \frac{\mathbb{E}_{X_{\sim i}}\big[\operatorname{Var}_{X_i}(Y \mid X_{\sim i})\big]}{\operatorname{Var}(Y)},\quad Y = C_a - C_b`,
  profile: String.raw`\tau(t) = (t - \beta) - \mathrm{dep}^*(t),\qquad \bar\tau = \tfrac{1}{T}\!\int \tau(t)\,dt`,
  risk: String.raw`\mathrm{CVaR}_{\alpha}(X) = \min_z\; z + \frac{\mathbb{E}[(X-z)^+]}{1-\alpha}`,
  evpi: String.raw`\mathrm{EVPI} = \mathbb{E}_s\big[C(\hat h,s)\big] - \mathbb{E}_s\big[\min_h C(h,s)\big]`,
};
const ttl = (n: string, t: string, k: string) => html`<div class="mt-h"><span class="card-icon">${n}</span><h3 class="sec-h">${t}</h3><span class="label">${k}</span></div>`;
const clock = (m: number) => { const h = Math.floor(m / 60) % 24, r = Math.round(m % 60); const h12 = ((h + 11) % 12) + 1; return `${h12}:${String(r).padStart(2, '0')}${h < 12 ? 'am' : 'pm'}`; };
const pend = (what: string) => html`<div class="pending"><b>Pending</b>POST /api/advanced/${esc(what)} has not answered (no live API and no snapshot).</div>`;

function sobolCard() {
  const d = plan['adv:sensitivity'];
  if (!d?.indices?.length) return pend('sensitivity');
  const rows = [...d.indices].filter((r: any) => typeof r.ST === 'number').sort((a: any, b: any) => b.ST - a.ST);
  const top = rows[0];
  const max = Math.max(...rows.map((r: any) => Math.max(r.ST, r.ST_ci90?.[1] ?? 0)), 0.05);
  const ci = (c: any) => (Array.isArray(c) ? `${fmt(c[0], 'pct')}–${fmt(c[1], 'pct')}` : '');
  return html`
    <div class="sob-head"><span class="sob-big">${num(fmt(top.ST, 'pct'), S + ' ST')}</span>
      <span>of the uncertainty in this decision is <b>${esc(top.label)}</b><br/><span class="small">${num('90% CI ' + ci(top.ST_ci90), S + ' ST_ci90')} · ${sname(d.a)} vs ${sname(d.b)}</span></span></div>
    <div class="sob">${rows.slice(0, 3).map((r: any) => html`<div class="sob-r"><span class="sob-n">${esc(r.label)}</span>
      <span class="sob-t"><i class="s1" style="width:${(r.ST / max) * 100}%"></i>${Array.isArray(r.ST_ci90) ? html`<i class="sob-ci" style="left:${(r.ST_ci90[0] / max) * 100}%;width:${(Math.max(0.004, r.ST_ci90[1] - r.ST_ci90[0]) / max) * 100}%"></i>` : ''}</span>
      <span class="sob-v">${num(fmt(r.ST, 'pct'), S + ' ST')}</span></div>`)}</div>
    <div class="small">Total-order indices of the cost gap; bars: ${num('90%', S + ' ST_ci90 level')} bootstrap CI. #1 flips in ${num(fmt(d.p_flip, 'pct1'), S + ' p_flip')} of draws.</div>`;
}

function sawCard() {
  const d = plan['adv:profile'];
  const series: any[] = d?.series?.length ? d.series : d?.t ? [d] : [];
  if (!series.length) return pend('profile');
  // the #1 home's most frequent destinations are often a walk (flat τ); show the destination with the most bus cliffs
  const s = [...series].sort((a, b) => (b.cliffs?.length ?? 0) - (a.cliffs?.length ?? 0) || (b.sd_tau ?? 0) - (a.sd_tau ?? 0))[0];
  const primary = series[0];
  if (!s.t?.length) return pend('profile');
  // zoom to two hours around the biggest cliff so the sawtooth is legible
  const big = [...(s.cliffs ?? [])].sort((a: any, b: any) => b.jump_min - a.jump_min)[0];
  const keep = (t: number) => !big || (t >= big.t - 90 && t <= big.t + 30);
  const idx = s.t.map((_: number, i: number) => i).filter((i: number) => keep(s.t[i]));
  const T: number[] = idx.map((i: number) => s.t[i]), Y: number[] = idx.map((i: number) => s.tau[i]);
  const W = 760, H = 150;
  const t0 = T[0], t1 = T[T.length - 1], ymax = Math.max(...Y) * 1.08, ymin = Math.max(0, Math.min(...Y) * 0.8);
  const x = (t: number) => ((t - t0) / (t1 - t0)) * W, y = (v: number) => H - ((v - ymin) / (ymax - ymin)) * H;
  const line = T.map((t, i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)} ${y(Y[i]).toFixed(1)}`).join('');
  const cl = [...(s.cliffs ?? [])].filter((c: any) => keep(c.t_earlier)).sort((a: any, b: any) => b.jump_min - a.jump_min);
  const c0 = cl[0];
  const ticks = [t0, t0 + (t1 - t0) / 3, t0 + (2 * (t1 - t0)) / 3, t1].map((t) => Math.round(t / 15) * 15);
  const sawLabel = html`From ${sname(s.listing_id ?? d.listing_id)} to ${said(s.event_label, PR)} (${said(({ M: 'Mon', T: 'Tue', W: 'Wed', R: 'Thu', F: 'Fri', S: 'Sat', U: 'Sun' } as Record<string, string>)[s.day] ?? s.day, PR)})`;
  return html`
    <div class="small saw-sub">${sawLabel}${primary !== s ? html` — the most frequent destination, ${said(primary.event_label, PR)}, is a flat walk from here` : ''}</div>
    <svg class="saw" viewBox="-6 -34 ${W + 12} ${H + 70}" role="img" aria-label="Door-to-door time by class start time">
      ${[0.25, 0.5, 0.75].map((f) => `<line x1="0" x2="${W}" y1="${H * f}" y2="${H * f}" class="saw-grid"/>`).join('')}
      <path d="${line}L${W} ${H}L0 ${H}Z" class="saw-area"/>
      <path d="${line}" class="saw-line" pathLength="1"/>
      <line x1="0" x2="${W}" y1="${H}" y2="${H}" class="saw-axis"/>
      ${ticks.map((t) => html`<text x="${x(t)}" y="${H + 26}" class="saw-t" text-anchor="middle" data-src="${PR} t">${clock(t)}</text>`)}
      ${cl.map((c: any) => html`<circle cx="${x(c.t_earlier)}" cy="${y(c.tau_earlier)}" r="5" class="saw-cliff"/>`)}
      ${c0 ? html`<text x="${Math.min(W - 10, Math.max(10, x(c0.t_earlier)))}" y="${y(c0.tau_earlier) - 14}" class="saw-ann" text-anchor="${x(c0.t_earlier) > W / 2 ? 'end' : 'start'}" data-src="${PR} cliffs[]">class at ${clock(c0.t)}: ${Math.round(c0.tau)} min · at ${clock(c0.t_earlier)}: ${Math.round(c0.tau_earlier)} min</text>` : ''}
    </svg>
    <div class="adv-k"><span>mean τ ${num(Number(s.mean_tau).toFixed(1) + ' min', PR + ' mean_tau')}</span><span>∫τ dt ${num(fmt(s.integral_tau, 'int') + ' min²', PR + ' integral_tau')}</span><span>${num(String((s.cliffs ?? []).length), PR + ' cliffs')} bus cliffs all day</span></div>`;
}

function riskCard() {
  const d = plan['adv:risk'];
  if (!d?.picks) return pend('risk');
  const H = (id: string) => d.homes.find((h: any) => h.id === id);
  const e = H(d.picks.expected), s = H(d.picks.safe_cvar);
  const pct = Math.round((d.alpha ?? 0.9) * 100);
  const same = d.picks.expected === d.picks.safe_cvar;
  const cell = (h: any, lab: string, dark: boolean) => html`<div class="rk ${dark ? 'on' : ''}"><div class="rk-l">${lab}</div><div class="rk-n">${sname(h.id)}</div>
    <div class="rk-v"><span>mean</span>${num(fmt(h.mean, 'usd'), RK + ' mean')}</div><div class="rk-v"><span>worst ${num(String(100 - pct) + '%', RK + ' alpha')} avg</span>${num(fmt(h.cvar, 'usd'), RK + ' cvar')}</div></div>`;
  return html`
    <div class="rk-pair">${cell(e, 'cheapest on average', false)}${same ? '' : cell(s, 'safest (lowest CVaR)', true)}</div>
    <div class="small">${same ? 'The average-cost pick is also the safe pick here.' : html`Price of safety: ${num(fmt(s.mean - e.mean, 'usd2') + '/mo', RK + ' mean diff')} more on average buys a ${num(fmt(e.cvar - s.cvar, 'usd') + '/mo', RK + ' cvar diff')} lower bad-semester tail. Minimax regret picks ${sname(d.picks.minimax_regret)}.`}</div>`;
}

function evpiCard() {
  const d = plan['adv:evpi'], m = plan['adv:evpiMusic'];
  if (!d) return pend('evpi');
  const pick = d.homes?.find((h: any) => h.id === d.expected_cost_pick);
  return html`
    <div class="evpi">${num(fmt(d.evpi_usd_month, 'usd2'), EV + ' evpi_usd_month')}<span>/mo</span></div>
    <div class="small">North Campus engineer: ${sname(d.expected_cost_pick)} is cheapest in ${num(fmt(pick?.best_in_share ?? 0, 'pct'), EV + ' best_in_share')} of ${num(String(d.semesters), EV + ' semesters')} sampled semesters — <b>your choice is robust to not knowing next semester.</b></div>
    ${m?.available !== false && m?.evpi_usd_month != null ? html`<div class="ev-music">
      <div class="small">Where it does matter — music / art & design template, time valued at ${num('$' + MUSIC_VOT + '/h', 'param:MUSIC_VOT')}:</div>
      <div class="ev-m"><b>${num(fmt(m.evpi_usd_month, 'usd2') + '/mo', EV + ' music evpi_usd_month')}</b> ${Array.isArray(m.evpi_ci90) ? num(`90% CI ${fmt(m.evpi_ci90[0], 'usd2')}–${fmt(m.evpi_ci90[1], 'usd2')}`, EV + ' music evpi_ci90') : ''}</div>
      ${m.expected_cost_pick !== m.deterministic_pick ? html`<div class="small">…and averaging over semesters changes the best home: ${sname(m.deterministic_pick)} → <b>${sname(m.expected_cost_pick)}</b>.</div>` : ''}
    </div>` : html`<div class="small">(The music-template case is shown only when the API computes it live.)</div>`}`;
}

export const math: Chapter = {
  id: 'math',
  title: 'The math under the hood',
  numeral: 'A',
  budget: 0,
  appendix: true,
  steps: 4,
  deps: ['adv:profile', 'adv:sensitivity', 'adv:evpi', 'adv:evpiMusic', 'adv:risk', 'listings'],
  render() {
    return html`
      ${eyebrow('A', 'Appendix · for Q&A', html`<span class="micro">click a card or press → for its equation</span>`)}
      <h2 class="mt-title">The math under the hood.</h2>
      <div class="math-grid">
        <div class="card">${ttl('I', 'What drives the decision', 'Sobol')}${sobolCard()}<div class="eq hide-until" data-step="1">${tex(EQ.sobol)}</div></div>
        <div class="card">${ttl('II', 'Door-to-door time is a sawtooth', 'τ(t)')}${sawCard()}<div class="eq hide-until" data-step="2">${tex(EQ.profile)}</div></div>
        <div class="card">${ttl('III', 'Safe pick vs cheapest on average', 'CVaR')}${riskCard()}<div class="eq hide-until" data-step="3">${tex(EQ.risk)}</div></div>
        <div class="card">${ttl('IV', 'Value of knowing your schedule', 'EVPI')}${evpiCard()}<div class="eq hide-until" data-step="4">${tex(EQ.evpi)}</div></div>
      </div>`;
  },
  notes() {
    return `<p><b>Appendix — Q&A only.</b> → reveals each card's equation.</p>
      <p><b>Sobol:</b> "For the Ross student, most of the uncertainty in Towers-vs-runner-up is your value of time — that's why VOT is a slider, not a constant."</p>
      <p><b>τ(t):</b> "From this house, a class a few minutes earlier means you just missed the bus — the cliff is annotated." The most frequent destinations from the #1 home are walks (flat), so we show the bus destination.</p>
      <p><b>CVaR:</b> "On average Escher is cheaper; in your worst 10% of semesters Towers costs less. The price of that insurance is on the card."</p>
      <p><b>EVPI:</b> "$0 for our demo students: the same home wins in every sampled semester, so you don't need to wait for your schedule." Music template case: ~$10–13/mo, and averaging over semesters changes the best home.</p>`;
  },
};
