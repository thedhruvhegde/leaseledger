import type { Listing } from '../types';
import type { CategoryFilter } from '../store/app';

export type Category = Exclude<CategoryFilter, 'all'>;

/** Three groups renters actually search by. University-owned grad apartments count as apartments. */
export const CATEGORIES: { id: Category; label: string; short: string; blurb: string }[] = [
  { id: 'apartments', label: 'Towers & apartments', short: 'Apartments', blurb: 'High-rises, student towers and apartment buildings, often leased per bed.' },
  { id: 'houses', label: 'Houses & rooms', short: 'Houses', blurb: 'Whole houses, duplex units and single rooms in shared houses.' },
  { id: 'coops', label: 'Co-ops', short: 'Co-ops', blurb: 'Student housing co-ops: rooms with meals and weekly work shifts.' },
];

export function categoryOf(l?: Listing | null): Category {
  switch (l?.building_type) {
    case 'coop': return 'coops';
    case 'house':
    case 'duplex': return 'houses';
    default: return 'apartments';
  }
}

export const categoryLabel = (c: Category) => CATEGORIES.find((x) => x.id === c)?.label ?? '';

/** Short type word for the facts line. */
export const TYPE_WORD: Record<Listing['building_type'], string> = { tower: 'Tower', apartment: 'Apartment', house: 'House', duplex: 'Duplex', coop: 'Co-op', other: 'University housing' };

/**
 * Clean display name: "University Towers - 2BR shared (up to 4 people)" → building "University Towers",
 * plan "2BR shared (up to 4 people)". Long plan strings lose trailing parentheticals on cards.
 */
export function displayName(name?: string | null): { building: string; plan: string | null } {
  const n = (name ?? '').trim();
  const i = n.indexOf(' - ');
  const building = (i < 0 ? n : n.slice(0, i)).replace(/\s+Ann Arbor$/, '').trim();
  const plan = i < 0 ? null : n.slice(i + 3).trim();
  return { building, plan: plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : null };
}
