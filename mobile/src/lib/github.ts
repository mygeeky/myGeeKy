import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchT } from './net';
import { freshToken } from './storage';

// Read-only GitHub API calls. With the sign-in token the limit is 5,000 calls an
// hour; without one it's 60, so screens that need many calls say so.
export const NAME_RE = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/;

export class GitHubError extends Error {}

// Slow numbers wait a day: a repo's own page (stars, forks, language), its commit activity and contributors, a
// person's profile and links, known from less than a day ago, are read from this phone without asking. The desktop
// keeps the same list (ghcache.py, SLOW); tests/test_ghcache.py checks both agree.
export const SLOW_MS = 24 * 3600 * 1000;
const SLOW = [/^\/repos\/[^/]+\/[^/]+$/, /^\/repos\/[^/]+\/[^/]+\/stats\/commit_activity$/,
  /^\/repos\/[^/]+\/[^/]+\/contributors$/, /^\/users\/[^/]+$/, /^\/users\/[^/]+\/social_accounts$/];
const KEPT = 300;                                  // slow answers kept on the phone, the newest first
const INDEX_KEY = 'mygeeky.gh.index';

export function isSlow(path: string): boolean {
  const p = path.replace(/^https:\/\/api\.github\.com/, '').split('?')[0].replace(/\/+$/, '');
  return SLOW.some((re) => re.test(p));
}

async function keptAnswer<T>(path: string): Promise<T | undefined> {
  try {
    const raw = await AsyncStorage.getItem(`mygeeky.gh.${path}`);
    const v = raw ? JSON.parse(raw) as { at: number; data: T } : null;
    return v && Date.now() - v.at < SLOW_MS ? v.data : undefined;
  } catch { return undefined; }
}

async function keepAnswer(path: string, data: unknown): Promise<void> {
  try {
    const at = Date.now();
    await AsyncStorage.setItem(`mygeeky.gh.${path}`, JSON.stringify({ at, data }));
    const index: [string, number][] = JSON.parse((await AsyncStorage.getItem(INDEX_KEY)) ?? '[]');
    const next = [[path, at] as [string, number], ...index.filter(([p]) => p !== path)];
    const gone = next.slice(KEPT).map(([p]) => `mygeeky.gh.${p}`);
    await AsyncStorage.setItem(INDEX_KEY, JSON.stringify(next.slice(0, KEPT)));
    if (gone.length) await AsyncStorage.multiRemove(gone);
  } catch { /* a full or broken store: the answer is simply asked again next time */ }
}

export async function gh<T = any>(path: string, token: string | null): Promise<T> {
  const slow = isSlow(path);
  if (slow) {
    const kept = await keptAnswer<T>(path);
    if (kept !== undefined) return kept;
  }
  const data = await ask<T>(path, token);
  if (slow) await keepAnswer(path, data);
  return data;
}

async function ask<T>(path: string, token: string | null): Promise<T> {
  if (token) token = await freshToken(token);     // an 8-hour sign-in renews itself first
  const r = await fetchT(`https://api.github.com${path}`, {
    headers: {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (r.status === 403 || r.status === 429) {
    throw new GitHubError(token ? 'GitHub asks us to slow down. Try again in a few minutes.'
                                : 'GitHub limits reading without signing in. Sign in with GitHub on the You tab.');
  }
  if (!r.ok) throw new GitHubError(`GitHub said ${r.status}.`);
  return r.json();
}

/** Everyone a user follows (up to 500). */
export async function following(user: string, token: string | null): Promise<string[]> {
  const out: string[] = [];
  for (let page = 1; page <= 5; page++) {
    const batch = await gh<{ login: string }[]>(`/users/${user}/following?per_page=100&page=${page}`, token);
    out.push(...batch.map((u) => u.login));
    if (batch.length < 100) break;
  }
  return out;
}

export async function followers(user: string, token: string | null): Promise<{ login: string; avatar: string }[]> {
  const out: { login: string; avatar: string }[] = [];
  for (let page = 1; page <= 3; page++) {
    const batch = await gh<{ login: string; avatar_url: string }[]>(`/users/${user}/followers?per_page=100&page=${page}`, token);
    out.push(...batch.map((u) => ({ login: u.login, avatar: u.avatar_url })));
    if (batch.length < 100) break;
  }
  return out;
}

export type Repo = {
  full_name: string; description: string | null; stargazers_count: number; language: string | null;
  topics?: string[]; pushed_at: string; html_url: string; fork: boolean; archived: boolean;
  owner: { login: string; avatar_url: string; type: string };
};

export async function searchRepos(q: string, token: string | null, perPage = 20): Promise<Repo[]> {
  const d = await gh<{ items: Repo[] }>(`/search/repositories?q=${encodeURIComponent(q)}&sort=stars&order=desc&per_page=${perPage}`, token);
  return d.items ?? [];
}
