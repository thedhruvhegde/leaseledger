// Speaker-notes window, synced with the deck over BroadcastChannel('lease-ledger-deck').
import '@fontsource/playfair-display/400.css';
import '@fontsource-variable/inter';
import './notes.css';

const root = document.getElementById('notes')!;
const chan = new BroadcastChannel('lease-ledger-deck');
const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, '0')}`;
const send = (cmd: string, extra = {}) => chan.postMessage({ type: 'cmd', cmd, ...extra });

root.innerHTML = `<header><div class="t-total"></div><div class="t-bar"><b></b><i></i></div><div class="t-ch"></div>
  <div class="btns"><button data-c="prev">← Prev</button><button data-c="next">Next →</button><button data-c="timer">Start / pause · T</button><button data-c="reset">Reset</button></div></header>
  <main><div class="cur"><div class="eyebrow"></div><h1></h1><div class="body"></div></div><aside><div class="lbl">Next</div><div class="next"></div><div class="lbl">Running order</div><ol class="order"></ol></aside></main>
  <footer>Waiting for the deck… (open it, then press S there)</footer>`;
root.querySelectorAll<HTMLButtonElement>('button[data-c]').forEach((b) => b.addEventListener('click', () => send(b.dataset.c!)));
addEventListener('keydown', (e) => {
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); send('next'); }
  if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); send('prev'); }
  if (e.key === 't') send('timer');
});

chan.onmessage = (ev) => {
  const m = ev.data;
  if (m?.type !== 'state') return;
  const q = (s: string) => root.querySelector<HTMLElement>(s)!;
  const t = m.timer;
  q('.t-total').innerHTML = `<span class="${t.elapsed > t.total ? 'over' : ''}">${mmss(t.elapsed)}</span> / ${mmss(t.total)} ${t.running ? '' : '<em>paused</em>'}`;
  q('.t-bar b').style.width = `${Math.min(100, (t.elapsed / t.total) * 100)}%`;
  q('.t-bar i').style.left = `${Math.min(100, ((t.budgetStart + t.budget) / t.total) * 100)}%`;
  const behind = t.elapsed - (t.budgetStart + t.ch);
  q('.t-ch').innerHTML = `This chapter <b class="${t.budget && t.ch > t.budget ? 'over' : ''}">${mmss(t.ch)}</b> / ${t.budget ? mmss(t.budget) : 'appendix'} · ${behind > 2 ? `<span class="over">${mmss(behind)} behind plan</span>` : 'on plan'}`;
  q('.eyebrow').textContent = `${String(m.idx + 1).padStart(2, '0')} · ${m.appendix ? 'appendix · ' : ''}reveal ${m.step}/${m.steps} · data ${m.data}`;
  q('h1').textContent = m.title;
  q('.body').innerHTML = m.notes;
  q('.next').textContent = m.next;
  q('.order').innerHTML = m.chapters.map((c: any) => `<li class="${c.i === m.idx ? 'cur' : ''} ${c.appendix ? 'app' : ''}"><button data-i="${c.i}">${c.title}</button><span>${c.budget ? mmss(c.budget) : 'appx'}</span></li>`).join('');
  q('.order').querySelectorAll<HTMLButtonElement>('button').forEach((b) => (b.onclick = () => send('goto', { idx: Number(b.dataset.i) })));
  q('footer').textContent = 'Synced with the deck.';
};
chan.postMessage({ type: 'hello' });
