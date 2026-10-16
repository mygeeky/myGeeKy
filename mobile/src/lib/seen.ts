// What you have already seen, as the desktop's freshness.py does it: the number on a planet is what is new
// to you, new things come first with a dot, and the ones you have seen step aside. Kept on this phone only.
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'mygeeky.seen';
const KEEP = 4000;             // the newest this many; older ones are forgotten (and would count as new again)

export async function loadSeen(): Promise<Set<string>> {
  try {
    const v = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '[]');
    return new Set(Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []);
  } catch {
    return new Set();
  }
}

/** Remember these as seen; returns the updated set. */
export async function markSeen(seen: Set<string>, ids: string[]): Promise<Set<string>> {
  const fresh = ids.filter((id) => !seen.has(id));
  if (!fresh.length) return seen;
  const next = [...seen, ...fresh].slice(-KEEP);
  try { await AsyncStorage.setItem(KEY, JSON.stringify(next)); } catch { /* the dots come back next time */ }
  return new Set(next);
}
