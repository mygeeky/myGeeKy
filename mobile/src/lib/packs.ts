// 📦 Packs: share your setup like a seed, in one to three QR codes (the desktop's packs.py: same format, same checks).
// A pack holds only what you ticked: keywords and topics, your research field, the researchers you follow, a note.
// Every code says which pack, which part and how many: `mygeeky-pack:1:<pack id>:<part>/<parts>:<piece>`, so the
// receiver knows from the first scan how many codes to expect and counts them in any order. The pack id is the
// CRC-32 of the compressed pack, so a mixed-up or damaged set is never imported. A pack is untrusted data: every
// field is checked on arrival, and nothing in it can run.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { strFromU8, strToU8, unzlibSync, zlibSync } from 'fflate';
import type { Settings } from './storage';

export const PREFIX = 'mygeeky-pack:1:';
const CHUNK = 700, MAX_CODES = 3, MAX_WORDS = 40, MAX_FIELD = 8, MAX_PEOPLE = 30, MAX_NOTE = 120;
const AID = /^A\d{2,12}$/;
const PART = /^mygeeky-pack:1:([0-9a-f]{8}):(\d)\/(\d):([A-Za-z0-9_-]+)$/;
const UNDO_KEY = 'mygeeky.pack.undo';

export type Pack = { v: 1; n: string; k: string[]; t: string[]; f: string[]; r: [string, string][] };
export type Part = { id: string; i: number; n: number; piece: string };
/** What the receiver has so far: one pack at a time. */
export type Gathering = { id: string; n: number; pieces: Record<number, string> };

function words(v: unknown, n = MAX_WORDS, len = 80): string[] {
  const out: string[] = [];
  for (const x of Array.isArray(v) ? v : []) {
    if (typeof x === 'string' && x.trim() && !out.includes(x.trim().slice(0, len))) out.push(x.trim().slice(0, len));
  }
  return out.slice(0, n);
}

export function clean(raw: unknown): Pack {
  const d = raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const people: [string, string][] = [];
  for (const p of Array.isArray(d.r) ? d.r : []) {
    if (Array.isArray(p) && p.length >= 2 && typeof p[0] === 'string' && AID.test(p[0]) && typeof p[1] === 'string'
        && !people.some((q) => q[0] === p[0])) people.push([p[0], p[1].trim().slice(0, 120)]);
  }
  const note = typeof d.n === 'string' ? d.n.split(/\s+/).filter(Boolean).join(' ').slice(0, MAX_NOTE) : '';
  return { v: 1, n: note, k: words(d.k), t: words(d.t), f: words(d.f, MAX_FIELD), r: people.slice(0, MAX_PEOPLE) };
}

/** A pack from your setup: `parts` is what you ticked ('words', 'field', 'people'). */
export function make(s: Settings, parts: Set<string>, note: string, following: { id: string; name: string }[]): Pack {
  return clean({ n: note, k: parts.has('words') ? s.keywords : [], t: parts.has('words') ? s.topics : [],
    f: parts.has('field') ? s.field : [], r: parts.has('people') ? following.map((p) => [p.id, p.name]) : [] });
}

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
export function crc32(b: Uint8Array): string {
  let c = 0xffffffff;
  for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xff] ^ (c >>> 8);
  return ((c ^ 0xffffffff) >>> 0).toString(16).padStart(8, '0');
}

function b64(raw: Uint8Array): string {
  let s = '';
  for (let i = 0; i < raw.length; i++) s += String.fromCharCode(raw[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function unb64(s: string): Uint8Array {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (ch) => ch.charCodeAt(0));
}

/** The pack as QR texts, one per code ([] when it's too big for three). */
export function codes(pack: Pack): string[] {
  const raw = zlibSync(strToU8(JSON.stringify(clean(pack))), { level: 9 });
  const body = b64(raw), id = crc32(raw), n = Math.ceil(body.length / CHUNK);
  if (n > MAX_CODES) return [];
  const size = Math.ceil(body.length / n);
  return Array.from({ length: n }, (_, i) => `${PREFIX}${id}:${i + 1}/${n}:${body.slice(i * size, (i + 1) * size)}`);
}

export function part(text: string): Part | null {
  const m = typeof text === 'string' ? PART.exec(text.trim()) : null;
  if (!m) return null;
  const i = Number(m[2]), n = Number(m[3]);
  return i >= 1 && i <= n && n <= MAX_CODES ? { id: m[1], i, n, piece: m[4] } : null;
}

export function assemble(pieces: Record<number, string>, id: string): Pack | null {
  try {
    const raw = unb64(Object.keys(pieces).map(Number).sort((a, b) => a - b).map((i) => pieces[i]).join(''));
    if (crc32(raw) !== id) return null;
    const out = unzlibSync(raw);
    if (out.length > 64000) return null;
    return clean(JSON.parse(strFromU8(out)));
  } catch {
    return null;
  }
}

/** One scan, added to what was gathered. `got`: 'new' (a part we didn't have), 'again' (already have it), 'other' (a
 * code from a different pack: we start over with it), 'bad' (not a pack code), 'done' (all parts: `pack` is ready),
 * 'broken' (all parts, but they don't make a pack). */
export function receive(g: Gathering | null, text: string): { g: Gathering | null; got: 'new' | 'again' | 'other' | 'bad' | 'done' | 'broken'; pack?: Pack } {
  const p = part(text);
  if (!p) return { g, got: 'bad' };
  const other = !!g && (g.id !== p.id || g.n !== p.n);
  if (g && !other && g.pieces[p.i] !== undefined) return { g, got: 'again' };
  const next: Gathering = { id: p.id, n: p.n, pieces: { ...(other || !g ? {} : g.pieces), [p.i]: p.piece } };
  if (Object.keys(next.pieces).length < p.n) return { g: next, got: other ? 'other' : 'new' };
  const pack = assemble(next.pieces, p.id);
  return pack ? { g: next, got: 'done', pack } : { g: null, got: 'broken' };
}

/** Which parts are still missing, e.g. [2, 3]. */
export const missing = (g: Gathering | null): number[] =>
  g ? Array.from({ length: g.n }, (_, i) => i + 1).filter((i) => g.pieces[i] === undefined) : [];

export function describe(p: Pack): string {
  const bits: string[] = [];
  if (p.k.length || p.t.length) bits.push(`${p.k.length + p.t.length} keywords and topics`);
  if (p.f.length) bits.push('a research field');
  if (p.r.length) bits.push(`${p.r.length} researcher${p.r.length !== 1 ? 's' : ''} to follow`);
  return bits.join(', ') || 'nothing yet';
}

/** Your keywords/topics/field after importing (packs.apply): 'merge' only adds, 'start' starts from the pack's. */
export function applyPack(mine: { keywords: string[]; topics: string[]; field: string[] }, pack: Pack, how: 'merge' | 'start') {
  const one = (have: string[], add: string[]) => {
    if (how === 'start' && add.length) return [...add];
    const low = new Set(have.map((x) => x.toLowerCase()));
    return [...have, ...add.filter((x) => !low.has(x.toLowerCase()))];
  };
  return { keywords: one(mine.keywords ?? [], pack.k), topics: one(mine.topics ?? [], pack.t), field: one(mine.field ?? [], pack.f) };
}

export type Undo = { at: string; note: string; before: { keywords: string[]; topics: string[]; field: string[] }; followed: string[] };

export async function loadUndo(): Promise<Undo | null> {
  try { return JSON.parse((await AsyncStorage.getItem(UNDO_KEY)) ?? 'null'); } catch { return null; }
}
export async function saveUndo(u: Undo | null): Promise<void> {
  if (u) await AsyncStorage.setItem(UNDO_KEY, JSON.stringify(u)); else await AsyncStorage.removeItem(UNDO_KEY);
}
