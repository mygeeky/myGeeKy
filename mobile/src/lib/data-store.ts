// Your saved data, locked, on the phone: the same storage and files as the desktop (src/mygeeky/storesync.py) --
// Google Drive's hidden app folder or a private GitHub repo -- encrypted with your key (lib/data-lock.ts).
// The phone reads your computers' files and adds what you do here to its own log files only (one per month), so it
// never writes a file another device writes. Every file read is opened with your key; one that doesn't open is
// skipped, never trusted.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import * as L from './data-lock';
import { driveToken } from './google-drive-auth';
import { fetchT } from './net';
import { b64, fromUtf8, unb64, utf8 } from './signal-crypto';

const KEY_ITEM = 'mygeeky.data.key';                     // (storage.ts SECRET_ITEMS: Start over forgets it)
const DEVICE_KEY = 'mygeeky.device';
const WHERE_KEY = 'mygeeky.saving.where';                // 'drive' | 'github' (locked) | absent
const ME = { name: 'myGeeKy', email: 'housekeeping@mygeeky.invalid' };

export class NeedsKey extends Error {
  constructor() {
    super('Your saved data is encrypted with a key this phone doesn\'t have yet. Type your recovery code, or scan the QR code your computer shows.');
  }
}

export class Moved extends Error {}

// ---- the key and this phone's id
async function secureGet(item: string): Promise<string | null> {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(item) ?? null;
  try { return await SecureStore.getItemAsync(item); } catch { return null; }
}

async function secureSet(item: string, value: string | null): Promise<void> {
  if (Platform.OS === 'web') {
    if (value) globalThis.localStorage?.setItem(item, value);
    else globalThis.localStorage?.removeItem(item);
  } else if (value) await SecureStore.setItemAsync(item, value);
  else await SecureStore.deleteItemAsync(item).catch(() => undefined);
}

export async function getKey(): Promise<Uint8Array | null> {
  const k = unb64(await secureGet(KEY_ITEM));
  return k && k.length === 32 ? k : null;
}

export async function setKey(key: Uint8Array | null): Promise<void> {
  await secureSet(KEY_ITEM, key ? b64(key) : null);
}

export async function deviceId(): Promise<string> {
  const have = await AsyncStorage.getItem(DEVICE_KEY);
  if (have && /^[0-9a-f]{8}$/.test(have)) return have;
  const id = L.newDeviceId();
  await AsyncStorage.setItem(DEVICE_KEY, id);
  return id;
}

export type Where = 'drive' | 'github';
export async function savedWhere(): Promise<Where | null> {
  const w = await AsyncStorage.getItem(WHERE_KEY);
  return w === 'drive' || w === 'github' ? w : null;
}
export async function setWhere(w: Where | null): Promise<void> {
  if (w) await AsyncStorage.setItem(WHERE_KEY, w);
  else await AsyncStorage.removeItem(WHERE_KEY);
}

// ---- the stores: list (name -> revision), read, write
export type Store = {
  label: string;
  list(): Promise<Record<string, string>>;
  read(name: string): Promise<Uint8Array | null>;
  write(name: string, data: Uint8Array): Promise<void>;
};

export function githubStore(repo: string, token: string): Store {
  const headers = { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28' };
  let shas: Record<string, string> = {};
  const fail = (status: number, what: string) => {
    if (status === 401 || status === 403) return new Error('The data repo token no longer works. Make a new one and connect again.');
    return new Error(`GitHub answered ${status} for ${what}.`);
  };
  return {
    label: repo,
    async list() {
      const r = await fetchT(`https://api.github.com/repos/${repo}/git/trees/HEAD`, { headers });
      if (r.status === 409 || r.status === 404) { shas = {}; return {}; }   // an empty repo
      if (!r.ok) throw fail(r.status, 'the file list');
      const j = await r.json();
      shas = {};
      for (const e of Array.isArray(j?.tree) ? j.tree : []) {
        if (e?.type === 'blob' && typeof e.path === 'string' && typeof e.sha === 'string') shas[e.path] = e.sha;
      }
      return { ...shas };
    },
    async read(name) {
      const sha = shas[name];
      if (!sha) return null;
      const r = await fetchT(`https://api.github.com/repos/${repo}/git/blobs/${sha}`, { headers }, 60000);
      if (!r.ok) throw fail(r.status, name);
      const j = await r.json();
      return unb64(String(j?.content ?? '').replace(/\s/g, ''));
    },
    async write(name, data) {
      const r = await fetchT(`https://api.github.com/repos/${repo}/contents/${name}`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `myGeeKy phone: ${name}`, sha: shas[name], author: ME, committer: ME, content: b64(data) }),
      }, 60000);
      if (r.status === 409 || r.status === 422) throw new Error('Another device was saving at the same moment. Try again in a minute.');
      if (!r.ok) throw fail(r.status, name);
      const j = await r.json();
      if (typeof j?.content?.sha === 'string') shas[name] = j.content.sha;
    },
  };
}

/** Raw bytes over HTTP. React Native's fetch turns a byte body into a Blob, which it can't build from bytes, and
 *  reads bytes back through a Blob too; its XMLHttpRequest carries an ArrayBuffer both ways. */
function bytesCall(method: string, url: string, headers: Record<string, string>, body?: Uint8Array, ms = 60000):
  Promise<{ status: number; bytes: Uint8Array; text: () => string }> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open(method, url);
    x.responseType = 'arraybuffer';
    x.timeout = ms;
    for (const [k, v] of Object.entries(headers)) x.setRequestHeader(k, v);
    x.onload = () => {
      const bytes = new Uint8Array((x.response as ArrayBuffer | null) ?? new ArrayBuffer(0));
      resolve({ status: x.status, bytes, text: () => fromUtf8(bytes) ?? '' });
    };
    x.onerror = () => reject(new Error(`Couldn't reach ${new URL(url).hostname}. Check your connection.`));
    x.ontimeout = () => reject(new Error(`${new URL(url).hostname} didn't answer in ${ms / 1000} s. Check your connection.`));
    x.send(body ? body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) as ArrayBuffer : null);
  });
}

export function driveStore(token: (fresh: boolean) => Promise<string> = driveToken): Store {
  const API = 'https://www.googleapis.com/drive/v3/files';
  const UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files';
  let ids: Record<string, string> = {};
  const call = async (url: string, init: RequestInit = {}, ms = 30000): Promise<Response> => {
    for (const fresh of [false, true]) {
      const r = await fetchT(url, { ...init, headers: { ...(init.headers as Record<string, string> ?? {}), Authorization: `Bearer ${await token(fresh)}` } }, ms);
      if (r.status === 401 && !fresh) continue;
      if (r.status === 401) throw new Error('Google Drive needs you to sign in with Google again (Settings → Accounts).');
      if (r.status === 403 && (await r.clone().text()).includes('storageQuota')) throw new Error('Your Google Drive is full, so your data can\'t be saved there.');
      if (!r.ok) throw new Error(`Google Drive answered ${r.status}.`);
      return r;
    }
    throw new Error('unreachable');
  };
  const media = async (method: string, url: string, body?: Uint8Array) => {
    for (const fresh of [false, true]) {
      const headers: Record<string, string> = { Authorization: `Bearer ${await token(fresh)}` };
      if (body) headers['Content-Type'] = 'application/octet-stream';
      const r = await bytesCall(method, url, headers, body);
      if (r.status === 401 && !fresh) continue;
      if (r.status === 401) throw new Error('Google Drive needs you to sign in with Google again (Settings → Accounts).');
      if (r.status === 403 && r.text().includes('storageQuota')) throw new Error('Your Google Drive is full, so your data can\'t be saved there.');
      if (r.status < 200 || r.status >= 300) throw new Error(`Google Drive answered ${r.status}.`);
      return r;
    }
    throw new Error('unreachable');
  };
  return {
    label: 'Google Drive',
    async list() {
      const out: Record<string, string> = {};
      const when: Record<string, string> = {};
      ids = {};
      let page = '';
      do {
        const q = new URLSearchParams({ spaces: 'appDataFolder', pageSize: '1000', fields: 'nextPageToken,files(id,name,md5Checksum,modifiedTime)' });
        if (page) q.set('pageToken', page);
        const j = await (await call(`${API}?${q}`)).json();
        for (const f of Array.isArray(j?.files) ? j.files : []) {
          const name = String(f?.name ?? ''), id = String(f?.id ?? ''), t = String(f?.modifiedTime ?? '');
          if (name && id && (!(name in when) || t > when[name])) {          // two copies: the newest
            when[name] = t;
            ids[name] = id;
            out[name] = String(f?.md5Checksum ?? '') || t;
          }
        }
        page = typeof j?.nextPageToken === 'string' ? j.nextPageToken : '';
      } while (page);
      return out;
    },
    async read(name) {
      const id = ids[name];
      if (!id) return null;
      return (await media('GET', `${API}/${id}?alt=media`)).bytes;
    },
    async write(name, data) {
      let id = ids[name];
      if (!id) {
        const made = await (await call(`${API}?fields=id`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, parents: ['appDataFolder'] }) })).json();
        id = String(made?.id ?? '');
        if (!id) throw new Error('Google Drive didn\'t make the file.');
        ids[name] = id;
      }
      await media('PATCH', `${UPLOAD}/${id}?uploadType=media&fields=id`, data);
    },
  };
}

// ---- reading and adding to locked data
export type Locked = {
  store: Store; key: Uint8Array; names: Record<string, string>;
  read(file: string): Promise<string | null>;
  append(file: string, lines: string[]): Promise<void>;
};

const timeOf = (line: string) => {
  try {
    const rec = JSON.parse(line);
    for (const k of ['at', 'timestamp', 'time', 'date', 'ts']) if (typeof rec?.[k] === 'string') return rec[k] as string;
  } catch { /* undated */ }
  return '';
};

/** Open a store with this phone's key. A new, empty store is made ours (mygeeky.json); one locked with another key
 *  throws NeedsKey; one another device moved away from throws Moved. */
export async function openLocked(store: Store, key: Uint8Array | null, claim = false): Promise<Locked> {
  const names = await store.list();
  const fmt = FORMAT in names ? await store.read(FORMAT) : null;
  const text = fmt ? fromUtf8(fmt) : null;
  const kid = L.formatKeyId(text);
  if (kid === null && claim) {
    key = key ?? L.newKey();
    await store.write(FORMAT, utf8(L.formatDoc(key)));
    names[FORMAT] = '';
  } else if (kid === null) {
    throw new Error(`There's no myGeeKy data in ${store.label} yet. Save from your computer first, or choose it here to start.`);
  } else if (!key || L.keyId(key) !== kid) {
    throw new NeedsKey();
  }
  const moved = movedTo(text);
  if (moved && claim && key) {                       // chosen again after another device moved away: it's the place again
    await store.write(FORMAT, utf8(L.formatDoc(key)));
  } else if (moved) throw new Moved(`Your data moved to ${moved === 'drive' ? 'Google Drive' : moved.replace(/^github:/, '')} on another device. Switch this phone too, in Settings → Accounts.`);
  const k = key as Uint8Array;
  const device = await deviceId();
  return {
    store, key: k, names,
    async read(file) {
      if (!file.endsWith('.jsonl')) {
        const blob = await store.read(file + L.SUFFIX);
        return blob ? L.openText(k, file, blob) : null;
      }
      const stem = file.slice(0, -'.jsonl'.length);
      const chunks = Object.keys(names).map(L.parseStored).filter((p) => p?.kind === 'log' && p.stem === stem) as Extract<L.Stored, { kind: 'log' }>[];
      if (!chunks.length) return null;
      const seen = new Set<string>();
      const lines: string[] = [];
      for (const c of chunks.sort((a, b) => (a.month < b.month ? -1 : a.month > b.month ? 1 : 0))) {
        const blob = await store.read(c.name + L.SUFFIX);
        const t = blob ? L.openText(k, c.name, blob) : null;
        for (const line of L.linesOf(t ?? '')) if (!seen.has(line)) { seen.add(line); lines.push(line); }
      }
      const order = lines.map((line, i) => ({ line, i, t: timeOf(line) }));
      order.sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : a.i - b.i));
      return order.map((x) => x.line).join('\n') + '\n';
    },
    async append(file, lines) {
      const stem = file.slice(0, -'.jsonl'.length);
      const byMonth: Record<string, string[]> = {};
      for (const line of lines) (byMonth[L.monthOf(line)] ??= []).push(line);
      for (const [month, add] of Object.entries(byMonth)) {
        const chunk = L.logChunk(stem, month, device);
        const stored = chunk + L.SUFFIX;
        const blob = stored in names ? await store.read(stored) : null;
        const have = blob ? L.openText(k, chunk, blob) ?? '' : '';
        const body = `${have}${have && !have.endsWith('\n') ? '\n' : ''}${add.join('\n')}\n`;
        await store.write(stored, L.sealText(k, chunk, body));
        names[stored] = '';
      }
    },
  };
}

const FORMAT = L.FORMAT_FILE;

function movedTo(text: string | null): string | null {
  try {
    const m = JSON.parse(text ?? 'null')?.moved_to;
    return typeof m === 'string' && /^(drive|github:[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100})$/.test(m) ? m : null;
  } catch {
    return null;
  }
}

/** Copy everything from one store to another (the files stay locked: nothing is opened), then mark the old one moved. */
export async function moveStore(from: Store, to: Store, key: Uint8Array, toLabel: 'drive' | `github:${string}`): Promise<number> {
  const src = await from.list();
  await to.list();
  let n = 0;
  for (const name of Object.keys(src)) {
    if (name !== FORMAT && !L.parseStored(name)) continue;
    const blob = await from.read(name);
    if (blob) { await to.write(name, blob); n++; }
  }
  await from.write(FORMAT, utf8(JSON.stringify({ ...JSON.parse(L.formatDoc(key)), moved_to: toLabel }, null, 1)));
  return n;
}
