// Agenda: the catalogue's table of contents, generated from the chapter list (numerals + titles + gists).
import type { Chapter } from '../deck';
import { allChapters } from '../deck';
import { html, esc, eyebrow } from '../lib';

export const agenda: Chapter = {
  id: 'agenda',
  title: 'Contents',
  budget: 7,
  render() {
    const list = allChapters().filter((c) => c.numeral && !c.appendix);
    const half = Math.ceil(list.length / 2);
    const col = (xs: Chapter[]) => html`<div class="ag-col">${xs.map((c, k) => html`
      <button class="agenda-row ag-row enter" style="--i:${2 + k}" data-goto="${c.id}">
        <span class="an">${esc(c.numeral!)}</span>
        <span class="ag-t"><span class="ag-title">${esc(c.title)}</span>${c.gist ? html`<span class="ag-gist">${esc(c.gist)}</span>` : ''}</span>
      </button>`)}</div>`;
    return html`
      <div class="geo geo-arc ag-arc"></div>
      ${eyebrow('', 'Contents')}
      <h2 class="enter" style="--i:1">One decision, <em>examined ten ways.</em></h2>
      <div class="ag-grid">${col(list.slice(0, half))}${col(list.slice(half))}</div>`;
  },
  mount(el) {
    el.querySelectorAll<HTMLElement>('[data-goto]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      el.dispatchEvent(new CustomEvent('deck:goto', { bubbles: true, detail: b.dataset.goto }));
    }));
  },
  notes() {
    return `<p><b>Agenda (≈7 s).</b> Don't read it. "One decision — where to live — and ten ways we checked our answer." Each row is clickable if a judge asks to jump.</p>`;
  },
};
