// Your 👍 and 👎: a port of the desktop's taste.py. A vote remembers the item and a
// few of its terms (its tags, a few title words), so it teaches more than that one
// item. Votes fade over a year, live only on this phone, and the same thumb again
// takes a vote back.
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'mygeeky.taste';
const HALF_LIFE_DAYS = 365;
const MAX_TERMS = 10;
const MAX_VOTES = 2000;
export const KINDS = ['skill', 'resource', 'job', 'funding', 'conference', 'collaborator'] as const;
export type Kind = (typeof KINDS)[number];
type Vote = { vote: 1 | -1; kind: Kind; terms: string[]; at: string };
const SKIP = new Set((
  'the and for with from into this that your their our are was were has have had not but all any can new using use based ' +
  'via about over under more most other some such than then them they its position positions job jobs phd postdoc ' +
  'postdoctoral master masters student students fellow fellowship research researcher scientist university institute ' +
  'department lab laboratory group center centre program programme course courses tutorial tutorials learn learning ' +
  'conference conferences annual international workshop call grant grants funding award awards apply application deadline open'
).split(' '));

export const keyOf = (kind: string, id: string) => `${kind}:${String(id).trim().toLowerCase()}`;

export function termsOf(text = '', tags: string[] = []): string[] {
  const out: string[] = [];
  for (const t of tags) {
    const s = String(t).toLowerCase().replace(/_/g, ' ').split(/\s+/).join(' ').trim();
    if (s.length >= 2 && s.length <= 40 && !out.includes(s)) out.push(s);
  }
  for (const m of (text || '').toLowerCase().matchAll(/[a-z][a-z0-9+#.-]{2,}/g)) {
    const w = m[0].replace(/^[.-]+|[.-]+$/g, '');
    if (w.length >= 3 && !SKIP.has(w) && !out.includes(w)) out.push(w);
  }
  return out.slice(0, MAX_TERMS);
}

let memo: Record<string, Vote> | null = null;

export async function load(): Promise<Record<string, Vote>> {
  if (memo) return memo;
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '{}');
    const votes = raw && typeof raw === 'object' && raw.votes && typeof raw.votes === 'object' ? raw.votes : {};
    memo = Object.fromEntries(Object.entries(votes).filter(([, v]: [string, any]) => v && (v.vote === 1 || v.vote === -1))) as Record<string, Vote>;
  } catch {
    memo = {};
  }
  return memo;
}

async function save(votes: Record<string, Vote>) {
  let entries = Object.entries(votes);
  if (entries.length > MAX_VOTES) entries = entries.sort((a, b) => b[1].at.localeCompare(a[1].at)).slice(0, MAX_VOTES);
  memo = Object.fromEntries(entries);
  await AsyncStorage.setItem(KEY, JSON.stringify({ votes: memo }));
}

/** 👍 (up) or 👎; the same thumb again takes it back. Returns the vote now in place: 1, -1 or 0. */
export async function vote(kind: Kind, id: string, up: boolean, text = '', tags: string[] = []): Promise<number> {
  if (!KINDS.includes(kind) || !String(id).trim()) return 0;
  const votes = { ...(await load()) };
  const k = keyOf(kind, id);
  const value = up ? 1 : -1;
  if (votes[k]?.vote === value) {
    delete votes[k];
    await save(votes);
    return 0;
  }
  votes[k] = { vote: value, kind, terms: termsOf(text, tags), at: new Date().toISOString() };
  await save(votes);
  return value;
}

export function voteOf(votes: Record<string, Vote>, kind: string, id: string): number {
  return votes[keyOf(kind, id)]?.vote ?? 0;
}

/** Take back every 👎 on one kind of thing, so they show again. */
export async function unhide(kind: Kind): Promise<number> {
  const votes = { ...(await load()) };
  const drop = Object.keys(votes).filter((k) => votes[k].kind === kind && votes[k].vote === -1);
  for (const k of drop) delete votes[k];
  if (drop.length) await save(votes);
  return drop.length;
}

/** term -> how much your votes like it (+) or don't (-), fading with time. */
export function weights(votes: Record<string, Vote>, kinds?: string[], now = Date.now()): Record<string, number> {
  const out: Record<string, number> = {};
  for (const v of Object.values(votes)) {
    if (kinds && !kinds.includes(v.kind)) continue;
    const age = Math.max((now - Date.parse(v.at)) / 86400000, 0) || 0;
    const fade = Math.pow(0.5, age / HALF_LIFE_DAYS);
    v.terms.forEach((t, i) => {
      out[t] = (out[t] ?? 0) + v.vote * (i < 3 ? 1 : 0.5) * fade;
    });
  }
  return out;
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** -1..1: how your votes lean on something with this text and these tags. */
export function lean(text: string, tags: string[], w: Record<string, number>): number {
  const hay = [(text || '').toLowerCase(), ...tags.map((t) => String(t).toLowerCase().replace(/_/g, ' '))].join(' ');
  let total = 0;
  for (const [t, v] of Object.entries(w)) {
    if (new RegExp(`(^|[^a-z0-9])${esc(t)}s?(?![a-z0-9])`).test(hay)) total += v;
  }
  return Math.tanh(total / 2);
}
