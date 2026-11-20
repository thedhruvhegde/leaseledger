// VIII · Seven cities, rapid fire (presentation/data/multicity.json + presentation/media/multicity/*.gif, from
// ledger/multicity — methods in analysis/multicity/METHODS.md). Each city: its simulation map (cropped from the GIF),
// the city name and ONE number; then a catalogue of all seven with the futures total. Every number comes from
// multicity.json. Caveats (travel-only, synthetic routines, feed status) are one visible tag + the notes.
import type { Chapter } from '../deck';
import { html, num, esc, reducedMotion, tag } from '../lib';

const jsonFiles = import.meta.glob('../../data/multicity.json', { eager: true, import: 'default' }) as Record<string, any>;
const mediaFiles = import.meta.glob('../../media/multicity/*.{gif,png}', { eager: true, query: '?url', import: 'default' }) as Record<string, string>;
const MC: any = Object.values(jsonFiles)[0] ?? null;
const SRC = 'facts:multicity.json';
const DWELL = 1500;
const SHORT: Record<string, string> = { 'New York City': 'New York', 'Champaign-Urbana': 'Champaign', 'Cambridge-Boston': 'Boston', 'San Francisco': 'San Francisco' };

const media = (file: string | undefined) => {
  if (!file) return undefined;
  const b = file.split('/').pop()!;
  return Object.entries(mediaFiles).find(([p]) => p.endsWith('/' + b))?.[1];
};
const still = (file: string | undefined) => (file ? media(file.replace(/\.gif$/, '_final.png')) : undefined);
const pct = (x: number) => `${Math.round(x * 100)}%`;

type Slide = { key: string; name: string; pd?: any; gif?: string; png?: string };
function slides(): Slide[] {
  if (!MC?.cities) return [];
  const order: string[] = MC.cities_completed ?? Object.keys(MC.cities);
  return order.filter((k) => MC.cities[k]).map((k) => {
    const c = MC.cities[k];
    const gifPath = MC.media?.city_gifs?.[k] ?? `${k}.gif`;
    return { key: k, name: c.city ?? k, pd: c.futures_study_area?.a_straight_line?.pick_differs, gif: media(gifPath), png: still(gifPath) };
  });
}

/** The map half of a simulation frame (the GIFs put the map left, their chart right). */
const crop = (src: string | undefined, alt: string, gif?: string) =>
  src ? html`<div class="mc-crop"><img src="${src}" ${gif ? html`data-gif="${gif}" data-still="${src}"` : ''} alt="${esc(alt)}" decoding="async"/></div>` : html`<div class="mc-crop img-ph"></div>`;

let timer = 0, idx = 0, paused = false;

export const multicity: Chapter = {
  id: 'multicity',
  title: 'Seven cities',
  budget: 12,
  render() {
    const cs = slides();
    if (!cs.length) {
      return html`<h2>Does it travel?</h2><div class="pending" style="margin-top:48px"><b>Multi-city results pending</b>Fills itself from presentation/data/multicity.json. Skip this chapter while this box shows.</div>`;
    }
    const total = MC.total_futures;
    const ps = cs.filter((c) => c.pd).map((c) => c.pd.p);
    const lo = Math.min(...ps), hi = Math.max(...ps);
    return html`
      <div class="geo vline"></div>
      <div class="mc-head enter" style="--i:1">
        <h2>Does it travel? <em>${num(String(cs.length), SRC + ' cities_completed')} real transit networks.</em></h2>
        ${tag('simulated · travel-only')}
      </div>
      <div class="mc-full grow" data-ok>
        ${cs.map((c, i) => html`
          <figure class="mc-slide" data-i="${i}">
            <div class="plate-img mc-plate">${crop(c.png ?? c.gif, c.name + ' simulation', c.gif)}</div>
            <div class="mc-cap">
              <h3 class="mc-city">${esc(c.name)}</h3>
              ${c.pd ? html`<div class="hero">${num(pct(c.pd.p), SRC + ' a_straight_line.pick_differs.p')}</div>
                <div class="hero-cap">of futures, the home <b>closest to campus</b> is the wrong pick</div>` : ''}
            </div>
          </figure>`)}
        <figure class="mc-slide mc-cat" data-i="${cs.length}">
          <div class="cat-grid">
            ${cs.map((c) => html`<div class="cat-cell">
              <div class="plate-img cat-plate">${crop(c.png, c.name)}</div>
              <div class="cat-cap"><span>${esc(SHORT[c.name] ?? c.name)}</span>${c.pd ? html`<b>${num(pct(c.pd.p), SRC + ' a_straight_line.pick_differs.p')}</b>` : ''}</div>
            </div>`)}
            <div class="cat-sum">
              <div class="hero sm">${num(`${pct(lo)}–${pct(hi)}`, SRC + ' cities.*.pick_differs.p (min–max)')}</div>
              <div class="hero-cap">closest-to-campus is wrong, across ${total ? html`<b>${num(Number(total).toLocaleString('en-US'), SRC + ' total_futures')}</b> simulated semesters` : 'all simulated semesters'}</div>
            </div>
          </div>
        </figure>
        <div class="mc-ticks">${Array.from({ length: cs.length + 1 }, (_, i) => html`<i data-i="${i}"></i>`)}</div>
      </div>`;
  },
  mount(el) {
    el.querySelector('.mc-full')?.addEventListener('click', (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>('.mc-ticks i');
      if (t) { show(el, Number(t.dataset.i)); return; }
      paused = !paused;
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
    const cav: string[] = MC?.global_caveats ?? [];
    const ar = MC?.annarbor_real_listings?.rules?.d_cheapest_rent;
    return cs.length
      ? `<p><b>VIII · Seven cities (12 s), rapid fire</b> — auto-advances (~1.5 s per city, then rests on the catalogue), click to pause, click a tick to jump. One line: "We simulated thousands of student-semesters on seven real transit networks: picking the home closest to campus is the wrong home in roughly a third to a half of futures, costing hours every semester."</p>
         ${ar ? `<p>Ann Arbor with real rents: cheapest-rent pick ≠ best all-in in ${Math.round(ar.pick_differs.p * 100)}% of futures, ~$${Math.round(ar.regret_usd_month.mean)}/mo.</p>` : ''}
         <p><b>Say the caveat:</b> ${cav.map(esc).join(' ')}</p>`
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
    const img = s.querySelector<HTMLImageElement>('.mc-plate img[data-gif]');
    if (img && on) {
      const gif = img.dataset.gif!, png = img.dataset.still;
      img.src = reducedMotion() && png ? png : `${gif}${gif.includes('?') ? '&' : '?'}r=${Date.now()}`; // restart the GIF
    }
  });
  el.querySelectorAll<HTMLElement>('.mc-ticks i').forEach((b) => {
    const k = Number(b.dataset.i);
    b.classList.toggle('done', k < i);
    b.classList.toggle('cur', k === i);
  });
}
