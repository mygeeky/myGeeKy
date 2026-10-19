// Careful notifications: a port of the desktop's notify.py (tests/test_notify.py runs both on the same inputs).
// Everything is off until you turn a kind on. When one is on, only what's really worth telling counts -- a Season
// open or opening within SEASON_DAYS, a job, funding call or conference fitting you very well, one of the papers
// rising fastest in your field and just out, a new Highlight -- each told once, all in ONE short line, at most
// once a day (or a week), never in your quiet hours. Nothing is sent anywhere: the phone notifies itself.

export type Settings = { kinds: string[]; every: 'daily' | 'weekly'; quiet: [number, number] };
export type Candidate = { id: string; kind: string; title: string; days: number | null };
export type Summary = { title: string; body: string; tab: string; kind: string };

// id, emoji, what the switch says, a few words under it, the short name in "On: ..."
export const KINDS: [string, string, string, string, string][] = [
  ['seasons', '🗓', 'A Season opening', 'Scholarships and calls that come back every year', 'Seasons'],
  ['jobs', '💼', 'A job that fits you very well', 'PhD places, postdocs and research jobs', 'jobs'],
  ['funding', '💶', 'Funding that fits you very well', 'Grants, fellowships and travel money', 'funding'],
  ['conferences', '🎤', 'A conference that fits you very well', 'Meetings, workshops and summer schools', 'conferences'],
  ['papers', '📄', 'An important new paper in your field', 'One of the papers rising fastest, just out', 'papers'],
  ['highlights', '✨', 'A new Highlight', 'A research article retold in plain words', 'Highlights'],
];
const ORDER = KINDS.map((k) => k[0]);
export const TAB: Record<string, string> = { seasons: 'chances', jobs: 'chances', funding: 'chances', conferences: 'chances',
  papers: 'papers', highlights: 'grow' };
const EVERY: Record<string, number> = { daily: 1, weekly: 7 };
export const FIT_MIN = 0.7;
export const SEASON_DAYS = 21;
const NEW_DAYS = { papers: 45, highlights: 14 };
const TOP_PAPERS = 3;
const MAX_TOLD = 600;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

export const defaults = (): Settings => ({ kinds: [], every: 'daily', quiet: [22, 8] });

export function cleanSettings(raw: any): Settings {
  const r = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
  const kinds: unknown[] = Array.isArray(r.kinds) ? r.kinds : [];
  const q = Array.isArray(r.quiet) && r.quiet.length === 2 ? r.quiet : [22, 8];
  const hour = (h: unknown, d: number) => (typeof h === 'number' && Number.isInteger(h) && h >= 0 && h <= 23 ? h : d);
  return { kinds: ORDER.filter((k) => kinds.includes(k)), every: r.every === 'weekly' ? 'weekly' : 'daily',
    quiet: [hour(q[0], 22), hour(q[1], 8)] };
}

export function inQuiet(s: Settings, hour: number): boolean {
  const [start, end] = s.quiet;
  if (start === end) return false;
  return start < end ? start <= hour && hour < end : hour >= start || hour < end;
}

function dayNumber(d: string): number | null {
  const s = String(d ?? '').slice(0, 10);
  if (!DAY.test(s)) return null;
  const t = Date.UTC(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10)));
  const back = new Date(t).toISOString().slice(0, 10);
  return back === s ? t / 86400000 : null;
}

export function due(s: Settings, lastSent: string, now: string, hour: number): boolean {
  if (!s.kinds.length || inQuiet(s, hour)) return false;
  if (!lastSent) return true;
  const a = dayNumber(now), b = dayNumber(lastSent);
  if (a === null || b === null) return true;
  return a - b >= EVERY[s.every];
}

const age = (today: string, d: unknown): number | null => {
  const a = dayNumber(today), b = dayNumber(String(d ?? ''));
  return a === null || b === null ? null : a - b;
};

export function candidates(today: string, seasons: any[] = [], ranked: Record<string, any[]> = {}, papers: any[] = [],
  highlights: any[] = []): Candidate[] {
  const out: Candidate[] = [];
  for (const s of seasons) {
    const w = s?.when ?? {};
    let days: number;
    if (w.state === 'open') {
      if (!w.confirmed) continue;                  // "expected to be open" is a guess, not news
      days = 0;
    } else if (Number.isInteger(w.days_to_open) && w.days_to_open >= 0 && w.days_to_open <= SEASON_DAYS) days = w.days_to_open;
    else continue;
    out.push({ id: `season:${s.id ?? ''}:${w.opens ?? ''}`, kind: 'seasons', title: String(s.title ?? ''), days });
  }
  for (const kind of ['jobs', 'funding', 'conferences']) {
    for (const it of ranked[kind] ?? []) {
      if (typeof it?.score === 'number' && it.score >= FIT_MIN) {
        out.push({ id: `${kind}:${it.id ?? ''}`, kind, title: String(it.title ?? ''),
          days: Number.isInteger(it.days_left) ? it.days_left : null });
      }
    }
  }
  for (const p of papers.slice(0, TOP_PAPERS)) {
    const a = age(today, p?.date);
    if (a !== null && a >= 0 && a <= NEW_DAYS.papers) out.push({ id: `paper:${p.id ?? ''}`, kind: 'papers', title: String(p.title ?? ''), days: null });
  }
  for (const h of highlights) {
    const a = age(today, h?.added);
    if (a !== null && a >= 0 && a <= NEW_DAYS.highlights) {
      out.push({ id: `highlight:${h.id ?? ''}`, kind: 'highlights', title: String(h.title ?? ''), days: null });
    }
  }
  return out;
}

export function pick(cands: Candidate[], told: string[], s: Settings): Candidate[] {
  const seen = new Set(told);
  return cands.filter((c) => s.kinds.includes(c.kind) && !seen.has(c.id)).sort((a, b) =>
    Number(a.days === null) - Number(b.days === null) || (a.days ?? 0) - (b.days ?? 0)
    || ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind) || (a.title < b.title ? -1 : a.title > b.title ? 1 : 0));
}

const n = (k: number, one: string, many: string) => `${k} ${k === 1 ? one : many}`;

export function summary(chosen: Candidate[]): Summary | null {
  if (!chosen.length) return null;
  const groups = new Map<string, Candidate[]>();
  for (const c of chosen) groups.set(c.kind, [...(groups.get(c.kind) ?? []), c]);
  const pieces: string[] = [];
  for (const [kind, items] of groups) {
    const k = items.length;
    if (kind === 'seasons') {
      if (k === 1) {
        let t = items[0].title;
        t = t.length <= 40 ? t : `${t.slice(0, 39)}…`;
        pieces.push(`🗓 ${t} ${items[0].days === 0 ? 'is open now' : `opens in ${items[0].days} days`}`);
      } else pieces.push(`🗓 ${k} Seasons open soon`);
    } else if (kind === 'jobs') pieces.push(`💼 ${n(k, 'job fits', 'jobs fit')} you`);
    else if (kind === 'funding') pieces.push(`💶 ${n(k, 'funding call fits', 'funding calls fit')} you`);
    else if (kind === 'conferences') pieces.push(`🎤 ${n(k, 'conference fits', 'conferences fit')} you`);
    else if (kind === 'papers') pieces.push(`📄 ${n(k, 'new paper', 'new papers')} rising in your field`);
    else pieces.push(`✨ ${n(k, 'new Highlight', 'new Highlights')}`);
  }
  const body = pieces.slice(0, 3).join(' · ') + (pieces.length > 3 ? ' · and more' : '');
  return { title: 'myGeeKy', body, tab: TAB[chosen[0].kind], kind: chosen[0].kind };
}

export function remember(told: string[], chosen: Candidate[]): string[] {
  const out = [...told];
  for (const c of chosen) if (!out.includes(c.id)) out.push(c.id);
  return out.slice(-MAX_TOLD);
}

export function describe(s: Settings): string {
  if (!s.kinds.length) return 'All off: myGeeKy never notifies you.';
  const names = KINDS.filter((k) => s.kinds.includes(k[0])).map((k) => k[4]);
  const listed = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
  const often = s.every === 'daily' ? 'at most once a day' : 'at most once a week';
  const [start, end] = s.quiet;
  const quiet = start !== end ? ` · quiet ${String(start).padStart(2, '0')}:00-${String(end).padStart(2, '0')}:00` : '';
  return `On: ${listed}, ${often}${quiet}.`;
}
