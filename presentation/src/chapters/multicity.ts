// Rapid fire: "thousands of futures" on 7 real transit networks (presentation/data/multicity.json +
// presentation/media/multicity/*.gif, from ledger/multicity — methods in analysis/multicity/METHODS.md).
// Presented as catalogue plates: each GIF sits in a hairline frame (white multiplied into the stone canvas),
// with a catalogue caption; then the all-city plate; then a catalogue grid of the final frames with a stats cluster.
// Every number comes from multicity.json; the honesty footer is derived from its feed statuses and caveats.
import type { Chapter } from '../deck';
import { html, num, said, esc, reducedMotion, eyebrow, ROMAN } from '../lib';

const jsonFiles = import.meta.glob('../../data/multicity.json', { eager: true, import: 'default' }) as Record<string, any>;
const mediaFiles = import.meta.glob('../../media/multicity/*.{gif,png}', { eager: true, query: '?url', import: 'default' }) as Record<string, string>;
const MC: any = Object.values(jsonFiles)[0] ?? null;
const SRC = 'facts:multicity.json';
const DWELL = 2800;
/** Plates I and II are the week strip and the Ann Arbor surface earlier in the deck; cities continue the series. */
const PLATE0 = 2;

const media = (file: string | undefined) => {
  if (!file) return undefined;
  const base = file.split('/').pop()!;
  return Object.entries(mediaFiles).find(([p]) => p.endsWith('/' + base))?.[1];
};
const still = (file: string | undefined) => (file ? media(file.replace(/\.gif$/, '_final.png')) : undefined);
const pct = (x: number) => `${Math.round(x * 100)}%`;
const h1 = (x: number) => x.toFixed(1);
const SHORT: Record<string, string> = { 'New York City': 'NYC', 'Champaign-Urbana': 'UIUC', 'Cambridge-Boston': 'Boston', 'San Francisco': 'SF' };

type Slide = { key: string; name: string; campus: string; pd?: any; rh?: any; line: string; sub: string; gif?: string; png?: string };

function slides(): Slide[] {
  if (!MC?.cities) return [];
  const order: string[] = MC.cities_completed ?? Object.keys(MC.cities);
  return order.filter((k) => MC.cities[k]).map((k) => {
    const c = MC.cities[k];
    const a = c.futures_study_area?.a_straight_line ?? {};
    const pd = a.pick_differs, rh = a.regret_h_semester;
    const line = pd && rh ? '' : c.headline ?? '';
    const feeds = (c.feeds ?? []).map((f: any) => `${f.key} ${f.status}, ${f.service_date}`).join(' · ');
    const sub = `${pd ? `n = ${pd.n.toLocaleString('en-US')} futures · ` : ''}${feeds}`;
    const gifPath = MC.media?.city_gifs?.[k] ?? `${k}.gif`;
    return { key: k, name: c.city ?? k, campus: c.campus ?? (Array.isArray(c.anchors) ? c.anchors.join(' · ') : ''), pd, rh, line, sub, gif: media(gifPath), png: still(gifPath) };
  });
}

/** "feeds: current for Ann Arbor & NYC; latest-valid (expired) for Austin (summer), …" from the per-city feed statuses. */
function feedFooter(): string {
  if (!MC?.cities) return '';
  const cur: string[] = [], exp: string[] = [];
  for (const k of MC.cities_completed ?? Object.keys(MC.cities)) {
    const c = MC.cities[k];
    const name = SHORT[c.city] ?? c.city;
    const fs = c.feeds ?? [];
    if (fs.length && fs.every((f: any) => f.status === 'current')) cur.push(name);
    else {
      const summer = fs.some((f: any) => /-0[78]-/.test(f.service_date ?? '')); // July/August service day = summer schedule (UIUC, Austin)
      exp.push(name + (summer ? ' (summer)' : ''));
    }
  }
  const join = (xs: string[]) => (xs.length > 1 ? xs.slice(0, -1).join(', ') + ' & ' + xs[xs.length - 1] : xs[0] ?? '');
  return `feeds: current for ${join(cur)}${exp.length ? `; latest-valid (expired) for ${join(exp)}` : ''}`;
}

function aaLine(): string {
  const r = MC?.annarbor_real_listings?.rules?.d_cheapest_rent;
  if (!r?.pick_differs || !r?.regret_usd_month) return '';
  const d = r.pick_differs, u = r.regret_usd_month;
  return html`<div class="mc-aa"><span class="label">Ann Arbor · real rents</span><p>Across ${num(String(MC.annarbor_real_listings.listings_pool), SRC + ' listings_pool')} observed listings priced all-in, the cheapest-rent pick is not the best all-in home in <b>${num(pct(d.p), SRC + ' d_cheapest_rent.pick_differs')}</b> of futures, costing <b>${num(`$${Math.round(u.mean)}/mo`, SRC + ' d_cheapest_rent.regret_usd_month')}</b> <span class="micro">${num(`[${Math.round(u.mean_ci[0])}–${Math.round(u.mean_ci[1])}]`, SRC + ' d_cheapest_rent.regret_usd_month.mean_ci')}</span>.</p></div>`;
}

function caption(c: Slide, i: number) {
  return html`
    <div class="mc-cap">
      <div class="label">Plate ${ROMAN[PLATE0 + i]} · ${esc(c.name)} · ${esc(c.campus)}</div>
      <h3 class="mc-city">${esc(c.name)}</h3>
      ${c.pd && c.rh ? html`
        <div class="mc-figs">
          <div><span class="fig">${num(pct(c.pd.p), SRC + ' a_straight_line.pick_differs.p')}</span><span class="cap">closest-to-campus pick is the wrong home ${num(`[${pct(c.pd.lo)}–${pct(c.pd.hi)}]`, SRC + ' pick_differs CI')}</span></div>
          <div><span class="fig">${num(h1(c.rh.mean) + ' h', SRC + ' a_straight_line.regret_h_semester.mean')}</span><span class="cap">lost per semester, on average ${num(`[${h1(c.rh.mean_ci[0])}–${h1(c.rh.mean_ci[1])}]`, SRC + ' regret CI')}</span></div>
        </div>` : html`<p>${said(c.line, SRC + ' headline')}</p>`}
      <div class="micro mc-sub">${said(c.sub, SRC + ' feeds')}</div>
    </div>`;
}

let timer = 0, idx = 0, paused = false;

export const multicity: Chapter = {
  id: 'multicity',
  title: 'Seven cities',
  numeral: 'VIII',
  gist: 'Thousands of futures on real transit networks',
  budget: 22,
  render() {
    const cs = slides();
    if (!cs.length) {
      return html`
        ${eyebrow(this.numeral, 'Seven cities')}
        <h2>Does it travel beyond Ann Arbor?</h2>
        <div class="pending" style="margin-top:48px"><b>Multi-city results pending</b>This chapter fills itself from presentation/data/multicity.json and presentation/media/multicity/*.gif. Skip it while this box is showing — nothing here is pre-typed.</div>`;
    }
    const finale = media(MC.media?.finale ?? 'finale_all_cities.gif'), finalePng = still(MC.media?.finale ?? 'finale_all_cities.gif');
    const total = MC.total_futures;
    const n = cs.length + 2; // cities + all-city plate + catalogue
    return html`
      <div class="geo vline"></div>
      <div class="mc-head">
        ${eyebrow(this.numeral, 'Seven cities · rapid fire', html`<span class="micro mc-hint" data-ok>click to pause</span>`)}
        <h2 class="enter" style="--i:1">Does it travel? <em>Thousands of futures on real transit networks.</em></h2>
      </div>
      <div class="mc-full" data-ok>
        <div class="mc-index">${Array.from({ length: n }, (_, i) => html`<span data-i="${i}">${i < cs.length ? ROMAN[PLATE0 + i] : i === cs.length ? 'all' : 'cat.'}</span>`)}</div>
        ${cs.map((c, i) => html`
          <figure class="mc-slide" data-i="${i}">
            <div class="plate">${c.gif ? html`<img src="${c.png ?? c.gif}" data-gif="${c.gif}" data-still="${c.png ?? ''}" alt="${esc(c.name)} simulation" decoding="async"/>` : html`<div class="img-ph"><span class="micro">${esc(c.name)}</span></div>`}<span class="plate-tick"><b></b></span></div>
            ${caption(c, i)}
          </figure>`)}
        <figure class="mc-slide" data-i="${cs.length}">
          <div class="plate">${finale ? html`<img src="${finalePng ?? finale}" data-gif="${finale}" data-still="${finalePng ?? ''}" alt="All cities compared" decoding="async"/>` : html`<div class="img-ph"><span class="micro">All cities</span></div>`}<span class="plate-tick"><b></b></span></div>
          <div class="mc-cap">
            <div class="label">Plate ${ROMAN[PLATE0 + cs.length]} · all cities</div>
            <h3 class="mc-city">Rule of thumb vs the full week</h3>
            ${total ? html`<div class="mc-figs"><div><span class="fig">${num(Number(total).toLocaleString('en-US'), SRC + ' total_futures')}</span><span class="cap">simulated student-semesters</span></div>
              <div><span class="fig">${num(String(cs.length), SRC + ' cities_completed')}</span><span class="cap">real transit networks</span></div></div>` : ''}
          </div>
        </figure>
        <figure class="mc-slide mc-cat" data-i="${cs.length + 1}">
          <div class="cat-grid">
            ${cs.map((c, i) => html`<div class="cat-cell"><div class="cat-img">${c.png ? html`<img src="${c.png}" alt="${esc(c.name)} final frame" decoding="async"/>` : html`<div class="img-ph"><span class="micro">${esc(c.name)}</span></div>`}</div>
              <div class="cat-cap"><span class="micro">${ROMAN[PLATE0 + i]} · ${esc(c.name)}</span>${c.pd ? html`<span class="cat-v">${num(pct(c.pd.p), SRC + ' a_straight_line.pick_differs.p')}</span>` : ''}</div></div>`)}
            <div class="cat-stats">
              <div class="label">Catalogue</div>
              ${total ? html`<div class="stats"><div><span class="fig">${num(Number(total).toLocaleString('en-US'), SRC + ' total_futures')}</span><span class="cap">futures</span></div><div><span class="fig">${num(String(cs.length), SRC + ' cities_completed')}</span><span class="cap">cities</span></div></div>` : ''}
              <p class="micro">Share of futures where the closest-to-campus home is the wrong one</p>
            </div>
          </div>
          ${aaLine()}
        </figure>
        <div class="mc-foot micro">Travel-only objective outside Ann Arbor (no rents) · synthetic routines · one representative weekday · ${said(feedFooter(), SRC + ' cities.*.feeds.status')}</div>
      </div>`;
  },
  mount(el) {
    el.querySelector('.mc-full')?.addEventListener('click', (e) => {
      const tab = (e.target as HTMLElement).closest<HTMLElement>('.mc-index span');
      if (tab) { show(el, Number(tab.dataset.i)); return; }
      paused = !paused;
      el.querySelector('.mc-hint')!.textContent = paused ? 'paused · click to resume' : 'click to pause';
      el.querySelector('.mc-full')!.classList.toggle('paused', paused);
    });
  },
  enter(el) {
    idx = 0; paused = false; show(el, 0);
    el.querySelector('.mc-full')?.classList.remove('paused');
    clearInterval(timer);
    timer = window.setInterval(() => { if (!paused) advance(el); }, DWELL);
  },
  leave() { clearInterval(timer); },
  notes() {
    const cs = slides();
    return cs.length
      ? `<p><b>VIII · Seven cities (22 s), rapid fire</b> — auto-advances (~3 s per plate), click to pause, click a numeral to jump. One line: "We simulated thousands of student-semesters on seven real transit networks: picking the home closest to campus is the wrong home in roughly a third to a half of futures, costing hours every semester."</p>
         <p>Catalogue + Ann Arbor with real rents: cheapest-rent pick ≠ best all-in in about a third of futures, ~$45/mo.</p>
         <p><b>Say the footer:</b> travel-only outside Ann Arbor (no rents), synthetic routines, one weekday; several feeds are latest-valid expired mirrors (UIUC/Austin are summer service).</p>`
      : `<p>Multi-city results not delivered — <b>skip this chapter</b>.</p>`;
  },
};

function advance(el: HTMLElement) {
  const n = el.querySelectorAll('.mc-slide').length;
  if (idx < n - 1) show(el, idx + 1);
  else clearInterval(timer); // rest on the catalogue
}
function show(el: HTMLElement, i: number) {
  idx = i;
  el.querySelectorAll<HTMLElement>('.mc-slide').forEach((s) => {
    const on = Number(s.dataset.i) === i;
    s.classList.toggle('on', on);
    const img = s.querySelector<HTMLImageElement>('.plate img');
    if (img && on) {
      const gif = img.dataset.gif!, png = img.dataset.still;
      img.src = reducedMotion() && png ? png : `${gif}${gif.includes('?') ? '&' : '?'}r=${Date.now()}`; // restart the GIF
    }
  });
  el.querySelectorAll<HTMLElement>('.mc-index span').forEach((b) => {
    const k = Number(b.dataset.i);
    b.classList.toggle('done', k < i);
    b.classList.toggle('cur', k === i);
  });
}
