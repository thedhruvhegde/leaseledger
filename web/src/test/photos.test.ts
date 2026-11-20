import { describe, expect, it } from 'vitest';
import { mergePhotos } from '../lib/photos';
import { categoryOf, displayName } from '../lib/category';
import type { Listing } from '../types';

const L = (id: string, extra: Partial<Listing> = {}) => ({ id, name: `${id} - plan`, building_type: 'tower', photos: [], ...extra }) as unknown as Listing;

describe('listing photos', () => {
  it('merges manifest entries (own folder and shared folder) after API photos', () => {
    const out = mergePhotos([L('a', { photos: [{ src: 'https://x.org/a.jpg', credit: 'API' }] }), L('b'), L('c')], {
      a: [{ file: 'front.jpg', credit: 'Me' }],
      b: [{ file: 'shared-dir/ext.jpg', credit: 'Team', position: 'center 30%' }],
    });
    expect(out[0].photos!.map((p) => p.src)).toEqual(['https://x.org/a.jpg', '/photos/a/front.jpg']);
    expect(out[1].photos![0]).toMatchObject({ src: '/photos/shared-dir/ext.jpg', position: 'center 30%' });
    expect(out[2].photos).toEqual([]);
  });
  it('drops unsafe sources, paths and positions', () => {
    const out = mergePhotos([L('a')], { a: [{ file: '../x.jpg' }, { src: 'javascript:alert(1)' }, { file: 'ok.webp', position: 'url(x)', source_url: 'javascript:1' }] });
    expect(out[0].photos).toHaveLength(1);
    expect(out[0].photos![0]).toMatchObject({ src: '/photos/a/ok.webp', position: undefined, source_url: undefined });
  });
});

describe('categories and names', () => {
  it('groups building types', () => {
    expect(categoryOf(L('t'))).toBe('apartments');
    expect(categoryOf(L('h', { building_type: 'duplex' }))).toBe('houses');
    expect(categoryOf(L('c', { building_type: 'coop' }))).toBe('coops');
  });
  it('splits building and plan', () => {
    expect(displayName('Verve Ann Arbor - studio')).toEqual({ building: 'Verve', plan: 'Studio' });
    expect(displayName('University Towers - 2BR shared (up to 4 people)').building).toBe('University Towers');
  });
});
