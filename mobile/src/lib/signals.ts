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
import { fetchT } from './net';
import { b64, newKeypair, publicOf, utf8 } from './signal-crypto';
import {
  BEACON_REPO, DAILY_LIMIT, DAY, decodeContent, GESTURES, isoNow, MAX_PER_SENDER, MAX_USERS, mergeIntoBeacon,
  MUTUAL_TEXT, openSignals, type Parsed, type Person, parseBeacon, parseTime, type Received, REPEAT_DAYS, SCHEMA,
  sealSignal, type Sent, TOPIC, TTL_DAYS,
  validLogin, validRepo, WEEKLY_NEW_PEOPLE,
} from './signals-core';

export { BEACON_REPO, GESTURES, MUTUAL_TEXT, type Parsed, type Person, type Received } from './signals-core';
const KEY_ITEM = 'mygeeky_signals_key';        // this phone's private key (secure store)
const TOKEN_ITEM = 'mygeeky_signals_token';    // this phone's Signals token (secure store)
const SENT_KEY = 'mygeeky.signals.sent';       // what this phone sent (for the courtesy limits)
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

// ---- what this phone sent (courtesy limits)
async function loadSent(): Promise<Sent[]> {
  try {
    const raw = await AsyncStorage.getItem(SENT_KEY);
    const list = raw ? (JSON.parse(raw) as Sent[]) : [];
    const oldest = Date.now() - TTL_DAYS * DAY;
    return list.filter((g) => (parseTime(g.at) ?? 0) > oldest);
  } catch {
    return [];
  }
}

export async function inboxAndPeople(me: string, myInterests: string[], users: Parsed[]):
    Promise<{ inbox: Received[]; people: Person[] }> {
  const key = await phoneKey();
  const sent = await loadSent();
  const sentTo = new Set(sent.map((g) => g.to.toLowerCase()));
  const myCollab = new Set(sent.filter((g) => g.type === 'collab').map((g) => g.to.toLowerCase()));
  const mine = new Set(myInterests.map((i) => i.toLowerCase()));
  const inbox: Received[] = [];
  const people: Person[] = [];
  for (const u of users) {
    const got = key ? openSignals(u, me, key.priv) : [];
    const visible = got.filter((g) => g.type !== 'collab' || myCollab.has(u.owner.toLowerCase()));
    for (const g of visible.sort((a, b) => b.at.localeCompare(a.at)).slice(0, MAX_PER_SENDER)) {
      const mutual = g.type === 'collab';
      const [emoji, verb] = GESTURES[g.type];
      inbox.push({ from: u.owner, avatar: u.avatar, type: g.type, emoji, repo: g.repo ?? '', at: g.at, mutual,
        text: mutual ? MUTUAL_TEXT : g.repo ? `${emoji} used ${g.repo} in their work` : `${emoji} ${verb}` });
    }
    people.push({ login: u.owner, avatar: u.avatar, status: u.quiet ? '🔕 not taking signals right now' : u.status,
      interests: u.interests, shared: u.interests.filter((i) => mine.has(i)), signalledYou: visible.length > 0,
      youSignalled: sentTo.has(u.owner.toLowerCase()), canReceive: u.keys.length > 0 && !u.quiet });
  }
  inbox.sort((a, b) => b.at.localeCompare(a.at));
  people.sort((a, b) => Number(b.signalledYou) - Number(a.signalledYou) || b.shared.length - a.shared.length);
  return { inbox, people };
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

/** Read, add, write; once more if one of your computers wrote in between. */
async function publish(me: string, newBoxes: string[], message: string): Promise<void> {
  const token = await signalsToken();
  const key = await phoneKey();
  if (!token || !key) throw new Error('Set up Signals on this phone first.');
  for (let attempt = 0; attempt < 2; attempt++) {
    const { raw, sha } = await readMine(me, token);
    const status = await writeMine(me, token, mergeIntoBeacon(raw, key.pub, newBoxes), sha, message);
    if (status === 200 || status === 201) return;
    if (status === 401 || status === 403) throw new Error(`This Signals token can't write to ${me}/${BEACON_REPO}. ` +
      'It needs Contents: Read and write on that repo.');
    if (status !== 409) throw new Error(`Writing your beacon failed (GitHub said ${status}).`);
  }
  throw new Error('Your beacon changed while sending. Try again.');
}

/** One-time setup: keep this phone's token, make its key, add the key to your beacon. */
export async function setUp(me: string, token: string): Promise<void> {
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
