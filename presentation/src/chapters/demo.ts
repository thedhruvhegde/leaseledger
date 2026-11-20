import type { Chapter } from '../deck';
import { call, plan, ranked, type Evaluation, sname } from '../api';
import { FLIPS, applyFlip, scopeIds } from '../requests.js';
import { html, num, said, esc, fmt, DAY_NAME, minToClock, reducedMotion, icon, ROMAN, tag, syncMedia } from '../lib';

const qs = new URLSearchParams(location.search);
/** The real app. Override with ?app=http://host:5173 */
export const APP = (qs.get('app') ?? 'http://localhost:5173').replace(/\/$/, '');
/** Recorded mode (static hosting, no app server): play the recorded run of the real app instead of iframes.
 *  On with ?app=recorded or a build with VITE_DEMO_MODE=recorded. */
export const RECORDED = qs.get('app') === 'recorded' || (import.meta as any).env?.VITE_DEMO_MODE === 'recorded';
// recorded mode: the laptop frame takes the walkthrough loop's 16:9 so the loop fills it edge to edge
const LAP = { w: 1280, h: RECORDED ? 720 : 1040, s: 0.55 };
const PHN = { w: 390, h: 950, s: 0.6 };
const ROW = 64;

function flipLabel(f: any, before: any): string {
  if (f.patch?.value_of_time != null) {
    const from = before?.value_of_time_used;
    return `${esc(f.verb)} ${from != null ? num(fmt(from, 'usd') + '/h', 'api:POST /evaluate value_of_time_used') + ' → ' : ''}${num('$' + f.patch.value_of_time + '/h', 'param:FLIPS.vot')}`;
  }
  if (f.addEvent) {
    const e = f.addEvent;
    return `${esc(f.verb)} ${num(`${e.days.map((d: string) => DAY_NAME[d]).join('/')} ${minToClock(e.start_min)}–${minToClock(e.end_min)}`, 'param:FLIPS.hospital')}`;
  }
  return esc(f.verb);
}

/** The app walkthrough loop (public/video/walkthrough.mp4, 10× speed): the laptop's recorded run, and its stand-in
 *  when the live app is unreachable. Playback is owned by syncMedia() (pauses off-slide, poster under reduced motion). */
const walk = (cls = '') => {
  const rm = reducedMotion();
  return `<video data-loop class="${cls}" src="./video/walkthrough.mp4" poster="./video/walkthrough.jpg" muted loop playsinline ${rm ? 'preload="none"' : 'preload="auto" autoplay'} disablepictureinpicture aria-hidden="true" style="width:100%;height:100%;object-fit:contain;object-position:center;background:var(--bg2)"></video>`;
};

function frame(kind: 'laptop' | 'phone', src: string) {
  const d = kind === 'laptop' ? LAP : PHN;
  return html`<figure class="device device-${kind}">
    <div class="frame">
      <div class="viewport" style="width:${d.w * d.s}px;height:${d.h * d.s}px">
        ${RECORDED
          ? (kind === 'laptop'
              ? walk()
              : html`<img src="./demo/phone-results.png" alt="Phone layout of the app (recorded run)" style="width:100%;height:100%;object-fit:cover;object-position:top" />`)
          : html`<iframe title="${kind} view of the app" loading="eager" src="${src}" style="width:${d.w}px;height:${d.h}px;transform:scale(${d.s})"></iframe>${kind === 'laptop' ? walk('vid-fallback') : ''}`}
        <div class="offline"><span class="label">App not reachable</span><span class="small" data-ok>${esc(APP)} — start it with <code>make web</code>. The ledger on the right calls the API directly and keeps working.</span></div>
      </div>
    </div>
  </figure>`;
}

export const demo: Chapter = {
  id: 'demo',
  title: 'Live demo',
  numeral: 'IV',
  gist: 'Change one thing, watch the answer move',
  budget: 70,
  deps: ['demoProfiles', ...FLIPS.map((f: any) => `eval:${f.profile}`)],
  render() {
    const laptopSrc = `${APP}/app?demo=north-engineer#results`;
    const phoneSrc = `${APP}/app?demo=north-engineer#results`;
    return html`
      <div class="geo vline"></div>
      <div class="demo-head enter" style="--i:1">
        <h2>Change one thing. <em>Watch it move.</em></h2>
        ${tag(RECORDED ? 'recorded run of the real app' : 'the real app, live', 'demo-tag')}
      </div>
      <div class="demo-grid">
        <div class="devices enter" style="--i:2">
          ${frame('laptop', laptopSrc)}
          ${frame('phone', phoneSrc)}
        </div>
        <div class="flip-col enter" style="--i:3">
          <div class="flip-btns">
            ${FLIPS.map((f: any, i: number) => html`<button class="flip-btn" data-flip="${f.id}">${icon(ROMAN[i])}<span class="fb-l">${flipLabel(f, plan[`eval:${f.profile}`])}</span></button>`)}
          </div>
          <div class="flip-out">
            <div class="fo-head"><span class="fo-title">Pick a change.</span></div>
            <ol class="ranks" style="height:${ROW * 5}px"></ol>
            <div class="fo-cause"></div>
          </div>
        </div>
      </div>`;
  },
  mount(el) {
    // app reachability: probe once; mark both frames down if the app isn't there
    if (!RECORDED) fetch(APP, { mode: 'no-cors', signal: AbortSignal.timeout(2500) }).catch(() => { el.querySelectorAll('.viewport').forEach((v) => v.classList.add('down')); syncMedia(); });
    el.querySelectorAll<HTMLButtonElement>('.flip-btn').forEach((b) => b.addEventListener('click', (ev) => { ev.stopPropagation(); runFlip(el, b.dataset.flip!); }));
  },
  notes() {
    return `<p><b>IV · Live demo (70 s) — the required live sensitivity beat.</b> Laptop and phone both show the app for the North Campus engineer (same listings as the deck).</p>
      <ol><li>In the app: show the receipt ranking, then open the diff drawer after a change.</li>
      <li>Button 1 (VOT): "If I value my time at $20/h instead of $8, the tower wins — the breakeven is on the next slide."</li>
      <li>Button 2 (hospital shift): adds T/R 7–12 at University Hospital → #1 changes. <b>Knife-edge</b>: the margin is tiny; say so if asked.</li>
      <li>Button 3 (exclude co-ops): a hard constraint, the next-best home takes over.</li></ol>
      <p>Recorded mode (static build): the laptop plays the app walkthrough loop (media/videos/fast/walkthrough.mp4, 10× speed); the same loop stands in on the laptop if the live app is unreachable.</p>
      <p>Lead over #2 on the hospital flip is about $2/mo on the app's scope (all observed listings): a knife edge — say so.</p>
      <p>If the iframe is blank: the buttons call the API directly (or the snapshot) — keep talking. All three flips are from execution/demo-flips.md, recomputed live.</p>`;
  },
};

let running = 0;
async function runFlip(el: HTMLElement, id: string) {
  const f: any = FLIPS.find((x: any) => x.id === id);
  const p = plan.demoProfiles?.find((d: any) => d.id === f.profile)?.profile;
  const out = el.querySelector<HTMLElement>('.flip-out')!;
  const title = out.querySelector<HTMLElement>('.fo-title')!;
    const cause = out.querySelector<HTMLElement>('.fo-cause')!;
  const list = out.querySelector<HTMLOListElement>('.ranks')!;
  el.querySelectorAll('.flip-btn').forEach((b) => {
    const on = (b as HTMLElement).dataset.flip === id;
    b.setAttribute('aria-pressed', String(on));
    b.querySelector('.card-icon')?.classList.toggle('on', on);
  });
  if (!p) { title.textContent = 'Waiting for data…'; return; }
  const token = ++running;
  title.textContent = 'Computing…';
  cause.textContent = '';
  const after = applyFlip(p, f);
  const ids = scopeIds(plan.listings); // same scope as the app's Homes page: all observed listings
  try {
    const t0 = performance.now();
    const [b, a, d] = await Promise.all([
      call('POST', '/evaluate', { profile: p, listing_ids: ids }),
      call('POST', '/evaluate', { profile: after, listing_ids: ids }),
      call('POST', '/diff', { before: p, after, listing_ids: ids }).catch(() => null),
    ]);
    if (token !== running) return;
    const ms = Math.round(performance.now() - t0);
    const src = a.source === 'live' && b.source === 'live' ? 'live' : 'snapshot';
    out.dataset.src = src === 'live' ? `live ${ms}ms` : 'snapshot';
    const B = ranked(b.data), A = ranked(a.data);
    animate(list, B, A);
    const b1 = B[0]?.listing_id, a1 = A[0]?.listing_id;
    const margin = A.length > 1 ? A[1].score - A[0].score : null;
    title.innerHTML = b1 !== a1
      ? html`<span class="label fo-flip">#1 flips</span><span class="fo-name">${sname(a1)}</span>`
      : html`<span class="label fo-flip">#1 holds</span><span class="fo-name">${sname(a1)}</span>`;
    const c0 = d?.data?.causes?.[0];
    cause.innerHTML = html`${c0 ? html`<p class="fo-c">${said(c0.length > 120 ? c0.slice(0, 117).replace(/\s+\S*$/, '') + '…' : c0, 'api:POST /diff causes[0]')}</p>` : ''}
      ${margin != null ? html`<div class="fo-margin"><span class="fo-ml">lead over #2</span><span class="fo-m">${num(fmt(margin, 'usd') + '/mo', 'api:POST /evaluate score')}</span>${f.knifeEdge || margin < 10 ? html`<span class="fo-knife">a knife edge</span>` : ''}</div>` : ''}`;
  } catch (e) {
    title.textContent = 'API and snapshot both unavailable';
    cause.textContent = String(e);
  }
}

/** FLIP-style rank animation: draw "before" positions, then move rows to "after" positions. */
function animate(list: HTMLOListElement, B: Evaluation[], A: Evaluation[]) {
  const N = 5;
  const before = B.slice(0, N).map((e) => e.listing_id);
  const after = A.slice(0, N).map((e) => e.listing_id);
  const all = [...new Set([...before, ...after])];
  const val = (arr: Evaluation[], id: string) => arr.find((e) => e.listing_id === id);
  list.innerHTML = all.map((id) => {
    const eb = val(B, id), ea = val(A, id);
    return html`<li data-id="${esc(id)}"><span class="r">${num(eb && before.includes(id) ? String(eb.rank) : '·', 'api:POST /evaluate rank')}</span><span class="n">${sname(id)}</span><span class="v">${num(fmt((ea ?? eb)!.all_in_total, 'usd'), 'api:POST /evaluate all_in_total')}</span></li>`;
  }).join('');
  const rows = [...list.querySelectorAll<HTMLLIElement>('li')];
  const pos = (arr: string[], id: string) => (arr.includes(id) ? arr.indexOf(id) : N + 0.3);
  rows.forEach((li) => {
    const id = li.dataset.id!;
    li.style.transition = 'none';
    li.style.transform = `translateY(${pos(before, id) * ROW}px)`;
    li.classList.toggle('gone', !before.includes(id));
    li.classList.toggle('top', before[0] === id);
  });
  const go = () => rows.forEach((li) => {
    const id = li.dataset.id!;
    const ea = val(A, id);
    li.style.transition = '';
    li.style.transform = `translateY(${pos(after, id) * ROW}px)`;
    li.classList.toggle('gone', !after.includes(id));
    li.classList.toggle('top', after[0] === id);
    li.classList.toggle('moved-up', after.includes(id) && pos(after, id) < pos(before, id));
    const r = li.querySelector('.r .num');
    if (r) r.textContent = ea && after.includes(id) ? String(ea.rank) : '·';
    const v = li.querySelector('.v .num');
    if (v && ea) v.textContent = fmt(ea.all_in_total, 'usd');
  });
  if (reducedMotion()) go();
  else { void list.offsetHeight; setTimeout(go, 650); }
}
