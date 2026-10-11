// The pure part of Signals on the phone (no phone APIs), so it can be checked against the
// desktop's Python in Node: reading beacons, opening boxes, sealing signals and adding to
// your beacon. See signals.ts for the parts that talk to GitHub and the phone's storage.
import { BOX_LEN, fromUtf8, openBox, seal, unb64, utf8, validPublicKey } from './signal-crypto';

export const NAME_RE = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/;
export const BEACON_REPO = 'mygeeky-beacon';
export const TOPIC = 'mygeeky-beacon';
export const SCHEMA = 2;
export const MAX_KEYS = 4;
export const MAX_SEALED_READ = 600;
export const MAX_PER_SENDER = 5;
export const MAX_USERS = 60;
export const TTL_DAYS = 90;
export const REPEAT_DAYS = 30;
export const DAILY_LIMIT = 10;
export const WEEKLY_NEW_PEOPLE = 5;

export const GESTURES: Record<string, [string, string]> = {
  thanks: ['🙏', 'thanked you for your work'],
  learn: ['📚', 'learned from your work'],
  used: ['⭐', 'used your work'],
  watching: ['👀', 'is following your work'],
  collab: ['🤝', 'would like to collaborate'],
};
export const MUTUAL_TEXT = '🤝 you both want to collaborate';
export const STATUSES: Record<string, string> = {
  '': '', 'open-to-collab': '🤝 open to collaborate', learning: '🌱 learning something new',
  'heads-down': '🎧 heads-down', 'seeking-reviewers': '🔍 looking for reviewers', mentoring: '🧭 happy to mentor',
};
export const REPO_RE = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}\/[A-Za-z0-9._-]{1,100}$/;
export const INTEREST_RE = /^[\w .+#-]{1,40}$/u;

export type Parsed = { owner: string; avatar: string; status: string; quiet: boolean; interests: string[];
  keys: string[]; sealed: string[] };
export type Received = { from: string; avatar: string; type: string; emoji: string; text: string; repo: string;
  at: string; mutual: boolean };
export type Person = { login: string; avatar: string; status: string; interests: string[]; shared: string[];
  signalledYou: boolean; youSignalled: boolean; canReceive: boolean };
export type Sent = { to: string; type: string; repo?: string; at: string };

export const validLogin = (v: unknown): v is string => typeof v === 'string' && NAME_RE.test(v);
export const validRepo = (v: unknown): v is string => typeof v === 'string' && REPO_RE.test(v) && !v.includes('..');
export const isoNow = () => new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00');    // what Python 3.9 can read
export const parseTime = (v: unknown) => {
  if (typeof v !== 'string') return null;
  const t = Date.parse(v.length === 10 ? `${v}T00:00:00Z` : v);
  return Number.isNaN(t) ? null : t;
};
export const DAY = 86400000;


// ---- reading beacons (anyone's: untrusted input, checked like the desktop does)
export function parseBeacon(raw: unknown, owner: string, now = Date.now()): Parsed | null {
  const r = raw as Record<string, unknown>;
  if (!r || typeof r !== 'object' || r.mygeeky_beacon !== SCHEMA || !validLogin(owner)) return null;
  const oldest = now - TTL_DAYS * DAY;
  const interests = (Array.isArray(r.interests) ? r.interests : [])
    .filter((i): i is string => typeof i === 'string' && INTEREST_RE.test(i)).map((i) => i.toLowerCase()).slice(0, 12);
  const keys = (Array.isArray(r.keys) ? r.keys : []).slice(0, MAX_KEYS).filter(validPublicKey) as string[];
  const sealed: string[] = [];
  for (const s of (Array.isArray(r.sealed) ? r.sealed : []).slice(0, MAX_SEALED_READ)) {
    const box = (s as { box?: unknown })?.box;
    const at = parseTime((s as { at?: unknown })?.at);
    if (typeof box !== 'string' || box.length !== BOX_LEN || at === null) continue;
    if (at < oldest - DAY || at > now + DAY) continue;
    sealed.push(box);
  }
  return { owner, avatar: '', status: STATUSES[String(r.status ?? '')] ?? '', quiet: r.quiet === true,
    interests, keys, sealed };
}

/** Signals in someone's beacon that are for `me` and that this phone's key opens. A box
 *  must name the beacon's owner as sender and you as recipient: a copied box fails. */
export function openSignals(p: Parsed, me: string, priv: string, now = Date.now()) {
  const out: { type: string; at: string; repo?: string }[] = [];
  for (const box of p.sealed) {
    const plain = openBox(priv, box);
    const text = plain ? fromUtf8(plain) : null;
    if (!text) continue;
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(text);
    } catch {
      continue;
    }
    if (!msg || typeof msg.type !== 'string' || !GESTURES[msg.type]) continue;
    if (String(msg.from ?? '').toLowerCase() !== p.owner.toLowerCase()) continue;
    if (String(msg.to ?? '').toLowerCase() !== me.toLowerCase()) continue;
    const at = parseTime(msg.at);
    if (at === null || at < now - TTL_DAYS * DAY || at > now + DAY) continue;
    if (msg.type === 'used' && !validRepo(msg.repo)) continue;
    out.push({ type: msg.type, at: new Date(at).toISOString(), ...(msg.type === 'used' ? { repo: msg.repo as string } : {}) });
  }
  return out;
}


export const decodeContent = (content: unknown) => {
  const bytes = unb64(String(content ?? '').replace(/\s/g, ''));
  const text = bytes ? fromUtf8(bytes) : null;
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
};


/** Your beacon with this phone's key and new boxes added, everything else kept as it is. */
export function mergeIntoBeacon(remote: Record<string, unknown>, phonePub: string,
                                newBoxes: string[], now = Date.now()): Record<string, unknown> {
  const keys = (Array.isArray(remote.keys) ? remote.keys : []).filter(validPublicKey) as string[];
  if (!keys.includes(phonePub) && keys.length >= MAX_KEYS) {
    // never push out a computer's key: that computer would quietly stop receiving signals
    throw new Error(`Your beacon already has ${MAX_KEYS} devices on Signals, the most it can hold.`);
  }
  const withPhone = keys.includes(phonePub) ? keys : [...keys, phonePub];
  const oldest = now - TTL_DAYS * DAY;
  const today = new Date(now).toISOString().slice(0, 10);
  const sealed = (Array.isArray(remote.sealed) ? remote.sealed : [])
    .filter((s) => {
      const box = (s as { box?: unknown })?.box;
      const at = parseTime((s as { at?: unknown })?.at);
      return typeof box === 'string' && box.length === BOX_LEN && at !== null && at > oldest - DAY;
    }) as { at: string; box: string }[];
  const have = new Set(sealed.map((s) => s.box));
  for (const box of newBoxes) if (!have.has(box)) sealed.push({ at: today, box });
  return { ...remote, mygeeky_beacon: SCHEMA, keys: withPhone,
    sealed: sealed.sort((a, b) => a.at.localeCompare(b.at)) };
}


/** The sealed boxes of one signal: one per key of the recipient (each of their devices). */
export function sealSignal(me: string, to: string, toKeys: string[], gesture: string, repo: string | undefined,
                           at: string): string[] {
  const msg: Record<string, unknown> = { at, from: me, to, type: gesture, v: SCHEMA };
  if (gesture === 'used') msg.repo = repo;
  const text = JSON.stringify(Object.fromEntries(Object.entries(msg).sort(([a], [b]) => a.localeCompare(b))));
  return toKeys.slice(0, MAX_KEYS).map((k) => seal(k, utf8(text)));
}
