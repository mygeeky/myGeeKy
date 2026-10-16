// The maker's admin part, on the phone (src/mygeeky/admin.py): adoption, the ideas inbox and the people who
// might want myGeeKy, with an invite to copy or send yourself.
//
// What keeps it the maker's:
//   * it shows only when GitHub says the phone's data-repo token belongs to an ADMINS account that owns
//     that repo (verifiedOwner) -- a username typed into the app proves nothing;
//   * everything in it comes from admin_prospects.json in that PRIVATE repo, so a modified copy of this
//     open-source app that shows the part anyway still has nothing to show;
//   * the phone's own lock (fingerprint, face or PIN) is asked for every time it opens (admin-part.tsx);
//   * nothing secret lives here: finding listings, publishing them, writing quizzes and their DeepSeek key
//     stay on the computer;
//   * the phone never edits admin_prospects.json or scout.json (whole files every computer writes): what you
//     do here is one line appended to admin_actions.jsonl, which your computers apply at their next sync
//     (src/mygeeky/adminlog.py), and which this part shows as done straight away.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import { bank } from './quiz';
import type { Lists } from './curated';
import { flushQueue, modelLink, readRepoFile, verifiedOwner } from './model-repo';

export const ADMINS = new Set(['alsammanalsamman']);
export const INVITE_DAILY_LIMIT = 10;
const ACTIVE_DAYS = 60;
const FILE = 'admin_prospects.json';

export type Person = {
  login: string; status: string; why: string[]; name: string; bio: string; email: string; followers: number;
  avatar: string; score: number; looked_up_at: string; events_30d: number; last_active: string; invited_at: string;
};
export type Idea = { number: number; kind: string; title: string; author: string; created_at: string; comments: number;
  reactions: number; url: string };
export type AdminData = {
  people: Person[]; inbox: Idea[]; adoption: Record<string, number | null>; updatedAt: string;
  keywordRequests: { word: string; people: number; suggested: number }[];
};

let verified: string | null = null;            // a yes is kept for this app run; a no is asked again next time

/** The admin account this phone is signed into, or null. */
export async function adminLogin(): Promise<string | null> {
  if (!verified) verified = await verifiedOwner();
  return verified && ADMINS.has(verified.toLowerCase()) ? verified : null;
}

const str = (v: unknown, n = 300) => (typeof v === 'string' ? v.slice(0, n) : '');
const int = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const httpsGithub = (v: unknown) => (typeof v === 'string' && /^https:\/\/(github\.com|avatars\.githubusercontent\.com)\//.test(v) ? v : '');

export async function loadAdmin(): Promise<AdminData | null> {
  if (!(await adminLogin())) return null;
  const text = await readRepoFile(FILE);
  if (!text) return null;
  let d: Record<string, any> = {};
  try { d = JSON.parse(text) ?? {}; } catch { return null; }
  const people: Person[] = Object.values(d.people && typeof d.people === 'object' ? d.people : {}).slice(0, 5000)
    .filter((p: any) => p && typeof p.login === 'string' && /^[A-Za-z0-9-]{1,39}$/.test(p.login))
    .map((p: any) => ({
      login: p.login, status: str(p.status, 20), why: (Array.isArray(p.why) ? p.why : []).map((w: unknown) => str(w, 160)).filter(Boolean),
      name: str(p.name, 120), bio: str(p.bio, 300), email: /^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$/.test(str(p.email)) ? p.email : '',
      followers: int(p.followers), avatar: httpsGithub(p.avatar), score: int(p.score), looked_up_at: str(p.looked_up_at, 40),
      events_30d: int(p.events_30d), last_active: str(p.last_active, 40), invited_at: str(p.invited_at, 40),
    }));
  const inbox: Idea[] = (Array.isArray(d.inbox) ? d.inbox : []).slice(0, 100).map((i: any) => ({
    number: int(i?.number), kind: str(i?.kind, 20) || 'idea', title: str(i?.title, 200), author: str(i?.author, 39),
    created_at: str(i?.created_at, 40), comments: int(i?.comments), reactions: int(i?.reactions), url: httpsGithub(i?.url),
  }));
  const adoption: Record<string, number | null> = {};
  for (const k of ['pypi_week', 'pypi_month', 'installer_downloads', 'stars', 'forks', 'signals_users']) {
    const v = d.adoption?.[k];
    adoption[k] = typeof v === 'number' && Number.isFinite(v) ? v : null;
  }
  const keywordRequests = (Array.isArray(d.keyword_requests) ? d.keyword_requests : []).slice(0, 60)
    .filter((r: any) => typeof r?.word === 'string').map((r: any) => ({ word: str(r.word, 60), people: int(r.people), suggested: int(r.suggested) }));
  return { people, inbox, adoption, updatedAt: str(d.updated_at, 40), keywordRequests };
}

// ---- admin.py, ported
const isActive = (p: Person) => {
  const t = Date.parse(p.last_active);
  return !Number.isNaN(t) && Date.now() - t < ACTIVE_DAYS * 86400000;
};

/** Only people active on GitHub lately: someone quiet for months won't see an invite. */
export const prospects = (people: Person[], n = 30) =>
  people.filter((p) => p.status === 'new' && p.looked_up_at && isActive(p)).sort((a, b) => b.score - a.score).slice(0, n);

export function funnel(people: Person[]): Record<'new' | 'invited' | 'joined' | 'declined', number> {
  const count = { new: 0, invited: 0, joined: 0, declined: 0 };
  for (const p of people) if (p.status in count) count[p.status as keyof typeof count] += 1;
  return count;
}

export const invitedToday = (people: Person[]) => {
  const today = new Date().toISOString().slice(0, 10);
  return people.filter((p) => p.invited_at.slice(0, 10) === today).length;
};

function opening(why: string[]): string {
  const reasons = why.join(' ');
  if (reasons.includes('starred myGeeKy')) return 'Thank you for starring myGeeKy on GitHub!';
  if (reasons.includes('forked myGeeKy')) return 'I saw you forked myGeeKy on GitHub, thank you!';
  const m = reasons.match(/builds (\S+) \(published\)/);
  if (m) return `I came across ${m[1]} on GitHub, the tool behind your published paper.`;
  if (reasons.includes('works in your field')) return "I came across your work on GitHub, and it's close to my own field.";
  return 'I came across your work on GitHub.';
}

/** A short, personal invite, word for word the desktop's (and a mailto: when they list an email). */
export function invite(p: Person, me: string): { subject: string; body: string; mailto?: string } {
  const first = (p.name || p.login).split(/\s+/)[0] ?? '';
  const subject = 'A tool for researchers to find each other: would you try it?';
  const body = `Hi ${first},\n\n${opening(p.why)}\n\n`
    + "I built myGeeKy because of a problem I kept running into. I'm not on Facebook or LinkedIn (I find "
    + 'them distracting), but I still want to connect with people in research: people I can learn from, '
    + 'and who might learn something from me. So I made a tool for researchers in data science and '
    + 'computer science. It looks at your GitHub, your CV and your papers, groups the people and projects '
    + "in your field, and shows you who's worth following, what's rising and what's new, in one small "
    + 'panel on your screen. It only suggests: it never posts or follows anyone for you.\n\n'
    + 'Would you be willing to install it and give it a try? https://mygeeky.org (a Windows installer, '
    + "one line on Linux, or pip install mygeeky). Any feedback would mean a lot, and there's a 💡 button "
    + `in the app for ideas.\n\nBest,\nAlsamman\n(github.com/${me})`;
  const out: { subject: string; body: string; mailto?: string } = { subject, body };
  if (p.email) out.mailto = `mailto:${p.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return out;
}

export const IDEA_KINDS: Record<string, string> = { idea: '💡', problem: '🐞', question: '❓', keyword: '🔤', report: '🚩', protocol: '🧭' };

// ---- what you do here: one line each in admin_actions.jsonl (adminlog.py applies it on your computers)
const ACTIONS = 'admin_actions.jsonl';
const APPLIED = 'admin_actions_applied.jsonl';
const QUEUE_KEY = 'mygeeky.admin.queue';
export type Action = { id: string; at: string; kind: 'prospect' | 'listing'; status: string; login?: string;
  id_listing?: string; item?: Record<string, unknown> };

const lines = (text: string | null) => (text ?? '').split('\n').flatMap((l) => {
  try { const v = JSON.parse(l); return v && typeof v === 'object' ? [v] : []; } catch { return []; }
});

/** Everything asked for and not yet applied by a computer: in the repo, or still on this phone. */
export async function pendingActions(): Promise<Action[]> {
  const [sent, applied, queued] = await Promise.all([readRepoFile(ACTIONS), readRepoFile(APPLIED), AsyncStorage.getItem(QUEUE_KEY)]);
  const done = new Set(lines(applied).map((r: any) => r.id));
  let local: Action[] = [];
  try { const q = JSON.parse(queued ?? '[]'); if (Array.isArray(q)) local = q; } catch { /* none */ }
  const all = [...lines(sent), ...local].filter((a: any) => typeof a?.id === 'string' && !done.has(a.id)) as Action[];
  const seen = new Set<string>();
  return all.filter((a) => !seen.has(a.id) && !!seen.add(a.id)).sort((x, y) => (x.at < y.at ? -1 : 1));
}

/** Record one action and send it at once (it stays queued on the phone if the network fails). */
export async function act(a: Omit<Action, 'id' | 'at'>): Promise<void> {
  if (!(await adminLogin())) throw new Error('Admin only.');
  const action: Action = { ...a, id: `phone-${Crypto.randomUUID().replace(/-/g, '').slice(0, 20)}`,
    at: `${new Date().toISOString().slice(0, 19)}+00:00` };
  const q = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) ?? '[]');
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify([...(Array.isArray(q) ? q : []), action]));
  const link = await modelLink();
  if (link) await flushQueue(link.repo, link.token, ACTIONS, QUEUE_KEY, 'admin action');
}

/** People as they will be once your computers apply what you did here. */
export function withPending(people: Person[], pending: Action[]): Person[] {
  const by = new Map(people.map((p) => [p.login.toLowerCase(), { ...p }]));
  for (const a of pending) {
    const p = a.kind === 'prospect' && a.login ? by.get(a.login.toLowerCase()) : undefined;
    if (!p) continue;
    p.status = a.status;
    p.invited_at = a.status === 'invited' ? a.at : a.status === 'new' ? '' : p.invited_at;
  }
  return [...by.values()];
}

// ---- 🎯 listings to review (scout.json, written by the scout on your computer)
export type Candidate = { id: string; kind: 'jobs' | 'funding' | 'conferences'; status: string; score: number;
  checks: [boolean, string][]; source: string; quote: string; edited: boolean; item: Record<string, any>; daysLeft: number | null };

const daysLeft = (deadline: unknown): number | null => {
  if (typeof deadline !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(deadline)) return null;
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((Date.parse(`${deadline}T00:00:00Z`) - today) / 86400000);
};

export async function loadListings(pending: Action[]): Promise<{ toReview: Candidate[]; accepted: Candidate[] } | null> {
  const text = await readRepoFile('scout.json');
  if (!text) return null;
  let d: any = {};
  try { d = JSON.parse(text) ?? {}; } catch { return null; }
  const all: Candidate[] = Object.entries(d.candidates && typeof d.candidates === 'object' ? d.candidates : {}).slice(0, 3000)
    .filter(([, c]: [string, any]) => c && typeof c.item === 'object' && ['jobs', 'funding', 'conferences'].includes(c.kind))
    .map(([id, c]: [string, any]) => ({
      id: id.slice(0, 120), kind: c.kind, status: str(c.status, 20), score: typeof c.score === 'number' ? c.score : 0,
      checks: (Array.isArray(c.checks) ? c.checks : []).filter((x: any) => Array.isArray(x)).map((x: any) => [!!x[0], str(x[1], 80)] as [boolean, string]).slice(0, 12),
      source: str(c.source, 200), quote: str(c.quote, 400), edited: !!c.edited, item: c.item, daysLeft: daysLeft(c.item?.deadline),
    }));
  for (const a of pending) {                   // what you did here, before your computer applies it
    const c = a.kind === 'listing' ? all.find((x) => x.id === a.id_listing) : undefined;
    if (c) { c.status = a.status; if (a.item) c.item = { ...c.item, ...a.item }; }
  }
  const live = (c: Candidate) => c.daysLeft === null || c.daysLeft >= 0;
  const best = (x: Candidate, y: Candidate) => y.score - x.score || (x.daysLeft ?? 9999) - (y.daysLeft ?? 9999);
  return { toReview: all.filter((c) => c.status === 'new' && live(c)).sort(best).slice(0, 40),
    accepted: all.filter((c) => c.status === 'accepted' && live(c)).sort(best) };
}

export const deadlineText = (days: number | null) => days === null ? '' : days <= 0 ? 'closes today'
  : days === 1 ? 'closes tomorrow' : days <= 60 ? `closes in ${days} days` : `closes in ${Math.floor(days / 30)} months`;

/** The fields the desktop's "Edit, then accept" offers, by kind. */
export const EDIT_FIELDS: Record<Candidate['kind'], string[]> = {
  jobs: ['title', 'org', 'place', 'deadline', 'type', 'url', 'summary', 'keywords'],
  funding: ['title', 'org', 'place', 'deadline', 'who', 'amount', 'url', 'summary', 'keywords'],
  conferences: ['title', 'org', 'place', 'deadline', 'starts', 'ends', 'student', 'url', 'summary', 'keywords'],
};

// ---- 📝 quizzes: how many each reviewed protocol has (app.quizwriter_state), and batches waiting for you
export const QUIZ_READY = 10;
export const QUIZ_GOOD = 20;
export type QuizRow = { id: string; title: string; count: number; spotCheck: boolean };

export async function quizStatus(lists: Lists | null): Promise<{ rows: QuizRow[]; bank: number; withQuiz: number } | null> {
  if (!lists) return null;
  const [b, writerText] = await Promise.all([bank(), readRepoFile('quizwriter.json')]);
  let batches: Record<string, any> = {};
  try { const w = JSON.parse(writerText ?? '{}'); if (w?.batches && typeof w.batches === 'object') batches = w.batches; } catch { /* none */ }
  const per: Record<string, number> = {};
  for (const q of b.questions) per[q.protocol] = (per[q.protocol] ?? 0) + 1;
  const rows = lists.protocols.map((p) => {
    const batch = batches[p.id];
    return { id: p.id, title: p.title || p.id, count: per[p.id] ?? 0,
      spotCheck: !!batch && Array.isArray(batch.questions) && batch.questions.length > 0 && !batch.verdict };
  });
  return { rows, bank: b.questions.length, withQuiz: rows.filter((r) => r.count >= QUIZ_READY).length };
}
