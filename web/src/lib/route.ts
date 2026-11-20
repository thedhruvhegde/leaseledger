import { SCREENS } from '../store/app';

/** Two routes: the landing page at "/" and the app at "/app" (screens are hash routes: /app#results).
 *  Old deep links keep working: any URL with a screen hash or ?demo= opens the app. */
export type Route = 'landing' | 'app';

export function currentRoute(): Route {
  if (typeof window === 'undefined') return 'landing';
  const { pathname, hash, search } = window.location;
  if (pathname.startsWith('/app')) return 'app';
  if (SCREENS.some((s) => hash === `#${s.id}`)) return 'app';
  if (new URLSearchParams(search).has('demo')) return 'app';
  return 'landing';
}

/** Client-side navigation without a reload (keeps the API client and query cache warm). */
export function navigate(href: string) {
  window.history.pushState(null, '', href);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

/** onClick handler for <a href> that navigates in-app for plain left clicks. */
export function linkTo(href: string) {
  return (e: { preventDefault: () => void; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean; button?: number }) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || (e.button ?? 0) !== 0) return;
    e.preventDefault();
    navigate(href);
  };
}
