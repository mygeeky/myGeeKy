// Your own GitHub events for My month: a port of the desktop's refresh_my_github / slim_github_event (gui/app.py).
// Read at most once an hour (three pages), slimmed, and kept with the earlier ones for 400 days, so earlier months
// still show after GitHub's own 90; plus the language of up to 10 repos you worked in that aren't your own.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { gh } from './github';

const KEY = 'mygeeky.month.github';
const HOURS = 1, DAYS = 400, LANG_LOOKUPS = 10;
export type Slim = { id: string; at: string; type: string; repo: string; n: number; action: string };
type Kept = { fetchedAt?: string; events?: Slim[]; langs?: Record<string, string> };

export function slimEvent(e: any): Slim | null {
  if (!e || typeof e !== 'object' || !e.id || !e.created_at) return null;
  const p = e.payload && typeof e.payload === 'object' ? e.payload : {};
  const n = p.distinct_size || p.size || (Array.isArray(p.commits) ? p.commits.length : 0) || 1;
  return { id: String(e.id), at: String(e.created_at), type: String(e.type ?? ''), repo: String(e.repo?.name ?? ''),
    n: Math.trunc(Number(n)) || 1, action: String(p.action ?? '') };
}

export async function myGitHub(): Promise<Kept> {
  try {
    const kept = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    return kept && typeof kept === 'object' ? kept : {};
  } catch {
    return {};
  }
}

/** Read your newest events and keep them; true if anything was read. */
export async function refreshMyGitHub(login: string, token: string | null, force = false): Promise<boolean> {
  if (!login) return false;
  const kept = await myGitHub();
  if (!force && kept.fetchedAt && Date.now() - Date.parse(kept.fetchedAt) < HOURS * 3600000) return false;
  const found = new Map<string, Slim>((kept.events ?? []).filter((e) => e && e.id).map((e) => [e.id, e]));
  try {
    for (const page of [1, 2, 3]) {
      const batch = await gh<any[]>(`/users/${encodeURIComponent(login)}/events?per_page=100&page=${page}`, token);
      for (const e of (Array.isArray(batch) ? batch : []).map(slimEvent)) if (e) found.set(e.id, e);
      if (!Array.isArray(batch) || batch.length < 100) break;
    }
  } catch {
    return false;
  }
  const oldest = new Date(Date.now() - DAYS * 86400000).toISOString().slice(0, 19);
  const events = [...found.values()].filter((e) => e.at >= oldest).sort((a, b) => (a.at < b.at ? -1 : 1)).slice(-5000);
  const langs: Record<string, string> = { ...(kept.langs ?? {}) };
  const todo = [...new Set([...events].reverse().map((e) => e.repo))].filter((r) => r && !(r in langs)).slice(0, LANG_LOOKUPS);
  for (const repo of todo) {
    try {
      langs[repo] = String((await gh<{ language?: string }>(`/repos/${repo}`, token)).language ?? '');
    } catch {
      break;
    }
  }
  await AsyncStorage.setItem(KEY, JSON.stringify({ fetchedAt: new Date().toISOString(), events, langs }));
  return true;
}
