// Closing plate: geo-ring, one sentence, the call to action. The app URL is presenter chrome (data-ok).
import type { Chapter } from '../deck';
import { html, esc } from '../lib';
import { APP } from './demo';

export const close: Chapter = {
  id: 'close',
  title: 'Close',
  budget: 8,
  render() {
    const host = APP.replace(/^https?:\/\//, '');
    return html`
      <div class="geo geo-ring"></div>
      <div class="geo h-accent"></div>
      <div class="cl-in">
        <div class="label enter" style="--i:0">Lease Ledger</div>
        <h1 class="cl-line enter" style="--i:1">Lowest rent isn’t the cheapest week. <em>Now a student can see by how much — and how sure we are.</em></h1>
        <div class="cl-cta enter" style="--i:2">
          <span class="h-rule"></span>
          <span class="cl-ask">Type your own week into it. Then ask us anything.</span>
        </div>
        <div class="cl-meta enter" style="--i:3"><span class="micro" data-ok>${esc(host)}</span><span class="micro">Appendix on request · press A</span></div>
      </div>`;
  },
  notes() {
    return `<p><b>Close (≈8 s).</b> Say the sentence on the slide, then the ask: "Type your own week into it — and ask us anything." Stop talking; Q&A.</p>
      <p>For Q&A: press A for the math appendix (Sobol, τ(t), CVaR, EVPI).</p>`;
  },
};
