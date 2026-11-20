import { create } from 'zustand';
import type { ApiClient } from '../api/client';
import type { AiMode, Event, Health, Member, Profile } from '../types';
import { DEFAULT_PROFILE } from '../api/mockData';

export type Screen = 'week' | 'results' | 'robustness' | 'baseline' | 'group' | 'add' | 'methods';

export const SCREENS: { id: Screen; label: string; short: string }[] = [
  { id: 'results', label: 'Homes', short: 'Homes' },
  { id: 'week', label: 'Your week', short: 'Week' },
  { id: 'robustness', label: 'How sure are we?', short: 'Sure?' },
  { id: 'baseline', label: 'Portal vs. your week', short: 'Portal' },
  { id: 'group', label: 'Group Week', short: 'Group' },
  { id: 'add', label: 'Add a listing', short: 'Add' },
  { id: 'methods', label: 'Methods & sources', short: 'Methods' },
];

const BURST_MS = 1500;

export type HomeScope = 'all' | 'shortlist';
export type CategoryFilter = 'all' | 'apartments' | 'houses' | 'coops';

function initialCategory(): CategoryFilter {
  if (typeof window === 'undefined') return 'all';
  const q = new URLSearchParams(window.location.search).get('type');
  return q === 'apartments' || q === 'houses' || q === 'coops' ? q : 'all';
}

function initialScope(): HomeScope {
  if (typeof window === 'undefined') return 'all';
  const q = new URLSearchParams(window.location.search).get('scope');
  return q === 'shortlist' ? 'shortlist' : 'all';
}

interface AppState {
  api: ApiClient | null;
  fellBack: boolean;
  health: Health | null;
  setApi: (api: ApiClient, fellBack: boolean, health: Health | null) => void;

  screen: Screen;
  setScreen: (s: Screen) => void;

  /** Draft profile — edits apply here immediately (UI is instant). */
  profile: Profile;
  /** Committed profile — debounced (150 ms) copy that drives queries. */
  committed: Profile;
  /** Baseline for the "What changed" diff: the committed profile before the latest burst of edits. */
  diffBase: Profile | null;
  lastCommitAt: number;
  /** Pinned snapshot: when set, diffs compare against it instead of the previous state. */
  pinned: Profile | null;
  changeSource: 'edit' | 'load';
  drawerOpen: boolean;
  setProfile: (p: Profile | ((p: Profile) => Profile), source?: 'edit' | 'load') => void;
  commit: () => void;
  pin: () => void;
  unpin: () => void;
  setDrawer: (open: boolean) => void;

  updateEvent: (i: number, patch: Partial<Event>) => void;
  addEvent: (e: Event) => void;
  removeEvent: (i: number) => void;
  needsConfirm: Record<number, string[]>;
  setNeedsConfirm: (m: Record<number, string[]>) => void;
  confirmEvent: (i: number) => void;

  selected: string | null;
  setSelected: (id: string | null) => void;
  compareWith: string | null;
  setCompareWith: (id: string | null) => void;
  /** Compare tray: up to two homes; `compareOpen` shows the side-by-side in the detail pane. */
  compare: string[];
  toggleCompare: (id: string) => void;
  clearCompare: () => void;
  compareOpen: boolean;
  setCompareOpen: (v: boolean) => void;
  /** Landing hand-off in flight: the week text is being read. */
  parsing: boolean;
  setParsing: (v: boolean) => void;

  theme: 'light' | 'dark';
  toggleTheme: () => void;
  present: boolean;
  togglePresent: () => void;
  aiEnabled: boolean;
  setAiEnabled: (v: boolean) => void;
  lastAiMode: AiMode | null;
  setLastAiMode: (m: AiMode) => void;

  /** Text typed into the landing page's week pill, handed to "Your week" to parse on arrival. */
  weekDraft: string | null;
  setWeekDraft: (t: string | null) => void;

  /** Which homes the Homes page ranks: every observed listing (default) or the 15-home demo shortlist. */
  scope: HomeScope;
  setScope: (s: HomeScope) => void;
  /** Category tab on Homes (client-side filter of the ranked list; ranks are unchanged). */
  category: CategoryFilter;
  setCategory: (c: CategoryFilter) => void;

  members: Member[];
  setMembers: (m: Member[] | ((m: Member[]) => Member[])) => void;
  customIds: string[];
  addCustomId: (id: string) => void;
}

function initialScreen(): Screen {
  if (typeof window === 'undefined') return 'results';
  const h = window.location.hash.replace('#', '');
  return SCREENS.some((s) => s.id === h) ? (h as Screen) : 'results';
}

function initialTheme(): 'light' | 'dark' {
  try {
    const t = localStorage.getItem('ll-theme');
    if (t === 'light' || t === 'dark') return t;
  } catch {
    /* storage unavailable */
  }
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const useApp = create<AppState>((set, get) => ({
  api: null,
  fellBack: false,
  health: null,
  setApi: (api, fellBack, health) => set({ api, fellBack, health }),

  screen: initialScreen(),
  setScreen: (screen) => set({ screen }),

  profile: DEFAULT_PROFILE,
  committed: DEFAULT_PROFILE,
  diffBase: null,
  lastCommitAt: 0,
  pinned: null,
  changeSource: 'load',
  drawerOpen: false,
  setProfile: (p, source = 'edit') => {
    const next = typeof p === 'function' ? p(get().profile) : p;
    set({ profile: next, changeSource: source });
    if (source === 'load') {
      // loads commit immediately and reset diff history
      set({ committed: next, diffBase: null, lastCommitAt: 0, drawerOpen: false, needsConfirm: {} });
    }
  },
  commit: () => {
    const { profile, committed, lastCommitAt, diffBase, changeSource } = get();
    if (profile === committed) return;
    const now = Date.now();
    const base = now - lastCommitAt > BURST_MS || !diffBase ? committed : diffBase;
    set({ committed: profile, diffBase: base, lastCommitAt: now, drawerOpen: changeSource === 'edit' ? true : get().drawerOpen });
  },
  pin: () => set({ pinned: get().committed }),
  unpin: () => set({ pinned: null }),
  setDrawer: (drawerOpen) => set({ drawerOpen }),

  updateEvent: (i, patch) =>
    get().setProfile((p) => ({ ...p, events: p.events.map((e, j) => (j === i ? { ...e, ...patch, provenance: patch.provenance ?? (e.provenance === 'estimated' ? 'user' : e.provenance) } : e)) })),
  addEvent: (e) => get().setProfile((p) => ({ ...p, events: [...p.events, e] })),
  removeEvent: (i) => {
    const nc: Record<number, string[]> = {};
    for (const [k, v] of Object.entries(get().needsConfirm)) {
      const n = Number(k);
      if (n < i) nc[n] = v;
      else if (n > i) nc[n - 1] = v;
    }
    set({ needsConfirm: nc });
    get().setProfile((p) => ({ ...p, events: p.events.filter((_, j) => j !== i) }));
  },
  needsConfirm: {},
  setNeedsConfirm: (needsConfirm) => set({ needsConfirm }),
  confirmEvent: (i) => {
    const nc = { ...get().needsConfirm };
    delete nc[i];
    set({ needsConfirm: nc });
  },

  selected: null,
  setSelected: (selected) => set({ selected }),
  compareWith: null,
  setCompareWith: (compareWith) => set({ compareWith }),
  compare: [],
  toggleCompare: (id) => {
    const c = get().compare;
    const next = c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-2);
    set({ compare: next, compareOpen: get().compareOpen && next.length === 2 });
  },
  clearCompare: () => set({ compare: [], compareOpen: false }),
  compareOpen: false,
  setCompareOpen: (compareOpen) => set({ compareOpen }),
  parsing: false,
  setParsing: (parsing) => set({ parsing }),

  theme: initialTheme(),
  toggleTheme: () => {
    const theme = get().theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('ll-theme', theme);
    } catch {
      /* ignore */
    }
    set({ theme });
  },
  present: false,
  togglePresent: () => set({ present: !get().present }),
  aiEnabled: true,
  setAiEnabled: (aiEnabled) => set({ aiEnabled }),
  lastAiMode: null,
  setLastAiMode: (lastAiMode) => set({ lastAiMode }),

  weekDraft: null,
  setWeekDraft: (weekDraft) => set({ weekDraft }),

  scope: initialScope(),
  setScope: (scope) => set({ scope, selected: null, compare: [], compareOpen: false }),
  category: initialCategory(),
  setCategory: (category) => set({ category }),

  members: [],
  setMembers: (m) => set({ members: typeof m === 'function' ? m(get().members) : m }),
  customIds: [],
  addCustomId: (id) => set({ customIds: [...get().customIds, id] }),
}));

// Expose the store for rehearsal scripts / screenshots (read-only use in dev tooling).
if (typeof window !== 'undefined') (window as unknown as { __ll: typeof useApp }).__ll = useApp;
