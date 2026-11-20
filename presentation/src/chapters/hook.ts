// I · The decision: two homes, two all-in totals, two real weeks of trips. Receipt lines live in the notes and the app.
import type { Chapter } from '../deck';
import { plan, ranked, listingName, type Evaluation, lname } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, countUp, fmt } from '../lib';
import { base, loadBase, bboxOf, routeLayer, streets } from '../routemap';

const SRC = `api:POST /evaluate ${PROFILE.hook}`;
const rentOf = (e: Evaluation) => e.ledger.find((x) => x.key === 'rent')?.usd_month ?? Infinity;

function miniMap(ev: any, both: any[], mute: boolean) {
  const b = base;
  if (!b || !ev) return html`<div class="hk-map img-ph"></div>`;
  const bb = bboxOf(b, both);
  const pad = 26, w = bb.x1 - bb.x0 + pad * 2, h = bb.y1 - bb.y0 + pad * 2;
  return html`<svg class="hk-map" viewBox="${bb.x0 - pad} ${bb.y0 - pad} ${w} ${h}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    ${streets(b)}${routeLayer(b, ev, mute ? 'mute' : '', 22)}</svg>`;
}

function side(e: Evaluation, ev: any, both: any[], best: boolean, i: number) {
  return html`
  <div class="hk-side ${best ? 'best' : 'cheap'} enter" style="--i:${i}">
    <div class="plate-img hk-plate">${miniMap(ev, both, !best)}</div>
    <div class="hk-who"><span class="hk-name">${lname(e.listing_id)}</span><span class="hk-rent">rent ${num(fmt(rentOf(e), 'usd'), SRC)}${best ? '' : html` <b class="hk-low">lowest</b>`}</span></div>
    <div class="hero md ${best ? '' : 'mute'}">${countUp(e.all_in_total, 'usd', SRC)}</div>
    <div class="hk-cap">a month, all-in · ${num(fmt(e.commute.weekly_min / 60, 'hours'), SRC)} of trips a week</div>
  </div>`;
}

export const hook: Chapter = {
  id: 'hook',
  title: 'The decision',
  budget: 26,
  deps: ['listings', `eval:${PROFILE.hook}`, 'routes'],
  render() {
    const top = ranked(plan[`eval:${PROFILE.hook}`]);
    let body: string;
    if (!top.length) {
      body = html`<div class="pending enter" style="--i:2"><b>Waiting for the engine</b>Computed live by the API (or its snapshot). Nothing is pre-typed.</div>`;
    } else {
      const cheapest = [...top].sort((a, b) => rentOf(a) - rentOf(b))[0];
      const best = top[0];
      if (cheapest.listing_id === best.listing_id) {
        body = html`<div class="pending enter" style="--i:2"><b>Here the lowest rent also wins</b>The engine says so instead of forcing a story.</div>`;
      } else {
        const r = plan.routes;
        const evA = r?.a?.listing_id === best.listing_id ? r.a : null, evB = r?.b?.listing_id === cheapest.listing_id ? r.b : null;
        const both = [evA, evB].filter(Boolean);
        body = html`
        <div class="hk-grid">
          ${side(cheapest, evB, both, false, 2)}
          <div class="hk-vs enter" style="--i:4"><span>vs</span></div>
          ${side(best, evA, both, true, 3)}
        </div>
        <p class="hk-line enter" style="--i:5">The lowest rent costs <b>${num(fmt(cheapest.all_in_total - best.all_in_total, 'usd'), SRC)} more</b> every month.</p>`;
      }
    }
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">Lowest rent isn’t the <em>cheapest week.</em></h2>
      <div class="grow hk-body">${body}</div>`;
  },
  mount(el) {
    if (!base) loadBase().then((b) => b && el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
  },
  notes() {
    const top = ranked(plan[`eval:${PROFILE.hook}`]);
    const lines = (e?: Evaluation) => e ? e.ledger.filter((x) => Math.abs(x.usd_month) >= 0.5 && x.key !== 'amenity_gap').map((x) => `${x.label} ${fmt(x.usd_month, 'usd')}`).join(' · ') : '…';
    const cheap = [...top].sort((a, b) => rentOf(a) - rentOf(b))[0];
    return `<p><b>I · The decision (26 s).</b> "Same student — a North Campus engineer — same listings, priced on this fall's real bus timetables." Left: the lowest rent on the list. Right: the cheapest actual week. The maps are each home's real week of trips (thick = bus, thin = walking).</p>
      <p>Land the two totals and the gap. Don't read the receipt lines; if asked:</p>
      <p><b>${cheap ? listingName(cheap.listing_id) : '…'}</b>: ${lines(cheap)}</p>
      <p><b>${top[0] ? listingName(top[0].listing_id) : '…'}</b> (#1): ${lines(top[0])}</p>
      <p>Transition: "So why do students get this wrong?"</p>`;
  },
};
