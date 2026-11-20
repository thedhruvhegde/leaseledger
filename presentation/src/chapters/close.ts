// Closing plate: the cover's city again, one sentence, the ask. The app URL is presenter chrome (data-ok).
import type { Chapter } from '../deck';
import { html } from '../lib';
import { cityMap } from './cover';
import { base, loadBase } from '../routemap';

export const close: Chapter = {
  id: 'close',
  title: 'Close',
  budget: 8,
  deps: ['routes'],
  render() {
    return html`
      <div class="geo cv-map cl-map">${cityMap('cv-svg', 10)}</div>
      <div class="cv-panel cl-panel enter" style="--i:1">
        <h1 class="cl-line">Lowest rent isn’t the <em>cheapest week.</em></h1>
        <p class="cv-sub">Type in your own week. Then ask us anything.</p>
      </div>`;
  },
  mount(el) {
    if (!base) loadBase().then((b) => b && el.dispatchEvent(new CustomEvent('deck:rerender', { bubbles: true })));
  },
  notes() {
    return `<p><b>Close (≈8 s).</b> Say the sentence, then the ask: "Type your own week into it — and ask us anything." Stop talking; Q&A.</p>
      <p>For Q&A: press A for the math appendix (Sobol, τ(t), CVaR, EVPI).</p>`;
  },
};
