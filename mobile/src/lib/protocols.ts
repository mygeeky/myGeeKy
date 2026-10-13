// Protocols: a skill turned into ordered stages, with a level check -- a port of the
// desktop's protocols.py. Reviewed ones come with the maker's curated file; for any
// other skill the phone builds one now: it searches GitHub and OpenAlex and the small
// protocol model (protomodel.ts) sorts what comes back into stages. Yours to change:
// reorder, rename, add and remove. 📤 Publish opens a prefilled public issue you send
// with your own GitHub account -- the protocol and the links you removed, never your
// progress or answers. Everything else stays on the phone.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { forSkill, type Lists } from './curated';
import { articleQueries, type Cand, githubQueries, predict, searchGithub, searchOpenalex, term } from './protomodel';
import { cleanLink, cleanProtocol, type Link, MAX_ITEMS, MAX_STAGES, type Protocol, type Role, slug, type Stage, text } from './protocol-shape';
import { type Doc, find } from './skills';
import * as taste from './taste';
import type { MyRepo } from './wins';

const KEY = 'mygeeky.protocols';
const OLD_PATHS_KEY = 'mygeeky.paths';
export const PASS = 0.75;
const PER_STAGE: Partial<Record<Role, number>> = { basics: 3, deeper: 3, applied: 3, project: 2 };
const LEARN_ROLES = ['basics', 'deeper', 'applied', 'project'] as const;
const IDEAS_REPO = 'mygeeky/myGeeKy-ideas';
const MAX_URL = 7000;

export type Entry = { startedAt: string; protocol: Protocol; done: string[]; known: Record<string, 'self' | 'no'>;
  quiz: Record<string, number>; removed: string[]; edited: boolean };
export type State = Record<string, Entry>;
export type StageView = Stage & { status: 'done' | 'known' | 'current' | 'todo'; how: '' | 'quiz' | 'self' | 'evidence';
  why: string; score?: number; overruled: boolean };
export type View = Omit<Protocol, 'stages'> & { stages: StageView[]; current: string | null; doneCount: number; total: number;
  finished: boolean; startedAt: string; edited: boolean };

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const today = () => new Date().toISOString().slice(0, 10);
const same = (a: string, b: string) => (a || '').trim().toLowerCase() === (b || '').trim().toLowerCase();
const aliases = (name: string) => [...new Set([name.toLowerCase(), ...(find(name)?.aliases ?? [])])];

export function findReviewed(skill: string, goal: string, lists: Lists): Protocol | null {
  const name = find(skill)?.name ?? skill;
  const mine = (lists.protocols ?? []).filter((p) => same(p.skill, name));
  return (goal && mine.find((p) => same(p.goal, goal))) || mine[0] || null;
}

function can(role: string, name: string, goal: string): string[] {
  const g = goal || 'a real analysis';
  return ({
    basics: [`I can explain what ${name} is for and when to use it`, `I've followed a beginner tutorial on ${name} from start to end`,
      'I can do the everyday tasks without looking everything up'],
    deeper: [`I know the main ideas behind ${name}, not only the commands`, `I can read someone else's ${name} work and follow it`,
      'I know the common mistakes and how to avoid them'],
    applied: [`I've used ${name} for ${g} from start to finish`, `I can choose the right approach in ${name} for a new problem`],
    project: [`I've read and rerun a real ${name} project from my field`],
  } as Record<string, string[]>)[role] ?? [];
}

export function template(skill: string, goal = ''): Protocol {
  const s = find(skill);
  const name = s?.name ?? text(skill, 60);
  goal = text(goal, 60);
  const stats = s?.kind === 'language' && goal.toLowerCase().includes('analy');
  const base: [string, string, Role, string][] = [
    ['basics', `${name} basics`, 'basics', ''],
    ['deeper', stats ? `Statistics with ${name}` : `${name} in depth`, 'deeper', stats ? 'statistics' : ''],
    ['applied', goal ? `${name} for ${goal}` : `Using ${name} on real data`, 'applied', goal],
    ['project', 'A real project to rerun', 'project', goal || 'analysis'],
    ['use', 'Use it in your own work', 'use', ''],
  ];
  return { id: slug(goal ? `${name} ${goal}` : name), skill: name, goal, title: goal ? `${name} for ${goal}` : `Learning ${name}`,
    summary: '', reviewed: false, source: 'auto', by: '', based_on: '',
    stages: base.map(([id, title, role, query]) => ({ id, title, role, query, skills: [name.toLowerCase()], can: can(role, name, goal),
      quiz: [], items: [] })) };
}

const searchLink = (name: string, words: string): Link => {
  const q = `${name} ${words}`.trim();
  return { title: `Search GitHub: ${q}`, url: `https://github.com/search?q=${encodeURIComponent(q)}&type=repositories&s=stars`,
    kind: 'repo', note: 'Nothing picked yet: the most-starred matches' };
};

/** GitHub and OpenAlex hits for this protocol, tagged with the stage that asked. */
export async function candidates(p: Protocol, token: string | null): Promise<Cand[]> {
  const kind = find(p.skill)?.kind ?? '';
  const asks: [string, string][] = githubQueries(p.skill, kind, p.goal).slice(0, 6).map((q) => [q, '']);
  for (const st of p.stages) if (st.query && st.role in PER_STAGE) asks.push([`${term(p.skill)} ${st.query}`, st.id]);
  const out: Cand[] = [];
  const seen = new Set<string>();
  const add = (cs: Cand[], by = '') => cs.forEach((c) => { if (!seen.has(c.id)) { seen.add(c.id); out.push({ ...c, askedBy: by }); } });
  for (const [q, by] of asks.slice(0, token ? 10 : 6)) {   // without a token GitHub allows 10 searches a minute
    try {
      add(await searchGithub(q, token), by);
    } catch {
      break;                                                // offline or rate-limited: use what we have
    }
  }
  const searches = articleQueries(p.skill, p.goal);
  for (const st of p.stages) if (st.query && (st.role === 'deeper' || st.role === 'applied')) searches.push([`${p.skill} ${st.query} tutorial`, '']);
  for (const [q, f] of searches.slice(0, 4)) {
    try {
      add(await searchOpenalex(q, f));
    } catch {
      /* skip */
    }
  }
  return out;
}

const LEVEL_ROLE: Record<string, Role> = { beginner: 'basics', '': 'basics', intermediate: 'deeper', advanced: 'deeper' };

/** The best candidates into the protocol's empty stages; the model decides which stage fits. */
export async function fill(p: Protocol, cands: Cand[], lists: Lists): Promise<Protocol> {
  const al = aliases(p.skill);
  const leanW = taste.weights(await taste.load(), ['resource']);
  const byRole: Record<string, [number, Link][]> = { basics: [], deeper: [], applied: [], project: [] };
  const s = find(p.skill);
  for (const r of forSkill(p.skill, s?.aliases ?? [p.skill.toLowerCase()], lists)) {
    byRole[LEVEL_ROLE[r.level ?? ''] ?? 'basics'].push([2, { title: r.title, url: r.url, kind: r.type ?? 'website', note: r.summary.slice(0, 200) }]);
  }
  const stageOf = Object.fromEntries(p.stages.map((st) => [st.id, st.role]));
  for (const c of cands) {
    if (c.archived) continue;
    const pr = predict(c, al);
    const role = LEARN_ROLES.reduce((a, b) => (pr[b] > pr[a] ? b : a));
    if (pr[role] < Math.max(0.35, pr.none)) continue;
    let boost = 1 + (c.kind === 'repo' ? 0.15 * Math.log10(1 + (c.stars ?? 0)) : 0.1 * Math.log10(1 + (c.cited ?? 0)));
    if (stageOf[c.askedBy ?? ''] === role) boost += 0.25;
    const tilt = taste.lean(`${c.title} ${c.text}`, c.topics ?? [], leanW);
    const link = cleanLink({ title: c.title, url: c.url, kind: c.kind, note: c.text ?? '', stars: c.stars, lang: c.language,
      updated: c.updated, year: c.year, cited: c.cited });
    if (link) byRole[role].push([pr[role] * boost + 0.25 * tilt, link]);
  }
  const out = clone(p);
  const used = new Set<string>();
  for (const st of out.stages) {
    const n = PER_STAGE[st.role];
    if (!n || st.items.length) {
      st.items.forEach((i) => used.add(i.url));
      continue;
    }
    const picked: Link[] = [];
    let articles = 0;
    for (const [, it] of [...byRole[st.role]].sort((a, b) => b[0] - a[0])) {
      if (used.has(it.url) || picked.length >= n) continue;
      if (it.kind === 'article') {
        if (articles >= 1) continue;
        articles++;
      }
      picked.push(it);
      used.add(it.url);
    }
    st.items = picked.length ? picked : [searchLink(p.skill, st.query || { basics: 'tutorial', deeper: 'awesome', applied: 'tutorial', project: 'analysis' }[st.role as 'basics'] || '')];
  }
  return out;
}

/** The reviewed protocol if there is one, else one built now from GitHub, OpenAlex and the model. */
export async function build(skill: string, goal: string, lists: Lists, token: string | null, docs: Doc[]): Promise<Protocol> {
  const found = findReviewed(skill, goal, lists);
  let p = found ? clone(found) : template(skill, goal);
  if (!found) p = await fill(p, await candidates(p, token), lists);
  const s = find(p.skill);
  for (const st of p.stages) {
    if (st.role !== 'project' || st.items.some((i) => !i.url.includes('github.com/search'))) continue;
    const near = s ? docs.filter((d) => ['repo', 'tool'].includes(d.source) && d.url.startsWith('https://') && s.re.test(d.text)).slice(0, 2)
      .map((d) => ({ title: d.title.slice(0, 160), url: d.url, kind: 'repo', note: 'From your field' })) : [];
    if (near.length) st.items = [...near, ...st.items.filter((i) => !i.url.includes('github.com/search'))];
  }
  return p;
}

// ---- the level check
export function evidence(p: Protocol, repos: MyRepo[], profile: string): Record<string, { known: boolean; why: string }> {
  const s = find(p.skill);
  const name = s?.name ?? p.skill;
  const repoText = (r: MyRepo) => `${r.name} ; ${r.description} ; ${r.topics.join(' ')} ; ${r.language}`;
  const withSkill = repos.filter((r) => (r.language || '').toLowerCase() === name.toLowerCase() || !!s?.re.test(repoText(r)));
  const inProfile = !!s?.re.test(profile);
  const n = withSkill.length;
  const out: Record<string, { known: boolean; why: string }> = {};
  for (const st of p.stages) {
    let words = (st.query.toLowerCase().match(/[a-z0-9-]{3,}/g) ?? []).filter((w) => w !== 'analysis');
    if (!words.length && st.query) words = ['analysis', 'analyses', 'pipeline'];
    const about = withSkill.filter((r) => words.length && words.some((w) => repoText(r).toLowerCase().includes(w)));
    if (st.role === 'basics') {
      out[st.id] = { known: n >= 2 || (n >= 1 && inProfile), why: n ? `${n} of your repos use ${name}` : inProfile ? `${name} is in your profile` : '' };
    } else if (st.role === 'deeper') {
      out[st.id] = { known: n >= 5 || about.length >= 2,
        why: about.length ? `${about.length} of your ${name} repos are about ${words[0]}` : n ? `${n} of your repos use ${name}` : '' };
    } else if (st.role === 'applied' || st.role === 'project') {
      out[st.id] = { known: about.length >= (st.role === 'applied' ? 2 : 3) || n >= 8,
        why: about.length ? `${about.length} of your ${name} repos look like ${st.query || 'real work'}` : '' };
    } else {
      const known = n >= 1 || inProfile;
      out[st.id] = { known, why: known ? (n ? `it's in ${n} of your repos` : "it's in your profile") : `Push a repo that uses ${name}: this ticks itself` };
    }
  }
  return out;
}

export const quizScore = (st: Stage, answers: number[]) =>
  st.quiz.length ? st.quiz.filter((q, i) => answers[i] === q.answer).length / st.quiz.length : 0;

// ---- your protocols
function migrateOld(old: Record<string, { startedAt: string; done: string[] }>, lists: Lists): State {
  const out: State = {};
  for (const [skill, e] of Object.entries(old ?? {})) {
    const p = clone(findReviewed(skill, '', lists) ?? template(skill));
    const map: Record<string, string> = { basics: 'basics', deeper: 'deeper', practice: 'project' };
    const roles = (e.done ?? []).map((d) => map[d]).filter(Boolean);
    out[p.id] = { startedAt: e.startedAt || today(), protocol: p, done: p.stages.filter((s) => roles.includes(s.role)).map((s) => s.id),
      known: {}, quiz: {}, removed: [], edited: false };
  }
  return out;
}

export async function load(lists: Lists): Promise<State> {
  let raw: State | null = null;
  try {
    raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? 'null');
  } catch {
    raw = null;
  }
  if (!raw) {                                       // learning paths saved before protocols
    try {
      raw = migrateOld(JSON.parse((await AsyncStorage.getItem(OLD_PATHS_KEY)) ?? '{}'), lists);
    } catch {
      raw = {};
    }
  }
  const out: State = {};
  for (const e of Object.values(raw ?? {})) {
    const p = cleanProtocol(e?.protocol, !!e?.protocol?.reviewed && !e.edited);
    if (p) out[p.id] = { startedAt: e.startedAt || today(), protocol: p, done: e.done ?? [], known: e.known ?? {}, quiz: e.quiz ?? {},
      removed: e.removed ?? [], edited: !!e.edited };
  }
  return out;
}

async function save(state: State) {
  await AsyncStorage.setItem(KEY, JSON.stringify(state));
}

async function change(lists: Lists, fn: (s: State) => void): Promise<State> {
  const state = await load(lists);
  fn(state);
  await save(state);
  return state;
}

export async function start(lists: Lists, proto: Protocol): Promise<string> {
  const p = cleanProtocol(proto, proto.reviewed);
  if (!p) return '';
  await change(lists, (state) => {
    if (state[p.id] && JSON.stringify(state[p.id].protocol) !== JSON.stringify(p)) {
      let k = 2;
      while (state[`${p.id}-${k}`.slice(0, 80)]) k++;
      p.id = `${p.id}-${k}`.slice(0, 80);
    }
    if (!state[p.id]) state[p.id] = { startedAt: today(), protocol: p, done: [], known: {}, quiz: {}, removed: [], edited: false };
  });
  return p.id;
}

export const stop = (lists: Lists, pid: string) => change(lists, (s) => { delete s[pid]; });
export const tick = (lists: Lists, pid: string, sid: string, done: boolean) => change(lists, (s) => {
  const e = s[pid];
  if (e) e.done = [...e.done.filter((x) => x !== sid), ...(done ? [sid] : [])];
});
export const markKnown = (lists: Lists, pid: string, sid: string, how: 'self' | 'no' | null) => change(lists, (s) => {
  const e = s[pid];
  if (!e) return;
  if (how) e.known[sid] = how;
  else delete e.known[sid];
});
export async function answerQuiz(lists: Lists, pid: string, sid: string, answers: number[]): Promise<number> {
  let score = 0;
  await change(lists, (s) => {
    const st = s[pid]?.protocol.stages.find((x) => x.id === sid);
    if (!st) return;
    score = quizScore(st, answers);
    s[pid].quiz[sid] = Math.round(score * 100) / 100;
  });
  return score;
}

// ---- editing: any change makes it yours ("mine"), remembering which reviewed one it came from
async function edit(lists: Lists, pid: string, fn: (e: Entry) => void): Promise<boolean> {
  let ok = false;
  await change(lists, (s) => {
    const e = s[pid];
    if (!e) return;
    const before = JSON.stringify(e.protocol);
    fn(e);
    if (JSON.stringify(e.protocol) !== before) {
      if (e.protocol.reviewed) e.protocol.based_on = e.protocol.id;
      e.protocol.reviewed = false;
      e.protocol.source = 'mine';
      e.edited = true;
      ok = true;
    }
  });
  return ok;
}
const stageIn = (e: Entry, sid: string) => e.protocol.stages.find((x) => x.id === sid);
const remember = (e: Entry, urls: string[]) => {
  e.removed = [...new Set([...e.removed, ...urls.filter((u) => !u.includes('github.com/search'))])].slice(-60);
};

export const moveStage = (lists: Lists, pid: string, sid: string, delta: number) => edit(lists, pid, (e) => {
  const st = e.protocol.stages;
  const i = st.findIndex((x) => x.id === sid);
  if (i >= 0 && i + delta >= 0 && i + delta < st.length) [st[i], st[i + delta]] = [st[i + delta], st[i]];
});
export const renameStage = (lists: Lists, pid: string, sid: string, title: string) => edit(lists, pid, (e) => {
  const st = stageIn(e, sid);
  const t = text(title, 80);
  if (st && t) st.title = t;
});
export const addStage = (lists: Lists, pid: string, title: string) => edit(lists, pid, (e) => {
  const st = e.protocol.stages;
  const t = text(title, 80);
  if (!t || st.length >= MAX_STAGES) return;
  const ids = new Set(st.map((x) => x.id));
  let sid = slug(t, 30);
  while (ids.has(sid)) sid = `${sid.slice(0, 34)}-${ids.size + 1}`;
  const at = st.length && st[st.length - 1].role === 'use' ? st.length - 1 : st.length;
  st.splice(at, 0, { id: sid, title: t, role: 'applied', query: '', skills: [e.protocol.skill.toLowerCase()], can: [], quiz: [], items: [] });
});
export const removeStage = (lists: Lists, pid: string, sid: string) => edit(lists, pid, (e) => {
  if (e.protocol.stages.length <= 1) return;
  const gone = stageIn(e, sid);
  if (gone) remember(e, gone.items.map((i) => i.url));
  e.protocol.stages = e.protocol.stages.filter((x) => x.id !== sid);
});
/** Up/down within its stage; past the top or bottom it moves to the stage before or after. */
export const moveItem = (lists: Lists, pid: string, sid: string, url: string, delta: number) => edit(lists, pid, (e) => {
  const stages = e.protocol.stages;
  const k = stages.findIndex((x) => x.id === sid);
  if (k < 0) return;
  const items = stages[k].items;
  const i = items.findIndex((x) => x.url === url);
  if (i < 0) return;
  const j = i + delta;
  if (j >= 0 && j < items.length) {
    [items[i], items[j]] = [items[j], items[i]];
    return;
  }
  const t = k + (delta > 0 ? 1 : -1);
  if (t >= 0 && t < stages.length && stages[t].items.length < MAX_ITEMS) {
    const [it] = items.splice(i, 1);
    if (delta > 0) stages[t].items.unshift(it);
    else stages[t].items.push(it);
  }
});
export const removeItem = (lists: Lists, pid: string, sid: string, url: string) => edit(lists, pid, (e) => {
  const st = stageIn(e, sid);
  if (!st || !st.items.some((i) => i.url === url)) return;
  st.items = st.items.filter((i) => i.url !== url);
  remember(e, [url]);
});
export async function addItem(lists: Lists, pid: string, sid: string, url: string, title: string): Promise<boolean> {
  const u = url.trim();
  const item = cleanLink({ url: u, title: title.trim() || u, kind: u.includes('github.com/') ? 'repo' : u.includes('doi.org/') ? 'article' : 'website' });
  if (!item) return false;
  return edit(lists, pid, (e) => {
    const st = stageIn(e, sid);
    if (st && st.items.length < MAX_ITEMS && !st.items.some((i) => i.url === item.url)) {
      st.items.push(item);
      e.removed = e.removed.filter((x) => x !== item.url);
    }
  });
}

// ---- progress
export function view(e: Entry, ev: Record<string, { known: boolean; why: string }>): View {
  let current: string | null = null;
  const stages: StageView[] = e.protocol.stages.map((st) => {
    const x = ev[st.id] ?? { known: false, why: '' };
    let how: StageView['how'] = '';
    if (st.role === 'use') how = x.known ? 'evidence' : '';
    else if (e.known[st.id] === 'self') how = 'self';
    else if ((e.quiz[st.id] ?? 0) >= PASS) how = 'quiz';
    else if (x.known && e.known[st.id] !== 'no') how = 'evidence';
    const done = e.done.includes(st.id) || (st.role === 'use' && !!how);
    let status: StageView['status'] = done ? 'done' : how ? 'known' : 'todo';
    if (status === 'todo' && current === null) {
      current = st.id;
      status = 'current';
    }
    return { ...st, status, how, why: x.why, score: e.quiz[st.id], overruled: e.known[st.id] === 'no' };
  });
  const n = stages.filter((s) => s.status === 'done' || s.status === 'known').length;
  return { ...e.protocol, stages, current, doneCount: n, total: stages.length, finished: n === stages.length, startedAt: e.startedAt,
    edited: e.edited };
}

// ---- publishing: a prefilled issue in the public ideas repo, sent with your own account
export function publish(e: Entry): { url: string; clipboard: string } {
  const p = e.protocol;
  const payload = { id: p.id, skill: p.skill, goal: p.goal, title: p.title, summary: p.summary, based_on: p.based_on,
    stages: p.stages.map((s) => ({ id: s.id, title: s.title, role: s.role, query: s.query,
      items: s.items.map((i) => ({ title: i.title, url: i.url, kind: i.kind, note: i.note })) })),
    removed: [...e.removed] };
  const block = (pl: object) => `<details><summary>For myGeeKy (don't edit)</summary>\n\n\`\`\`json\n${JSON.stringify(pl)}\n\`\`\`\n</details>\n`;
  const readable = (links: boolean) => [`A protocol for **${p.skill}**${p.goal ? ` (${p.goal})` : ''}${p.based_on ? `, changed from \`${p.based_on}\`` : ''}:`, '',
    ...p.stages.flatMap((s, i) => [`${i + 1}. **${s.title}**`, ...(links ? s.items.map((it) => `   - [${it.title}](${it.url})`) : [])])].join('\n') + '\n\n';
  const url = (body: string) => `https://github.com/${IDEAS_REPO}/issues/new?${new URLSearchParams({ title: `🧭 Protocol: ${p.title}`.slice(0, 120), body,
    labels: 'protocol' }).toString()}`;
  const bare = clone(payload);
  bare.stages.forEach((s) => s.items.forEach((i) => { i.note = ''; }));
  for (const body of [readable(true) + block(payload), readable(false) + block(payload), readable(false) + block(bare)]) {
    const u = url(body);
    if (u.length <= MAX_URL) return { url: u, clipboard: '' };
  }
  return { url: url(`${readable(false)}**Paste the protocol here** (myGeeKy copied it for you):\n\n`), clipboard: block(payload) };
}

// ---- how a protocol is shown (the same as the desktop's protocols.Step and protocols.Resource)
export const ROLE_LABEL: Record<string, string> = { basics: 'Learn the basics', deeper: 'Go deeper', applied: 'Apply it',
  project: 'Practise on a real project', use: 'Use it in your own work' };
export const STATUS_LABEL: Record<string, string> = { done: 'Done', known: 'You know this', current: 'Start here', todo: 'Still to do' };
/** kind: [icon, what it is, the button] */
export const RESOURCE_KINDS: Record<string, [string, string, string]> = {
  repo: ['📦', 'GitHub repo', 'Open on GitHub'], article: ['📄', 'Paper', 'Read the paper'], book: ['📖', 'Free book', 'Read the book'],
  course: ['🎓', 'Course', 'Start the course'], tutorial: ['🧭', 'Tutorial', 'Follow the tutorial'], video: ['🎬', 'Video', 'Watch it'],
  website: ['🌐', 'Website', 'Open the site'], search: ['🔎', 'GitHub search', 'Search GitHub'],
};

/** One link inside a step, as it's shown: what it is, its name, the facts that help you choose, one button. */
export type Resource = { kind: string; icon: string; label: string; title: string; subtitle: string; blurb: string; action: string;
  url: string; link: Link };
/** One stage, as it's shown: its number, what kind of step, where you stand and why, and its resources. */
export type Step = { number: number; id: string; title: string; role: string; roleLabel: string; status: StageView['status'];
  statusLabel: string; why: string; how: StageView['how']; overruled: boolean; canCheck: boolean; auto: boolean;
  resources: Resource[]; stage: StageView };

const short = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k` : String(n));
const host = (url: string) => (url.split('/')[2] ?? '').toLowerCase().replace(/^www\./, '');

export function resourceOf(it: Link): Resource {
  const kind = it.url.startsWith('https://github.com/search?') ? 'search' : it.kind;
  const [icon, label, action] = RESOURCE_KINDS[kind] ?? RESOURCE_KINDS.website;
  let title = it.title;
  const facts: string[] = [];
  if (kind === 'repo') {
    const [owner, name] = it.title.includes('/') && !it.title.includes(' ') ? it.title.split('/', 2) : ['', ''];
    if (name) {
      title = name.replace(/[-_]/g, ' ');
      facts.push(`by ${owner}`);
    }
    if (it.stars) facts.push(`⭐ ${short(it.stars)}`);
    if (it.lang) facts.push(it.lang);
    if (it.updated) facts.push(`updated ${it.updated.slice(0, 4)}`);
  } else if (kind === 'article') {
    if (it.year) facts.push(String(it.year));
    if (it.cited) facts.push(`cited ${short(it.cited)}×`);
    facts.push(host(it.url).replace('doi.org', 'DOI'));
  } else if (kind === 'search') {
    title = it.title.replace('Search GitHub: ', '');
    facts.push('nothing picked yet: the most-starred matches');
  } else {
    facts.push(host(it.url));
  }
  return { kind, icon, label, title, subtitle: facts.filter(Boolean).join(' · '), blurb: kind === 'search' ? '' : it.note, action,
    url: it.url, link: it };
}

export function stepOf(st: StageView, number: number): Step {
  let why = st.why;
  if (st.role === 'use') why = st.status === 'done' || st.status === 'known' ? `Done: ${why}` : why || 'Ticks itself when one of your repos shows the skill';
  else if (st.how === 'evidence' && why) why = `From your work: ${why}`;
  else if (st.how === 'quiz' && st.score != null) why = `You passed the check (${Math.round(st.score * 100)}%)`;
  else if (st.how === 'self') why = 'You said you can do this';
  else if (st.overruled) why = `${why || 'Your work suggests you know this'}, but you said not yet`;
  else why = '';
  return { number, id: st.id, title: st.title, role: st.role, roleLabel: ROLE_LABEL[st.role] ?? 'Step', status: st.status,
    statusLabel: STATUS_LABEL[st.status] ?? '', why, how: st.how, overruled: st.overruled,
    canCheck: (st.quiz.length > 0 || st.can.length > 0) && st.status !== 'done' && st.status !== 'known' && st.role !== 'use',
    auto: st.role === 'use', resources: st.items.map(resourceOf), stage: st };
}
