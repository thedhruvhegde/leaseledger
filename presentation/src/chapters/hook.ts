import type { Chapter } from '../deck';
import { plan, ranked, listing, listingName, profile, type Evaluation, lname } from '../api';
import { PROFILE } from '../requests.js';
import { html, num, countUp, fmt, esc, said, eyebrow, icon } from '../lib';

const SRC = `api:POST /evaluate ${PROFILE.hook}`;

function receipt(e: Evaluation, role: 'cheap' | 'best') {
  const l = listing(e.listing_id);
  const rent = e.ledger.find((x) => x.key === 'rent')?.usd_month ?? l?.rent;
  const lines = e.ledger.filter((x) => x.key !== 'rent' && x.key !== 'amenity_gap' && Math.abs(x.usd_month) >= 0.5);
  const best = role === 'best';
  return html`
  <div class="card receipt ${best ? 'rc-best' : ''} enter" style="--i:${best ? 4 : 3}">
    <div class="rc-head">
      ${icon(best ? 'II' : 'I', best ? 'on' : '')}
      <span class="label">${role === 'cheap' ? 'Lowest rent on the list' : 'Cheapest actual week'}</span>
      <span class="prov">${esc(l?.provenance ?? '')}</span>
    </div>
    <h3 class="rc-name">${lname(e.listing_id)}</h3>
    <div class="rc-rent"><span>Rent</span>${num(fmt(rent, 'usd'), SRC)}</div>
    <ul class="rc-lines">
      ${lines.map((x) => html`<li><span>${esc(x.label)}</span>${num((x.usd_month >= 0 ? '+' : '') + fmt(x.usd_month, 'usd'), SRC)}</li>`)}
    </ul>
    <div class="rc-total"><span class="label">All-in, per month</span>${countUp(e.all_in_total, 'usd', SRC, 'rc-big')}</div>
    <div class="rc-foot micro">${num(`#${e.rank}`, SRC)} by all-in cost · ${num(fmt(e.commute.weekly_min / 60, 'hours'), SRC)} door-to-door per week</div>
  </div>`;
}

export const hook: Chapter = {
  id: 'hook',
  title: 'The decision',
  numeral: 'I',
  gist: 'Lowest rent is not the cheapest week',
  budget: 22,
  deps: ['listings', `eval:${PROFILE.hook}`],
  render() {
    const ev = plan[`eval:${PROFILE.hook}`];
    const top = ranked(ev);
    const prof = profile(PROFILE.hook);
    let body: string;
    if (!top.length) {
      body = html`<div class="pending enter" style="--i:2"><b>Waiting for the engine</b>The receipts are computed live by the API (or its snapshot). Nothing is pre-typed.</div>`;
    } else {
      const rentOf = (e: Evaluation) => e.ledger.find((x) => x.key === 'rent')?.usd_month ?? Infinity;
      const cheapest = [...top].sort((a, b) => rentOf(a) - rentOf(b))[0];
      const best = top[0];
      if (cheapest.listing_id === best.listing_id) {
        body = html`<div class="hook-grid">${receipt(best, 'best')}<div class="pending enter" style="--i:3"><b>Here the lowest rent also wins</b>For this student the cheapest rent is also the cheapest week — the engine says so instead of forcing a story.</div></div>`;
      } else {
        const gapRent = Math.abs(rentOf(cheapest) - rentOf(best));
        const gapAll = cheapest.all_in_total - best.all_in_total;
        body = html`
        <div class="hook-grid">
          ${receipt(cheapest, 'cheap')}
          <div class="hook-mid enter" style="--i:5">
            <div class="vs-b"><div class="label">Rent says</div><div class="vs-n">${num(fmt(gapRent, 'usd'), SRC)}</div><div class="micro">cheaper</div></div>
            <div class="vs-rule"></div>
            <div class="vs-b"><div class="label">The week says</div><div class="vs-n ink">${num(fmt(gapAll, 'usd'), SRC)}</div><div class="micro">more, every month</div></div>
          </div>
          ${receipt(best, 'best')}
        </div>`;
      }
    }
    return html`
      <div class="geo vline"></div>
      ${eyebrow(this.numeral, 'The decision')}
      <h1 class="hook-title enter" style="--i:1">Lowest rent <em class="neq">≠</em> cheapest week.</h1>
      <p class="sub enter" style="--i:2">Same student — ${said(prof?.name ?? 'demo student', 'api:GET /demo-profiles')} — same listings, priced on this fall’s real bus timetables.</p>
      <div class="grow">${body}</div>`;
  },
  notes() {
    const top = ranked(plan[`eval:${PROFILE.hook}`]);
    return `<p><b>I · The decision (22 s).</b> "Listings tell you rent. Your life is a week." Point at the left receipt: lowest rent on the list. Then the right one: what the week actually costs once fees, utilities and every bus/walk trip of the routine are priced.</p>
      <p>Live numbers — #1 is <b>${top[0] ? listingName(top[0].listing_id) : '…'}</b>. Don't read every line; land the two totals.</p>
      <p>Transition: "So why do students get this wrong?"</p>`;
  },
};
