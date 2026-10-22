// Signals on the phone: the same beacons, rules and encryption as the desktop
// (src/mygeeky/beacon.py). The phone has its OWN key -- created here, kept in the
// phone's secure store, never copied anywhere -- and adds its public half to your
// beacon next to your computers' keys, so signals sent to you can be opened here
// too. It writes to your beacon with its own Signals token (one per device), and
// keeps everything your computers published there: their keys, your status,
// interests and the signals they sent.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { gh } from './github';
import { match, todaySeed, type Weights } from './interests';
import { fetchT } from './net';
import { b64, newKeypair, publicOf, utf8 } from './signal-crypto';
import {
  addCall, BEACON_REPO, type Call, CALL_LEVELS, CALL_TIMES, callsIn, DAILY_LIMIT, DAY, decodeContent, GESTURES, isoNow,
  MAX_PER_SENDER, MAX_USERS, mergeIntoBeacon, MUTUAL_TEXT, NAME_RE, newCall, openSignals, type Parsed, type Person, parseBeacon,
  parseTime, type Received, REPEAT_DAYS, SCHEMA, sealSignal, type Sent, TERMS_NEEDED, TERMS_VERSION, TOPIC, TTL_DAYS,
  validLogin, validRepo, WEEKLY_NEW_PEOPLE,
} from './signals-core';
import { loadLists } from './curated';
import { readCache } from './storage';

export {
  BEACON_REPO, type Call, CALL_DAYS, CALL_LEVELS, CALL_TIMES, GESTURES, MAX_CALLS, MAX_CALL_SKILLS, MAX_NOTE, MUTUAL_TEXT,
  type Parsed, type Person, type Received,
} from './signals-core';
const KEY_ITEM = 'mygeeky_signals_key';        // this phone's private key (secure store)
const TOKEN_ITEM = 'mygeeky_signals_token';    // this phone's Signals token (secure store; both in storage.ts SECRET_ITEMS)
const SENT_KEY = 'mygeeky.signals.sent';       // what this phone sent (for the courtesy limits)
const HIDDEN_KEY = 'mygeeky.signals.hiddenCalls';  // "owner/id" of calls you said aren't for you
const RECEIVED_KEY = 'mygeeky.signals.received';  // when and what kind of signals reached you (My month), never who
const BLOCKED_KEY = 'mygeeky.signals.blocked';     // people you blocked: nothing of theirs shows on this phone
const TERMS_KEY = 'mygeeky.signals.terms';         // the Signals terms agreed to on this phone (TERMS_VERSION)
const ME = { name: 'myGeeKy', email: 'housekeeping@mygeeky.invalid' };   // never counts as your activity

// ---- this phone's secrets
async function secureGet(item: string): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(item) ?? null;
  try {
    return await SecureStore.getItemAsync(item);
  } catch {
    return null;
  }
}

async function secureSet(item: string, value: string | null): Promise<void> {
  if (Platform.OS === 'web') {
    if (value) globalThis.localStorage?.setItem(item, value);
    else globalThis.localStorage?.removeItem(item);
  } else if (value) await SecureStore.setItemAsync(item, value);
  else await SecureStore.deleteItemAsync(item).catch(() => undefined);
}

export async function phoneKey(): Promise<{ priv: string; pub: string } | null> {
  const priv = await secureGet(KEY_ITEM);
  return priv ? { priv, pub: publicOf(priv) } : null;
}

export const signalsToken = () => secureGet(TOKEN_ITEM);
export const isSetUp = async () => !!(await secureGet(TOKEN_ITEM)) && !!(await secureGet(KEY_ITEM));

/** Everyone on Signals (beacon repos found by topic and by name), with their beacons. */
export async function loadBeacons(me: string, token: string | null): Promise<Parsed[]> {
  const found = new Map<string, string>();
  for (const q of [`topic:${TOPIC} fork:false`, `${BEACON_REPO} in:name fork:false`]) {
    const res = await gh<{ items: { name: string; private: boolean; owner: { login: string; type: string; avatar_url: string } }[] }>(
      `/search/repositories?q=${encodeURIComponent(q)}&per_page=100&sort=updated`, token);
    for (const r of res.items ?? []) {
      const login = r.owner?.login;
      if (r.name?.toLowerCase() !== BEACON_REPO || r.owner?.type !== 'User' || r.private || !validLogin(login)) continue;
      if (login.toLowerCase() !== me.toLowerCase() && !found.has(login)) found.set(login, r.owner.avatar_url ?? '');
      if (found.size >= MAX_USERS) break;
    }
  }
  const out: Parsed[] = [];
  const logins = [...found.keys()];
  for (let i = 0; i < logins.length; i += 6) {                     // a few at a time: gentle on GitHub
    const batch = await Promise.all(logins.slice(i, i + 6).map(async (login) => {
      try {
        const file = await gh<{ content?: string; size?: number }>(`/repos/${login}/${BEACON_REPO}/contents/beacon.json`, token);
        if ((file.size ?? 0) > 256 * 1024) return null;
        const parsed = parseBeacon(decodeContent(file.content), login);
        return parsed && { ...parsed, avatar: found.get(login) ?? '' };
      } catch {
        return null;
      }
    }));
    out.push(...(batch.filter(Boolean) as Parsed[]));
  }
  return out;
}

/** Everyone this phone already asked to collaborate (🤝), lowercased. */
export async function collabAsked(): Promise<Set<string>> {
  return new Set((await loadSent()).filter((g) => g.type === 'collab').map((g) => g.to.toLowerCase()));
}

// ---- what this phone sent (courtesy limits)
export async function loadSent(): Promise<Sent[]> {
  try {
    const raw = await AsyncStorage.getItem(SENT_KEY);
    const list = raw ? (JSON.parse(raw) as Sent[]) : [];
    const oldest = Date.now() - TTL_DAYS * DAY;
    return list.filter((g) => (parseTime(g.at) ?? 0) > oldest);
  } catch {
    return [];
  }
}

export type CallForMe = Call & { owner: string; avatar: string; fullName: string; matched: string[]; fit: number;
  explore: boolean; joined: boolean; levelLabel: string; timeLabel: string; daysLeft: number };
export type MyCall = Call & { fullName: string; levelLabel: string; timeLabel: string; daysLeft: number;
  responders: { login: string; avatar: string; skills: string[]; at: string }[] };
export type SignalsData = { inbox: Received[]; people: Person[]; calls: CallForMe[]; myCalls: MyCall[]; blocked: string[] };

const daysLeft = (until: string) => Math.max(0, Math.round((Date.parse(`${until}T00:00:00Z`) - Date.parse(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`)) / DAY));

async function loadList(key: string): Promise<string[]> {
  try {
    const v = JSON.parse((await AsyncStorage.getItem(key)) ?? '[]');
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}
const loadHidden = () => loadList(HIDDEN_KEY);
export const loadBlocked = () => loadList(BLOCKED_KEY);

/** Block someone: their signals, calls and dot leave this phone. */
export async function blockPerson(login: string): Promise<void> {
  const rest = (await loadBlocked()).filter((b) => b.toLowerCase() !== login.toLowerCase());
  await AsyncStorage.setItem(BLOCKED_KEY, JSON.stringify([...rest, login].slice(-500)));
}

export async function unblockPerson(login: string): Promise<void> {
  const rest = (await loadBlocked()).filter((b) => b.toLowerCase() !== login.toLowerCase());
  await AsyncStorage.setItem(BLOCKED_KEY, JSON.stringify(rest));
}

/** Everything someone posts on Signals lives in their GitHub beacon, so abuse is reported to GitHub. */
export const reportUrl = (login: string) => `https://github.com/contact/report-abuse?report=${encodeURIComponent(login)}`;

/** Your calls as your beacon publishes them (from any of your devices). Read-only. */
export async function loadMyCalls(me: string, token: string | null): Promise<Call[]> {
  try {
    const file = await gh<{ content?: string }>(`/repos/${me}/${BEACON_REPO}/contents/beacon.json`, token);
    return callsIn(decodeContent(file.content));
  } catch {
    return [];
  }
}

/** Everything the 📡 planet shows. The matching happens here, on the phone: nothing about you is sent. */
/** When and what kind of signals reached you, as last seen in Signals (for My month). */
export async function loadReceived(): Promise<{ at: string; type: string }[]> {
  try {
    const list = JSON.parse((await AsyncStorage.getItem(RECEIVED_KEY)) ?? '[]');
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

/** The Signals terms: agreed to on this phone? (beacon.terms_accepted) */
export async function termsAccepted(): Promise<boolean> {
  try { return (await AsyncStorage.getItem(TERMS_KEY)) === TERMS_VERSION; } catch { return false; }
}
export async function acceptTerms(): Promise<void> { await AsyncStorage.setItem(TERMS_KEY, TERMS_VERSION); }

/** Beacons myGeeKy's maker hid from everyone for breaking the terms (beacon.hidden_by_maker): from the curated lists
 *  (fetched again when over 6 hours old), else as last kept, else the ones shipped with the app. */
export async function hiddenByMaker(): Promise<Set<string>> {
  try {
    const lists: any = await loadLists().catch(async () => (await readCache<any>('curated'))?.data ?? require('../data/curated.json'));
    return new Set((lists?.signals_hidden ?? []).filter((u: unknown) => typeof u === 'string' && NAME_RE.test(u)).map((u: string) => u.toLowerCase()));
  } catch {
    return new Set();
  }
}

export async function signalsData(me: string, weights: Weights, users: Parsed[], mine: Call[], share = 0.2): Promise<SignalsData> {
  const key = await phoneKey();
  const sent = await loadSent();
  const hidden = new Set((await loadHidden()).map((h) => h.toLowerCase()));
  const blocked = await loadBlocked();
  const isBlocked = new Set([...blocked.map((b) => b.toLowerCase()), ...(await hiddenByMaker())]);
  const sentTo = new Set(sent.map((g) => g.to.toLowerCase()));
  const myCollab = new Set(sent.filter((g) => g.type === 'collab').map((g) => g.to.toLowerCase()));
  const joined = new Set(sent.filter((g) => g.type === 'join').map((g) => `${g.to.toLowerCase()}/${g.call}`));
  const myTerms = new Set(Object.keys(weights));
  const byId = new Map(mine.map((c) => [c.id, c]));
  const inbox: Received[] = [];
  const people: Person[] = [];
  const found: CallForMe[] = [];
  for (const u of users) {
    if (isBlocked.has(u.owner.toLowerCase())) continue;
    const got = key ? openSignals(u, me, key.priv) : [];
    const visible = got.filter((g) => g.type !== 'collab' || myCollab.has(u.owner.toLowerCase()));
    for (const g of visible.sort((a, b) => b.at.localeCompare(a.at)).slice(0, MAX_PER_SENDER)) {
      const mutual = g.type === 'collab';
      const [emoji, verb] = GESTURES[g.type];
      let text = mutual ? MUTUAL_TEXT : g.repo ? `${emoji} used ${g.repo} in their work` : `${emoji} ${verb}`;
      let repo = g.repo ?? '';
      if (g.type === 'join') {
        const call = byId.get(g.call ?? '');
        repo = call ? `${me}/${call.repo}` : '';
        text = call ? `🙋 would like to help with ${repo}` : "🙋 answered a call you've closed";
      }
      inbox.push({ from: u.owner, avatar: u.avatar, type: g.type, emoji, repo, at: g.at, mutual, text,
        call: g.call, skills: g.skills });
    }
    const shared = u.interests.filter((i) => myTerms.has(i));
    const score = match(u.interests.join(' ; '), weights)[0];
    people.push({ login: u.owner, avatar: u.avatar, status: u.quiet ? '🔕 not taking signals right now' : u.status,
      interests: u.interests, shared, signalledYou: visible.length > 0, fit: Math.max(score, Math.min(1, shared.length / 4)),
      youSignalled: sentTo.has(u.owner.toLowerCase()), canReceive: u.keys.length > 0 && !u.quiet });
    if (u.quiet || !u.keys.length) continue;
    for (const c of u.calls) {
      if (c.filled || hidden.has(`${u.owner}/${c.id}`.toLowerCase())) continue;
      const [sc] = match([...c.skills, c.repo.replace(/[-_]/g, ' '), c.note].join(' '), weights);
      const matched = c.skills.filter((sk) => myTerms.has(sk) || match(sk, weights)[0] > 0);
      const fit = matched.length ? Math.max(sc, (matched.length / c.skills.length) * 0.9) : sc * 0.5;
      found.push({ ...c, owner: u.owner, avatar: u.avatar, fullName: `${u.owner}/${c.repo}`, matched, fit, explore: false,
        joined: joined.has(`${u.owner.toLowerCase()}/${c.id}`), levelLabel: CALL_LEVELS[c.level], timeLabel: CALL_TIMES[c.time],
        daysLeft: daysLeft(c.until) });
    }
  }
  found.sort((a, b) => b.fit - a.fit);
  const fits = found.filter((c) => c.fit >= 0.15 || c.joined);
  const rest = found.filter((c) => c.fit < 0.15 && !c.joined);
  const k = share <= 0 || !rest.length ? 0 : Math.max(1, Math.round(fits.length * share));
  const seed = todaySeed();
  const picks = rest.map((c, i) => ({ c, r: ((seed * 9301 + i * 49297) % 233280) / 233280 }))
    .sort((a, b) => a.r - b.r).slice(0, k).map(({ c }) => ({ ...c, explore: true }));
  inbox.sort((a, b) => b.at.localeCompare(a.at));
  AsyncStorage.setItem(RECEIVED_KEY, JSON.stringify(inbox.map((i) => ({ at: i.at, type: i.type })))).catch(() => undefined);
  people.sort((a, b) => Number(b.signalledYou) - Number(a.signalledYou) || b.fit - a.fit);
  const myCalls: MyCall[] = mine.map((c) => ({ ...c, fullName: `${me}/${c.repo}`, levelLabel: CALL_LEVELS[c.level],
    timeLabel: CALL_TIMES[c.time], daysLeft: daysLeft(c.until),
    responders: inbox.filter((i) => i.type === 'join' && i.call === c.id)
      .map((i) => ({ login: i.from, avatar: i.avatar, skills: i.skills ?? [], at: i.at })) }));
  return { inbox, people, calls: [...fits, ...picks], myCalls, blocked };
}

/** Public repos (yours by default) for the invite and signal sheets: forks, archived and your beacon left out. */
export async function listRepos(login: string, token: string | null):
    Promise<{ name: string; fullName: string; topics: string[]; language: string }[]> {
  try {
    const repos = await gh<{ name: string; full_name: string; fork: boolean; archived: boolean; private: boolean;
      topics?: string[]; language?: string | null }[]>(`/users/${login}/repos?per_page=100&sort=updated&type=owner`, token);
    return repos.filter((r) => !r.fork && !r.archived && !r.private && r.name !== BEACON_REPO)
      .map((r) => ({ name: r.name, fullName: r.full_name, topics: (r.topics ?? []).map((t) => t.replace(/-/g, ' ')).slice(0, 8),
        language: r.language ?? '' }));
  } catch {
    return [];
  }
}

// ---- writing YOUR beacon (with this phone's Signals token)
async function readMine(me: string, token: string): Promise<{ raw: Record<string, unknown>; sha?: string }> {
  const r = await fetchT(`https://api.github.com/repos/${me}/${BEACON_REPO}/contents/beacon.json`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } });
  if (r.status === 404) throw new Error(`${me}/${BEACON_REPO} doesn't exist yet. Turn on Signals on your computer first.`);
  if (r.status === 401) throw new Error('GitHub refused this Signals token. Check it, or make a new one.');
  if (!r.ok) throw new Error(`GitHub said ${r.status}.`);
  const file = await r.json();
  const raw = decodeContent(file.content);
  if (!raw || raw.mygeeky_beacon !== SCHEMA) throw new Error('Your beacon is from an older myGeeKy. Update myGeeKy on your computer first.');
  return { raw, sha: file.sha };
}

async function writeMine(me: string, token: string, beacon: Record<string, unknown>, sha: string | undefined,
                         message: string): Promise<number> {
  const r = await fetchT(`https://api.github.com/repos/${me}/${BEACON_REPO}/contents/beacon.json`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sha, author: ME, committer: ME,
      content: b64(utf8(`${JSON.stringify(beacon, null, 2)}\n`)) }),
  });
  return r.status;
}

/** Read, add, write; once more if one of your computers wrote in between. `changeCalls`
 *  edits your published calls (it sees what's published right now). */
async function publish(me: string, newBoxes: string[], message: string,
                       opts: { changeCalls?: (current: Call[]) => Call[]; removeBoxes?: string[]; quiet?: boolean } = {}): Promise<void> {
  const token = await signalsToken();
  const key = await phoneKey();
  if (!token || !key) throw new Error('Set up Signals on this phone first.');
  for (let attempt = 0; attempt < 2; attempt++) {
    const { raw, sha } = await readMine(me, token);
    const calls = opts.changeCalls ? opts.changeCalls(callsIn(raw)) : undefined;
    const merged = mergeIntoBeacon(raw, key.pub, newBoxes, Date.now(), { calls, removeBoxes: opts.removeBoxes });
    // beacon.adopt_quiet: the later change wins, so your computers keep this instead of publishing over it
    const beacon = opts.quiet === undefined ? merged
      : { ...merged, quiet: opts.quiet, quiet_at: `${new Date().toISOString().slice(0, 19)}+00:00` };
    const status = await writeMine(me, token, beacon, sha, message);
    if (status === 200 || status === 201) return;
    if (status === 401 || status === 403) throw new Error(`This Signals token can't write to ${me}/${BEACON_REPO}. ` +
      'It needs Contents: Read and write on that repo.');
    if (status !== 409) throw new Error(`Writing your beacon failed (GitHub said ${status}).`);
  }
  throw new Error('Your beacon changed while sending. Try again.');
}

/** "Not taking signals right now", as published in your beacon (beacon.set_quiet). */
export async function readQuiet(me: string): Promise<boolean> {
  const token = await signalsToken();
  if (!token) return false;
  try {
    return (await readMine(me, token)).raw.quiet === true;
  } catch {
    return false;
  }
}

/** Turn "not taking signals" on or off for you, on every device: others can't send while it's on. */
export async function setQuiet(me: string, quiet: boolean): Promise<void> {
  await publish(me, [], quiet ? 'Not taking signals right now' : 'Taking signals again', { quiet });
}

/** One-time setup: keep this phone's token, make its key, add the key to your beacon. */
export async function setUp(me: string, token: string): Promise<void> {
  if (!(await termsAccepted())) throw new Error(TERMS_NEEDED);
  const clean = token.trim();
  if (!/^(github_pat_|ghp_)/.test(clean)) throw new Error('Paste a Signals token: it starts with github_pat_.');
  await readMine(me, clean);                                       // checks the token can read your beacon
  await secureSet(TOKEN_ITEM, clean);
  if (!(await secureGet(KEY_ITEM))) await secureSet(KEY_ITEM, newKeypair()[0]);
  try {
    await publish(me, [], 'Add a phone to Signals');
  } catch (e) {
    await secureSet(TOKEN_ITEM, null);                             // didn't work: leave nothing half set up
    throw e;
  }
}

export async function turnOff(): Promise<void> {
  await secureSet(TOKEN_ITEM, null);          // the key stays, so turning it on again keeps the same identity
}

/** Send a signal: the same courtesy rules as the desktop, checked before anything is sent. */
export async function send(me: string, to: Parsed, gesture: string, repo?: string): Promise<void> {
  if (!GESTURES[gesture]) throw new Error('Unknown signal.');
  if (to.owner.toLowerCase() === me.toLowerCase()) throw new Error("You can't signal yourself.");
  if (gesture === 'used' && !validRepo(repo)) throw new Error('"Used your work" needs the repo you used, as owner/name.');
  if (to.quiet) throw new Error(`${to.owner} isn't taking signals right now. Maybe another time.`);
  if (!to.keys.length) throw new Error(`${to.owner} uses an older myGeeKy that can't receive private signals yet.`);
  const now = Date.now();
  const sent = await loadSent();
  const recent = (days: number) => sent.filter((g) => (parseTime(g.at) ?? 0) > now - days * DAY);
  if (recent(REPEAT_DAYS).some((g) => g.to.toLowerCase() === to.owner.toLowerCase() && g.type === gesture
      && (g.repo ?? '') === (gesture === 'used' ? repo : ''))) {
    throw new Error(`You already sent ${to.owner} this lately. Once is enough: it stays with them for ${TTL_DAYS} days.`);
  }
  const today = new Date(now).toISOString().slice(0, 10);
  if (sent.filter((g) => g.at.slice(0, 10) === today).length >= DAILY_LIMIT) throw new Error(`That's ${DAILY_LIMIT} signals today. Try again tomorrow.`);
  const known = new Set(sent.filter((g) => (parseTime(g.at) ?? 0) <= now - 7 * DAY).map((g) => g.to.toLowerCase()));
  const newThisWeek = new Set(recent(7).map((g) => g.to.toLowerCase()).filter((t) => !known.has(t)));
  if (!known.has(to.owner.toLowerCase()) && !newThisWeek.has(to.owner.toLowerCase()) && newThisWeek.size >= WEEKLY_NEW_PEOPLE) {
    throw new Error(`You've signalled ${WEEKLY_NEW_PEOPLE} new people this week. Pace it: try again in a few days.`);
  }
  const at = isoNow();
  const boxes = sealSignal(me, to.owner, to.keys, gesture, repo, at);
  await publish(me, boxes, 'Update myGeeKy beacon');
  await AsyncStorage.setItem(SENT_KEY, JSON.stringify([...sent, { to: to.owner, type: gesture, at, ...(gesture === 'used' ? { repo } : {}) }]));
}


// ---- calls for contributors
/** Publish a call for one of your own repos (at most MAX_CALLS open at once). */
export async function createCall(me: string, input: { repo: string; note: string; skills: string[]; level: string;
  time: string; days: number }): Promise<Call> {
  if (!(await termsAccepted())) throw new Error(TERMS_NEEDED);
  const call = newCall(input.repo, input.note, input.skills, input.level, input.time, input.days);
  await publish(me, [], 'Update myGeeKy beacon', { changeCalls: (current) => addCall(current, call) });
  return call;
}

/** Filled: it stays, marked filled, so it stops showing to others. Closed: it leaves your beacon. */
export async function closeCall(me: string, id: string, filled: boolean): Promise<void> {
  await publish(me, [], 'Update myGeeKy beacon', { changeCalls: (current) => {
    if (!current.some((c) => c.id === id)) throw new Error("That call isn't in your beacon any more.");
    return filled ? current.map((c) => (c.id === id ? { ...c, filled: true } : c)) : current.filter((c) => c.id !== id);
  } });
}

/** I'm in: a sealed signal to the call's owner with the skills of yours that matched. */
export async function joinCall(me: string, to: Parsed, callId: string, skills: string[]): Promise<void> {
  const call = to.calls.find((c) => c.id === callId && !c.filled);
  if (!call) throw new Error(`That call from ${to.owner} isn't open any more. Nothing was sent.`);
  if (!to.keys.length || to.quiet) throw new Error(`${to.owner} can't receive signals right now.`);
  const now = Date.now();
  const sent = await loadSent();
  if (sent.some((g) => g.type === 'join' && g.call === callId && g.to.toLowerCase() === to.owner.toLowerCase())) {
    throw new Error("You already said you're in.");
  }
  const day = new Date(now).toISOString().slice(0, 10);
  if (sent.filter((g) => g.at.slice(0, 10) === day).length >= DAILY_LIMIT) throw new Error(`That's ${DAILY_LIMIT} signals today. Try again tomorrow.`);
  const at = isoNow();
  const boxes = sealSignal(me, to.owner, to.keys, 'join', undefined, at, callId, skills);
  await publish(me, boxes, 'Update myGeeKy beacon');
  await AsyncStorage.setItem(SENT_KEY, JSON.stringify([...sent, { to: to.owner, type: 'join', at, call: callId, boxes }]));
}

/** Changed your mind: the "I'm in" this phone sent leaves your beacon. */
export async function leaveCall(me: string, owner: string, callId: string): Promise<void> {
  const sent = await loadSent();
  const mine = sent.filter((g) => g.type === 'join' && g.call === callId && g.to.toLowerCase() === owner.toLowerCase());
  const boxes = mine.flatMap((g) => g.boxes ?? []);
  if (!boxes.length) throw new Error('It was sent from another device: take it back there.');
  await publish(me, [], 'Update myGeeKy beacon', { removeBoxes: boxes });
  await AsyncStorage.setItem(SENT_KEY, JSON.stringify(sent.filter((g) => !mine.includes(g))));
}

/** Not for me: this call won't show again on this phone. */
export async function hideCall(owner: string, callId: string): Promise<void> {
  const hidden = await loadHidden();
  await AsyncStorage.setItem(HIDDEN_KEY, JSON.stringify([...hidden.filter((h) => h !== `${owner}/${callId}`), `${owner}/${callId}`].slice(-200)));
}
