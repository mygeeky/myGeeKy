// My month's eight drawings, each with GeekOc: a port of the desktop's monthviz.py. Pure, and the same drawings
// (tests/test_phone_month_match_desktop.py runs both on the same records and compares numbers and SVG).
//   1 GitHub work (a glowing calendar)   2 languages (GeekOc's arms)   3 wins (a ribbon)   4 learning (constellations)
//   5 exploring (a compass)   6 habits (a sky clock and medals)   7 people (give and get)   8 interests (ribbons)
import { DAY, MONTHS, STAR, text } from './month';

type Rec = Record<string, any>;
export type Stats = {
  month_name: string; has_github: boolean;
  github: { days: number[]; prs: boolean[]; total: number; by_repo: Record<string, number>; first: number };
  languages: [string, number][]; wins: [number, number, number, number][]; ndays: number;
  protocols: { title?: string; steps?: [string, boolean][] }[]; topics: [string, number, boolean][];
  shift: [string, number, number][]; hours: number[]; badges: [string, string, string][];
  give: [string, number, number | null][];
};

const W = 320;
const [INK, MUTED, FAINT] = ['#eef0ff', '#a9b0d6', '#6f78a8'];
const SERIES = ['#8a72f2', '#169a7e', '#b98410', '#e255ad', '#4a92dd'];
const [GOLD, PINK, CYAN, VIOLET] = ['#ffd24a', '#ff6fd8', '#7fd8ff', '#8a72f2'];
const TIERS: Record<string, string> = { bronze: '#d58a5a', silver: '#c9d1e8', gold: '#ffd24a' };
const CONTRIB = new Set(['PushEvent', 'PullRequestEvent', 'IssuesEvent', 'PullRequestReviewEvent', 'CreateEvent']);
const INVITES = new Set(['collab', 'join']);
const TOPIC_KINDS = new Set(['repo', 'news', 'star', 'fork', 'paper', 'join']);   // what you read and keep: not follows (names)

const rn = (v: number) => Math.floor(v * 10 + 0.5) / 10;           // one decimal, .05 up: as the desktop's _r
const r = (v: number) => String(rn(v));
const r2 = (v: number) => String(Math.floor(v * 100 + 0.5) / 100);
const pad = (n: number, w: number) => String(n).padStart(w, '0');
const day10 = (x: unknown) => String(x ?? '').slice(0, 10);
const inMonth = (day: string, y: number, m: number) => DAY.test(day) && day.slice(0, 7) === `${pad(y, 4)}-${pad(m, 2)}`;
const isObj = (x: unknown): x is Rec => !!x && typeof x === 'object' && !Array.isArray(x);

function ndays(y: number, m: number): number {
  return [31, (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
}

/** The weekday of the 1st, Sunday = 0 (Zeller's). */
function firstDay(y: number, m: number): number {
  const [yy, mm] = m < 3 ? [y - 1, m + 12] : [y, m];
  const h = (1 + Math.floor((13 * (mm + 1)) / 5) + (yy % 100) + Math.floor((yy % 100) / 4) + Math.floor(Math.floor(yy / 100) / 4)
    + 5 * Math.floor(yy / 100)) % 7;
  return (h + 6) % 7;
}

// ---- the counting
export function githubMonth(events: unknown[], y: number, m: number): Stats['github'] {
  const days = new Array(ndays(y, m)).fill(0), prs = new Array(ndays(y, m)).fill(false);
  const byRepo: Record<string, number> = {};
  for (const e of events) {
    if (!isObj(e) || !CONTRIB.has(e.type) || !inMonth(day10(e.at), y, m)) continue;
    const kind = e.type, action = e.action ?? '';
    if ((kind === 'PullRequestEvent' || kind === 'IssuesEvent') && action !== 'opened') continue;
    const n = kind === 'PushEvent' ? Math.max(Math.trunc(Number(e.n) || 1) || 1, 1) : 1;
    const i = Number(String(e.at).slice(8, 10)) - 1;
    days[i] += n;
    prs[i] = prs[i] || kind === 'PullRequestEvent';
    const repo = String(e.repo ?? '');
    byRepo[repo] = (byRepo[repo] ?? 0) + n;
  }
  return { days, prs, total: days.reduce((a, b) => a + b, 0), by_repo: byRepo, first: firstDay(y, m) };
}

export function languages(byRepo: Record<string, number>, repoLangs: Record<string, string>): [string, number][] {
  const weight: Record<string, number> = {};
  for (const [repo, n] of Object.entries(byRepo)) {
    const lang = repoLangs[repo] || 'Other';
    weight[lang] = (weight[lang] ?? 0) + n;
  }
  const total = Object.values(weight).reduce((a, b) => a + b, 0);
  if (!total) return [];
  const ranked = Object.entries(weight).sort((a, b) =>
    Number(a[0] === 'Other') - Number(b[0] === 'Other') || b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  const top = ranked.filter(([k]) => k !== 'Other').slice(0, 4);
  const rest = total - top.reduce((a, [, n]) => a + n, 0);
  const out: [string, number][] = top.map(([name, n]) => [name, Math.floor((100 * n) / total + 0.5)]);
  if (rest) out.push(['Other', Math.floor((100 * rest) / total + 0.5)]);
  return out;
}

export function winsMonth(wins: unknown[], y: number, m: number): [number, number, number, number][] {
  const per = new Map<number, [number, number, number, number]>();
  const slot: Record<string, 1 | 2 | 3> = { stars: 1, forks: 2, citations: 3 };
  for (const w of wins) {
    if (!isObj(w) || !(w.kind in slot) || !inMonth(day10(w.at), y, m)) continue;
    const d = Number(String(w.at).slice(8, 10));
    const row = per.get(d) ?? [d, 0, 0, 0];
    row[slot[w.kind]] += Math.max(Math.trunc(Number(w.count) || 1) || 1, 1);
    per.set(d, row);
  }
  return [...per.keys()].sort((a, b) => a - b).map((d) => per.get(d)!);
}

function termWeights(events: Rec[], start: string, end: string): Map<string, number> {
  const out = new Map<string, number>();
  for (const e of events) {
    if (!isObj(e.terms) || !TOPIC_KINDS.has(e.kind)) continue;
    const day = day10(e.at);
    if (DAY.test(day) && start <= day && day < end) {
      for (const [t, w] of Object.entries(e.terms)) if (typeof w === 'number') out.set(t, (out.get(t) ?? 0) + w);
    }
  }
  return out;
}

const bounds = (y: number, m: number): [string, string] =>
  [`${pad(y, 4)}-${pad(m, 2)}-01`, `${pad(y + Math.floor(m / 12), 4)}-${pad((m % 12) + 1, 2)}-01`];
const byWeight = (a: [string, number], b: [string, number]) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);

export function topics(events: Rec[], y: number, m: number, n = 8): [string, number, boolean][] {
  const [start, end] = bounds(y, m);
  const now = termWeights(events, start, end);
  const before = termWeights(events, '0000-00-00', start);
  const top = [...now.entries()].sort(byWeight).slice(0, n);
  if (!top.length) return [];
  const mx = top[0][1];
  return top.map(([t, w]) => [t, Math.floor((100 * w) / mx + 0.5), !before.has(t)]);
}

export function shift(events: Rec[], y: number, m: number, n = 6): [string, number, number][] {
  const [start, end] = bounds(y, m);
  const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
  const now = termWeights(events, start, end);
  const was = termWeights(events, bounds(py, pm)[0], start);
  if (!now.size && !was.size) return [];
  const mn = Math.max(0, ...now.values()) || 1, mw = Math.max(0, ...was.values()) || 1;
  const terms = new Set([...now.keys(), ...was.keys()]);
  const level = new Map([...terms].map((t) => [t, [Math.floor((100 * (was.get(t) ?? 0)) / mw + 0.5) / 100,
    Math.floor((100 * (now.get(t) ?? 0)) / mn + 0.5) / 100]] as [string, [number, number]]));
  const top = [...terms].map((t) => [t, Math.max(...level.get(t)!)] as [string, number]).sort(byWeight).slice(0, n);
  return top.map(([t]) => [t, level.get(t)![0], level.get(t)![1]]);
}

export function hours(usage: unknown[], y: number, m: number, tzMinutes = 0): number[] {
  const out = new Array(24).fill(0);
  for (const e of usage) {
    const at = isObj(e) ? String(e.at ?? '') : '';
    if (at.length < 16 || !inMonth(at.slice(0, 10), y, m) || !/^\d\d$/.test(at.slice(11, 13)) || !/^\d\d$/.test(at.slice(14, 16))) continue;
    const mins = Number(at.slice(11, 13)) * 60 + Number(at.slice(14, 16)) + tzMinutes;
    out[((Math.floor(mins / 60) % 24) + 24) % 24] += 1;
  }
  return out;
}

export function giveGet(sent: unknown[], received: unknown[], events: unknown[], y: number, m: number): [string, number, number | null][] {
  const count = (items: unknown[], invites: boolean) =>
    items.filter((g) => isObj(g) && inMonth(day10(g.at), y, m) && INVITES.has(g.type) === invites).length;
  const follows = events.filter((e) => isObj(e) && e.kind === 'follow' && inMonth(day10(e.at), y, m)).length;
  return [['thank-yous', count(sent, false), count(received, false)], ['invites', count(sent, true), count(received, true)],
    ['follows', follows, null]];
}

export function stats(inputs: Rec, y: number, m: number, tzMinutes = 0): Stats {
  const gh = githubMonth(inputs.github ?? [], y, m);
  const events = (inputs.events ?? []).filter(isObj);
  return {
    month_name: MONTHS[m - 1], has_github: !!inputs.has_github,
    github: gh, languages: languages(gh.by_repo, inputs.repo_langs ?? {}),
    wins: winsMonth(inputs.wins ?? [], y, m), ndays: ndays(y, m),
    protocols: (inputs.protocols ?? []).filter(isObj).slice(0, 2),
    topics: topics(events, y, m), shift: shift(events, y, m),
    hours: hours(inputs.usage ?? [], y, m, tzMinutes),
    badges: (inputs.badges ?? []).filter((b: unknown) => Array.isArray(b) && b.length === 3).slice(0, 5),
    give: giveGet(inputs.sent ?? [], inputs.received ?? [], events, y, m),
  };
}

// ---- the drawings
type Gk = Record<string, string>;

function frame(uid: string, h: number, body: string, defs = ''): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${h}" width="${W}" height="${h}">`
    + `<defs><linearGradient id="${uid}bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d2b5e"/>`
    + `<stop offset="1" stop-color="#0b1130"/></linearGradient>${defs}</defs>`
    + `<rect width="${W}" height="${h}" rx="18" fill="url(#${uid}bg)"/>${body}</svg>`;
}

const geek = (markup: string | undefined, x: number, y: number, scale: string) =>
  (markup ? `<g transform="translate(${r(x)},${r(y)}) scale(${scale})">${markup}</g>` : '');

const empty = (uid: string, line: string, markup = '') =>
  frame(uid, 120, geek(markup, 14, 14, '0.1452') + text(116, 58, line, 12, MUTED, 700) + text(116, 76, 'It fills in as you go.', 11, FAINT));

const trim = (s: string, n: number) => (s.length <= n ? s : `${s.slice(0, n - 1)}…`);

export function githubSvg(s: Stats, gk: Gk): string {
  const g = s.github;
  if (!s.has_github) return empty('gh', 'Add GitHub to see your work', gk.wave ?? '');
  if (!g.total) return empty('gh', 'No GitHub work yet', gk.wave ?? '');
  const [c, ch, gap, x0, y0] = [36, 26, 6, 18, 86];
  const rows = Math.floor((g.first + g.days.length + 6) / 7);
  const h = y0 + rows * (ch + gap) + 22;
  const mx = Math.max(...g.days);
  const out = [geek(gk.wave, 214, -6, '0.1355'), text(18, 42, g.total, 30, INK, 800), text(18, 60, `GitHub contributions in ${s.month_name}`, 11, MUTED)];
  [...'SMTWTFS'].forEach((d, col) => out.push(text(x0 + col * (c + gap) + c / 2, y0 - 6, d, 9, FAINT, 700, 'middle')));
  g.days.forEach((n, i) => {
    const p = g.first + i, x = x0 + (p % 7) * (c + gap), y = y0 + Math.floor(p / 7) * (ch + gap);
    if (n) {
      if (n * 4 >= mx * 3) out.push(`<rect x="${x - 3}" y="${y - 3}" width="${c + 6}" height="${ch + 6}" rx="10" fill="${PINK}" opacity="0.22"/>`);
      out.push(`<rect x="${x}" y="${y}" width="${c}" height="${ch}" rx="8" fill="url(#ghc)" opacity="${r2(0.3 + (0.7 * n) / mx)}"/>`);
    } else out.push(`<rect x="${x}" y="${y}" width="${c}" height="${ch}" rx="8" fill="#ffffff" fill-opacity="0.06"/>`);
    if (g.prs[i]) out.push(`<circle cx="${x + c - 6}" cy="${y + 6}" r="3" fill="#ffffff"/>`);
  });
  out.push(`<circle cx="22" cy="${h - 12}" r="3" fill="#ffffff"/>`);
  out.push(text(30, h - 9, 'a day with a pull request', 9.5, MUTED));
  const defs = `<linearGradient id="ghc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${PINK}"/>`
    + '<stop offset="1" stop-color="#7a5cff"/></linearGradient>';
  return frame('gh', h, out.join(''), defs);
}

export function languagesSvg(s: Pick<Stats, 'languages'>, gk: Gk): string {
  const langs = s.languages;
  if (!langs.length) return empty('lg', 'Languages come with GitHub', gk.think ?? '');
  const [cx, cy, h] = [160, 96, 250];
  const out: string[] = [], defs: string[] = [];
  langs.forEach(([name, v], i) => {
    const a = Math.PI * (0.06 + i * 0.22), ca = Math.cos(a), sa = Math.sin(a);
    const length = 58 + v * 1.1;
    const right = ca > 0.05, left = ca < -0.05;
    const ex = cx + ca * length * 0.9, ey = cy + 22 + sa * length * 0.72;
    const mx = cx + ca * length * 0.45 - sa * 14, my = cy + 40 + sa * length * 0.55;
    const curl = right ? 1 : -1, w = 5 + v / 5;
    const d = `M${r(cx + ca * 14)},${cy + 24} Q${r(mx)},${r(my)} ${r(ex)},${r(ey)} q${curl * 9},4 ${curl * 7},-6`;
    defs.push(`<linearGradient id="lga${i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b45e0"/>`
      + `<stop offset="0.45" stop-color="${SERIES[i]}"/></linearGradient>`);
    out.push(`<path d="${d}" stroke="url(#lga${i})" stroke-width="${r(w)}" stroke-linecap="round" fill="none"/>`);
    out.push(`<path d="${d}" stroke="#ffffff" stroke-opacity="0.28" stroke-width="${r(Math.max(1.5, w / 5))}" `
      + 'stroke-linecap="round" fill="none" stroke-dasharray="1 7"/>');
    const label = `${name} ${v}%`;
    const far = right && ex + 12 + label.length * 6.2 > 314;
    const lx = far ? ex + 6 : ex + (right ? 12 : left ? -12 : 0);
    const ly = far ? ey - 14 : ey + (right || left ? 4 : 22);
    const anchor = far ? 'end' : right ? 'start' : left ? 'end' : 'middle';
    out.push(text(rn(lx), rn(ly), label, 11, INK, 700, anchor));
  });
  out.push(geek(gk.head, cx - 80, cy - 74, '0.2581'));
  return frame('lg', h, out.join(''), defs.join(''));
}

export function winsSvg(s: Stats, gk: Gk): string {
  const rows = s.wins;
  if (!rows.length) return empty('wn', 'No stars or citations yet', gk.swim ?? '');
  const [h, base] = [220, 124];
  const ry = (x: number) => base + Math.sin(x / 38) * 14;
  const pts: string[] = [];
  for (let x = 8; x < 313; x += 4) pts.push(`${x === 8 ? 'M' : 'L'}${x},${r(ry(x))}`);
  const out = [geek(gk.swim, 232, -8, '0.1355'),
    `<path d="${pts.join(' ')}" stroke="url(#wnr)" stroke-width="10" fill="none" stroke-linecap="round" opacity="0.85"/>`];
  rows.forEach(([day, stars, , cites], lane) => {
    const x = 12 + (day - 1) * 9.8, y0 = ry(x);
    const off = lane % 4 < 2 ? 26 : 52;
    const y = lane % 2 ? y0 + off : y0 - off;
    const col = cites ? PINK : stars ? GOLD : CYAN;
    out.push(`<line x1="${r(x)}" y1="${r(y0)}" x2="${r(x)}" y2="${r(y)}" stroke="${col}" stroke-opacity="0.5"/>`);
    out.push(`<rect x="${r(x - 11)}" y="${r(y - 8)}" width="22" height="16" rx="8" fill="#101a40" stroke="${col}" stroke-width="1.5"/>`);
    out.push(text(rn(x), rn(y + 4), cites ? '“' : stars ? String(stars) : 'Y', 9.5, col, 700, 'middle'));
  });
  out.push(text(8, h - 30, `${s.month_name.slice(0, 3)} 1`, 9.5, FAINT));
  out.push(text(312, h - 30, `${s.month_name.slice(0, 3)} ${s.ndays}`, 9.5, FAINT, 400, 'end'));
  ([[GOLD, 'new stars'], [CYAN, 'forks'], [PINK, 'citations']] as [string, string][]).forEach(([col, word], i) => {
    out.push(`<circle cx="${110 + i * 66}" cy="${h - 12}" r="3.5" fill="${col}"/>`);
    out.push(text(117 + i * 66, h - 9, word, 9.5, MUTED));
  });
  const defs = '<linearGradient id="wnr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7a5cff"/>'
    + `<stop offset="1" stop-color="${PINK}"/></linearGradient>`;
  return frame('wn', h, out.join(''), defs);
}

function sky(seed: number, n: number, w: number, h: number): string {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    seed = (seed * 16807) % 2147483647;
    const x = ((seed - 1) / 2147483646) * w;
    seed = (seed * 16807) % 2147483647;
    const y = ((seed - 1) / 2147483646) * h;
    out.push(`<circle cx="${r(x)}" cy="${r(y)}" r="0.8" fill="#ffffff" opacity="0.5"/>`);
  }
  return out.join('');
}

export function constellationSvg(s: Stats, gk: Gk): string {
  const protos = s.protocols;
  if (!protos.length) return empty('cs', 'Start a protocol in Grow', gk.point ?? '');
  const h = 50 + 96 * protos.length;
  const out = [sky(11, 40, W, h), geek(gk.point, 244, -6, '0.1129')];
  protos.forEach((p, pi) => {
    const steps = (p.steps ?? []).filter((st) => Array.isArray(st) && st.length === 2).slice(0, 7);
    const base = 86 + pi * 96;
    const known = steps.filter(([, k]) => k).length;
    out.push(text(18, base - 40, trim(String(p.title ?? ''), 30), 11.5, INK, 700));
    out.push(text(18, base - 26, `${known} of ${steps.length} steps`, 9.5, MUTED));
    const pts = steps.map((_, j) => [steps.length > 1 ? 30 + j * (260 / (steps.length - 1)) : 160, base + (j % 2 ? -12 : 12)]);
    for (let j = 1; j < pts.length; j++) {
      const lit = steps[j][1] && steps[j - 1][1];
      out.push(`<line x1="${r(pts[j - 1][0])}" y1="${pts[j - 1][1]}" x2="${r(pts[j][0])}" y2="${pts[j][1]}" `
        + `stroke="${VIOLET}" stroke-width="1.5" opacity="${lit ? 1 : 0.35}"/>`);
    }
    pts.forEach(([x, y], j) => {
      const [name, k] = steps[j];
      if (k) {
        out.push(`<circle cx="${r(x)}" cy="${y}" r="11" fill="${GOLD}" opacity="0.18"/>`);
        out.push(`<path d="${STAR}" fill="${GOLD}" transform="translate(${r(x)},${y}) scale(0.3)"/>`);
      } else {
        out.push(`<path d="${STAR}" fill="none" stroke="${FAINT}" stroke-width="4" transform="translate(${r(x)},${y}) scale(0.26)"/>`);
      }
      out.push(text(rn(x), y + 22, trim(String(name), 14), 8.5, k ? INK : FAINT, 400, 'middle'));
    });
  });
  return frame('cs', h, out.join(''));
}

export function compassSvg(s: Stats, gk: Gk): string {
  const tops = s.topics;
  if (!tops.length) return empty('cp', 'Open papers, news, repos', gk.idle ?? '');
  const [cx, cy, h] = [160, 118, 250];
  const out = [40, 70, 95].map((rr) => `<circle cx="${cx}" cy="${cy}" r="${rr}" fill="none" stroke="#a0b4ff" stroke-opacity="0.12"/>`);
  tops.forEach(([term, v, isNew], i) => {
    const a = (i / tops.length) * Math.PI * 2 - Math.PI / 2;
    const length = 30 + (70 * v) / 100;
    const p = (ang: number, rr: number) => `${r(cx + Math.cos(ang) * rr)},${r(cy + Math.sin(ang) * rr)}`;
    out.push(`<path d="M${p(a - 0.16, 14)} L${p(a, length)} L${p(a + 0.16, 14)}Z" fill="${isNew ? PINK : VIOLET}" opacity="0.9"/>`);
    const ca = Math.cos(a);
    const anchor = Math.abs(ca) < 0.3 ? 'middle' : ca > 0 ? 'start' : 'end';
    out.push(text(rn(cx + ca * (length + 12)), rn(cy + Math.sin(a) * (length + 12) + 4), trim(term, 18), 10, INK, 400, anchor));
  });
  out.push(geek(gk.idle, cx - 27, cy - 30, '0.0871'));
  ([[VIOLET, 'your usual'], [PINK, 'new territory']] as [string, string][]).forEach(([col, word], i) => {
    out.push(`<circle cx="${100 + i * 80}" cy="${h - 12}" r="3.5" fill="${col}"/>`);
    out.push(text(107 + i * 80, h - 9, word, 9.5, MUTED));
  });
  return frame('cp', h, out.join(''));
}

function when(hrs: number[]): string {
  let peak = 0;
  for (let i = 1; i < 24; i++) if (hrs[i] > hrs[peak]) peak = i;
  return peak >= 5 && peak < 12 ? 'mornings' : peak < 17 && peak >= 12 ? 'afternoons' : peak >= 17 && peak < 22 ? 'evenings' : 'nights';
}

export function habitsSvg(s: Stats, gk: Gk): string {
  const { hours: hrs, badges } = s;
  const [h, cx, cy] = [376, 160, 168];
  const out = [`<path d="M${cx - 150},${cy} A150,150 0 0 1 ${cx + 150},${cy}" stroke="url(#hbs)" stroke-width="10" fill="none" `
    + 'stroke-linecap="round"/>'];
  const mx = Math.max(...hrs) || 1;
  hrs.forEach((v, hr) => {
    const a = Math.PI + (hr / 23) * Math.PI, r1 = 60 + (v / mx) * 74;
    out.push(`<line x1="${r(cx + Math.cos(a) * 56)}" y1="${r(cy + Math.sin(a) * 56)}" x2="${r(cx + Math.cos(a) * r1)}" `
      + `y2="${r(cy + Math.sin(a) * r1)}" stroke="${hr >= 20 || hr < 6 ? VIOLET : '#f6b25e'}" stroke-width="6" stroke-linecap="round"/>`);
  });
  out.push(text(cx - 152, cy + 16, '0h', 10, FAINT, 400, 'middle'), text(cx, cy - 158, '12h', 10, FAINT, 400, 'middle'),
    text(cx + 152, cy + 16, '24h', 10, FAINT, 400, 'middle'), geek(gk.sleep, cx - 31, cy - 64, '0.1'));
  out.push(text(cx, cy + 18, hrs.some(Boolean) ? `mostly ${when(hrs)}` : 'no visits yet', 12, INK, 700, 'middle'));
  out.push('<line x1="40" y1="198" x2="280" y2="198" stroke="#ffffff" stroke-opacity="0.1" stroke-dasharray="2 5"/>');
  if (!badges.length) out.push(text(cx, 290, 'Your badges hang here as you earn them', 11, MUTED, 400, 'middle'));
  badges.forEach(([icon, name, tier], i) => {
    const x = 34 + i * 63, col = TIERS[tier] ?? TIERS.bronze, rib = SERIES[i % 5];
    out.push(`<path d="M${x - 11},210 V248 L${x},256 L${x + 11},248 V210Z" fill="${rib}"/>`);
    out.push(`<rect x="${x - 2.5}" y="210" width="5" height="42" fill="#ffffff" fill-opacity="0.3"/>`);
    out.push(`<line x1="${x}" y1="256" x2="${x}" y2="268" stroke="${col}" stroke-width="2"/>`);
    for (const side of [-1, 1]) {
      for (let k = 0; k < 7; k++) {
        const ang = Math.PI / 2 + side * (0.42 + k * 0.33), rr = 24 + (k % 2 ? 2.5 : -1);
        const px = x + Math.cos(ang) * rr, py = 294 + Math.sin(ang) * rr;
        const deg = (ang * 180) / Math.PI + 90 + side * 25;
        out.push(`<ellipse cx="0" cy="0" rx="6.5" ry="2.6" fill="${col}" opacity="${r2(0.9 - k * 0.05)}" `
          + `transform="translate(${r(px)},${r(py)}) rotate(${r(deg)})"/>`);
      }
    }
    out.push(text(x, 304, icon, 26, INK, 400, 'middle'));
    out.push(`<rect x="${x - 30}" y="332" width="60" height="20" rx="10" fill="#ffffff" fill-opacity="0.07" stroke="${col}" stroke-opacity="0.6"/>`);
    out.push(text(x, 346, trim(name, 12), 9, INK, 700, 'middle'));
  });
  const defs = '<linearGradient id="hbs" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1b2a6b"/>'
    + '<stop offset="0.3" stop-color="#f6b25e"/><stop offset="0.55" stop-color="#7fd8ff"/>'
    + '<stop offset="0.8" stop-color="#e2669e"/><stop offset="1" stop-color="#1b2a6b"/></linearGradient>';
  return frame('hb', h, out.join(''), defs);
}

export function givegotSvg(s: Stats, gk: Gk): string {
  const rows = s.give;
  const mx = Math.max(...rows.flatMap(([, a, b]) => [a, b]).filter((v): v is number => v !== null), 1);
  const unit = Math.min(14, 120 / mx);
  const h = 70 + rows.length * 44 + 24;
  const out = [geek(gk.wave, 12, -2, '0.1129'), `<line x1="160" y1="66" x2="160" y2="${h - 34}" stroke="#ffffff" stroke-opacity="0.2"/>`];
  rows.forEach(([what, gave, got], i) => {
    const y = 78 + i * 44;
    out.push(text(160, y - 2, what, 11, INK, 700, 'middle'));
    if (gave) out.push(`<rect x="${r(160 - gave * unit)}" y="${y + 4}" width="${r(gave * unit)}" height="18" rx="9" fill="${VIOLET}"/>`);
    out.push(text(gave ? rn(150 - gave * unit) : 154, y + 17, gave || 0, 10, INK, 700, 'end'));
    if (got === null) out.push(text(166, y + 17, '—', 10, FAINT));
    else {
      if (got) out.push(`<rect x="162" y="${y + 4}" width="${r(got * unit)}" height="18" rx="9" fill="#169a7e"/>`);
      out.push(text(got ? rn(172 + got * unit) : 166, y + 17, got, 10, INK, 700));
    }
  });
  out.push(text(150, h - 12, '← you gave', 10, MUTED, 400, 'end'));
  out.push(text(170, h - 12, 'you got →', 10, MUTED));
  return frame('gg', h, out.join(''));
}

export function ribbonsSvg(s: Stats, gk: Gk): string {
  const rows = s.shift;
  if (!rows.length) return empty('rb', 'Your interests show here', gk.think ?? '');
  const h = 220;
  const y = (v: number) => 196 - v * 140;
  const out = [geek(gk.think, 252, -6, '0.1129'),
    text(70, 30, MONTHS[(MONTHS.indexOf(s.month_name) + 11) % 12], 10, MUTED, 400, 'middle'),
    text(220, 30, s.month_name, 10, MUTED, 400, 'middle')];
  const labelY: Record<string, number> = {};
  let prev = 60;                                            // the first name sits below GeekOc
  for (const [t, , b] of [...rows].sort((p, q) => q[2] - p[2] || (p[0] < q[0] ? -1 : p[0] > q[0] ? 1 : 0))) {
    labelY[t] = Math.max(y(b), prev + 14);
    prev = labelY[t];
  }
  for (const [t, a, b] of rows) {
    const up = b > a;
    const d = `M70,${r(y(a))} C145,${r(y(a))} 145,${r(y(b))} 220,${r(y(b))}`;
    if (up) out.push(`<path d="${d}" stroke="#169a7e" stroke-opacity="0.25" stroke-width="10" fill="none"/>`);
    out.push(`<path d="${d}" stroke="${up ? '#169a7e' : '#ffffff'}" stroke-opacity="${up ? 1 : 0.25}" stroke-width="${up ? 4 : 2}" fill="none"/>`);
    out.push(`<circle cx="220" cy="${r(y(b))}" r="4.5" fill="${up ? '#7fe6c8' : FAINT}"/>`);
    out.push(text(230, rn(labelY[t] + 4), trim(t, 14), 10, INK, 400));
  }
  return frame('rb', h, out.join(''));
}

export const DIVES: [string, string, string, (s: Stats, gk: Gk) => string][] = [
  ['github', 'Your GitHub work', 'cheer', githubSvg],
  ['languages', 'The languages you used', 'proud', languagesSvg],
  ['wins', 'Your wins', 'proud', winsSvg],
  ['learning', 'What you learned', 'think', constellationSvg],
  ['exploring', 'What you explored', 'swim', compassSvg],
  ['habits', 'Your habits', 'cheer', habitsSvg],
  ['people', 'People and signals', 'wave', givegotSvg],
  ['shift', 'How your interests moved', 'think', ribbonsSvg],
];

/** GeekOc's line for one drawing. */
export function say(s: Stats, key: string): string {
  if (key === 'github') {
    return s.github.total ? `You made ${s.github.total} contributions on GitHub in ${s.month_name}!` : 'Your GitHub work shows here when there is some.';
  }
  if (key === 'languages') return s.languages.length ? `${s.languages[0][0]} was your favourite arm this month.` : 'Your languages come from the repos you work on.';
  if (key === 'wins') {
    const stars = s.wins.reduce((a, w) => a + w[1], 0), cites = s.wins.reduce((a, w) => a + w[3], 0);
    return s.wins.length ? `${stars} new stars and ${cites} citation${cites === 1 ? '' : 's'}. I caught them all!` : 'Stars and citations on your work land here.';
  }
  if (key === 'learning') {
    const known = s.protocols.reduce((a, p) => a + (p.steps ?? []).filter((st) => Array.isArray(st) && st[1] === true).length, 0);
    return known ? `${known} steps lit up in your protocols. Clever!` : 'Each step you know lights a star.';
  }
  if (key === 'exploring') {
    const fresh = s.topics.filter(([, , n]) => n).map(([t]) => t);
    return fresh.length ? `You swam into new waters: ${fresh.slice(0, 3).join(', ')}!`
      : s.topics.length ? 'You went deeper into your field.' : 'What you open shows where you explored.';
  }
  if (key === 'habits') return s.hours.some(Boolean) ? `You come by mostly in the ${when(s.hours).slice(0, -1)}, like a real geek.` : 'Your hours show as you use myGeeKy.';
  if (key === 'people') {
    const gave = s.give.reduce((a, g) => a + g[1], 0);
    return gave ? `You gave ${gave} time${gave === 1 ? '' : 's'} to the people around you. Making friends!` : 'Thank someone or follow a person, and it shows here.';
  }
  const up = s.shift.filter(([, a, b]) => b > a);
  return up.length ? `${up[0][0]} grew the most in you this month.` : 'Your interests show as you open things.';
}
