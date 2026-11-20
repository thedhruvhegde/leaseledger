import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useApp } from '../store/app';
import type { ApiClient } from './client';
import type { Building, Listing, Member, Profile } from '../types';

function useApi(): ApiClient {
  const api = useApp((s) => s.api);
  if (!api) throw new Error('API not ready');
  return api;
}

const REF = { staleTime: Infinity, gcTime: Infinity } as const;

/** The API rejects a profile with no events and no template (422) — don't ask until there's a week. */
export const hasWeek = (p: Profile | null | undefined): boolean => !!p && (p.events.length > 0 || !!p.template_id);

export function useBuildings() {
  const api = useApi();
  return useQuery({ queryKey: ['buildings', api.kind], queryFn: () => api.buildings(), ...REF });
}
export function useListings() {
  const api = useApi();
  const custom = useApp((s) => s.customIds);
  return useQuery({ queryKey: ['listings', api.kind, custom], queryFn: () => api.listings(true), placeholderData: keepPreviousData, ...REF });
}
export function useTemplates() {
  const api = useApi();
  return useQuery({ queryKey: ['templates', api.kind], queryFn: () => api.templates(), ...REF });
}
export function useDemoProfiles() {
  const api = useApi();
  return useQuery({ queryKey: ['demo', api.kind], queryFn: () => api.demoProfiles(), ...REF });
}
export function useManifest() {
  const api = useApi();
  return useQuery({ queryKey: ['manifest', api.kind], queryFn: () => api.manifest(), ...REF });
}
export function useMethods() {
  const api = useApi();
  return useQuery({ queryKey: ['methods', api.kind], queryFn: () => api.methods(), ...REF });
}

export function useListingMap(): Map<string, Listing> {
  const { data } = useListings();
  return useMemo(() => new Map((data ?? []).map((l) => [l.id, l])), [data]);
}
export function useBuildingMap(): Map<string, Building> {
  const { data } = useBuildings();
  return useMemo(() => new Map((data ?? []).map((b) => [b.id, b])), [data]);
}

/** Main evaluation, driven by the debounced committed profile; keeps previous data to avoid flicker. */
export function useEvaluation() {
  const api = useApi();
  const committed = useApp((s) => s.committed);
  const custom = useApp((s) => s.customIds);
  return useQuery({
    queryKey: ['evaluate', api.kind, committed, custom],
    queryFn: () => api.evaluate(committed, null),
    enabled: hasWeek(committed),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useDiff() {
  const api = useApi();
  const committed = useApp((s) => s.committed);
  const diffBase = useApp((s) => s.diffBase);
  const pinned = useApp((s) => s.pinned);
  const before = pinned ?? diffBase;
  return useQuery({
    queryKey: ['diff', api.kind, before, committed],
    queryFn: () => api.diff(before!, committed, null),
    enabled: hasWeek(before) && hasWeek(committed) && before !== committed,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useBeforeEvaluation() {
  const api = useApi();
  const diffBase = useApp((s) => s.diffBase);
  const pinned = useApp((s) => s.pinned);
  const custom = useApp((s) => s.customIds);
  const before = pinned ?? diffBase;
  return useQuery({
    queryKey: ['evaluate', api.kind, before, custom],
    queryFn: () => api.evaluate(before!, null),
    enabled: hasWeek(before),
    staleTime: 60_000,
  });
}

export function useRobustness(samples = 2000, seed = 42) {
  const api = useApi();
  const committed = useApp((s) => s.committed);
  const custom = useApp((s) => s.customIds);
  return useQuery({
    queryKey: ['robustness', api.kind, committed, samples, seed, custom],
    queryFn: () => api.robustness(committed, samples, seed, null),
    enabled: hasWeek(committed),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useCompare(a: string | null, b: string | null) {
  const api = useApi();
  const committed = useApp((s) => s.committed);
  return useQuery({
    queryKey: ['compare', api.kind, committed, a, b],
    queryFn: () => api.compare(committed, a!, b!),
    enabled: !!a && !!b && a !== b && hasWeek(committed),
    placeholderData: keepPreviousData,
  });
}

export function useCounterfactual(a: string | null, b: string | null) {
  const api = useApi();
  const committed = useApp((s) => s.committed);
  return useQuery({
    queryKey: ['counterfactual', api.kind, committed, a, b],
    queryFn: () => api.counterfactual(committed, a!, b!),
    enabled: !!a && !!b && a !== b && hasWeek(committed),
    placeholderData: keepPreviousData,
  });
}

export function useDebounced<T>(value: T, ms = 150): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function useGroup(members: Member[]) {
  const api = useApi();
  const deb = useDebounced(members, 150);
  return useQuery({
    queryKey: ['group', api.kind, deb],
    queryFn: () => api.group(deb, null),
    enabled: deb.length >= 2 && deb.every((m) => hasWeek(m.profile)),
    placeholderData: keepPreviousData,
  });
}

export function useParseSchedule() {
  const api = useApi();
  const ai = useApp((s) => s.aiEnabled);
  return useMutation({ mutationFn: (text: string) => api.parseSchedule(text, ai) });
}

export function useExtractListing() {
  const api = useApi();
  const ai = useApp((s) => s.aiEnabled);
  return useMutation({ mutationFn: (text: string) => api.extractListing(text, ai) });
}

export function useAddListing() {
  const api = useApi();
  const qc = useQueryClient();
  const addCustomId = useApp((s) => s.addCustomId);
  return useMutation({
    mutationFn: (l: Listing) => api.addCustomListing(l),
    onSuccess: (l) => {
      addCustomId(l.id);
      void qc.invalidateQueries({ queryKey: ['listings'] });
    },
  });
}
