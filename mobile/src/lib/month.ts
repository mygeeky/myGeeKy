// My month and your rank: a port of the desktop's month.py. Pure (tests/test_phone_month_match_desktop.py runs it
// in Node against the desktop on the same records, card and ladder drawings included).
//   * usage lines (usage.jsonl, the same format as the desktop): days you came by, what you opened, ideas,
//     protocol steps, protocols built and shared, quizzes, skills, chances saved;
//   * interest events: people you followed (new friends);
//   * wins (wins.ts): new stars and citations on your own work.
// Points come only from what you do yourself (data/ranks.json, a copy of the desktop's), counted over all your
// time, so a rank never goes down. Wins show on the card but earn no points. Nothing is sent anywhere.
import rules from '../data/ranks.json';

export type Usage = { at: string; what: string; kind?: string; cat?: string; explore?: boolean };
export type Summary = {
  year: number; month: number; month_name: string; starter: boolean; days: string[][]; active: number;
  counts: Record<string, number>; highlights: [string, number, boolean][]; points: number; month_points: number;
  rank: number; rank_name: string; promoted: boolean; next: string | null; to_next: number | null;
};

export const RANKS = rules.ranks as unknown as [string, number][];
export const POINTS = rules.points as unknown as Record<string, number>;
export const KINDS = rules.kinds as unknown as Record<string, [string, string, string]>;
export const FAMILIES = rules.families as unknown as [string, string][];
const ORDER = Object.keys(KINDS);

const CLICK_KINDS: Record<string, string> = { headline: 'news', news: 'news', paper: 'paper', repo: 'repo', model: 'repo' };
const DONE = ['idea', 'step', 'build', 'share', 'quiz', 'skill', 'chance'];
const WIN_KINDS: Record<string, string> = { stars: 'star', citations: 'cite' };
const WIN_WEIGHT: Record<string, number> = { star: 2, cite: 15 };
const HIGHLIGHTS = 3;
export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
  'November', 'December'];
export const DAY = /^\d{4}-\d{2}-\d{2}$/;
const pad = (n: number, w: number) => String(n).padStart(w, '0');
const dayOf = (e: unknown) => (e && typeof e === 'object' ? String((e as { at?: unknown }).at ?? '').slice(0, 10) : '');

/** Every dated thing you did, as [YYYY-MM-DD, kind]; "day" marks a day you came by. */
export function entries(usage: unknown[], events: unknown[] = []): [string, string][] {
  const out: [string, string][] = [];
  for (const e of usage) {
    const day = dayOf(e);
    if (!DAY.test(day)) continue;
    const u = e as Usage;
    if (u.what === 'click') {
      const kind = CLICK_KINDS[String(u.kind ?? '')];
      if (kind) out.push([day, kind]);
      if (u.explore) out.push([day, 'topic']);
    } else if (u.what === 'open') out.push([day, 'day']);
    else if (DONE.includes(u.what)) out.push([day, u.what]);
  }
  for (const e of events) {
    const day = dayOf(e);
    if (DAY.test(day) && (e as { kind?: string }).kind === 'follow') out.push([day, 'friend']);
  }
  return out.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
}

/** Points for everything done before the day `before` (all of it by default). */
export function points(done: [string, string][], before = '9999-99-99'): number {
  return done.reduce((sum, [day, kind]) => sum + (day < before ? POINTS[kind] ?? 0 : 0), 0);
}

export function rankOf(pts: number): number {
  return RANKS.reduce((at, [, need], i) => (pts >= need ? i : at), 0);
}

export function summary(usage: unknown[], events: unknown[], wins: unknown[], year: number, month: number): Summary {
  const done = entries(usage, events);
  const start = `${pad(year, 4)}-${pad(month, 2)}-01`;
  const end = `${pad(year + Math.floor(month / 12), 4)}-${pad((month % 12) + 1, 2)}-01`;
  const ndays = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const days: Set<string>[] = Array.from({ length: ndays }, () => new Set<string>());
  const active = new Set<number>();
  const counts: Record<string, number> = {};
  for (const [day, kind] of done) {
    if (start <= day && day < end) {
      const i = Number(day.slice(8, 10)) - 1;
      if (kind !== 'day') {                      // a day you only came by isn't counted: the card lights what you did
        active.add(i);
        days[i].add(kind);
        counts[kind] = (counts[kind] ?? 0) + 1;
      }
    }
  }
  for (const w of wins) {
    if (!w || typeof w !== 'object') continue;
    const kind = WIN_KINDS[String((w as { kind?: unknown }).kind ?? '')];
    const day = dayOf(w);
    if (kind && DAY.test(day) && start <= day && day < end) {
      const n = Math.max(Math.trunc(Number((w as { count?: unknown }).count ?? 1)) || 1, 1);
      days[Number(day.slice(8, 10)) - 1].add(kind);
      counts[kind] = (counts[kind] ?? 0) + n;
    }
  }
  const seen = new Set(done.filter(([day]) => day < start).map(([, kind]) => kind));
  const first = new Set(Object.keys(counts).filter((k) => !seen.has(k) && !(k in WIN_WEIGHT)));
  const worth = (k: string) => POINTS[k] ?? WIN_WEIGHT[k] ?? 0;
  const picked = Object.keys(counts).sort((a, b) =>
    Number(first.has(b)) - Number(first.has(a)) || worth(b) - worth(a) || counts[b] - counts[a] || ORDER.indexOf(a) - ORDER.indexOf(b),
  ).slice(0, HIGHLIGHTS);
  const before = points(done, start), total = points(done, end);
  const rank = rankOf(total), was = rankOf(before);
  const nxt = rank + 1 < RANKS.length ? RANKS[rank + 1] : null;
  return {
    year, month, month_name: MONTHS[month - 1], starter: seen.size === 0,
    days: days.map((d) => ORDER.filter((k) => d.has(k))),
    active: active.size,
    counts: Object.fromEntries(ORDER.filter((k) => counts[k]).map((k) => [k, counts[k]])),
    highlights: picked.map((k) => [k, counts[k], first.has(k)] as [string, number, boolean]),
    points: total, month_points: total - before,
    rank, rank_name: RANKS[rank][0], promoted: rank > was,
    next: nxt ? nxt[0] : null, to_next: nxt ? nxt[1] - total : null,
  };
}

/** The month of your first record: how far back ‹ can go. */
export function firstMonth(usage: unknown[], events: unknown[] = []): [number, number] | null {
  const done = entries(usage, events);
  return done.length ? [Number(done[0][0].slice(0, 4)), Number(done[0][0].slice(5, 7))] : null;
}

// ---- the card (an SVG, the same as the desktop's)
export const STAR = 'M0,-30 L9,-9 L32,-9 L13,5 L20,28 L0,14 L-20,28 L-13,5 L-32,-9 L-9,-9Z';
export const CARD_W = 400, CARD_H = 500;
const FONT = 'Helvetica, Arial, sans-serif';
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');

export function text(x: number, y: number, txt: string | number, size: number, fill: string, weight = 400, anchor = 'start', extra = ''): string {
  return `<text x="${x}" y="${y}" font-family="${FONT}" font-size="${size}" font-weight="${weight}" `
    + `fill="${fill}" text-anchor="${anchor}"${extra}>${esc(String(txt))}</text>`;
}

/** A rank's shield: chevrons for the first three ranks, then one to five stars. */
export function insignia(i: number, x: number, y: number, k = 1, uid = 'ins'): string {
  const officer = i >= 3;
  const [top, bottom] = officer ? ['#5b33d6', '#24104f'] : ['#2a3f8f', '#121c45'];
  let g = `<defs><linearGradient id="${uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/>`
    + `<stop offset="1" stop-color="${bottom}"/></linearGradient></defs>`
    + `<path d="M-20,-24 H20 V4 Q20,22 0,31 Q-20,22 -20,4Z" fill="url(#${uid})" stroke="#ffd24a" stroke-width="2.5"/>`;
  if (!officer) {
    for (let c = 0; c <= i; c++) {
      const yy = -6 + c * 9 - i * 4.5;
      g += `<path d="M-12,${yy + 6} L0,${yy - 3} L12,${yy + 6}" stroke="#ffd24a" stroke-width="4" `
        + 'fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
    }
  } else {
    const n = i - 2;
    const rows = n <= 3 ? [n] : n === 4 ? [2, 2] : [3, 2];
    rows.forEach((m, r) => {
      for (let c = 0; c < m; c++) {
        g += `<path d="${STAR}" fill="#ffd24a" transform="translate(${(c - (m - 1) / 2) * 12},`
          + `${(r - (rows.length - 1) / 2) * 12 - 2}) scale(0.17)"/>`;
      }
    });
  }
  return `<g transform="translate(${x},${y}) scale(${k})">${g}</g>`;
}

export function cheer(s: Summary): string {
  if (s.promoted) return `Promoted to ${s.rank_name}! Keep growing`;
  if (s.starter && s.active) return 'Every expert started here. Well done';
  if (s.active >= 15) return 'Small steps add up. Keep growing';
  if (s.active) return 'Every day counts. Keep growing';
  return 'A quiet month. GeekOc is waiting for you';
}

/** Which GeekOc goes on the card (a pose in data/geekoc.json). */
export function cardPose(s: Summary): string {
  if (s.promoted) return 'cheer';
  if (!s.active) return 'sleep';
  if (s.starter) return 'wave';
  return s.active >= 15 ? 'cheer' : 'think';
}

/** The month card, 400 x 500 (4:5); `geekoc` is the inside of a 620-square GeekOc, `hidden` kinds left off. */
export function cardSvg(s: Summary, geekoc = '', hidden: string[] = []): string {
  const hide = new Set(hidden);
  const famColour = Object.fromEntries(FAMILIES);
  const colour = (k: string) => famColour[KINDS[k][0]];
  const out = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${CARD_W} ${CARD_H}" width="${CARD_W}" height="${CARD_H}">`,
    '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fdfbff"/>'
    + '<stop offset="1" stop-color="#efe9ff"/></linearGradient>'
    + '<radialGradient id="pk" cx="0.95" cy="0.02" r="0.55"><stop offset="0" stop-color="#ff9fe0" stop-opacity="0.55"/>'
    + '<stop offset="1" stop-color="#ff9fe0" stop-opacity="0"/></radialGradient>'
    + '<radialGradient id="bl" cx="0.02" cy="0.98" r="0.6"><stop offset="0" stop-color="#9fd8ff" stop-opacity="0.5"/>'
    + '<stop offset="1" stop-color="#9fd8ff" stop-opacity="0"/></radialGradient></defs>',
    `<rect width="${CARD_W}" height="${CARD_H}" fill="url(#bg)"/>`,
    `<rect width="${CARD_W}" height="${CARD_H}" fill="url(#pk)"/>`,
    `<rect width="${CARD_W}" height="${CARD_H}" fill="url(#bl)"/>`];
  if (geekoc) out.push(`<g transform="translate(14,8) scale(0.1129)">${geekoc}</g>`);
  out.push(text(90, 40, `My ${s.month_name}`, 27, '#1d1a2e', 800));
  out.push(text(92, 60, `${s.active} day${s.active === 1 ? '' : 's'} of growing · ${s.year}`, 13, '#6c6488'));
  out.push(insignia(s.rank, 352, 36, 0.95));
  out.push(text(352, 82, s.rank_name.toUpperCase(), 10, '#3a2a7a', 800, 'middle', ' letter-spacing="1"'));
  if (s.promoted) {
    out.push('<rect x="318" y="2" width="68" height="15" rx="7.5" fill="#ff4fb8"/>');
    out.push(text(352, 13, 'PROMOTED!', 8.5, '#ffffff', 800, 'middle'));
  }

  // the calendar: one dot per family for each day you did something
  const first = new Date(Date.UTC(s.year, s.month - 1, 1)).getUTCDay();          // Sunday first
  const [cw, ch, gx, gy, x0, y0] = [44, 36, 6, 6, 28, 104];
  [...'SMTWTFS'].forEach((d, c) => out.push(text(x0 + c * (cw + gx) + cw / 2, 96, d, 10, '#9a93b5', 700, 'middle')));
  s.days.forEach((all, i) => {
    const kinds = all.filter((k) => !hide.has(k));
    const p = first + i, x = x0 + (p % 7) * (cw + gx), y = y0 + Math.floor(p / 7) * (ch + gy);
    const busy = kinds.length > 0;
    out.push(`<rect x="${x}" y="${y}" width="${cw}" height="${ch}" rx="10" `
      + (busy ? 'fill="#ffffff" stroke="#6a4be0" stroke-opacity="0.18"/>' : 'fill="#6a4be0" fill-opacity="0.05"/>'));
    out.push(text(x + 6, y + 13, i + 1, 9.5, busy ? '#3a3352' : '#b8b2cf', 700));
    const fams = FAMILIES.map(([f]) => f).filter((f) => kinds.some((k) => KINDS[k][0] === f));
    fams.slice(0, 4).forEach((f, n) => out.push(`<circle cx="${x + 9 + n * 9}" cy="${y + 26}" r="3.6" fill="${famColour[f]}"/>`));
    if (fams.length > 4) out.push(text(x + cw - 5, y + 29, '+', 10, '#6c6488', 800, 'end'));
  });
  const rows = Math.floor((first + s.days.length + 6) / 7);
  const ly = y0 + rows * (ch + gy) + 6;
  FAMILIES.forEach(([f, col], n) => {
    const x = 30 + n * 58;
    out.push(`<circle cx="${x + 4}" cy="${ly}" r="3.6" fill="${col}"/>`);
    out.push(text(x + 11, ly + 3, f, 9.5, '#6c6488', 700));
  });

  // three highlights, firsts first
  const hy = 336;
  const shown = s.highlights.filter((h) => !hide.has(h[0]));
  if (!shown.length) {
    out.push(text(200, hy + 40, 'Open something, take a quiz or build a protocol:', 12, '#6c6488', 400, 'middle'));
    out.push(text(200, hy + 58, 'it all shows here next month.', 12, '#6c6488', 400, 'middle'));
  }
  shown.forEach(([k, count, isFirst], n) => {
    const x = 28 + n * 116, col = colour(k);
    const label = count === 1 ? KINDS[k][2] : KINDS[k][1];
    out.push(`<rect x="${x}" y="${hy}" width="108" height="72" rx="16" fill="#ffffff" stroke="${col}" `
      + 'stroke-opacity="0.4" stroke-width="1.5"/>');
    out.push(`<circle cx="${x + 20}" cy="${hy + 20}" r="7" fill="${col}"/>`);
    out.push(text(x + 12, hy + 52, count, 22, '#1d1a2e', 800));
    out.push(text(x + 12, hy + 65, label, 10.5, '#6c6488'));
    if (isFirst) {
      out.push(`<rect x="${x + 56}" y="${hy - 8}" width="46" height="18" rx="9" fill="#ff4fb8"/>`);
      out.push(text(x + 79, hy + 5, 'FIRST!', 9.5, '#ffffff', 800, 'middle'));
    }
  });

  // every count, small: nothing done this month is left out
  Object.entries(s.counts).filter(([k]) => !hide.has(k)).slice(0, 12).forEach(([k, v], n) => {
    const x = 28 + (n % 3) * 118, y = 424 + Math.floor(n / 3) * 15;
    out.push(`<circle cx="${x + 5}" cy="${y - 4}" r="3.6" fill="${colour(k)}"/>`);
    out.push(text(x + 13, y, `${v} ${v === 1 ? KINDS[k][2] : KINDS[k][1]}`, 10, '#3a3352', 700));
  });
  out.push(text(28, 488, cheer(s), 13, '#6a4be0', 800));
  out.push(text(372, 488, 'mygeeky.org', 10, '#9a93b5', 400, 'end'));
  out.push('</svg>');
  return out.join('');
}

/** The ranks from Soldier to General, yours big (640 x 170); `light` for a light background. */
export function ladderSvg(pts: number, light = false): string {
  const [ink, soft, faint, track] = light ? ['#241f1a', '#5b5470', '#7a7390', '#000000'] : ['#ffffff', '#b9b0e8', '#8f86c6', '#ffffff'];
  const at = rankOf(pts);
  const nxt = at + 1 < RANKS.length ? RANKS[at + 1][1] : null;
  const part = nxt !== null ? Math.min((pts - RANKS[at][1]) / (nxt - RANKS[at][1]), 1.0) : 0;
  const x = (i: number) => 40 + i * 80;
  const y = 70;
  const reach = nxt !== null ? Math.floor(x(at) + part * 80 + 0.5) : x(at);
  const out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 170" width="640" height="170">',
    `<line x1="${x(0)}" y1="${y}" x2="${x(RANKS.length - 1)}" y2="${y}" stroke="${track}" stroke-opacity="0.14" `
    + 'stroke-width="6" stroke-linecap="round"/>',
    `<line x1="${x(0)}" y1="${y}" x2="${reach}" y2="${y}" stroke="#ffd24a" stroke-width="6" stroke-linecap="round"/>`];
  RANKS.forEach(([name, need], i) => {
    const cur = i === at;
    const body = insignia(i, x(i), y, cur ? 1.4 : 0.9, `lad${i}`);
    out.push(i <= at ? body : `<g opacity="0.38">${body}</g>`);
    out.push(text(x(i), y + (cur ? 62 : 46), name, cur ? 14 : 11, cur ? ink : soft, 700, 'middle'));
    out.push(text(x(i), y + (cur ? 78 : 60), need, 9.5, faint, 400, 'middle'));
  });
  out.push(text(reach, 18, `you: ${pts}`, 11, ink, 700, 'middle'));
  out.push('</svg>');
  return out.join('');
}

export const rankLine = (s: Summary) => (s.next === null
  ? `${s.rank_name} · ${s.points} points: the top rank!`
  : `${s.rank_name} · ${s.points} points · ${s.to_next} more to ${s.next}`);
export const monthLine = (s: Summary) => `+${s.month_points} points in ${s.month_name}`
  + (s.promoted ? ` · promoted to ${s.rank_name} this month!` : '');
