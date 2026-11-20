/**
 * Typed API client. Two implementations share one interface:
 *  - LiveApi: HTTP to the FastAPI backend (VITE_API_BASE, default http://localhost:8000/api)
 *  - MockApi (./mock.ts): deterministic in-browser fixtures + simplified engine, all listings synthetic
 * Selection: VITE_API_MODE=mock|live (default live). In live mode, if GET /health fails the app
 * falls back to mock automatically and shows the "API offline — showing mock data" banner.
 */
import type {
  Building,
  CompareResult,
  CounterfactualResult,
  DemoProfile,
  DiffResult,
  EvaluationResult,
  ExtractListingResult,
  GroupResult,
  Health,
  Listing,
  Manifest,
  Member,
  MethodsResult,
  ParseScheduleResult,
  Profile,
  RobustnessResult,
  ScheduleTemplate,
} from '../types';

export interface ApiClient {
  readonly kind: 'live' | 'mock';
  health(): Promise<Health>;
  manifest(): Promise<Manifest>;
  buildings(): Promise<Building[]>;
  listings(includeSynthetic?: boolean): Promise<Listing[]>;
  templates(): Promise<ScheduleTemplate[]>;
  demoProfiles(): Promise<DemoProfile[]>;
  methods(): Promise<MethodsResult>;
  evaluate(profile: Profile, listingIds?: string[] | null): Promise<EvaluationResult>;
  robustness(profile: Profile, samples: number, seed: number, listingIds?: string[] | null): Promise<RobustnessResult>;
  counterfactual(profile: Profile, a: string, b: string): Promise<CounterfactualResult>;
  compare(profile: Profile, a: string, b: string): Promise<CompareResult>;
  diff(before: Profile, after: Profile, listingIds?: string[] | null): Promise<DiffResult>;
  group(members: Member[], listingIds?: string[] | null): Promise<GroupResult>;
  parseSchedule(text: string, useAi?: boolean): Promise<ParseScheduleResult>;
  extractListing(text: string, useAi?: boolean): Promise<ExtractListingResult>;
  addCustomListing(listing: Listing): Promise<Listing>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000/api';
export const API_MODE: 'live' | 'mock' = (import.meta.env.VITE_API_MODE as string | undefined) === 'mock' ? 'mock' : 'live';

/** Unwrap list endpoints that may return either `T[]` or `{items|buildings|listings|...: T[]}`. */
function asList<T>(data: unknown, ...keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const k of [...keys, 'items', 'data', 'results']) {
      const v = (data as Record<string, unknown>)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}

export class LiveApi implements ApiClient {
  readonly kind = 'live' as const;
  constructor(private base: string = API_BASE) {}

  private async req<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), init?.timeoutMs ?? 30000);
    try {
      const res = await fetch(`${this.base}${path}`, {
        ...init,
        signal: init?.signal ?? ctl.signal,
        headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      });
      if (!res.ok) {
        let detail: unknown;
        try {
          detail = await res.json();
        } catch {
          detail = await res.text().catch(() => undefined);
        }
        const msg = typeof detail === 'object' && detail && 'detail' in detail ? JSON.stringify((detail as { detail: unknown }).detail).slice(0, 300) : res.statusText;
        throw new ApiError(`${res.status} ${path}: ${msg}`, res.status, detail);
      }
      return (await res.json()) as T;
    } finally {
      clearTimeout(t);
    }
  }
  private post<T>(path: string, body: unknown, timeoutMs?: number): Promise<T> {
    return this.req<T>(path, { method: 'POST', body: JSON.stringify(body), timeoutMs });
  }

  health() { return this.req<Health>('/health', { timeoutMs: 2500 }); }
  manifest() { return this.req<Manifest>('/manifest'); }
  async buildings() { return asList<Building>(await this.req<unknown>('/buildings'), 'buildings'); }
  async listings(includeSynthetic = true) { return asList<Listing>(await this.req<unknown>(`/listings?include_synthetic=${includeSynthetic}`), 'listings'); }
  async templates() { return asList<ScheduleTemplate>(await this.req<unknown>('/templates'), 'templates'); }
  async demoProfiles() { return asList<DemoProfile>(await this.req<unknown>('/demo-profiles'), 'profiles', 'demo_profiles'); }
  methods() { return this.req<MethodsResult>('/methods'); }
  evaluate(profile: Profile, listing_ids?: string[] | null) { return this.post<EvaluationResult>('/evaluate', { profile, listing_ids: listing_ids ?? null }); }
  robustness(profile: Profile, samples: number, seed: number, listing_ids?: string[] | null) {
    return this.post<RobustnessResult>('/robustness', { profile, samples, seed, listing_ids: listing_ids ?? null }, 60000);
  }
  counterfactual(profile: Profile, a: string, b: string) { return this.post<CounterfactualResult>('/counterfactual', { profile, a, b }); }
  compare(profile: Profile, a: string, b: string) { return this.post<CompareResult>('/compare', { profile, a, b }); }
  diff(before: Profile, after: Profile, listing_ids?: string[] | null) { return this.post<DiffResult>('/diff', { before, after, listing_ids: listing_ids ?? null }); }
  group(members: Member[], listing_ids?: string[] | null) { return this.post<GroupResult>('/group', { members, listing_ids: listing_ids ?? null }, 60000); }
  parseSchedule(text: string, useAi = true) { return this.post<ParseScheduleResult>('/parse-schedule', { text, use_ai: useAi }, 45000); }
  extractListing(text: string, useAi = true) { return this.post<ExtractListingResult>('/extract-listing', { text, use_ai: useAi }, 45000); }
  async addCustomListing(listing: Listing) {
    // API: POST {listing: <Listing without id>} -> {id, listing, stored, expires_in_s}
    const { id: _omit, ...rest } = listing;
    void _omit;
    const r = await this.post<{ id: string; listing?: Listing }>('/listings/custom', { listing: rest });
    return r.listing ?? { ...listing, id: r.id };
  }
}

/** Resolve the client: mock if requested or if live /health fails. */
export async function resolveClient(): Promise<{ api: ApiClient; fellBack: boolean; health: Health | null }> {
  const { MockApi } = await import('./mock');
  if (API_MODE === 'mock') {
    const m = new MockApi();
    return { api: m, fellBack: false, health: await m.health() };
  }
  const live = new LiveApi();
  try {
    const h = await live.health();
    return { api: live, fellBack: false, health: h };
  } catch {
    const m = new MockApi();
    return { api: m, fellBack: true, health: await m.health() };
  }
}
