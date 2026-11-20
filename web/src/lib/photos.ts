import type { Listing, ListingPhoto } from '../types';

/**
 * Listing photos come from two places, merged client-side:
 *  1. the API (`Listing.photos`, default []), and
 *  2. a static manifest the team maintains at /photos/manifest.json:
 *     { "<listing-id>": [{ "file": "front.jpg", "credit": "...", "source_url": "...", "license": "..." }] }
 *     with the files at /photos/<listing-id>/<file>.
 * Only photos someone has the right to use go in either place (see public/photos/README.md).
 * A listing without photos shows its generated street-map thumbnail instead; never a stand-in picture.
 */
export interface ManifestEntry { file?: string; src?: string; credit?: string; source_url?: string; license?: string; position?: string }
export type PhotoManifest = Record<string, ManifestEntry[]>;

const SAFE_ID = /^[A-Za-z0-9._-]+$/;
const SAFE_FILE = /^(?:[A-Za-z0-9_][A-Za-z0-9._-]*\/)?[A-Za-z0-9_][A-Za-z0-9._ -]*\.(jpe?g|webp|png|avif)$/i;
const SAFE_POS = /^(?:center|top|bottom|left|right|\d{1,3}%)(?: (?:center|top|bottom|left|right|\d{1,3}%))?$/;

let cached: Promise<PhotoManifest> | null = null;

/** Fetch /photos/manifest.json once; a missing or malformed manifest is simply "no local photos". */
export function loadPhotoManifest(): Promise<PhotoManifest> {
  if (cached) return cached;
  cached = (async () => {
    try {
      if (typeof fetch === 'undefined' || typeof window === 'undefined' || !window.location?.origin?.startsWith('http')) return {};
      const res = await fetch('/photos/manifest.json', { cache: 'no-cache' });
      if (!res.ok) return {};
      const j: unknown = await res.json();
      return j && typeof j === 'object' && !Array.isArray(j) ? (j as PhotoManifest) : {};
    } catch {
      return {};
    }
  })();
  return cached;
}

/** Only allow http(s) URLs and same-site absolute paths as image sources. */
function safeSrc(src: string | undefined): string | null {
  if (!src) return null;
  if (src.startsWith('/') && !src.startsWith('//')) return src;
  try {
    const u = new URL(src);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}
function safeLink(href: string | undefined | null): string | null {
  if (!href) return null;
  try {
    const u = new URL(href);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}

export function normalizePhoto(p: Partial<ListingPhoto> | null | undefined): ListingPhoto | null {
  if (!p || typeof p !== 'object') return null;
  const src = safeSrc(p.src);
  if (!src) return null;
  const position = p.position && SAFE_POS.test(p.position) ? p.position : undefined;
  return { src, credit: (p.credit ?? '').toString().slice(0, 120), source_url: safeLink(p.source_url) ?? undefined, license: p.license ? String(p.license).slice(0, 80) : undefined, position };
}

function fromManifest(id: string, entries: ManifestEntry[] | undefined): ListingPhoto[] {
  if (!Array.isArray(entries) || !SAFE_ID.test(id)) return [];
  const out: ListingPhoto[] = [];
  for (const e of entries) {
    if (!e || typeof e !== 'object') continue;
    // "front.jpg" → /photos/<listing-id>/front.jpg; "university-towers/exterior.jpg" → /photos/university-towers/exterior.jpg
    // (one file can serve several listing ids: repeat the entry under each id).
    const src = e.file && SAFE_FILE.test(e.file) ? (e.file.includes('/') ? `/photos/${e.file.split('/').map(encodeURIComponent).join('/')}` : `/photos/${id}/${encodeURIComponent(e.file)}`) : e.src;
    const p = normalizePhoto({ src, credit: e.credit, source_url: e.source_url, license: e.license, position: e.position });
    if (p) out.push(p);
  }
  return out;
}

/** API photos first, then manifest photos (deduplicated by src). */
export function mergePhotos(listings: Listing[], manifest: PhotoManifest): Listing[] {
  return listings.map((l) => {
    const api = (Array.isArray(l.photos) ? l.photos : []).map(normalizePhoto).filter((p): p is ListingPhoto => !!p);
    const local = fromManifest(l.id, manifest[l.id]);
    if (api.length === 0 && local.length === 0) return l.photos === undefined ? l : { ...l, photos: [] };
    const seen = new Set<string>();
    const photos = [...api, ...local].filter((p) => (seen.has(p.src) ? false : (seen.add(p.src), true)));
    return { ...l, photos };
  });
}

export const photosOf = (l?: Listing | null): ListingPhoto[] => (l?.photos ?? []);
