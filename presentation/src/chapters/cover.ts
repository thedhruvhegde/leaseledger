// Cover: the monograph's title page. No numbers on it.
import type { Chapter } from '../deck';
import { html } from '../lib';

export const cover: Chapter = {
  id: 'cover',
  title: 'Lease Ledger',
  budget: 8,
  render() {
    return html`
      <div class="geo geo-deco cv-deco"></div>
      <div class="geo h-accent"></div>
      <div class="cv-top enter" style="--i:0"><span class="label">Hack the Lease</span><span class="label">University of Michigan · Ann Arbor</span></div>
      <div class="cv-main">
        <div class="label enter" style="--i:1">A monograph in one week</div>
        <h1 class="display cv-title enter" style="--i:2">Lease Ledger</h1>
        <p class="sub cv-sub enter" style="--i:3">What a home really costs <em class="serif">the week you actually live</em> — rent, fees, utilities and every trip of your routine, priced on this fall’s real bus timetables.</p>
      </div>
      <div class="cv-foot enter" style="--i:4">
        <span class="micro">Live demo</span><span class="micro">Real timetables</span><span class="micro">No invented numbers</span>
      </div>`;
  },
  notes() {
    return `<p><b>Cover (≈8 s).</b> "We're Lease Ledger." Press T as you start talking. Don't linger — the first number lands on the next-but-one slide.</p>`;
  },
};
