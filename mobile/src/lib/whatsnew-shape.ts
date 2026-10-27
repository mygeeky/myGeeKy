// 📰 What's new, on the phone -- a port of the desktop's whatsnew_shape.py: the AI and technology news the maker
// accepted from TRACE, published in curated.json's "whatsnew" list. Everything is checked again here as untrusted:
// text plain and capped, links https with nothing hidden before the host, nothing older than KEEP_DAYS, at most KEEP,
// newest first. tests/test_whatsnew.py checks both apps give the same answers.
export const KEEP = 40;
export const KEEP_DAYS = 30;

export type WhatsNew = { id: string; title: string; summary: string; why: string; url: string; sources: string[];
  topic: string; keywords: string[]; added: string };

const ID_RE = /^tr-[a-f0-9]{8,32}$/;
const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const text = (v: unknown, n: number) => (typeof v === 'string' || typeof v === 'number' ? String(v).split(/\s+/).join(' ').trim().slice(0, n) : '');
function https(v: unknown): string {
  const u = String(v ?? '').trim();
  return /^https:\/\/[^\s/?#@\\]+\.[^\s/?#@\\]+([/?#][^\s\\]*)?$/.test(u) && !/[\u0000-\u001f]/.test(u) ? u.slice(0, 500) : '';
}
const words = (v: unknown, n = 12) => Array.isArray(v)
  ? [...new Set(v.map((x) => text(x, 40).toLowerCase()).filter(Boolean))].slice(0, n) : [];
const isoDay = (d: Date) => d.toISOString().slice(0, 10);

export function clean(raw: any, today: Date = new Date()): WhatsNew | null {
  if (!raw || typeof raw !== 'object' || !ID_RE.test(String(raw.id ?? ''))) return null;
  const added = String(raw.added ?? '').slice(0, 10);
  if (!DAY_RE.test(added) || Number.isNaN(Date.parse(`${added}T00:00:00Z`))) return null;
  const oldest = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()) - KEEP_DAYS * 86400000);
  if (added < isoDay(oldest)) return null;
  const title = text(raw.title, 140), url = https(raw.url);
  if (!title || !url) return null;
  const sources = (Array.isArray(raw.sources) ? raw.sources.slice(0, 8) : []).filter((s: unknown) => typeof s === 'string')
    .map(https).filter(Boolean);
  return { id: raw.id, title, summary: text(raw.summary, 400), why: text(raw.why, 200), url,
    sources: [...new Set([url, ...sources])].slice(0, 8), topic: text(raw.topic, 40).toLowerCase(),
    keywords: words(raw.keywords), added };
}

export function cleanAll(raw: unknown, today: Date = new Date()): WhatsNew[] {
  const seen = new Set<string>();
  const out: WhatsNew[] = [];
  for (const r of (Array.isArray(raw) ? raw : []).slice(0, 200)) {
    const it = clean(r, today);
    if (it && !seen.has(it.id)) {
      seen.add(it.id);
      out.push(it);
    }
  }
  out.sort((a, b) => (a.added === b.added ? (a.id < b.id ? 1 : -1) : a.added < b.added ? 1 : -1));
  return out.slice(0, KEEP);
}

/** whatsnew_shape.ranked: newest first, nudged by how well each fits your field (a match counts like two days newer). */
export function ranked(items: WhatsNew[], weights: Record<string, number>, today: Date = new Date()): WhatsNew[] {
  const t0 = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const score = (it: WhatsNew) => {
    const age = Math.round((t0 - Date.parse(`${it.added}T00:00:00Z`)) / 86400000);
    const hay = [it.title, it.summary, it.topic, it.keywords.join(' ')].join(' ').toLowerCase();
    const fit = Object.entries(weights).reduce((s, [k, w]) => (k && hay.includes(k.toLowerCase()) ? s + w : s), 0);
    return -age + 2 * Math.min(1, fit);
  };
  return items.map((it, i) => ({ it, i, s: score(it) })).sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.it);
}
