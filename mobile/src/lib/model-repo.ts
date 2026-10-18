// Your model on the phone, from your PRIVATE data repo (the one `mygeeky sync` keeps your
// computers' data in, e.g. you/mygeeky-data) -- both ways, like one more computer in sync:
//   * it computes the interest map exactly as the desktop does (get_brain in src/mygeeky/gui/app.py):
//       field    papers.your_topics: your OpenAlex topics, filled up from your topics and interests
//       learned  interests.learned_terms: interest_events.jsonl, each action weighted and fading
//       explore  interests.explore_terms: today's new territory, the same daily pick as the desktop
//   * what you open on the phone becomes interest events (interests.record: terms only, never
//     the item's text), queued here and appended to interest_events.jsonl, so your computers
//     learn from the phone too. The desktop merges .jsonl files line by line (git's union driver).
// It uses its OWN fine-grained token -- that one repo only, Contents: Read and write -- kept in
// the phone's secure store, like the Signals token. The only file it ever writes is
// interest_events.jsonl. What comes back is your own data, but it arrives over the network,
// so every field is type-checked and capped before it is used.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { type Dict, expand } from './interests';
import { fetchT } from './net';
import { b64, utf8 } from './signal-crypto';
import { readCache, writeCache } from './storage';
import { blendLearned, type Event, extractTerms, KIND_WEIGHTS, learnedTerms, STOPWORDS } from './learn';

export { blendLearned, extractTerms, learnedTerms } from './learn';

const TOKEN_ITEM = 'mygeeky.model.token';
const REPO_KEY = 'mygeeky.model.repo';
const CACHE_KEY = 'modelrepo';
const QUEUE_KEY = 'mygeeky.model.queue';
const EVENTS_FILE = 'interest_events.jsonl';
const USAGE_FILE = 'usage.jsonl';
const USAGE_QUEUE_KEY = 'mygeeky.model.usagequeue';
const MIGRATED_KEY = 'mygeeky.model.migrated';
const ME = { name: 'myGeeKy', email: 'housekeeping@mygeeky.invalid' };   // as the desktop's sync commits
export const MODEL_TOKEN_PAGE = 'https://github.com/settings/personal-access-tokens/new';

// (the learning numbers and rules, as interests.py: lib/learn.ts)
// scikit-learn's English stop words, as CountVectorizer(stop_words='english') on the desktop
const SKLEARN_STOP = new Set('a about above across after afterwards again against all almost alone along already also although always am among amongst amoungst amount an and another any anyhow anyone anything anyway anywhere are around as at back be became because become becomes becoming been before beforehand behind being below beside besides between beyond bill both bottom but by call can cannot cant co con could couldnt cry de describe detail do done down due during each eg eight either eleven else elsewhere empty enough etc even ever every everyone everything everywhere except few fifteen fifty fill find fire first five for former formerly forty found four from front full further get give go had has hasnt have he hence her here hereafter hereby herein hereupon hers herself him himself his how however hundred i ie if in inc indeed interest into is it its itself keep last latter latterly least less ltd made many may me meanwhile might mill mine more moreover most mostly move much must my myself name namely neither never nevertheless next nine no nobody none noone nor not nothing now nowhere of off often on once one only onto or other others otherwise our ours ourselves out over own part per perhaps please put rather re same see seem seemed seeming seems serious several she should show side since sincere six sixty so some somehow someone something sometime sometimes somewhere still such system take ten than that the their them themselves then thence there thereafter thereby therefore therein thereupon these they thick thin third this those though three through throughout thru thus to together too top toward towards twelve twenty two un under until up upon us very via was we well were what whatever when whence whenever where whereafter whereas whereby wherein whereupon wherever whether which while whither who whoever whole whom whose why will with within without would yet you your yours yourself yourselves'.split(' '));
const EXPLORE_POOL = [
  'single-cell', 'spatial transcriptomics', 'protein design', 'llm agents', 'causal inference',
  'graph neural networks', 'reproducibility', 'data visualization', 'rust', 'webassembly',
  'privacy', 'climate', 'epidemiology', 'microscopy', 'robotics', 'quantum computing',
  'open science', 'bayesian', 'time series', 'drug discovery', 'metagenomics', 'neuroscience',
  'computer vision', 'education', 'accessibility', 'high performance computing', 'ecology',
  'statistics', 'knowledge graphs', 'workflow management',
];

export type Brain = {
  repo: string; syncedAt: string | null; user: string;
  field: string[]; learned: [string, number][]; explore: string[];
  taught: { clicks: number; follows: number; stars: number; forks: number };
  learning: boolean; halfLife: number; exploreShare: number;
  // who follows you back (model_history.jsonl) and what the model weighs (retrained from training_data.jsonl)
  history: { timestamp: string; n_train: number; n_pos: number; auc: number | null }[];
  weights: { feature: string; label: string; weight: number }[];
  // what badges count (achievements.counts' inputs): usage.jsonl, your interest events' kinds, signals sent
  usage: Usage[]; eventKinds: { at: string; kind: string }[]; sent: number; keywords: number; syncing: boolean;
  // you, as "Connect your phone" would bring you (pairing.payload): what every list on the phone is ranked by
  profile: { orcid: string; keywords: string[]; topics: string[]; interests: Record<string, number> };
};
export type Usage = { at: string; what: string; kind?: string; cat?: string; explore?: boolean };

type SyncedConfig = {
  github_username: string; topics: string[]; keywords: string[]; languages: string[];
  interest_learning: boolean; interest_half_life_days: number; explore_share: number;
  sync_repo: string; training_mass_follow_outlier: number; orcid_id: string;
};

// ---- the token and repo
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

export async function modelLink(): Promise<{ repo: string; token: string } | null> {
  const [repo, token] = await Promise.all([AsyncStorage.getItem(REPO_KEY), secureGet(TOKEN_ITEM)]);
  return repo && token ? { repo, token } : null;
}

export const validRepo = (repo: string) => /^[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}$/.test(repo);

/** Check the token reaches the repo and can't do more than read it, then keep both. */
export async function connectModel(repo: string, token: string): Promise<void> {
  repo = repo.trim();
  token = token.trim();
  if (!validRepo(repo)) throw new Error('Give the repo as owner/name, e.g. you/mygeeky-data.');
  if (!token.startsWith('github_pat_')) {
    throw new Error('Use a fine-grained token (it starts with github_pat_): only that repo, Contents: Read and write. '
      + 'A classic token would reach every repo you have.');
  }
  const r = await api(`/repos/${repo}`, token);
  if (r.status === 401) throw new Error('GitHub refused that token. Check it was copied whole and hasn\'t expired.');
  if (!r.ok) throw new Error(`The token can't see ${repo}. When making it, choose "Only select repositories" and pick ${repo}.`);
  const info = await r.json();
  if (!info.private) throw new Error(`${repo} is public. myGeeKy only keeps your data in a private repo.`);
  // can it write? the desktop's probe (token_check.py): a git blob nothing points at -- invisible,
  // and GitHub garbage-collects it. 201 only with Contents: Read and write.
  const probe = await fetchT(`https://api.github.com/repos/${repo}/git/blobs`, {
    method: 'POST', body: JSON.stringify({ content: 'myGeeKy permission check (unreferenced; safe to ignore)', encoding: 'utf-8' }),
    headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
      'X-GitHub-Api-Version': '2022-11-28' } });
  if (probe.status === 403 || probe.status === 404) {
    const said = await probe.json().then((j) => String(j?.message ?? '').slice(0, 120)).catch(() => '');
    const needs = probe.headers.get('x-accepted-github-permissions') ?? '';
    throw new Error('That token can only read. Set Contents to "Read and write", so the phone can add what you open here. '
      + `(GitHub: ${probe.status}${said ? ` "${said}"` : ''}${needs ? `, needs ${needs}` : ''})`);
  }
  // anything else but 201 (e.g. 409: the repo is still empty) can't tell -- as on the desktop, don't refuse
  await secureSet(TOKEN_ITEM, token);
  await AsyncStorage.setItem(REPO_KEY, repo);
  flushInterests(repo, token).catch(() => undefined);   // what this phone learned before: into the repo now
}

export async function disconnectModel(): Promise<void> {
  await secureSet(TOKEN_ITEM, null);
  await AsyncStorage.multiRemove([REPO_KEY, QUEUE_KEY, USAGE_QUEUE_KEY, `mygeeky.cache.${CACHE_KEY}`]);
}

export async function cachedBrain(): Promise<{ at: string; data: Brain } | null> {
  return readCache<Brain>(CACHE_KEY);
}

// ---- reading the repo
function api(path: string, token: string, accept = 'application/vnd.github+json') {
  return fetchT(`https://api.github.com${path}`, { headers: { Accept: accept, Authorization: `Bearer ${token}` } });
}

async function raw(repo: string, token: string, file: string): Promise<string | null> {
  const r = await api(`/repos/${repo}/contents/${file}`, token, 'application/vnd.github.raw');
  if (r.status === 404) return null;            // not synced yet
  if (r.status === 401 || r.status === 403) throw new Error('The model token no longer works. Make a new one and connect again.');
  if (!r.ok) throw new Error(`GitHub answered ${r.status} for ${file}.`);
  return r.text();
}

const strs = (v: unknown, n: number, len = 120) =>
  (Array.isArray(v) ? v : []).filter((x): x is string => typeof x === 'string' && !!x.trim()).slice(0, n).map((x) => x.slice(0, len));
const num = (v: unknown, fallback: number) => (typeof v === 'number' && Number.isFinite(v) ? v : fallback);

function parseConfig(text: string | null): SyncedConfig {
  let c: Record<string, unknown> = {};
  try {
    const v = JSON.parse(text ?? '{}');
    if (v && typeof v === 'object') c = v;
  } catch { /* a damaged copy: defaults */ }
  return {
    github_username: typeof c.github_username === 'string' ? c.github_username.slice(0, 39) : '',
    topics: strs(c.topics, 60), keywords: strs(c.keywords, 60), languages: strs(c.languages, 30, 40),
    interest_learning: c.interest_learning !== false,
    interest_half_life_days: num(c.interest_half_life_days, 30),
    explore_share: num(c.explore_share, 0.2),
    sync_repo: typeof c.sync_repo === 'string' ? c.sync_repo.slice(0, 140) : '',
    training_mass_follow_outlier: num(c.training_mass_follow_outlier, 3000),
    orcid_id: typeof c.orcid_id === 'string' && /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(c.orcid_id) ? c.orcid_id : '',
  };
}

const jsonl = (text: string | null, max: number): Record<string, any>[] => {
  const out: Record<string, any>[] = [];
  for (const line of (text ?? '').split('\n').slice(-max)) {
    try { const v = JSON.parse(line); if (v && typeof v === 'object' && !Array.isArray(v)) out.push(v); } catch { /* skip */ }
  }
  return out;
};
const short = (v: unknown, n = 20) => (typeof v === 'string' ? v.slice(0, n) : undefined);

function parseUsage(text: string | null): Usage[] {
  return jsonl(text, 50000).filter((e) => typeof e.at === 'string' && typeof e.what === 'string')
    .map((e) => ({ at: e.at.slice(0, 40), what: e.what.slice(0, 20), kind: short(e.kind), cat: short(e.cat), explore: e.explore === true || undefined }));
}

function parseHistory(text: string | null): Brain['history'] {   // storage.load_model_history: the last 100
  return jsonl(text, 100).filter((h) => typeof h.timestamp === 'string').map((h) => ({
    timestamp: h.timestamp.slice(0, 40), n_train: num(h.n_train, 0), n_pos: num(h.n_pos, 0),
    auc: typeof h.auc === 'number' && Number.isFinite(h.auc) ? h.auc : null }));
}

// ---- the follow-back model's weights, without its pickle
// The desktop never syncs model.pkl (opening a pickle that came over the network could run code),
// but it does sync the examples it learns from. Its model is StandardScaler + LogisticRegression
// (C=1, L2, intercept not penalized), which has exactly one answer -- so retraining on the same
// examples (those up to your latest retrain, mass-followers left out) gives the same weights.
const FEATURES: [string, string][] = [
  ['content_similarity', 'Content match'], ['follow_back_ratio', 'Follows people back'],
  ['activity_recency', 'Recently active'], ['shared_languages', 'Shared languages'], ['shared_topics', 'Shared topics'],
];

export function retrainWeights(text: string | null, upTo: string | null, outlier: number): Brain['weights'] {
  if (!upTo) return [];
  const cut = Date.parse(upTo);
  const rows = jsonl(text, 20000).filter((e) => Array.isArray(e.features) && e.features.length === FEATURES.length
    && e.features.every((f: unknown) => typeof f === 'number' && Number.isFinite(f)) && (e.label === 0 || e.label === 1)
    && num(e.following, 0) <= outlier && typeof e.timestamp === 'string' && Date.parse(e.timestamp) <= cut);
  if (rows.length < 2 || !rows.some((r) => r.label === 1) || !rows.some((r) => r.label === 0)) return [];
  const d = FEATURES.length;
  const n = rows.length;
  const mean = Array.from({ length: d }, (_, j) => rows.reduce((a, r) => a + r.features[j], 0) / n);
  const sd = mean.map((m, j) => Math.sqrt(rows.reduce((a, r) => a + (r.features[j] - m) ** 2, 0) / n) || 1);
  const X = rows.map((r) => [...r.features.map((f: number, j: number) => (f - mean[j]) / sd[j]), 1]);   // last column: intercept
  const y = rows.map((r) => r.label as number);
  const w = new Array(d + 1).fill(0);
  for (let it = 0; it < 100; it++) {                       // Newton's method: a handful of steps to the optimum
    const g = w.map((wj, j) => (j < d ? wj : 0));
    const H = w.map((_, i) => w.map((__, j) => (i === j && i < d ? 1 : 0)));
    for (let k = 0; k < n; k++) {
      const z = X[k].reduce((a, x, j) => a + x * w[j], 0);
      const p = 1 / (1 + Math.exp(-z));
      for (let i = 0; i <= d; i++) {
        g[i] += (p - y[k]) * X[k][i];
        for (let j = 0; j <= d; j++) H[i][j] += p * (1 - p) * X[k][i] * X[k][j];
      }
    }
    const step = solve(H, g);
    for (let i = 0; i <= d; i++) w[i] -= step[i];
    if (Math.max(...step.map(Math.abs)) < 1e-10) break;
  }
  return FEATURES.map(([feature, label], j) => ({ feature, label, weight: w[j] }))
    .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
}

function solve(A: number[][], b: number[]): number[] {    // Gaussian elimination with pivoting
  const m = A.map((row, i) => [...row, b[i]]);
  const n = b.length;
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(m[r][c]) > Math.abs(m[p][c])) p = r;
    [m[c], m[p]] = [m[p], m[c]];
    for (let r = 0; r < n; r++) {
      if (r === c || !m[c][c]) continue;
      const f = m[r][c] / m[c][c];
      for (let k = c; k <= n; k++) m[r][k] -= f * m[c][k];
    }
  }
  return m.map((row, i) => (row[i] ? row[n] / row[i] : 0));
}

// ---- badges (achievements.counts), from your computers' usage plus this phone's
export function badgeCounts(b: Pick<Brain, 'usage' | 'eventKinds' | 'sent' | 'keywords' | 'syncing'>, extra: Usage[] = []): Record<string, number> {
  const usage = [...b.usage, ...extra];
  const clicks = usage.filter((e) => e.what === 'click');
  const kind = (k: string) => clicks.filter((e) => e.kind === k).length;
  const days = new Set(usage.filter((e) => e.what === 'open').map((e) => e.at.slice(0, 10)));
  const ev = (k: string) => b.eventKinds.filter((e) => e.kind === k).length;
  const firstUse = usage.reduce((m, e) => (e.at < m ? e.at : m), '9999');
  // before the usage log existed, clicks were only kept as interest events: count those too
  const past = b.eventKinds.filter((e) => ['person', 'repo', 'news'].includes(e.kind) && e.at < firstUse);
  for (const e of b.eventKinds) if (e.at) days.add(e.at.slice(0, 10));
  const first = [...usage.map((e) => e.at), ...b.eventKinds.map((e) => e.at)].filter(Boolean).sort()[0] ?? '';
  return {
    active: days.size, clicker: clicks.length + past.length,
    reader: kind('headline') + kind('news') + past.filter((e) => e.kind === 'news').length,
    analyst: kind('paper'), ai: clicks.filter((e) => e.cat === 'ai' || e.kind === 'model').length, models: kind('model'),
    explorer: clicks.filter((e) => e.explore).length, networker: ev('follow'), stargazer: ev('star'), builder: ev('fork'),
    grateful: b.sent, wordsmith: b.keywords, ideas: usage.filter((e) => e.what === 'idea').length,
    everywhere: b.syncing ? 1 : 0, early: first && first < '2027-01-01' ? 1 : 0,
  };
}

function parseEvents(text: string | null): Event[] {
  const out: Event[] = [];
  for (const line of (text ?? '').split('\n')) {
    if (!line.trim()) continue;
    try {
      const e = JSON.parse(line);
      if (!e || typeof e !== 'object' || typeof e.at !== 'string' || !e.terms || typeof e.terms !== 'object') continue;
      const terms: Record<string, number> = {};
      for (const [t, w] of Object.entries(e.terms).slice(0, 40)) {
        if (typeof w === 'number' && Number.isFinite(w) && t.length <= 60) terms[t] = w;
      }
      out.push({ at: e.at, kind: typeof e.kind === 'string' ? e.kind : '', terms });
    } catch { /* a half-written line: skip it */ }
  }
  return out;
}

// scholar.scholar_corpus: your topics and keywords (three times over), titles, abstracts
export function scholarCorpus(text: string | null): string {
  try {
    const p = JSON.parse(text ?? 'null');
    if (!p || typeof p !== 'object') return '';
    const orcid = p.orcid_record ?? {};
    const oa = p.openalex ?? {};
    const gs = p.google_scholar ?? {};
    const parts: string[] = [];
    for (const list of [strs(orcid.keywords, 200), strs(oa.topics, 200), strs(gs.interests, 200)]) parts.push(...list, ...list, ...list);
    const titles = new Set<string>();
    for (const w of Array.isArray(oa.works) ? oa.works.slice(0, 2000) : []) {
      const title = typeof w?.title === 'string' ? w.title : '';
      titles.add(title.toLowerCase());
      parts.push(title, ...strs(w?.keywords, 50), typeof w?.abstract === 'string' ? w.abstract.slice(0, 20000) : '');
    }
    for (const t of [...strs(orcid.titles, 2000, 400), ...strs(gs.titles, 2000, 400)]) {
      if (!titles.has(t.toLowerCase())) { titles.add(t.toLowerCase()); parts.push(t); }
    }
    return parts.filter(Boolean).join('\n');
  } catch {
    return '';
  }
}

// matcher.build_domain_vocabulary: CountVectorizer(stop_words='english', ngram_range=(1, 2),
// max_features=size) -- your most frequent words and word pairs. Ties at the cut are broken
// alphabetically; scikit-learn leaves their order open, so a tie can rarely land differently.
export function domainVocabulary(corpus: string, size: number): string[] {
  return domainWeights(corpus, size).map(([t]) => t);
}

/** build_domain_vocabulary with its weights: each term's count over the top term's. */
export function domainWeights(corpus: string, size: number): [string, number][] {
  const tokens = (corpus.toLowerCase().match(/[\p{L}\p{N}_]{2,}/gu) ?? []).filter((t) => !SKLEARN_STOP.has(t));
  const counts = new Map<string, number>();
  tokens.forEach((t, i) => {
    counts.set(t, (counts.get(t) ?? 0) + 1);
    if (i + 1 < tokens.length) { const pair = `${t} ${tokens[i + 1]}`; counts.set(pair, (counts.get(pair) ?? 0) + 1); }
  });
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, size);
  const most = top[0]?.[1] ?? 1;
  return top.map(([t, n]) => [t, n / most] as [string, number]);
}

// papers.your_topics: your OpenAlex author's topics, then your stated topics, Scholar interests
// and your top learned terms, each looked up by name, until there are six (OpenAlex is public)
export async function yourTopics(scholarText: string | null, cfg: SyncedConfig, learned: [string, number][], n = 6): Promise<string[]> {
  let profile: Record<string, any> = {};
  try { profile = JSON.parse(scholarText ?? '{}') ?? {}; } catch { /* none */ }
  const topics: { id: string; name: string }[] = [];
  const idOf = (v: unknown) => { const id = String(v ?? '').split('/').pop() ?? ''; return /^T\d+$/.test(id) ? id : ''; };
  const clip = (v: unknown) => String(v ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, 80);
  const author = String(profile.openalex?.author_id ?? '').split('/').pop() ?? '';
  if (/^[AW]\d+$/.test(author)) {
    try {
      const r = await fetchT(`https://api.openalex.org/authors/${author}?select=topics`);
      if (r.ok) for (const t of ((await r.json()).topics ?? []).slice(0, n)) if (idOf(t.id)) topics.push({ id: idOf(t.id), name: clip(t.display_name) });
    } catch { /* offline */ }
  }
  const names = [...cfg.topics, ...strs(profile.google_scholar?.interests, 40), ...learned.slice(0, 3).map(([t]) => t)];
  for (const name of names) {
    if (topics.length >= n) break;
    try {
      const r = await fetchT(`https://api.openalex.org/topics?search=${encodeURIComponent(name)}&per-page=1`);
      if (!r.ok) continue;
      const t = ((await r.json()).results ?? [])[0];
      if (t && idOf(t.id) && !topics.some((x) => x.id === idOf(t.id))) topics.push({ id: idOf(t.id), name: clip(t.display_name) });
    } catch { /* offline */ }
  }
  return topics.slice(0, n).map((t) => t.name);
}

function sentSignals(text: string | null): number {   // beacon.load_my_beacon()['sent']
  try { const b = JSON.parse(text ?? '{}'); return Array.isArray(b?.sent) ? b.sent.length : 0; } catch { return 0; }
}

function scholarTopics(text: string | null): string[] {   // scholar.scholar_topics
  try {
    const p = JSON.parse(text ?? 'null');
    if (!p || typeof p !== 'object') return [];
    const all = [...strs(p.orcid_record?.keywords, 40), ...strs(p.google_scholar?.interests, 40), ...strs(p.openalex?.topics, 40)];
    const seen = new Set<string>();
    return all.filter((t) => !seen.has(t.toLowerCase()) && !!seen.add(t.toLowerCase()));
  } catch {
    return [];
  }
}

// ---- interests.py, ported


/** What this phone has kept of what you opened (until a sync sends it to your data repo). */
export async function localEvents(): Promise<Event[]> {
  try {
    const q = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) ?? '[]');
    return Array.isArray(q) ? q.filter((e) => e && typeof e.at === 'string' && e.terms && typeof e.terms === 'object') : [];
  } catch {
    return [];
  }
}

/** With no data repo, the phone learns on its own: what you opened here fades and weighs as on the desktop
 *  (interests.profile_terms) and sharpens your weights. Once a repo is connected, your computers' model
 *  (withRepoProfile) does that instead, with these events in it. */
export async function withLocalLearning<P extends { weights: Record<string, number> }>(p: P): Promise<P> {
  if (await modelLink()) return p;
  const learned = learnedTerms(await localEvents(), { interest_learning: true, interest_half_life_days: 30 } as SyncedConfig, 15);
  return learned.length ? { ...p, weights: blendLearned(p.weights, learned) } : p;
}

// Python's random.Random(seed).shuffle, so "new territory today" is the desktop's pick
function pythonShuffle<T>(items: T[], seed: number): T[] {
  const mt = new Uint32Array(624);
  let idx = 624;
  const init = (s: number) => {
    mt[0] = s >>> 0;
    for (let i = 1; i < 624; i++) mt[i] = (Math.imul(1812433253, mt[i - 1] ^ (mt[i - 1] >>> 30)) + i) >>> 0;
  };
  // init_by_array([seed]) -- an ordinal date fits in one 32-bit word
  init(19650218);
  let i = 1;
  let j = 0;
  const key = [seed >>> 0];
  for (let k = Math.max(624, key.length); k; k--) {
    mt[i] = ((mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1664525)) + key[j] + j) >>> 0;
    i++; j++;
    if (i >= 624) { mt[0] = mt[623]; i = 1; }
    if (j >= key.length) j = 0;
  }
  for (let k = 623; k; k--) {
    mt[i] = ((mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1566083941)) - i) >>> 0;
    i++;
    if (i >= 624) { mt[0] = mt[623]; i = 1; }
  }
  mt[0] = 0x80000000;
  const next = () => {
    if (idx >= 624) {
      for (let k = 0; k < 624; k++) {
        const y = (mt[k] & 0x80000000) | (mt[(k + 1) % 624] & 0x7fffffff);
        mt[k] = mt[(k + 397) % 624] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      idx = 0;
    }
    let y = mt[idx++];
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  };
  const below = (n: number) => {      // _randbelow_with_getrandbits
    const bits = 32 - Math.clz32(n);
    let r = next() >>> (32 - bits);
    while (r >= n) r = next() >>> (32 - bits);
    return r;
  };
  const out = [...items];
  for (let k = out.length - 1; k > 0; k--) {
    const m = below(k + 1);
    [out[k], out[m]] = [out[m], out[k]];
  }
  return out;
}

const todayOrdinal = () => {          // Python's date.today().toordinal()
  const d = new Date();
  return Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000) + 719163;
};

// interests.explore_terms. `known` is your profile's terms: topics, keywords and what they mean,
// languages, what you've learned (the desktop also adds words from your CV)
export function exploreTerms(known: Set<string>, k: number, ordinal = todayOrdinal()): string[] {
  const pool = EXPLORE_POOL.filter((t) => !known.has(t) && ![...known].some((kt) => t.includes(kt) || kt.includes(t)));
  return pythonShuffle(pool, ordinal).slice(0, k);
}

// ---- the whole map
export async function fetchBrain(repo: string, token: string, dict: Dict | null): Promise<Brain> {
  const [cfgText, eventsText, scholarText, cvText, usageText, beaconText, historyText, trainingText, commits] = await Promise.all([
    raw(repo, token, 'config.synced.json'), raw(repo, token, EVENTS_FILE), raw(repo, token, 'scholar_profile.json'),
    raw(repo, token, 'cv_text.txt'), raw(repo, token, USAGE_FILE), raw(repo, token, 'beacon.json'),
    raw(repo, token, 'model_history.jsonl'), raw(repo, token, 'training_data.jsonl'),
    api(`/repos/${repo}/commits?per_page=1`, token).then((r) => (r.ok ? r.json() : [])).catch(() => []),
  ]);
  const cfg = parseConfig(cfgText);
  const events = parseEvents(eventsText);

  const known = new Set<string>([...cfg.topics, ...cfg.keywords].map((t) => t.toLowerCase().replace(/-/g, ' ')));
  for (const phrase of Object.keys(expand(dict, [...cfg.topics, ...cfg.keywords]))) if (phrase.length >= 3) known.add(phrase);
  for (const t of cfg.languages) known.add(t.toLowerCase());
  const corpus = `${(cvText ?? '').slice(0, 500000)} ${scholarCorpus(scholarText)}`;
  for (const t of domainVocabulary(corpus, 60)) if (!STOPWORDS.has(t)) known.add(t);
  for (const [t] of learnedTerms(events, cfg, 15)) known.add(t);

  // interests.profile_terms, then pairing._learned's cut: your top 30 terms, 0..1
  const terms: Record<string, number> = {};
  const setdefault = (t: string, w: number) => { if (!(t in terms)) terms[t] = w; };
  for (const t of [...cfg.topics, ...cfg.keywords]) terms[t.toLowerCase().replace(/-/g, ' ')] = 1;
  for (const [phrase, w] of Object.entries(expand(dict, [...cfg.topics, ...cfg.keywords]))) if (phrase.length >= 3) setdefault(phrase, w);
  for (const t of cfg.languages) terms[t.toLowerCase()] = 0.4;
  if (corpus.trim()) for (const [t, w] of domainWeights(corpus, 60)) if (!STOPWORDS.has(t)) setdefault(t, 0.8 * w);
  const learned15 = learnedTerms(events, cfg, 15);
  if (learned15.length) {
    const top = learned15[0][1];
    for (const [t, w] of learned15) terms[t] = Math.max(terms[t] ?? 0, 0.3 + (0.7 * w) / top);
  }
  const langs = new Set(cfg.languages.map((x) => x.toLowerCase()));
  const interests: Record<string, number> = {};
  for (const [t, w] of Object.entries(terms).sort((a, b) => b[1] - a[1])) {
    if (t.length >= 2 && t.length <= 40 && /^[\x00-\x7f]+$/.test(t) && /[a-z]/i.test(t) && !langs.has(t)) {
      interests[t] = Math.round(Math.min(Math.max(w, 0), 1) * 100) / 100;
    }
    if (Object.keys(interests).length >= 30) break;
  }

  const since = Date.now() - 30 * 86400000;
  const taught = { clicks: 0, follows: 0, stars: 0, forks: 0 };
  for (const ev of events) {
    const at = Date.parse(ev.at);
    if (Number.isNaN(at) || at < since) continue;
    const key = ({ follow: 'follows', star: 'stars', fork: 'forks' } as const)[ev.kind as 'follow'] ?? 'clicks';
    taught[key] += 1;
  }
  const learned = learnedTerms(events, cfg, 10);
  const history = parseHistory(historyText);
  // get_brain: the trends' topics, else your topics and scholar profile
  const topics = await yourTopics(scholarText, cfg, learned);
  const fieldNow = topics.length ? topics : [...cfg.topics, ...scholarTopics(scholarText)];
  const brain: Brain = {
    repo, user: cfg.github_username,
    syncedAt: Array.isArray(commits) && typeof commits[0]?.commit?.committer?.date === 'string' ? commits[0].commit.committer.date : null,
    field: fieldNow.slice(0, 6), learned,
    explore: cfg.explore_share > 0 ? exploreTerms(known, 3) : [],
    taught, learning: cfg.interest_learning, halfLife: cfg.interest_half_life_days, exploreShare: cfg.explore_share,
    history, weights: retrainWeights(trainingText, history.at(-1)?.timestamp ?? null, cfg.training_mass_follow_outlier),
    usage: parseUsage(usageText), eventKinds: events.map((e) => ({ at: e.at, kind: e.kind })),
    sent: sentSignals(beaconText), keywords: cfg.keywords.length, syncing: !!cfg.sync_repo,
    profile: { orcid: cfg.orcid_id, keywords: cfg.keywords, topics: cfg.topics, interests },
  };
  await writeCache(CACHE_KEY, brain);
  return brain;
}

// ---- what you open on the phone, as interest events (interests.py: extract_terms, record)

let flushing = false;

export type Learn = { kind: string; text: string; topics?: string[]; source?: string };

const LEARN_CAP = 500;           // what you opened, kept on the phone: enough for months at a 30-day half-life

/** Remember that you opened something (terms only). Kept on the phone, and used to rank what you see there
 *  while no data repo is connected (withLocalLearning); sent to the repo at the next sync once one is. */
export async function recordInterest(item: Learn): Promise<void> {
  try {
    if (!KIND_WEIGHTS[item.kind]) return;
    const link = await modelLink();
    const cached = link ? await cachedBrain() : null;
    if (cached?.data && !cached.data.learning) return;                 // learning is off on your computer
    const terms = extractTerms(item.text, item.topics);
    if (!Object.keys(terms).length) return;
    const event = { at: `${new Date().toISOString().slice(0, 19)}+00:00`, kind: item.kind,
      source: (item.source ?? '').slice(0, 120), terms };
    const queue = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) ?? '[]');
    const next = [...(Array.isArray(queue) ? queue : []), event].slice(-LEARN_CAP);
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(next));
    if (link && next.length >= 5) {                      // every few, quietly; the rest go when you open Your model
      flushInterests(link.repo, link.token).catch(() => undefined);
    }
  } catch { /* learning never gets in the way of opening something */ }
}

/** Append the queued events to interest_events.jsonl; once more if a computer pushed in between. */
export async function flushInterests(repo: string, token: string): Promise<number> {
  if (flushing) return 0;                                // one at a time, so nothing is sent twice
  flushing = true;
  try {
    await migrateLocalUsage();
    const sent = await flushQueue(repo, token, EVENTS_FILE, QUEUE_KEY, 'interest event');
    await flushQueue(repo, token, USAGE_FILE, USAGE_QUEUE_KEY, 'usage line');
    return sent;
  } finally {
    flushing = false;
  }
}

/** Append one queue's lines to its .jsonl file; once more if a computer pushed in between. */
export async function flushQueue(repo: string, token: string, file: string, key: string, what: string): Promise<number> {
  const queue = JSON.parse((await AsyncStorage.getItem(key)) ?? '[]');
  if (!Array.isArray(queue) || !queue.length) return 0;
  const lines = queue.map((e) => JSON.stringify(e)).join('\n') + '\n';
  for (let attempt = 0; attempt < 2; attempt++) {
    const meta = await api(`/repos/${repo}/contents/${file}`, token);
    if (meta.status === 401 || meta.status === 403) throw new Error('The model token no longer works. Make a new one and connect again.');
    let current = '';
    let sha: string | undefined;
    if (meta.ok) {
      sha = (await meta.json()).sha;
      current = (await raw(repo, token, file)) ?? '';
      if (current && !current.endsWith('\n')) current += '\n';     // as append_jsonl: never glue onto a cut line
    } else if (meta.status !== 404) {
      throw new Error(`GitHub answered ${meta.status} for ${file}.`);
    }
    const put = await fetchT(`https://api.github.com/repos/${repo}/contents/${file}`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: `myGeeKy phone: ${queue.length} ${what}${queue.length === 1 ? '' : 's'}`,
        sha, author: ME, committer: ME, content: b64(utf8(current + lines)) }),
    });
    if (put.ok) {
      // keep anything you did while this was on its way
      const now = JSON.parse((await AsyncStorage.getItem(key)) ?? '[]');
      await AsyncStorage.setItem(key, JSON.stringify(Array.isArray(now) ? now.slice(queue.length) : []));
      return queue.length;
    }
    if (put.status !== 409 && put.status !== 422) throw new Error(`GitHub answered ${put.status} when saving ${file}.`);
  }
  throw new Error('Your computer was syncing at the same moment. Try again in a minute.');
}

// ---- this phone's usage, for badges (achievements.log): the kind of thing only, never titles or links
const isoNow = () => `${new Date().toISOString().slice(0, 19)}+00:00`;

/** One usage line, kept until the next sync -- only while your data repo is connected. */
export async function queueUsage(entry: Omit<Usage, 'at'>): Promise<void> {
  try {                                                  // kept with or without a repo: it goes there once there is one
    const line: Usage = { at: isoNow(), what: entry.what };
    if (entry.kind) line.kind = entry.kind.slice(0, 20);
    if (entry.cat) line.cat = entry.cat.slice(0, 20);
    if (entry.explore) line.explore = true;
    const queue = JSON.parse((await AsyncStorage.getItem(USAGE_QUEUE_KEY)) ?? '[]');
    await AsyncStorage.setItem(USAGE_QUEUE_KEY, JSON.stringify([...(Array.isArray(queue) ? queue : []), line].slice(-1000)));
  } catch { /* never in the way */ }
}

export async function queuedUsage(): Promise<Usage[]> {
  try {
    const q = JSON.parse((await AsyncStorage.getItem(USAGE_QUEUE_KEY)) ?? '[]');
    return Array.isArray(q) ? q : [];
  } catch {
    return [];
  }
}

// What this phone counted before you connected (badges.ts keeps it), sent once, so those badges
// carry over: each day of use as an "open", each click as a click today.
async function migrateLocalUsage(): Promise<void> {
  if (await AsyncStorage.getItem(MIGRATED_KEY)) return;
  try {
    const local = JSON.parse((await AsyncStorage.getItem('mygeeky.usage')) ?? 'null');
    const lines: Usage[] = [];
    for (const d of Array.isArray(local?.days) ? local.days : []) {
      if (typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d)) lines.push({ at: `${d}T12:00:00+00:00`, what: 'open' });
    }
    for (const c of Array.isArray(local?.clicks) ? local.clicks : []) {
      if (!c || typeof c.kind !== 'string') continue;
      const line: Usage = { at: isoNow(), what: 'click', kind: c.kind.slice(0, 20) };
      if (typeof c.cat === 'string') line.cat = c.cat.slice(0, 20);
      if (c.explore) line.explore = true;
      lines.push(line);
    }
    if (lines.length) {
      const queue = JSON.parse((await AsyncStorage.getItem(USAGE_QUEUE_KEY)) ?? '[]');
      await AsyncStorage.setItem(USAGE_QUEUE_KEY, JSON.stringify([...lines, ...(Array.isArray(queue) ? queue : [])]));
    }
  } catch { /* nothing to carry over */ }
  await AsyncStorage.setItem(MIGRATED_KEY, '1');
}

/** Send what you opened here, then read the map back (so it includes the phone's own clicks). */
export async function syncModel(dict: Dict | null): Promise<{ brain: Brain; sent: number } | null> {
  const link = await modelLink();
  if (!link) return null;
  const sent = await flushInterests(link.repo, link.token);
  return { brain: await fetchBrain(link.repo, link.token, dict), sent };
}

// ---- for the maker's admin part (admin.ts): one file from your data repo, and who the token belongs to
/** A file from your data repo, read with this phone's token; null when not connected or not synced. */
export async function readRepoFile(file: string): Promise<string | null> {
  const link = await modelLink();
  return link ? raw(link.repo, link.token, file) : null;
}

/** The GitHub account the phone's data-repo token belongs to, as GitHub itself says -- not a name typed
 *  anywhere in the app -- and only if that account owns the repo the token reads. */
export async function verifiedOwner(): Promise<string | null> {
  const link = await modelLink();
  if (!link) return null;
  try {
    const r = await api('/user', link.token);
    if (!r.ok) return null;
    const login = String((await r.json())?.login ?? '');
    return login && link.repo.split('/')[0].toLowerCase() === login.toLowerCase() ? login : null;
  } catch {
    return null;
  }
}
