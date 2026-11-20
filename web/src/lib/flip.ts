import { useCallback, useLayoutEffect, useRef } from 'react';

/**
 * FLIP animation for reordered lists. Usage: const flip = useFlip(orderKey); <li ref={flip(id)} />
 * When `orderKey` changes, each element animates from its previous position to its new one.
 */
export function useFlip(orderKey: string, durationMs = 450) {
  const nodes = useRef(new Map<string, HTMLElement>());
  const rects = useRef(new Map<string, DOMRect>());

  const register = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) nodes.current.set(id, el);
      else nodes.current.delete(id);
    },
    [],
  );

  useLayoutEffect(() => {
    const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const next = new Map<string, DOMRect>();
    nodes.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      next.set(id, r);
      const prev = rects.current.get(id);
      if (!prev || reduce) return;
      const dy = prev.top - r.top;
      if (Math.abs(dy) < 1) return;
      el.style.transition = 'none';
      el.style.transform = `translateY(${dy}px)`;
      el.style.zIndex = '5';
      requestAnimationFrame(() => {
        el.style.transition = `transform ${durationMs}ms cubic-bezier(.2,.8,.2,1)`;
        el.style.transform = '';
        const done = () => { el.style.zIndex = ''; el.removeEventListener('transitionend', done); };
        el.addEventListener('transitionend', done);
      });
    });
    rects.current = next;
  }, [orderKey, durationMs]);

  return register;
}
