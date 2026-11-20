import { useState } from 'react';
import type { Listing, ListingPhoto } from '../types';
import type { MapLine } from './MapView';
import { MapThumb } from './MapThumb';
import { photosOf } from '../lib/photos';
import { displayName } from '../lib/category';

/** "Photo: <credit>" linking to the source page. Always visible next to a photo. */
export function PhotoCredit({ p, className = '' }: { p: ListingPhoto; className?: string }) {
  const text = /^photo\b/i.test(p.credit) ? p.credit : `Photo: ${p.credit || 'source'}`;
  return p.source_url ? (
    <a href={p.source_url} target="_blank" rel="noreferrer noopener" className={`relative z-10 truncate underline decoration-current/40 underline-offset-2 hover:decoration-current ${className}`} title={p.license ? `${text} · ${p.license}` : text}>{text}</a>
  ) : <span className={`truncate ${className}`} title={p.license}>{text}</span>;
}

/**
 * The picture slot of a listing: its first licensed photo, or — when there is none — the generated street map
 * around the home with its week routes. Never a stand-in photo of another building.
 */
export function ListingVisual({ l, lines = [], className = '', routeChips = false }: { l?: Listing; lines?: MapLine[]; className?: string; routeChips?: boolean }) {
  const photos = photosOf(l);
  const [broken, setBroken] = useState(false);
  if (!l) return <div className={`bg-raised ${className}`} />;
  const p = photos[0];
  if (p && !broken) {
    return (
      <div className={`overflow-hidden bg-raised ${className}`}>
        <img src={p.src} alt={`${displayName(l.name).building}, ${l.address ?? l.neighborhood ?? ''}`} loading="lazy" decoding="async" onError={() => setBroken(true)} className="absolute inset-0 h-full w-full object-cover" style={{ objectPosition: p.position ?? 'center' }} />
        <div className="absolute inset-x-0 bottom-0 flex justify-end bg-gradient-to-t from-black/45 to-transparent px-2 pb-1 pt-4 text-[10.5px] text-white">
          <PhotoCredit p={p} className="max-w-full" />
        </div>
      </div>
    );
  }
  return <MapThumb lat={l.lat} lon={l.lon} lines={lines} label={l.name} className={className} chips={routeChips} />;
}

/** Detail gallery: large first photo, up to four thumbnails, credit line under the image. */
export function Gallery({ l }: { l: Listing }) {
  const photos = photosOf(l);
  const [i, setI] = useState(0);
  if (photos.length === 0) return null;
  const p = photos[Math.min(i, photos.length - 1)];
  const name = displayName(l.name).building;
  return (
    <figure className="border-b border-line">
      <div className="relative aspect-[16/9] max-h-[280px] w-full overflow-hidden bg-raised sm:aspect-[16/7]">
        <img src={p.src} alt={`${name}, photo ${i + 1} of ${photos.length}`} className="absolute inset-0 h-full w-full object-cover" style={{ objectPosition: p.position ?? 'center' }} />
        {photos.length > 1 && <span className="num absolute right-3 top-3 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white">{i + 1} / {photos.length}</span>}
      </div>
      {photos.length > 1 && (
        <div className="no-scrollbar flex gap-1.5 overflow-x-auto px-5 pt-2 sm:px-6" role="tablist" aria-label="Photos">
          {photos.slice(0, 8).map((q, j) => (
            <button key={q.src} role="tab" aria-selected={j === i} aria-label={`Photo ${j + 1}`} onClick={() => setI(j)}
              className={`relative h-12 w-[4.5rem] shrink-0 overflow-hidden rounded-md border ${j === i ? 'border-ink' : 'border-line opacity-75 hover:opacity-100'}`}>
              <img src={q.src} alt="" className="absolute inset-0 h-full w-full object-cover" loading="lazy" />
            </button>
          ))}
        </div>
      )}
      <figcaption className="flex items-center gap-2 px-5 py-2 text-[11.5px] text-faint sm:px-6">
        <PhotoCredit p={p} className="min-w-0" />
      </figcaption>
    </figure>
  );
}
