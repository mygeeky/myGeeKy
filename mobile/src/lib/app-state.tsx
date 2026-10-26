// Settings, the read token and your profile, shared by every screen; plus a
// small hook that shows cached data at once and refreshes it when it's stale.
import { timerDue } from './wisep';
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { logOpenToday } from './badges';
import { Profile } from './interests';
import { type Brain, syncModel, withLocalLearning } from './model-repo';
import { buildProfile, loadDictionary } from './profile';
import { clearAll, getToken, isStale, loadSettings, onTokenRejected, readCache, saveSettings, setToken, Settings, writeCache } from './storage';

type AppState = {
  ready: boolean;
  settings: Settings | null;
  token: string | null;
  profile: Profile | null;
  save: (s: Settings, token?: string | null) => Promise<void>;
  refreshProfile: () => Promise<Profile | null>;
  forget: () => Promise<void>;
};

const Ctx = createContext<AppState | null>(null);

/** Your keywords and topics alone: no network, so nothing ever waits on it. */
export function quickProfile(s: Settings): Profile {
  const weights: Record<string, number> = {};
  for (const t of [...s.keywords, ...s.topics]) weights[t.toLowerCase()] = 1;
  for (const [t, w] of Object.entries(s.interests ?? {})) weights[t] = Math.max(weights[t] ?? 0, w);
  return { weights, topicIds: [], field: [...(s.field ?? [])] };
}

/** Settings with your profile from your data repo (as a pairing scan would set it); null when nothing changes.
 *  Keywords and topics added on the phone are kept alongside your computers'. */
export function withRepoProfile(s: Settings, b: Brain): Settings | null {
  if (!b.profile) return null;
  const union = (a: string[], c: string[]) => [...new Map([...c, ...a].map((x) => [x.toLowerCase(), x])).values()];
  const next: Settings = {
    ...s, orcid: s.orcid || b.profile.orcid, keywords: union(s.keywords, b.profile.keywords), topics: union(s.topics, b.profile.topics),
    interests: b.profile.interests, field: b.field.length ? b.field : s.field,
  };
  return JSON.stringify(next) === JSON.stringify(s) ? null : next;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [token, setTok] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  // GitHub refused the token (lib/github.ts): it's forgotten, and the app shows "Sign in with GitHub" again
  useEffect(() => onTokenRejected(() => setTok(null)), []);

  useEffect(() => {
    (async () => {
      const [s, t] = await Promise.all([loadSettings(), getToken()]);
      setSettings(s);
      setTok(t);
      setReady(true);
      if (!s) return;
      logOpenToday();
      setProfile(quickProfile(s));             // lists start at once from your keywords...
      setProfile(await withLocalLearning(quickProfile(s)));   // ...with what you opened here (no data repo)...
      try {
        setProfile(await withLocalLearning(await buildProfile(s, t)));  // ...and sharpen when your full profile is ready
      } catch {
        /* offline: the quick profile stays */
      }
      // connected to your data repo: you as your computers know you, every time the app starts -- what
      // "Connect your phone" brings, kept up to date without scanning (lib/model-repo.ts)
      try {
        const r = await syncModel(await loadDictionary());
        const next = r ? withRepoProfile(s, r.brain) : null;
        if (next) {
          await saveSettings(next);
          setSettings(next);
          setProfile(quickProfile(next));
          setProfile(await buildProfile(next, t, true));
        }
      } catch {
        /* offline or not connected: keep what the phone has */
      }
    })();
  }, []);

  const save = useCallback(async (s: Settings, t?: string | null) => {
    await saveSettings(s);
    if (t !== undefined) {
      await setToken(t);
      setTok(t);
    }
    setSettings(s);
    setProfile(quickProfile(s));
    try {
      setProfile(await withLocalLearning(await buildProfile(s, t === undefined ? token : t, true)));
    } catch {
      /* keep the quick profile */
    }
  }, [token]);

  const refreshProfile = useCallback(async () => {
    if (!settings) return null;
    try {
      const p = await withLocalLearning(await buildProfile(settings, token, true));
      setProfile(p);
      return p;
    } catch {
      return null;
    }
  }, [settings, token]);

  // Start over: what's stored AND what this running app holds (else setup filled itself from the old settings)
  const forget = useCallback(async () => {
    await clearAll();
    setSettings(null);
    setTok(null);
    setProfile(null);
  }, []);

  return <Ctx.Provider value={{ ready, settings, token, profile, save, refreshProfile, forget }}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppProvider');
  return v;
}

/** Cached data first, then a fresh load when it's older than `hours` (or on pull-to-refresh). */
/** What a list was ranked by: when your profile changes, every list is fetched again, not just when stale. */
const profileSig = (p: Profile) => JSON.stringify([Object.entries(p.weights).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([t]) => t),
  p.topicIds.map((t) => t.id)]);

const WISE_FEEDS = new Set(['research']);        // Papers: OpenAlex, through WISEP

export function useFeed<T>(key: string, hours: number, load: (p: Profile) => Promise<T>) {
  const { profile } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [at, setAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loaderRef = useRef(load);
  useEffect(() => {
    loaderRef.current = load;
  });

  const refresh = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      const fresh = await loaderRef.current(profile);
      setData(fresh);
      setAt(new Date().toISOString());
      await writeCache(key, fresh);
      await writeCache(`${key}:for`, profileSig(profile));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [key, profile]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [cached, madeFor] = await Promise.all([readCache<T>(key), readCache<string>(`${key}:for`)]);
      if (!alive) return;
      if (cached) {
        setData(cached.data);
        setAt(cached.at);
      }
      // feeds whose answers come through WISEP hand their timer to it once it has proven itself (timerDue)
      const stale = !cached || isStale(cached.at, hours)
        || (WISE_FEEDS.has(key) && await timerDue(false, (Date.now() - Date.parse(cached.at)) / 3600000));
      if (!alive) return;
      if (profile && (stale || madeFor?.data !== profileSig(profile))) refresh();
    })();
    return () => {
      alive = false;
    };
  }, [key, hours, profile, refresh]);

  return { data, at, loading, error, refresh };
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
