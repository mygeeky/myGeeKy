// Private signals: only the person a signal is for can read it. The same scheme as the
// desktop (src/mygeeky/signal_crypto.py), byte for byte, so phones and computers read
// each other's signals:
//
//   ephemeral X25519 key  ->  shared secret with the recipient's key
//   HKDF-SHA256(shared, info = label | ephemeral pub | recipient pub)  ->  key
//   ChaCha20-Poly1305(key, zero nonce -- every key is used exactly once, AAD = label)
//
//   box = base64(ephemeral pub (32 bytes) || ciphertext + tag), plaintext padded to 256 bytes
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { x25519 } from '@noble/curves/ed25519.js';
import { hkdf } from '@noble/hashes/hkdf.js';
import { sha256 } from '@noble/hashes/sha2.js';
import { getRandomValues } from 'expo-crypto';

// noble draws randomness from crypto.getRandomValues; a phone gets it from expo-crypto
const g = globalThis as { crypto?: { getRandomValues?: unknown } };
if (!g.crypto?.getRandomValues) {
  g.crypto = { ...(g.crypto ?? {}), getRandomValues: getRandomValues as unknown };
}

/** UTF-8 without TextEncoder/TextDecoder (not in every phone's JavaScript engine). */
export function utf8(text: string): Uint8Array {
  const out: number[] = [];
  for (const ch of text) {
    let c = ch.codePointAt(0) as number;
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else {
      c = Math.min(c, 0x10ffff);
      out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
  }
  return Uint8Array.from(out);
}

export function fromUtf8(bytes: Uint8Array): string | null {
  let out = '';
  for (let i = 0; i < bytes.length;) {
    const b = bytes[i];
    const n = b < 0x80 ? 1 : (b & 0xe0) === 0xc0 ? 2 : (b & 0xf0) === 0xe0 ? 3 : (b & 0xf8) === 0xf0 ? 4 : 0;
    if (!n || i + n > bytes.length) return null;
    let c = n === 1 ? b : b & (0xff >> (n + 1));
    for (let k = 1; k < n; k++) {
      if ((bytes[i + k] & 0xc0) !== 0x80) return null;
      c = (c << 6) | (bytes[i + k] & 63);
    }
    out += String.fromCodePoint(c);
    i += n;
  }
  return out;
}

const LABEL = utf8('mygeeky-signal-v2');
const PAD_TO = 256;
const NONCE = new Uint8Array(12);

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

export function b64(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] ?? 0) << 8) | (bytes[i + 2] ?? 0);
    out += B64[(n >> 18) & 63] + B64[(n >> 12) & 63];
    out += i + 1 < bytes.length ? B64[(n >> 6) & 63] : '=';
    out += i + 2 < bytes.length ? B64[n & 63] : '=';
  }
  return out;
}

export function unb64(text: unknown): Uint8Array | null {
  if (typeof text !== 'string' || text.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(text)) return null;
  const pad = text.endsWith('==') ? 2 : text.endsWith('=') ? 1 : 0;
  const out = new Uint8Array((text.length / 4) * 3 - pad);
  let j = 0;
  for (let i = 0; i < text.length; i += 4) {
    const n = (B64.indexOf(text[i]) << 18) | (B64.indexOf(text[i + 1]) << 12)
      | ((text[i + 2] === '=' ? 0 : B64.indexOf(text[i + 2])) << 6) | (text[i + 3] === '=' ? 0 : B64.indexOf(text[i + 3]));
    if (j < out.length) out[j++] = (n >> 16) & 255;
    if (j < out.length) out[j++] = (n >> 8) & 255;
    if (j < out.length) out[j++] = n & 255;
  }
  return out;
}

export const BOX_LEN = b64(new Uint8Array(32 + PAD_TO + 16)).length;   // after b64/B64 exist

const concat = (...parts: Uint8Array[]) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
};

/** [private, public], both base64 of the raw 32-byte keys. */
export function newKeypair(): [string, string] {
  const priv = x25519.utils.randomSecretKey();
  return [b64(priv), b64(x25519.getPublicKey(priv))];
}

export function publicOf(privateB64: string): string {
  return b64(x25519.getPublicKey(unb64(privateB64) as Uint8Array));
}

export function validPublicKey(value: unknown): boolean {
  const raw = typeof value === 'string' && value.length === 44 ? unb64(value) : null;
  return !!raw && raw.length === 32;
}

const keyFor = (shared: Uint8Array, ephPub: Uint8Array, recipientPub: Uint8Array) =>
  hkdf(sha256, shared, undefined, concat(LABEL, ephPub, recipientPub), 32);

export function seal(recipientPubB64: string, plaintext: Uint8Array): string {
  if (plaintext.length > PAD_TO) throw new Error('signal too long to seal');
  const recipientPub = unb64(recipientPubB64);
  if (!recipientPub || recipientPub.length !== 32) throw new Error('not a public key');
  const eph = x25519.utils.randomSecretKey();
  const ephPub = x25519.getPublicKey(eph);
  const shared = x25519.getSharedSecret(eph, recipientPub);
  const padded = new Uint8Array(PAD_TO);
  padded.set(plaintext);
  const body = chacha20poly1305(keyFor(shared, ephPub, recipientPub), NONCE, LABEL).encrypt(padded);
  return b64(concat(ephPub, body));
}

/** The plaintext if this box was sealed to our key, else null (never throws). */
export function openBox(privateB64: string, box: unknown): Uint8Array | null {
  if (typeof box !== 'string' || box.length !== BOX_LEN) return null;
  const data = unb64(box);
  const priv = unb64(privateB64);
  if (!data || !priv || data.length < 48 || priv.length !== 32) return null;
  try {
    const ephPub = data.slice(0, 32);
    const shared = x25519.getSharedSecret(priv, ephPub);
    const padded = chacha20poly1305(keyFor(shared, ephPub, x25519.getPublicKey(priv)), NONCE, LABEL)
      .decrypt(data.slice(32));
    let end = padded.length;
    while (end > 0 && padded[end - 1] === 0) end--;
    return padded.slice(0, end);
  } catch {
    return null;
  }
}
