// Quizzes: a protocol's questions, how they're drawn and marked, and how a score is shown --
// a port of the desktop's quiz.py, so the phone and the computer give the same numbers.
//
// The bank ships with the app (data/questions.json) and is refreshed from the repo like the
// curated lists. Each question belongs to one protocol and one of its steps, and carries the
// source that proves its answer with the sentence quoted from it.
//
// Each attempt is 10 questions in a fixed mix: 50% easy, 35% medium, 15% tricky (a real
// pitfall, never confusing wording). Only your best score per protocol counts, one attempt a
// day. Everything stays on the phone unless you choose to share a score.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { sha256 } from '@noble/hashes/sha2.js';
import { bytesToHex } from '@noble/hashes/utils.js';
import { fetchT } from './net';
import { https, text } from './protocol-shape';
import type { Protocol } from './protocol-shape';
import { type Resource, resourceOf } from './protocols';

const KEY = 'mygeeky.quiz';
export const REMOTE_URL = 'https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/questions.json';
export const CHECK_EVERY_HOURS = 12;
export const LEVELS = ['easy', 'medium', 'tricky'] as const;
export type Level = (typeof LEVELS)[number];
export const MIX: Record<Level, number> = { easy: 0.5, medium: 0.35, tricky: 0.15 };
export const PER_ATTEMPT = 10;
export const OPTIONS = 4;
export const PASS = 0.75;
export const PER_DAY = 1;
export const KEEP_ATTEMPTS = 60;
export const LEVEL_LABEL: Record<Level, string> = { easy: 'Basics', medium: 'Applied', tricky: 'Watch out' };
export const LEVEL_ICON: Record<Level, string> = { easy: '🟢', medium: '🔵', tricky: '🟠' };
export const KINDS: Record<string, [string, string]> = {
  choice: ['🔤', 'Multiple choice'], code: ['💻', 'What does this code do?'],
};
const QID_RE = /^[a-z0-9][a-z0-9.-]{3,79}$/;
export const ANSWER_CHARS = 16;

/** A short fingerprint of one option, tied to its question -- the same one quiz.py computes.
 *  The shipped bank stores the hash of the right answer rather than its position, so the file doesn't
 *  hand the answers to anyone who opens it. It is obfuscation, not security: four options can simply be
 *  hashed and compared, and a question's own reason usually gives it away. See docs/QUIZZES.md. */
export function answerToken(qid: string, option: string): string {
  const text = String(option ?? '').split(/\s+/).join(' ').trim().toLowerCase();
  return bytesToHex(sha256(new TextEncoder().encode(`${qid}\u001f${text}`))).slice(0, ANSWER_CHARS);
}

/** How many questions of each level one attempt holds. They always add up to `n`: the shares are cut by
 *  largest remainder, so 10 questions are 5 easy, 4 medium and 1 tricky (the same as quiz.py's share). */
export function share(n: number = PER_ATTEMPT): Record<Level, number> {
  const floors = Object.fromEntries(LEVELS.map((lv) => [lv, Math.floor(n * MIX[lv])])) as Record<Level, number>;
  let left = n - LEVELS.reduce((a, lv) => a + floors[lv], 0);
  const order = [...LEVELS].sort((a, b) => (n * MIX[b] - floors[b]) - (n * MIX[a] - floors[a])
    || LEVELS.indexOf(a) - LEVELS.indexOf(b));
  for (const lv of order) { if (left <= 0) break; floors[lv] += 1; left -= 1; }
  return floors;
}

export type Source = { title: string; url: string; kind: string; quote: string };
export type Raw = { id: string; protocol: string; stage: string; level: Level; kind: string; q: string; code: string;
  options: string[]; answer: number; why: string; source: Source; checks: string[] };
export type Bank = { version: string; questions: Raw[] };

export function cleanQuestion(raw: any): Raw | null {
  if (!raw || typeof raw !== 'object' || !QID_RE.test(String(raw.id ?? ''))) return null;
  const q = text(raw.q, 400);
  const options: string[] = (Array.isArray(raw.options) ? raw.options : [])
    .map((o: unknown) => text(o, 200)).filter(Boolean).slice(0, OPTIONS);
  const unique = new Set(options.map((o) => o.toLowerCase())).size;
  if (!q || options.length !== OPTIONS || unique !== OPTIONS) return null;
  const answer = raw.answer_hash                       // the shipped form: a hash of the right option
    ? options.findIndex((o) => answerToken(String(raw.id), o) === String(raw.answer_hash).trim().toLowerCase())
    : Math.trunc(Number(raw.answer));
  if (!(answer >= 0 && answer < OPTIONS)) return null;
  const level = String(raw.level ?? 'easy').toLowerCase() as Level;
  const kind = String(raw.kind ?? 'choice').toLowerCase();
  const src = raw.source && typeof raw.source === 'object' ? raw.source : {};
  return { id: raw.id, protocol: text(raw.protocol, 80), stage: text(raw.stage, 40),
    level: (LEVELS as readonly string[]).includes(level) ? level : 'easy',
    kind: kind in KINDS ? kind : 'choice', q, code: raw.code ? String(raw.code).slice(0, 600) : '',
    options, answer, why: text(raw.why, 400),
    source: { title: text(src.title, 160), url: https(src.url), kind: String(src.kind ?? 'website').toLowerCase(),
      quote: text(src.quote, 400) },
    checks: (Array.isArray(raw.checks) ? raw.checks : []).map((c: unknown) => text(c, 60)).filter(Boolean).slice(0, 8) };
}

export function cleanBank(data: any): Bank {
  const out: Bank = { version: text(data?.version, 40), questions: [] };
  const seen = new Set<string>();
  for (const raw of (Array.isArray(data?.questions) ? data.questions : []).slice(0, 20_000)) {
    const q = cleanQuestion(raw);
    if (q && !seen.has(q.id)) {
      seen.add(q.id);
      out.questions.push(q);
    }
  }
  return out;
}

let cached: Bank | null = null;
const CACHE_KEY = 'mygeeky.questions';

/** The newest bank we have: the one shipped, or a newer one fetched since. */
export async function bank(): Promise<Bank> {
  if (cached) return cached;
  refreshIfDue().catch(() => undefined);              // new questions, like the lists (docs/QUIZZES.md); next time
  // loaded the first time it's needed, not at startup: the bundle's data files are parsed into memory when imported
  // (Metro's inline requires are off), and most people never open this (docs/RESOURCES.md, plan 9)
  const shipped = cleanBank(require('../data/questions.json'));
  try {
    const saved = JSON.parse((await AsyncStorage.getItem(CACHE_KEY)) ?? 'null');
    const fetched = cleanBank(saved?.bank);
    cached = fetched.version > shipped.version ? fetched : shipped;
  } catch {
    cached = shipped;
  }
  return cached;
}

/** Fetch the newest bank, at most every CHECK_EVERY_HOURS. True if it changed. */
export async function refreshIfDue(force = false): Promise<boolean> {
  let saved: any = null;
  try {
    saved = JSON.parse((await AsyncStorage.getItem(CACHE_KEY)) ?? 'null');
  } catch {
    saved = null;
  }
  const checked = Date.parse(saved?.checkedAt ?? '');
  if (!force && checked && Date.now() - checked < CHECK_EVERY_HOURS * 3600_000) return false;
  const r = await fetchT(REMOTE_URL);
  if (r.status === 404) {
    await AsyncStorage.setItem(CACHE_KEY, JSON.stringify({ ...(saved ?? {}), checkedAt: new Date().toISOString() }));
    return false;
  }
  if (!r.ok) throw new Error(`questions: ${r.status}`);
  const fresh = cleanBank(await r.json());
  const changed = JSON.stringify(fresh) !== JSON.stringify(cleanBank(saved?.bank));
  await AsyncStorage.setItem(CACHE_KEY, JSON.stringify({ checkedAt: new Date().toISOString(), bank: fresh }));
  cached = null;
  return changed;
}

export async function forProtocol(pid: string, basedOn = ''): Promise<Raw[]> {
  const ids = new Set([pid, basedOn].filter(Boolean));
  return (await bank()).questions.filter((q) => ids.has(q.protocol));
}

export async function counts(pid: string, basedOn = ''): Promise<Record<string, number>> {
  const qs = await forProtocol(pid, basedOn);
  const out: Record<string, number> = { total: qs.length };
  for (const lv of LEVELS) out[lv] = qs.filter((q) => q.level === lv).length;
  return out;
}

// ---- one question, as it's shown
export type Question = { id: string; number: number; of: number; protocol: string; stage: string; stageTitle: string;
  level: Level; levelLabel: string; levelIcon: string; kind: string; kindIcon: string; kindLabel: string; text: string;
  code: string; options: string[]; answer: number; picked: number | null; why: string; source: Source;
  resource: Resource | null; flagged: boolean };

export function questionOf(q: Raw, number: number, of: number, order: number[], stageTitle = '', flagged = false): Question {
  const [kindIcon, kindLabel] = KINDS[q.kind] ?? KINDS.choice;
  return { id: q.id, number, of, protocol: q.protocol, stage: q.stage, stageTitle: stageTitle || q.stage,
    level: q.level, levelLabel: LEVEL_LABEL[q.level], levelIcon: LEVEL_ICON[q.level], kind: q.kind, kindIcon, kindLabel,
    text: q.q, code: q.code, options: order.map((i) => q.options[i]), answer: order.indexOf(q.answer), picked: null,
    why: q.why, source: q.source,
    // the quote is shown above the card in its own right, so the card itself stays plain
    resource: q.source.url
      ? resourceOf({ title: q.source.title || q.source.url, url: q.source.url, kind: q.source.kind, note: '' })
      : null,
    flagged };
}

export const answered = (q: Question) => q.picked != null;
export const right = (q: Question) => q.picked === q.answer;

export type Quiz = { protocol: string; title: string; questions: Question[]; passMark: number };

function shuffle<T>(rows: T[], rnd: () => number): T[] {
  const out = [...rows];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Draw a quiz: `n` questions in the MIX, from this protocol's own bank. `stage`: one step only. */
export async function draw(proto: Protocol, n = PER_ATTEMPT, flags: string[] = [], stage = '',
                           rnd: () => number = Math.random): Promise<Quiz> {
  const flagged = new Set(flags);
  const titles = new Map((proto.stages ?? []).map((st) => [st.id, st.title]));
  const pool = (await forProtocol(proto.id, proto.based_on)).filter(
    (q) => !flagged.has(q.id) && (!stage || q.stage === stage));
  const picked: Raw[] = [];
  for (const lv of LEVELS) {
    const rows = shuffle(pool.filter((q) => q.level === lv), rnd);
    picked.push(...rows.slice(0, Math.round(n * MIX[lv])));
  }
  const taken = new Set(picked.map((q) => q.id));
  picked.push(...shuffle(pool.filter((q) => !taken.has(q.id)), rnd).slice(0, Math.max(0, n - picked.length)));
  const rows = shuffle(picked.slice(0, n), rnd);
  return { protocol: proto.id, title: proto.title || proto.id, passMark: PASS,
    questions: rows.map((q, i) => questionOf(q, i + 1, rows.length,
      shuffle([...Array(q.options.length).keys()], rnd), titles.get(q.stage) ?? '')) };
}

export type Attempt = { protocol: string; title: string; questions: Question[]; right: number; total: number;
  score: number; passed: boolean; best: number; improved: boolean; perfect: boolean;
  byStage: { stage: string; title: string; right: number; total: number }[];
  byLevel: { level: Level; label: string; icon: string; right: number; total: number }[] };

/** Mark an attempt. `answers`: what was picked per question (-1 for none). */
export function mark(quiz: Quiz, answers: number[], bestBefore = 0): Attempt {
  quiz.questions.forEach((q, i) => { q.picked = answers[i] == null || answers[i] < 0 ? null : answers[i]; });
  const correct = quiz.questions.filter(right).length;
  const total = quiz.questions.length;
  const score = total ? correct / total : 0;
  const stages = new Map<string, { stage: string; title: string; right: number; total: number }>();
  for (const q of quiz.questions) {
    const g = stages.get(q.stage) ?? { stage: q.stage, title: q.stageTitle, right: 0, total: 0 };
    g.total += 1;
    if (right(q)) g.right += 1;
    stages.set(q.stage, g);
  }
  const byLevel = LEVELS.map((lv) => {
    const rows = quiz.questions.filter((q) => q.level === lv);
    return { level: lv, label: LEVEL_LABEL[lv], icon: LEVEL_ICON[lv], right: rows.filter(right).length, total: rows.length };
  }).filter((l) => l.total > 0);
  return { protocol: quiz.protocol, title: quiz.title, questions: quiz.questions, right: correct, total,
    score: Math.round(score * 1e4) / 1e4, passed: score >= quiz.passMark,
    best: Math.round(Math.max(score, bestBefore) * 1e4) / 1e4, improved: score > bestBefore,
    perfect: total > 0 && correct === total, byStage: [...stages.values()], byLevel };
}

// ---- your scores (on this phone, nowhere else)
export type Best = { score: number; at: string; title: string; right: number; questions: number };
export type Saved = { best: Record<string, Best>; attempts: { protocol: string; at: string; score: number }[];
  flags: string[]; seen: Record<string, number> };

const EMPTY: Saved = { best: {}, attempts: [], flags: [], seen: {} };

export async function load(): Promise<Saved> {
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? 'null');
    if (!raw || typeof raw !== 'object') return { ...EMPTY };
    return { best: raw.best ?? {}, attempts: Array.isArray(raw.attempts) ? raw.attempts : [],
      flags: Array.isArray(raw.flags) ? raw.flags : [], seen: raw.seen ?? {} };
  } catch {
    return { ...EMPTY };
  }
}

const save = (s: Saved) => AsyncStorage.setItem(KEY, JSON.stringify(s));
const todayStr = () => new Date().toISOString().slice(0, 10);

export async function attemptsToday(pid: string): Promise<number> {
  const s = await load();
  return s.attempts.filter((a) => a.protocol === pid && String(a.at).slice(0, 10) === todayStr()).length;
}

export async function canTry(pid: string): Promise<{ ok: boolean; why: string }> {
  const n = await attemptsToday(pid);
  return n < PER_DAY ? { ok: true, why: '' }
    : { ok: false, why: "You've already taken this quiz today. Your best score counts, so try again tomorrow." };
}

/** Keep an attempt: the best score per protocol, and the attempt itself (for the daily limit). */
export async function record(attempt: Attempt): Promise<Best> {
  const s = await load();
  const row = s.best[attempt.protocol];
  if (!row || attempt.score >= row.score) {
    s.best[attempt.protocol] = { score: attempt.score, at: todayStr(), title: attempt.title,
      right: attempt.right, questions: attempt.total };
  }
  s.attempts = [...s.attempts, { protocol: attempt.protocol, at: todayStr(), score: attempt.score }].slice(-KEEP_ATTEMPTS);
  for (const q of attempt.questions) s.seen[q.id] = (s.seen[q.id] ?? 0) + 1;
  await save(s);
  return s.best[attempt.protocol];
}

/** 🚩 this question looks wrong (or take the flag back). It's left out of your next attempts. */
export async function flag(qid: string, on = true): Promise<boolean> {
  const s = await load();
  const have = new Set(s.flags);
  if (on) have.add(qid); else have.delete(qid);
  s.flags = [...have].sort().slice(0, 500);
  await save(s);
  return have.has(qid);
}

export const IDEAS_REPO = 'mygeeky/myGeeKy-ideas';

/** A prefilled issue telling the maker a question is wrong (you press Submit, your own account). */
export function reportUrl(q: Question, reason = ''): string {
  const body = `This quiz question looks wrong.\n\n- question: \`${q.id}\`\n- protocol: \`${q.protocol}\`\n`
    + `- step: ${q.stageTitle}\n\n> ${q.text}\n\nAnswers shown: ${q.options.join('; ')}\n\nWhat's wrong: ${reason}\n`;
  return `https://github.com/${IDEAS_REPO}/issues/new?${new URLSearchParams({
    title: `🚩 Quiz question looks wrong: ${q.text.slice(0, 70)}`, body, labels: 'report' }).toString()}`;
}

