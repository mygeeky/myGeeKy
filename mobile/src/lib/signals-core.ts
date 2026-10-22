// The pure part of Signals on the phone (no phone APIs), so it can be checked against the
// desktop's Python in Node: reading beacons, opening boxes, sealing signals and adding to
// your beacon. See signals.ts for the parts that talk to GitHub and the phone's storage.
import { BOX_LEN, fromUtf8, openBox, PAD_TO, randomHex, seal, unb64, utf8, validPublicKey } from './signal-crypto';

// The Signals terms (website/terms.html), word for word the desktop's beacon.py: agreed to before turning Signals on
// here or posting a call. A new date asks everyone again.
export const TERMS_VERSION = '2026-10-21';
export const TERMS_URL = 'https://mygeeky.org/terms.html';
export const TERMS_POINTS = [
  'Your beacon is public: your status, your interest tags and the calls you post can be read by anyone.',
  'Be kind and honest: no harassment, hate, threats, spam, scams, sexual content or anything illegal.',
  "Never post someone else's private information.",
  'You can block anyone, and report a beacon to GitHub or to support@mygeeky.org.',
  "A beacon that breaks these rules is hidden from everyone's myGeeKy.",
];
export const TERMS_NEEDED = 'Agree to the Signals terms first (mygeeky.org/terms.html).';

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
  join: ['🙋', 'would like to help with your project'],     // an answer to one of your calls (carries its id)
};
export const MUTUAL_TEXT = '🤝 you both want to collaborate';
export const STATUSES: Record<string, string> = {
  '': '', 'open-to-collab': '🤝 open to collaborate', learning: '🌱 learning something new',
  'heads-down': '🎧 heads-down', 'seeking-reviewers': '🔍 looking for reviewers', mentoring: '🧭 happy to mentor',
};
export const REPO_RE = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}\/[A-Za-z0-9._-]{1,100}$/;
export const INTEREST_RE = /^[\w .+#-]{1,40}$/u;

export type Call = { id: string; repo: string; note: string; skills: string[]; level: string; time: string;
  created: string; until: string; filled: boolean };
export type Parsed = { owner: string; avatar: string; status: string; quiet: boolean; interests: string[];
  keys: string[]; sealed: string[]; calls: Call[] };
export type Received = { from: string; avatar: string; type: string; emoji: string; text: string; repo: string;
  at: string; mutual: boolean; call?: string; skills?: string[] };
export type Person = { login: string; avatar: string; status: string; interests: string[]; shared: string[];
  signalledYou: boolean; youSignalled: boolean; canReceive: boolean; fit: number };
export type Sent = { to: string; type: string; repo?: string; at: string; call?: string; boxes?: string[] };

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
    interests, keys, sealed, calls: callsIn(r, now) };
}

/** Signals in someone's beacon that are for `me` and that this phone's key opens. A box
 *  must name the beacon's owner as sender and you as recipient: a copied box fails. */
export function openSignals(p: Parsed, me: string, priv: string, now = Date.now()) {
  const out: { type: string; at: string; repo?: string; call?: string; skills?: string[] }[] = [];
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
    if (msg.type === 'join' && !validCallId(msg.call)) continue;
    out.push({ type: msg.type, at: new Date(at).toISOString(), ...(msg.type === 'used' ? { repo: msg.repo as string } : {}),
      ...(msg.type === 'join' ? { call: msg.call as string,
        skills: cleanInterests(Array.isArray(msg.skills) ? msg.skills : []).slice(0, MAX_JOIN_SKILLS) } : {}) });
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


/** Your beacon with this phone's key and new boxes added, everything else kept as it is.
 *  `opts.calls` replaces your calls; `opts.removeBoxes` takes signals back. */
export function mergeIntoBeacon(remote: Record<string, unknown>, phonePub: string,
                                newBoxes: string[], now = Date.now(),
                                opts: { calls?: Call[]; removeBoxes?: string[] } = {}): Record<string, unknown> {
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
  const gone = new Set(opts.removeBoxes ?? []);
  const kept = sealed.filter((s) => !gone.has(s.box));
  const have = new Set(kept.map((s) => s.box));
  for (const box of newBoxes) if (!have.has(box)) kept.push({ at: today, box });
  const calls = opts.calls !== undefined ? callsIn({ calls: opts.calls }, now) : callsIn(remote, now);
  return { ...remote, mygeeky_beacon: SCHEMA, keys: withPhone,
    sealed: kept.sort((a, b) => a.at.localeCompare(b.at)), calls };
}


/** The sealed boxes of one signal: one per key of the recipient (each of their devices).
 *  A "join" names the call (`call`) and carries the `skills` of yours that matched it. */
export function sealSignal(me: string, to: string, toKeys: string[], gesture: string, repo: string | undefined,
                           at: string, call?: string, skills: string[] = []): string[] {
  const msg: Record<string, unknown> = { at, from: me, to, type: gesture, v: SCHEMA };
  if (gesture === 'used') msg.repo = repo;
  if (gesture === 'join') {
    msg.call = call;
    msg.skills = cleanInterests(skills).slice(0, MAX_JOIN_SKILLS);
  }
  const textOf = () => JSON.stringify(Object.fromEntries(Object.entries(msg).sort(([a], [b]) => (a < b ? -1 : 1))));
  while (utf8(textOf()).length > PAD_TO && Array.isArray(msg.skills) && msg.skills.length) msg.skills.pop();  // always fits
  const text = textOf();
  return toKeys.slice(0, MAX_KEYS).map((k) => seal(k, utf8(text)));
}


// ---- calls for contributors (the same rules as the desktop's beacon.py)
// A call is a public invitation to help with one of the caller's own repos, kept in their
// beacon.json under "calls". Nobody is targeted: each reader's own myGeeKy decides whether it
// fits them. "I'm in" is a sealed "join" signal to the caller with the skills that matched.
export const MAX_CALLS = 3;
export const MAX_CALL_SKILLS = 6;
export const MAX_JOIN_SKILLS = 3;
export const MAX_NOTE = 200;
export const CALL_DAYS = [30, 60, 90];
export const CALL_LEVELS: Record<string, string> = { first: 'good first task', any: 'any level', experienced: 'experienced' };
export const CALL_TIMES: Record<string, string> = { afternoon: 'an afternoon', hours: 'a few hours', weeks: 'a few weeks',
  ongoing: 'ongoing' };
const CALL_ID_RE = /^[0-9a-f]{8}$/;
const REPO_NAME_RE = /^[A-Za-z0-9._-]{1,100}$/;
const LINK_RE = /(https?:|www\.|\b[\w-]+\.(?:com|org|net|io|ai|dev|app|xyz|ly|me|co|gg|link)\b|@\w)/i;
const CONTROL_RE = /[\u0000-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g;

export const validCallId = (v: unknown): v is string => typeof v === 'string' && CALL_ID_RE.test(v);
const today = (now: number) => new Date(now).toISOString().slice(0, 10);
const dayOf = (v: unknown) => (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`))
  && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v ? Date.parse(`${v}T00:00:00Z`) : null);

/** Interest tags as the desktop cleans them: lower case, single spaces, a safe alphabet, no repeats. */
export function cleanInterests(values: unknown[]): string[] {
  const out: string[] = [];
  for (const v of values) {
    if (typeof v !== 'string') continue;
    const t = v.trim().toLowerCase().split(/\s+/).filter(Boolean).join(' ');
    if (INTEREST_RE.test(t) && !out.includes(t)) out.push(t);
    if (out.length >= 12) break;
  }
  return out;
}

/** A call's sentence: plain text, one line, 10 to 200 characters, no links or @mentions. */
export function cleanNote(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const text = v.replace(CONTROL_RE, ' ').split(/\s+/).filter(Boolean).join(' ');
  const n = [...text].length;
  return n >= 10 && n <= MAX_NOTE && !LINK_RE.test(text) ? text : null;
}

export function parseCall(raw: unknown, now = Date.now()): Call | null {
  const r = raw as Record<string, unknown>;
  if (!r || typeof r !== 'object') return null;
  const note = cleanNote(r.note);
  const created = dayOf(r.created);
  const until = dayOf(r.until);
  const skills = cleanInterests(Array.isArray(r.skills) ? r.skills : []).slice(0, MAX_CALL_SKILLS);
  const t = Date.parse(`${today(now)}T00:00:00Z`);
  if (!validCallId(r.id) || typeof r.repo !== 'string' || !REPO_NAME_RE.test(r.repo) || r.repo === '.' || r.repo === '..'
      || note === null || !skills.length || !CALL_LEVELS[String(r.level)] || !CALL_TIMES[String(r.time)]
      || created === null || until === null || until < t || created > t + DAY
      || (until - created) / DAY > Math.max(...CALL_DAYS) + 1) return null;
  return { id: r.id, repo: r.repo, note, skills, level: String(r.level), time: String(r.time),
    created: r.created as string, until: r.until as string, filled: r.filled === true };
}

/** The valid, unexpired calls in a beacon (at most MAX_CALLS, newest first). */
export function callsIn(raw: unknown, now = Date.now()): Call[] {
  const items = (raw && typeof raw === 'object' && Array.isArray((raw as { calls?: unknown }).calls))
    ? (raw as { calls: unknown[] }).calls.slice(0, 20) : [];
  const seen = new Set<string>();
  const out: Call[] = [];
  for (const c of items) {
    const call = parseCall(c, now);
    if (call && !seen.has(call.id)) {
      seen.add(call.id);
      out.push(call);
    }
  }
  return out.sort((a, b) => (a.created < b.created ? 1 : a.created > b.created ? -1 : 0)).slice(0, MAX_CALLS);
}

/** A call ready to publish, or an error saying what to fix. */
export function newCall(repo: string, note: string, skills: string[], level: string, time: string, days: number,
                        now = Date.now(), id = randomHex(4)): Call {
  if (!REPO_NAME_RE.test(repo) || repo === '.' || repo === '..') throw new Error('Pick one of your own repos.');
  const clean = cleanNote(note);
  if (clean === null) throw new Error(`Say what you need in a sentence or two (10 to ${MAX_NOTE} characters, no links).`);
  const tags = cleanInterests(skills).slice(0, MAX_CALL_SKILLS);
  if (!tags.length) throw new Error('Add at least one skill you need.');
  if (!CALL_LEVELS[level] || !CALL_TIMES[time]) throw new Error('Choose a level and how much time it takes.');
  if (!CALL_DAYS.includes(days)) throw new Error(`A call stays open ${CALL_DAYS.join(', ')} days.`);
  const t = today(now);
  const until = new Date(Date.parse(`${t}T00:00:00Z`) + days * DAY).toISOString().slice(0, 10);
  return { id, repo, note: clean, skills: tags, level, time, created: t, until, filled: false };
}

/** Add a call to your published ones (the limits the desktop checks too). */
export function addCall(current: Call[], call: Call): Call[] {
  if (current.filter((c) => !c.filled).length >= MAX_CALLS) throw new Error(`You have ${MAX_CALLS} open calls. Close or fill one first.`);
  if (current.some((c) => c.repo.toLowerCase() === call.repo.toLowerCase() && !c.filled)) {
    throw new Error(`There's already an open call for ${call.repo}. Close it to post a new one.`);
  }
  return [call, ...current];
}
