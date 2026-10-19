// What a Highlight is, and how one is read safely from the curated lists: a research article retold as a short
// science news article (a headline, a standfirst and a few paragraphs, one idea each). A port of the desktop's
// highlight_shape.py (tests/test_highlights.py runs both on the same entries); the maker writes them in the
// desktop's admin tab with the article skill, and here they are only checked, trimmed and read in a language.

export const KINDS = ['article'] as const;
const COVERAGE = ['full', 'abstract'];
export const KEEP = 60;
const PARAGRAPHS = 9;
const PARAGRAPH_MAX = 900;
export const MIN_PARAGRAPHS = 3;
const ID = /^[a-z0-9][a-z0-9-]{2,79}$/;
const DOI = /^10\.\d{4,9}\/\S{1,200}$/;
const CODE = /^[a-z]{2}(-[a-z]{2})?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export type Story = { name: string; rtl: boolean; title: string; hook: string; body: string[] };
export type Highlight = {
  id: string; kind: string; title: string; hook: string; url: string; added: string; coverage: string;
  body: string[]; doi: string;
  meta: { journal: string; published: string; lead: string; authors: string[]; institutions: string[]; countries: string[]; open_access: boolean };
  tools: string[]; skills: string[]; keywords: string[]; translations?: Record<string, Story>;
};

export const LABELS: Record<string, Record<string, string>> = {
  en: { read: 'Read the article', full: 'From the full article', abstract: 'From the abstract only', learn: 'Learn these tools' },
  ar: { read: 'اقرأ المقال', full: 'من المقال كاملًا', abstract: 'من الملخص فقط', learn: 'تعلّم هذه الأدوات' },
  fr: { read: "Lire l'article", full: "D'après l'article complet", abstract: "D'après le résumé seulement", learn: 'Apprendre ces outils' },
  de: { read: 'Den Artikel lesen', full: 'Aus dem ganzen Artikel', abstract: 'Nur aus der Zusammenfassung', learn: 'Diese Werkzeuge lernen' },
  es: { read: 'Leer el artículo', full: 'Del artículo completo', abstract: 'Solo del resumen', learn: 'Aprender estas herramientas' },
  zh: { read: '阅读文章', full: '根据全文', abstract: '仅根据摘要', learn: '学习这些工具' },
};
const NAMES: Record<string, [string, boolean]> = { ar: ['العربية', true], fr: ['Français', false], de: ['Deutsch', false],
  es: ['Español', false], zh: ['中文', false] };

const text = (v: unknown, n: number) => (typeof v === 'string' || typeof v === 'number'
  ? String(v).split(/\s+/).filter(Boolean).join(' ').slice(0, n) : '');
function https(v: unknown): string {
  const url = String(v ?? '').trim();
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && u.host && !url.includes(' ') ? url.slice(0, 500) : '';
  } catch {
    return '';
  }
}
function day(v: unknown): string {
  const s = String(v ?? '').slice(0, 10);
  if (!DATE.test(s)) return '';
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s ? s : '';
}
function names(values: unknown, n: number, size: number): string[] {
  const out: string[] = [];
  for (const v of Array.isArray(values) ? values : []) {
    const t = text(v, size);
    if (t && !out.some((o) => o.toLowerCase() === t.toLowerCase())) out.push(t);
  }
  return out.slice(0, n);
}
const words = (values: unknown, n: number) => names(values, n, 40).map((w) => w.toLowerCase());
/** The article's paragraphs: text only, empty ones dropped, at most PARAGRAPHS. */
const body = (raw: unknown): string[] =>
  (Array.isArray(raw) ? raw.slice(0, PARAGRAPHS * 2) : []).map((p) => text(p, PARAGRAPH_MAX)).filter(Boolean).slice(0, PARAGRAPHS);

export function cleanTranslations(raw: unknown): Record<string, Story> {
  const out: Record<string, Story> = {};
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return out;
  for (const [c, val] of Object.entries(raw).slice(0, 20)) {
    const code = c.trim().toLowerCase();
    if (!CODE.test(code) || !val || typeof val !== 'object') continue;
    const v = val as Record<string, unknown>, known = NAMES[code];
    const name = text(v.name, 30) || (known ? known[0] : '');
    const title = text(v.title, 140);
    if (!name || !title) continue;
    out[code] = { name, rtl: Boolean(v.rtl ?? (known ? known[1] : false)), title, hook: text(v.hook, 220), body: body(v.body) };
  }
  return out;
}

export function clean(raw: any): Highlight | null {
  if (!raw || typeof raw !== 'object' || !ID.test(String(raw.id ?? ''))) return null;
  const kind = String(raw.kind ?? 'article');
  const paras = body(raw.body);
  const item: Highlight = {
    id: raw.id, kind: (KINDS as readonly string[]).includes(kind) ? kind : 'article', title: text(raw.title, 140),
    hook: text(raw.hook, 220), url: https(raw.url), added: day(raw.added),
    coverage: COVERAGE.includes(raw.coverage) ? raw.coverage : 'abstract', body: paras, doi: '',
    meta: { journal: '', published: '', lead: '', authors: [], institutions: [], countries: [], open_access: false },
    tools: [], skills: [], keywords: [],
  };
  if (!item.title || !item.url || !item.added || paras.length < MIN_PARAGRAPHS) return null;
  const doi = text(raw.doi, 220);
  item.doi = DOI.test(doi) ? doi : '';
  const m = raw.meta && typeof raw.meta === 'object' && !Array.isArray(raw.meta) ? raw.meta : {};
  item.meta = { journal: text(m.journal, 120), published: day(m.published), lead: text(m.lead, 100), authors: names(m.authors, 8, 80),
    institutions: names(m.institutions, 8, 120), countries: names(m.countries, 12, 60), open_access: m.open_access === true };
  item.tools = names(raw.tools, 12, 60);
  item.skills = words(raw.skills, 6);
  item.keywords = words(raw.keywords, 8);
  const said = cleanTranslations(raw.translations);
  if (Object.keys(said).length) item.translations = said;
  return item;
}

export function cleanAll(raw: unknown): Highlight[] {
  const seen = new Set<string>();
  const out: Highlight[] = [];
  for (const r of (Array.isArray(raw) ? raw : []).slice(0, 300)) {
    const h = clean(r);
    if (h && !seen.has(h.id)) {
      seen.add(h.id);
      out.push(h);
    }
  }
  out.sort((a, b) => (a.added !== b.added ? (a.added < b.added ? 1 : -1) : a.id < b.id ? 1 : a.id > b.id ? -1 : 0));
  return out.slice(0, KEEP);
}

/** The story in one language. A translation whose paragraphs no longer line up gives way to the English body. */
export function readIn(item: Highlight, code: string) {
  const tr = code !== 'en' ? item.translations?.[code] : undefined;
  if (!tr) return { code: 'en', rtl: false, title: item.title, hook: item.hook, body: item.body, labels: LABELS.en };
  return { code, rtl: tr.rtl, title: tr.title, hook: tr.hook || item.hook,
    body: tr.body.length === item.body.length ? tr.body : item.body, labels: LABELS[code] ?? LABELS.en };
}

/** The languages a story can be read in: English first, then its translations in the order offered. */
export function languages(item: Highlight): [string, string][] {
  const known = Object.keys(NAMES);
  const codes = Object.keys(item.translations ?? {}).sort((a, b) =>
    (known.includes(a) ? known.indexOf(a) : 99) - (known.includes(b) ? known.indexOf(b) : 99) || (a < b ? -1 : 1));
  return [['en', 'English'], ...codes.map((c) => [c, item.translations![c].name] as [string, string])];
}
