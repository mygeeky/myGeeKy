// "Is this you?" on the phone: the search kept while OpenAlex was busy, what a later try found, and what you
// confirmed -- the desktop's whois state (gui/app.py whois_*). Finding and ranking is lib/whois.ts.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as W from './whois';

const KEY = 'mygeeky.whois';
export type WhoisState = {
  pending?: { name: string; hint: string; nextTry: number };
  found?: W.Candidate[];
  none?: boolean;
  confirmed?: string;
};

export async function loadWhois(): Promise<WhoisState> {
  try {
    const s = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    return s && typeof s === 'object' ? s : {};
  } catch {
    return {};
  }
}

export const saveWhois = (s: WhoisState) => AsyncStorage.setItem(KEY, JSON.stringify(s));

/** OpenAlex was busy: keep the search, to try again after Retry-After (at least half an hour). */
export async function keepPending(name: string, hint: string, retryAfter = 0): Promise<void> {
  await saveWhois({ pending: { name, hint, nextTry: W.nextTry(Date.now() / 1000, retryAfter) } });
}

/** A pending search whose time has come: try it. The candidates if OpenAlex answered (to ask "Is this you?"). */
export async function retryWhois(): Promise<W.Candidate[]> {
  const s = await loadWhois();
  const p = s.pending;
  if (!p || Date.now() / 1000 < p.nextTry) return [];
  const out = await W.search(p.name, p.hint);
  if (out.status === 'busy') {
    await keepPending(p.name, p.hint, out.retry_after ?? 0);
    return [];
  }
  if (out.status === 'none') {
    await saveWhois({ none: true });
    return [];
  }
  await saveWhois({ found: out.candidates });
  return out.candidates;
}
