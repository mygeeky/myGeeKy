// The shape of a protocol, checked -- the same rules as the desktop's protocols.py
// (clean_protocol). Protocols come from the maker's curated file, from GitHub and
// OpenAlex, or from the person editing one: all someone's text, so every field is
// capped and only https links survive. Kept apart so curated.ts can use it too.

import { blockedSource, isBench } from './safety';

export const ROLES = ['basics', 'deeper', 'applied', 'project', 'use'] as const;
export type Role = (typeof ROLES)[number];
export const ITEM_KINDS: Record<string, string> = { repo: '📦', article: '📄', website: '🌐', course: '🎓', book: '📖',
  tutorial: '🧭', video: '🎬', guide: '📘' };
export const MAX_STAGES = 10;
export const MAX_ITEMS = 8;

export type Link = { title: string; url: string; kind: string; note: string; stars?: number; cited?: number; year?: number;
  lang?: string; updated?: string; venue?: string };
export type Quiz = { q: string; options: string[]; answer: number };
export type Stage = { id: string; title: string; role: Role; query: string; skills: string[]; can: string[]; quiz: Quiz[];
  items: Link[] };
export type Protocol = { id: string; skill: string; goal: string; title: string; summary: string; stages: Stage[];
  reviewed: boolean; source: 'reviewed' | 'auto' | 'mine'; by: string; based_on: string };

const ID_RE = /^[a-z0-9][a-z0-9-]{2,79}$/;
const SID_RE = /^[a-z0-9][a-z0-9-]{0,39}$/;
export const text = (v: unknown, n: number) =>
  typeof v === 'string' || typeof v === 'number' ? String(v).split(/\s+/).join(' ').trim().slice(0, n) : '';
export function https(v: unknown): string {
  const u = String(v ?? '').trim();
  return /^https:\/\/[^\s/]+\.[^\s]*$/.test(u) && !u.includes(' ') ? u.slice(0, 500) : '';
}
const words = (v: unknown, n = 12) => Array.isArray(v)
  ? [...new Set(v.map((x) => text(x, 40).toLowerCase()).filter(Boolean))].slice(0, n) : [];

export function slug(t: string, n = 60): string {
  const s = (t || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, n).replace(/-+$/g, '');
  return s.length >= 3 ? s : `${s}-protocol`.slice(0, n);
}

export function cleanLink(raw: any): Link | null {
  if (!raw || typeof raw !== 'object') return null;
  const url = https(raw.url);
  const title = text(raw.title, 160);
  if (!url || !title) return null;
  // the one door every link comes through: a bench protocol's home never gets in (safety.ts)
  if (blockedSource(url) || isBench(`${title} ${text(raw.note, 200)}`)) return null;
  const kind = String(raw.kind ?? 'website').toLowerCase();
  const out: Link = { title, url, kind: kind in ITEM_KINDS ? kind : 'website', note: text(raw.note, 200) };
  for (const k of ['stars', 'cited', 'year'] as const) {      // facts shown on the link's card (optional)
    const n = Math.trunc(Number(raw[k] ?? 0));
    if (n > 0 && n < 10_000_000) out[k] = n;
  }
  const lang = text(raw.lang, 40);
  const updated = text(raw.updated, 10);
  const venue = text(raw.venue, 80);
  if (lang) out.lang = lang;
  if (updated) out.updated = updated;
  if (venue) out.venue = venue;                              // the journal a 🧪 lab protocol came from
  return out;
}

function cleanQuiz(raw: unknown): Quiz[] {
  if (!Array.isArray(raw)) return [];
  const out: Quiz[] = [];
  for (const q of raw) {
    if (!q || typeof q !== 'object') continue;
    const options = (Array.isArray(q.options) ? q.options : []).map((o: unknown) => text(o, 140)).filter(Boolean).slice(0, 5);
    const answer = Number.isInteger(q.answer) ? q.answer : Number.parseInt(String(q.answer), 10);
    const t = text(q.q, 220);
    if (t && options.length >= 2 && answer >= 0 && answer < options.length) out.push({ q: t, options, answer });
  }
  return out.slice(0, 8);
}

export function cleanStage(raw: any, i = 0): Stage | null {
  if (!raw || typeof raw !== 'object') return null;
  const title = text(raw.title, 80);
  if (!title) return null;
  const sid = String(raw.id ?? '').toLowerCase();
  const role = String(raw.role ?? 'applied').toLowerCase();
  const seen = new Set<string>();
  const items: Link[] = [];
  for (const it of (Array.isArray(raw.items) ? raw.items : []).slice(0, MAX_ITEMS)) {
    const c = cleanLink(it);
    if (c && !seen.has(c.url)) {
      seen.add(c.url);
      items.push(c);
    }
  }
  return { id: SID_RE.test(sid) ? sid : `s${i + 1}`, title, role: (ROLES as readonly string[]).includes(role) ? role as Role : 'applied',
    query: text(raw.query, 60), skills: words(raw.skills, 6),
    can: (Array.isArray(raw.can) ? raw.can : []).map((c: unknown) => text(c, 160)).filter(Boolean).slice(0, 6),
    quiz: cleanQuiz(raw.quiz), items };
}

/** A checked protocol, or null. `reviewed` is only ever set by the caller, never by the file. */
export function cleanProtocol(raw: any, reviewed = false): Protocol | null {
  // a protocol about laboratory work is refused wherever it came from: the curated file, one a user
  // published, or one built here (safety.ts)
  if (raw && typeof raw === 'object'
      && isBench(`${text(raw.skill, 60)} ${text(raw.title, 100)} ${text(raw.goal, 60)} ${text(raw.summary, 300)}`)) {
    return null;
  }
  if (!raw || typeof raw !== 'object') return null;
  const skill = text(raw.skill, 60);
  const title = text(raw.title, 100);
  if (!skill || !title) return null;
  const stages: Stage[] = [];
  const seen = new Set<string>();
  (Array.isArray(raw.stages) ? raw.stages : []).slice(0, MAX_STAGES).forEach((s: any, i: number) => {
    const st = cleanStage(s, i);
    if (!st) return;
    while (seen.has(st.id)) st.id = `${st.id}-${seen.size + 1}`.slice(0, 40);
    seen.add(st.id);
    stages.push(st);
  });
  if (!stages.length) return null;
  const pid = String(raw.id ?? '').toLowerCase();
  const source = String(raw.source ?? '').toLowerCase();
  return { id: ID_RE.test(pid) ? pid : slug(title), skill, goal: text(raw.goal, 60), title, summary: text(raw.summary, 300),
    stages, reviewed, source: reviewed ? 'reviewed' : source === 'auto' ? 'auto' : 'mine', by: text(raw.by, 40),
    based_on: text(raw.based_on, 80) };
}
