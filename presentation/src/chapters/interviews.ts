// "What students told us": a collage of the user's interview images (public/interviews/*) and keyword chips from
// data/interviews.json. Nothing here is invented: with neither present, the chapter is not in the talk at all.
import type { Chapter } from '../deck';
import { html, esc, num } from '../lib';
import { interviews } from '../facts';
import manifestFile from '../interviews-manifest.json';

const manifest = manifestFile as { images: string[] };

const IMAGES: string[] = [...new Set([...(manifest.images ?? []), ...((interviews?.images ?? []) as string[]).map((p) => String(p).split('/').pop()!)])]
  .filter((f) => (manifest.images ?? []).includes(f));
const SRC = 'facts:interviews.json';

type Chip = { label: string; count?: number };
function chips(): Chip[] {
  if (!interviews) return [];
  const pool = interviews.keywords ?? interviews.themes ?? interviews.tags ?? interviews.codes ?? interviews.tally ?? interviews.hypotheses ?? [];
  const list = Array.isArray(pool) ? pool : Object.entries(pool).map(([k, v]) => (typeof v === 'number' ? { label: k, count: v } : { label: k, ...(v as object) }));
  return list.map((x: any) => (typeof x === 'string' ? { label: x } : { label: String(x.label ?? x.keyword ?? x.theme ?? x.name ?? x.id ?? ''), count: typeof (x.count ?? x.n) === 'number' ? (x.count ?? x.n) : undefined }))
    .filter((c: Chip) => c.label).slice(0, 8);
}

const count = (): number | null => { const n = interviews?.completed ?? interviews?.n ?? (Array.isArray(interviews?.rows) ? interviews.rows.length : null); return typeof n === 'number' ? n : null; };
export const hasInterviews = IMAGES.length > 0 || chips().length > 0 || count() != null;

export const interviewsChapter: Chapter = {
  id: 'interviews',
  title: 'What students told us',
  budget: 10,
  render() {
    const cs = chips();
    const n = count();
    const imgs = IMAGES.slice(0, 5);
    return html`
      <div class="geo vline"></div>
      <h2 class="enter" style="--i:1">${interviews?.simulated ? html`What our test personas <em>told us.</em>` : html`What students <em>told us.</em>`}</h2>
      <div class="iv-grid grow">
        ${imgs.length ? html`<div class="iv-collage n${imgs.length} enter" style="--i:2">${imgs.map((f, i) => html`<div class="plate-img iv-img" style="--r:${(i % 2 ? 1 : -1) * (0.6 + (i % 3) * 0.4)}deg"><img src="./interviews/${encodeURIComponent(f)}" alt="Interview photo" decoding="async"/></div>`)}</div>` : ''}
        <div class="iv-side enter" style="--i:3">
          ${n != null ? html`<div class="hero md">${num(n, SRC)}</div><div class="hero-cap">${interviews?.simulated ? 'simulated personas · not real users' : 'students interviewed'}</div>` : ''}
          ${Array.isArray(interviews?.findings) ? interviews.findings.map((f: any) => html`<div class="hero-cap" style="margin-top:18px"><b>${num(String(f.value), SRC)}</b> ${esc(String(f.label))}</div>`).join('') : ''}
          ${cs.length ? html`<div class="iv-chips">${cs.map((c) => html`<span class="iv-chip">${esc(c.label)}${c.count != null ? html` <b>${num(c.count, SRC)}</b>` : ''}</span>`)}</div>` : ''}
        </div>
      </div>`;
  },
  notes() {
    return `<p><b>What students told us (10 s).</b> Say only what's on the slide: the images and keywords come straight from presentation/public/interviews/ and data/interviews.json. ${interviews?.note ? esc(interviews.note) : ''}</p>`;
  },
};
