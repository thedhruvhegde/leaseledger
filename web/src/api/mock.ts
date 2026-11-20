/**
 * MockApi: realistic, deterministic offline implementation of ApiClient. Fixtures are generated to
 * the exact schemas in ../types.ts (mirror of ledger/schemas.py). ALL fixture listings are synthetic.
 */
import type { ApiClient } from './client';
import type { Building, Listing, Member, Profile } from '../types';
import { MOCK_BUILDINGS, MOCK_DEMO_PROFILES, MOCK_LISTINGS, MOCK_MANIFEST, MOCK_METHODS, MOCK_TEMPLATES } from './mockData';
import { compare, counterfactual, diff, evaluate, robustness, type EngineCtx } from './mockEngine';
import { group } from './mockGroup';
import { extractListing, parseSchedule } from './mockNlp';

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T;
const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export class MockApi implements ApiClient {
  readonly kind = 'mock' as const;
  private custom: Listing[] = [];
  private latency: number;

  constructor(opts: { latencyMs?: number } = {}) {
    this.latency = opts.latencyMs ?? 60;
  }

  private ctx(): EngineCtx {
    return { buildings: new Map<string, Building>(MOCK_BUILDINGS.map((b) => [b.id, b])), listings: [...MOCK_LISTINGS, ...this.custom] };
  }
  private async run<T>(f: () => T, extra = 0): Promise<T> {
    await delay(this.latency + extra);
    return clone(f());
  }

  health() { return this.run(() => ({ status: 'ok', ai_mode: 'regex', mode: 'mock' }), -this.latency); }
  manifest() { return this.run(() => MOCK_MANIFEST); }
  buildings() { return this.run(() => MOCK_BUILDINGS); }
  listings(includeSynthetic = true) { return this.run(() => [...MOCK_LISTINGS, ...this.custom].filter((l) => includeSynthetic || l.provenance !== 'synthetic')); }
  templates() { return this.run(() => MOCK_TEMPLATES); }
  demoProfiles() { return this.run(() => MOCK_DEMO_PROFILES); }
  methods() { return this.run(() => MOCK_METHODS); }
  evaluate(profile: Profile, ids?: string[] | null) { return this.run(() => evaluate(profile, this.ctx(), ids)); }
  robustness(profile: Profile, samples: number, seed: number, ids?: string[] | null) {
    return this.run(() => robustness(profile, this.ctx(), MOCK_TEMPLATES, samples, seed, ids), 120);
  }
  counterfactual(profile: Profile, a: string, b: string) { return this.run(() => counterfactual(profile, this.ctx(), a, b)); }
  compare(profile: Profile, a: string, b: string) { return this.run(() => compare(profile, this.ctx(), a, b)); }
  diff(before: Profile, after: Profile, ids?: string[] | null) { return this.run(() => diff(before, after, this.ctx(), ids)); }
  group(members: Member[], ids?: string[] | null) { return this.run(() => group(members, this.ctx(), ids), 80); }
  parseSchedule(text: string, _useAi = true) { return this.run(() => parseSchedule(text, MOCK_BUILDINGS), 250); }
  extractListing(text: string, _useAi = true) { return this.run(() => extractListing(text), 250); }
  addCustomListing(listing: Listing) {
    return this.run(() => {
      const l = { ...listing, id: listing.id || `custom-${this.custom.length + 1}` };
      this.custom = [...this.custom.filter((x) => x.id !== l.id), l];
      return l;
    });
  }
}
