// Your saved data, locked: every file myGeeKy keeps in your storage (Google Drive or a GitHub repo) is
// encrypted on the device first. The same format as the desktop (src/mygeeky/datalock.py), byte for byte:
//
//   "MGK1" | nonce (12 random bytes) | ChaCha20-Poly1305(key, nonce, raw deflate(plaintext), AAD = label + name)
//
// What's in the storage (docs/STORAGE.md):
//   mygeeky.json                                  plain: which key the files are locked with (its id, never the key)
//   config.synced.json.mgk                        a state file: the latest copy wins
//   interest_events.2026-10.d3f1a2b4.jsonl.mgk    a log, split by month and by the device that wrote it
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { sha256 } from '@noble/hashes/sha2.js';
import { getRandomValues } from 'expo-crypto';
import { deflateSync, inflateSync } from 'fflate';
import { fromUtf8, utf8 } from './signal-crypto';

const MAGIC = utf8('MGK1');
const LABEL = 'mygeeky-data-v1:';
export const SUFFIX = '.mgk';
export const FORMAT_FILE = 'mygeeky.json';
export const UNDATED = '0000-00';
const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
const CODE_LEN = 56;
const NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/;
const LOG = /^([A-Za-z0-9_-]{1,60})\.(\d{4}-\d{2})\.([0-9a-f]{8})\.jsonl$/;

const random = (n: number) => { const a = new Uint8Array(n); getRandomValues(a); return a; };
const hex = (b: Uint8Array) => [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
const concat = (...parts: Uint8Array[]) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
};

export const newKey = () => random(32);
export const newDeviceId = () => hex(random(4));

/** A short name for the key that gives nothing away: two devices with the same id have the same key. */
export const keyId = (key: Uint8Array) => hex(sha256(concat(utf8('mygeeky-key-id:'), key))).slice(0, 16);

export const isSealed = (blob: Uint8Array) => blob.length >= 4 && MAGIC.every((b, i) => blob[i] === b);

export function seal(key: Uint8Array, name: string, plaintext: Uint8Array): Uint8Array {
  const nonce = random(12);
  return concat(MAGIC, nonce, chacha20poly1305(key, nonce, utf8(LABEL + name)).encrypt(deflateSync(plaintext)));
}

/** The plaintext, or null if this isn't a locked file, it was locked with another key, or it was changed. */
export function openSealed(key: Uint8Array, name: string, blob: Uint8Array): Uint8Array | null {
  if (!isSealed(blob) || blob.length < 32) return null;
  try {
    return inflateSync(chacha20poly1305(key, blob.slice(4, 16), utf8(LABEL + name)).decrypt(blob.slice(16)));
  } catch {
    return null;
  }
}

export const sealText = (key: Uint8Array, name: string, text: string) => seal(key, name, utf8(text));
export function openText(key: Uint8Array, name: string, blob: Uint8Array): string | null {
  const plain = openSealed(key, name, blob);
  return plain ? fromUtf8(plain) : null;
}

// ---- the recovery code: the key, written out to keep on paper (56 letters, no I, L, O or U)
const check = (key: Uint8Array) => sha256(concat(utf8('mygeeky-recovery:'), key)).slice(0, 3);

export function recoveryCode(key: Uint8Array): string {
  const data = concat(key, check(key));
  let bits = 0n;
  for (const b of data) bits = (bits << 8n) | BigInt(b);
  let text = '';
  for (let i = 0; i < CODE_LEN; i++) text += CROCKFORD[Number((bits >> BigInt(5 * (CODE_LEN - 1 - i))) & 31n)];
  return text.match(/.{4}/g)!.join('-');
}

/** The key a recovery code holds, or null if it's mistyped (its last letters check the rest). */
export function keyFromCode(text: unknown): Uint8Array | null {
  if (typeof text !== 'string') return null;
  const s = text.toUpperCase().replace(/[\s-]/g, '').replace(/O/g, '0').replace(/[IL]/g, '1');
  if (s.length !== CODE_LEN || [...s].some((c) => !CROCKFORD.includes(c))) return null;
  let bits = 0n;
  for (const c of s) bits = (bits << 5n) | BigInt(CROCKFORD.indexOf(c));
  const raw = new Uint8Array(35);
  for (let i = 34; i >= 0; i--) { raw[i] = Number(bits & 255n); bits >>= 8n; }
  const key = raw.slice(0, 32);
  return check(key).every((b, i) => b === raw[32 + i]) ? key : null;
}

// ---- what goes where
export function formatDoc(key: Uint8Array): string {
  return JSON.stringify({ format: 2, key: keyId(key), app: 'myGeeKy',
    note: 'Your myGeeKy data, encrypted on your devices. Only your devices can read it.' }, null, 1);
}

/** The key id a storage's mygeeky.json names, or null (no file, or not ours). */
export function formatKeyId(text: string | null): string | null {
  try {
    const doc = JSON.parse(text ?? 'null');
    const kid = doc && typeof doc === 'object' && doc.format === 2 ? doc.key : null;
    return typeof kid === 'string' && /^[0-9a-f]{16}$/.test(kid) ? kid : null;
  } catch {
    return null;
  }
}

export const validName = (name: string) => NAME.test(name) && !name.includes('..');
export const logChunk = (stem: string, month: string, device: string) => `${stem}.${month}.${device}.jsonl`;

export type Stored = { kind: 'state'; name: string } | { kind: 'log'; name: string; stem: string; month: string; device: string };

/** What a stored file is; null for anything else (mygeeky.json, someone else's file, a name that isn't safe). */
export function parseStored(stored: string): Stored | null {
  if (!stored.endsWith(SUFFIX)) return null;
  const name = stored.slice(0, -SUFFIX.length);
  if (!validName(name)) return null;
  const m = LOG.exec(name);
  if (m) return { kind: 'log', name, stem: m[1], month: m[2], device: m[3] };
  return name.endsWith('.jsonl') ? null : { kind: 'state', name };
}

/** The month a log line belongs to, from its time ("at", "timestamp"...); UNDATED if it has none. */
export function monthOf(line: string): string {
  let rec: unknown;
  try { rec = JSON.parse(line); } catch { return UNDATED; }
  if (rec && typeof rec === 'object' && !Array.isArray(rec)) {
    for (const k of ['at', 'timestamp', 'time', 'date', 'ts']) {
      const v = (rec as Record<string, unknown>)[k];
      if (typeof v === 'string') {
        const m = /^(\d{4}-\d{2})/.exec(v);
        if (m && m[1] >= '1970-01' && m[1] <= '2999-12') return m[1];
      }
    }
  }
  return UNDATED;
}

export const linesOf = (text: string) => text.split(/\r\n|\r|\n/).filter((l) => l.trim());
