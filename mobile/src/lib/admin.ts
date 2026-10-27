// The maker's admin part, on the phone (src/mygeeky/admin.py): a read-only glance -- downloads, stars, people on
// Signals and how much waits on the computer (components/admin-part.tsx). Everything you act on is on the computer.
//
// What keeps it the maker's:
//   * it shows only when GitHub says the phone's data-repo token belongs to an ADMINS account that owns
//     that repo (verifiedOwner) -- a username typed into the app proves nothing;
//   * everything in it comes from admin_prospects.json in that PRIVATE repo, so a modified copy of this
//     open-source app that shows the part anyway still has nothing to show;
//   * the phone shows numbers only and writes nothing: finding listings, reviewing them, inviting people, writing
//     quizzes and their DeepSeek key stay on the computer.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { bank } from './quiz';
import type { Lists } from './curated';
import { readRepoFile, verifiedOwner } from './model-repo';

export const ADMINS = new Set(['alsammanalsamman']);
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
      name: str(p.name, 120), bio: str(p.bio, 300), email: /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,}$/.test(str(p.email)) ? p.email : '',
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
/** How many people are at each step of an invite (the numbers on the phone's glance). */
export function funnel(people: Person[]): Record<'new' | 'invited' | 'joined' | 'declined', number> {
  const count = { new: 0, invited: 0, joined: 0, declined: 0 };
  for (const p of people) if (p.status in count) count[p.status as keyof typeof count] += 1;
  return count;
}

// ---- what earlier versions sent from the phone (admin_actions.jsonl), not yet applied by a computer: counted as done
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

// ---- 📝 quizzes: how many each reviewed protocol has (app.quizwriter_state), and batches waiting for you
export const QUIZ_READY = 10;
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
