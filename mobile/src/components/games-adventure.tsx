// The two adventures of Play with GeeKOc, the desktop's gui/games_adventure.py on the same GEMS rules, run by the
// arcade engine (games-arcade.tsx): Rise (tap the right next step of a pipeline; a wrong platform sinks and says why;
// the tide rises while you think; at the surface, the pipeline you climbed) and GeeKOc goes home (tap beside GeeKOc to
// walk; doors ask quiz-bank questions, Basics easy, Core medium, Advanced hard; a wrong answer locks that door, and if
// there's no other way round it asks a different question). Everything shown comes from the pack: plain text only.
import { memo, type ReactNode } from 'react';
import { Text, View } from 'react-native';
import { questions, roundItems, type Question } from '../lib/games-store';
import { ArcadeEngine, Oc, W0, type Api, type Spec, type World } from './games-arcade';

const shuffle = <T,>(xs: T[]): T[] => { const a = xs.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
export const PROTOCOL_TERMS: Record<string, string[]> = {
  gwas: ['gwas', 'genetics'], 'single-cell-rna-seq': ['single-cell', 'rna-seq'], 'python-data-analysis': ['python'],
  'r-data-analysis': ['r'], 'ml-in-practice': ['machine learning'], 'git-github-teamwork': ['git'],
  'stats-for-experiments': ['statistics'], 'figures-for-papers': ['visualization'], nextflow: ['workflow'],
  'image-analysis-fiji': ['imaging'], 'excel-to-r': ['r', 'data analysis'], 'open-source-first-pr': ['open source', 'git'],
  'algorithms-interviews': ['programming'], 'first-web-app': ['software'],
};

// ------------------------------------------------------------------------------------------------ Rise
const ROW = 150;
const rowY = (w: World, r: number) => w.H - 150 - r * ROW;
function layRow(w: World) {
  const r = w.ladder.rows[w.row];
  const opts = shuffle([{ text: r.right, ok: true, why: '' }, ...r.wrong.map((x: any) => ({ text: x.text, ok: false, why: x.why }))]);
  const n = opts.length, gap = 12, wid = (W0 - 30 - gap * (n - 1)) / n;
  opts.forEach((o: any, i: number) => Object.assign(o, { x: 15 + i * (wid + gap), w: wid, y: rowY(w, w.row + 1) }));
  w.opts = opts; w.first = true;
  if (w.row === 0) { w.me = [W0 / 2, rowY(w, 0)]; w.tide = rowY(w, 0) + 140; }
}
function choose(w: World, i: number) {
  if (w.jump) return;
  const o = w.opts[i];
  w.jump = { from: [...w.me], to: [o.x + o.w / 2, o.y], t: 0, opt: o };
}
const RISE: Spec = {
  game: 'rise', title: 'Rise: climb out of the sea', bg: '#0d4a63',
  howto: 'Each row: tap the right next step of the pipeline. Wrong platforms sink and say why. The tide rises while you think.',
  load: (wts) => roundItems('rise', 'ladder', 1, wts),
  init: (items, w) => { Object.assign(w, { ladder: items[0], row: 0, opts: [], jump: null, cam: 0, camTo: 0, mistakes: 0, laid: false }); },
  step: (w, dt, api: Api) => {
    if (!w.laid) { layRow(w); w.laid = true; }
    w.cam += (w.camTo - w.cam) * Math.min(1, dt * 4);
    if (!w.jump) {
      w.tide -= dt * 4;                                   // gentle: about 27 s a row, as on the desktop
      if (w.tide < w.me[1] + 30) { api.say('The tide caught GeeKOc.', 3); api.feel('sad'); api.end(); return; }
    } else {
      const j = w.jump;
      j.t = Math.min(1, j.t + dt / 0.55);
      const k = j.t;
      w.me = [j.from[0] + (j.to[0] - j.from[0]) * k, j.from[1] + (j.to[1] - j.from[1]) * k - (1 - (2 * k - 1) ** 2) * 90];
      if (k >= 1) {
        w.jump = null;
        const o = j.opt;
        if (!o) return;
        const rid = `${w.ladder.id}:${w.row}`;
        if (o.ok) {
          if (w.first) api.answer(rid, true, w.ladder.level, w.ladder.terms);
          w.row += 1; w.camTo = -w.row * ROW; api.feel('happy');
          w.tide = Math.min(Math.max(w.tide, w.me[1] + 140), w.me[1] + 220);
          if (w.row >= w.ladder.rows.length) {
            const steps = w.ladder.rows.map((r: any, i: number) => `${i + 1}. ${r.right}`).join('\n');
            api.end({ title: 'GeeKOc reached the surface!', text: `The pipeline you climbed, ${w.ladder.name}:\n${steps}` });
          } else layRow(w);
        } else {
          if (w.first) api.answer(rid, false, w.ladder.level, w.ladder.terms);
          w.first = false; w.mistakes += 1; o.gone = true; api.feel('sad', 1.4);
          api.say(o.why, 3.6);
          w.jump = { from: [...w.me], to: [W0 / 2, rowY(w, w.row)], t: 0, opt: null };
        }
      }
    }
    w.hud = `step ${Math.min(w.row + 1, w.ladder.rows.length)}/${w.ladder.rows.length} · ${w.mistakes} sank`;
  },
  press: (w, x, y) => {
    y += w.cam;
    (w.opts ?? []).forEach((o: any, i: number) => {
      if (!o.gone && x >= o.x && x <= o.x + o.w && y >= o.y + 20 && y <= o.y + 120) choose(w, i);
    });
  },
  // whole units for the tide (it creeps up 4 a second) and the camera (it eases in for ever): a frame only when they
  // visibly move
  snap: (w) => ({ H: w.H, cam: Math.round(w.cam), me: w.me && [...w.me], jump: !!w.jump, row: w.row, name: w.ladder?.name ?? '', tide: Math.round(w.tide),
                  opts: (w.opts ?? []).map((o: any) => ({ text: o.text, x: o.x, y: o.y, w: o.w, gone: !!o.gone })) }),
  draw: (v, k) => !v.me ? null : <>
    <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, transform: [{ translateY: -v.cam * k }] }}>
      <View style={{ position: 'absolute', left: (W0 / 2 - 70) * k, top: (v.H - 150 - v.row * ROW + 36) * k, width: 140 * k, height: 12 * k, borderRadius: 6, backgroundColor: '#2f6f7a' }} />
      <Platforms opts={v.opts} jump={v.jump} k={k} />
      <Oc moment={v.jump ? 'jump' : 'stand'} x={v.me[0]} y={v.me[1]} size={86} k={k} />
      <View style={{ position: 'absolute', left: 0, right: 0, top: v.tide * k, height: 4000, backgroundColor: 'rgba(8,30,70,0.82)' }} />
    </View>
    <Text style={{ position: 'absolute', top: 6, left: 0, right: 0, textAlign: 'center', color: '#f0f0f5', fontWeight: '800', fontSize: 14 }}>Climbing {v.name}</Text>
  </>,
};

// a row's platforms: drawn again only when one sinks or GeeKOc takes off, not while the tide rises
const Platforms = memo(function Platforms({ opts, jump, k }: { opts: any[]; jump: boolean; k: number }) {
  return <>{opts.map((o: any, i: number) => o.gone ? null : (
    <View key={i} style={{ position: 'absolute', left: o.x * k, top: (o.y + 36) * k, width: o.w * k, minHeight: 64 * k, borderRadius: 10,
                           borderWidth: 2, borderColor: jump ? '#5a6aa0' : '#ffc457', backgroundColor: '#24304f', padding: 6, justifyContent: 'center' }}>
      <Text style={{ color: '#f0f0f5', fontWeight: '700', fontSize: 12, textAlign: 'center' }}>{o.text}</Text>
    </View>
  ))}</>;
}, (a, b) => a.jump === b.jump && a.k === b.k && JSON.stringify(a.opts) === JSON.stringify(b.opts));

// ------------------------------------------------------------------------------------------------ GeeKOc goes home
const CW = 9, CH = 9;
const key = (x: number, y: number, dx: number, dy: number) => (dx < 0 ? `${x - 1},${y},r` : dy < 0 ? `${x},${y - 1},d` : dx > 0 ? `${x},${y},r` : `${x},${y},d`);
function isOpen(w: World, x: number, y: number, dx: number, dy: number) {
  const nx = x + dx, ny = y + dy;
  if (nx < 0 || ny < 0 || nx >= CW || ny >= CH) return false;
  return dx > 0 ? !w.right[x][y] : dx < 0 ? !w.right[nx][ny] : dy > 0 ? !w.down[x][y] : !w.down[nx][ny];
}
function pathHome(w: World, sx: number, sy: number, blocked: (k: string) => boolean): [number, number][] | null {
  const prev = new Map<string, string | null>([[`${sx},${sy}`, null]]);
  const queue: [number, number][] = [[sx, sy]];
  while (queue.length) {
    const [x, y] = queue.shift()!;
    if (x === CW - 1 && y === CH - 1) {
      const out: [number, number][] = [];
      let k: string | null = `${x},${y}`;
      while (k) { out.unshift(k.split(',').map(Number) as [number, number]); k = prev.get(k) ?? null; }
      return out;
    }
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nk = `${x + dx},${y + dy}`;
      if (isOpen(w, x, y, dx, dy) && !blocked(key(x, y, dx, dy)) && !prev.has(nk)) { prev.set(nk, `${x},${y}`); queue.push([x + dx, y + dy]); }
    }
  }
  return null;
}
const cell = (w: { H: number }) => { const s = Math.min((W0 - 24) / CW, (w.H - 60) / CH); return { s, ox: (W0 - s * CW) / 2, oy: 40 }; };
function build(w: World, weights: Record<string, number>) {
  w.right = Array.from({ length: CW }, () => Array(CH).fill(true));
  w.down = Array.from({ length: CW }, () => Array(CH).fill(true));
  const seen = Array.from({ length: CW }, () => Array(CH).fill(false));
  const stack: [number, number][] = [[0, 0]];
  seen[0][0] = true;
  while (stack.length) {
    const [x, y] = stack[stack.length - 1];
    const nbr = [[1, 0], [-1, 0], [0, 1], [0, -1]].filter(([dx, dy]) => x + dx >= 0 && y + dy >= 0 && x + dx < CW && y + dy < CH && !seen[x + dx][y + dy]);
    if (!nbr.length) { stack.pop(); continue; }
    const [dx, dy] = nbr[Math.floor(Math.random() * nbr.length)], nx = x + dx, ny = y + dy;
    if (dx === 1) w.right[x][y] = false; if (dx === -1) w.right[nx][ny] = false;
    if (dy === 1) w.down[x][y] = false; if (dy === -1) w.down[nx][ny] = false;
    seen[nx][ny] = true; stack.push([nx, ny]);
  }
  for (let i = 0; i < 10; i++) {
    const x = Math.floor(Math.random() * (CW - 1)), y = Math.floor(Math.random() * (CH - 1));
    if (Math.random() < 0.5) w.right[x][y] = false; else w.down[x][y] = false;
  }
  const rel = (q: Question) => (PROTOCOL_TERMS[q.protocol] ?? []).reduce((s, t) => s + (weights[t] ?? 0), 0);
  const pools: Record<number, Question[]> = { 0: [], 1: [], 2: [] };
  for (const q of shuffle(questions()).sort((a, b) => rel(b) - rel(a))) pools[({ easy: 0, medium: 1, hard: 2 } as Record<string, number>)[(q as any).level] ?? 1].push(q);
  w.pools = pools;
  w.doors = {};
  const path = pathHome(w, 0, 0, () => false) ?? [];
  for (let i = 2; i < path.length - 1; i += 3) {
    const [x, y] = path[i - 1], [nx, ny] = path[i];
    w.doors[key(x, y, nx - x, ny - y)] = { state: 'shut', a: [x, y], b: [nx, ny] };
  }
  Object.assign(w, { at: [0, 0], anim: [0, 0, 1], home: false, asked: 0, rightFirst: 0, built: true });
}
function stepTo(w: World, dx: number, dy: number) { w.anim = [w.at[0], w.at[1], 0]; w.at = [w.at[0] + dx, w.at[1] + dy]; }
function walk(w: World, dx: number, dy: number, api: Api) {
  if (w.home || w.anim[2] < 1) return;
  const [x, y] = w.at;
  if (!isOpen(w, x, y, dx, dy)) return;
  const d = w.doors[key(x, y, dx, dy)];
  if (d && d.state === 'locked') { api.say('This door stays shut: find another way round.'); api.feel('sad'); return; }
  if (d && d.state === 'shut') {
    const region = Math.min(2, Math.floor((d.b[0] * 3) / CW));
    const pool: Question[] = w.pools[region].length ? w.pools[region] : w.pools[1].length ? w.pools[1] : w.pools[0];
    const q = pool.shift()!;
    pool.push(q);
    const options = shuffle(q.options);
    api.ask({ kicker: `${['Basics', 'Core', 'Advanced'][region]} door`, title: q.q, options, right: options.indexOf(q.options[0]),
              why: q.why, go: 'Through the door ›' }, (ok) => {
      w.asked += 1; if (ok) w.rightFirst += 1;
      api.answer(q.id, ok, ({ easy: 1, medium: 2, hard: 3 } as Record<string, number>)[(q as any).level] ?? 1, PROTOCOL_TERMS[q.protocol] ?? []);
      if (ok) { d.state = 'open'; api.feel('happy'); stepTo(w, dx, dy); return; }
      d.state = 'locked'; api.feel('sad', 1.6);
      if (!pathHome(w, w.at[0], w.at[1], (k) => w.doors[k]?.state === 'locked')) { d.state = 'shut'; api.say('No other way round here: this door will ask a different question.', 3.2); }
      else api.say("That door stays shut now. There's another way round.");
    });
    return;
  }
  stepTo(w, dx, dy);
}
// the maze itself (regions, border, walls): drawn once, never again while GeeKOc walks -- only he and the doors move
const Walls = memo(function Walls({ right, down, s, ox, oy, k }: { right: boolean[][]; down: boolean[][]; s: number; ox: number; oy: number; k: number }) {
  const lines: ReactNode[] = [];
  const ink = '#6a5acd', th = 2.5;
  for (let x = 0; x < CW; x++) for (let y = 0; y < CH; y++) {
    if (right[x][y] && x < CW - 1) lines.push(<View key={`r${x}-${y}`} style={{ position: 'absolute', left: (ox + (x + 1) * s) * k - th / 2, top: (oy + y * s) * k, width: th, height: s * k + th / 2, backgroundColor: ink }} />);
    if (down[x][y] && y < CH - 1) lines.push(<View key={`d${x}-${y}`} style={{ position: 'absolute', left: (ox + x * s) * k, top: (oy + (y + 1) * s) * k - th / 2, width: s * k + th / 2, height: th, backgroundColor: ink }} />);
  }
  return <>
    {['Basics', 'Core', 'Advanced'].map((n, i) => {
      const x0 = ox + s * Math.floor((i * CW) / 3), x1 = ox + s * Math.floor(((i + 1) * CW) / 3);
      return <View key={n}>
        <View style={{ position: 'absolute', left: x0 * k, top: oy * k, width: (x1 - x0) * k, height: s * CH * k, backgroundColor: ['rgba(127,216,255,0.07)', 'rgba(255,196,87,0.07)', 'rgba(255,111,216,0.08)'][i] }} />
        <Text style={{ position: 'absolute', left: x0 * k, top: (oy - 22) * k, width: (x1 - x0) * k, textAlign: 'center', color: '#a9a9c0', fontWeight: '800', fontSize: 12 }}>{n}</Text>
      </View>;
    })}
    <View style={{ position: 'absolute', left: ox * k, top: oy * k, width: s * CW * k, height: s * CH * k, borderWidth: th, borderColor: ink }} />
    {lines}
  </>;
});

const MAZE: Spec = {
  game: 'maze', title: 'GeeKOc goes home', bg: '#0b0b16',
  howto: 'Tap beside GeeKOc to walk. Doors ask questions: a wrong answer keeps that door shut, so find another way round.',
  load: async (wts) => { const lower: Record<string, number> = {}; for (const [t, v] of Object.entries(wts)) lower[t.toLowerCase()] = v; return [{ id: 'weights', kind: 'meta', level: 1, terms: [], weights: lower }]; },
  init: (items, w) => { w.weights = items[0]?.weights ?? {}; w.built = false; },
  step: (w, dt, api) => {
    if (!w.built) build(w, w.weights);
    if (w.anim[2] < 1) {
      w.anim[2] = Math.min(1, w.anim[2] + dt * 7);
      if (w.anim[2] >= 1 && w.at[0] === CW - 1 && w.at[1] === CH - 1 && !w.home) {
        w.home = true; api.feel('happy', 99);              // home: happy to the end
        api.end({ title: 'GeeKOc is home!', text: `${w.rightFirst} of ${w.asked} doors opened on the first try.` });
      }
    }
    w.hud = `${w.rightFirst}/${w.asked} doors right`;
  },
  press: (w, x, y, api) => {
    if (!w.built) return;
    const { s, ox, oy } = cell(w);
    const dx = x - (ox + (w.at[0] + 0.5) * s), dy = y - (oy + (w.at[1] + 0.5) * s);
    if (Math.abs(dx) > Math.abs(dy)) walk(w, dx > 0 ? 1 : -1, 0, api); else walk(w, 0, dy > 0 ? 1 : -1, api);
  },
  snap: (w) => (!w.built ? { H: w.H } : { H: w.H, right: w.right, down: w.down, at: [...w.at], anim: [...w.anim],
    doors: Object.entries(w.doors).map(([k, d]: [string, any]) => ({ k, state: d.state, a: d.a, b: d.b })) }),
  draw: (v, k) => {
    if (!v.right) return null;
    const { s, ox, oy } = cell(v as { H: number });
    const p = v.anim[2], px = v.anim[0] + (v.at[0] - v.anim[0]) * p, py = v.anim[1] + (v.at[1] - v.anim[1]) * p;
    return <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0 }}>
      <Walls right={v.right} down={v.down} s={s} ox={ox} oy={oy} k={k} />
      {v.doors.filter((d: any) => d.state !== 'open').map((d: any) => {
        const cx = ox + ((d.a[0] + d.b[0]) / 2 + 0.5) * s, cy = oy + ((d.a[1] + d.b[1]) / 2 + 0.5) * s, horiz = d.k.endsWith(',d');
        return <View key={d.k} style={{ position: 'absolute', backgroundColor: d.state === 'locked' ? '#f87171' : '#ffc457', borderRadius: 4,
          left: (horiz ? cx - s / 2 + 5 : cx - 4) * k, top: (horiz ? cy - 4 : cy - s / 2 + 5) * k, width: (horiz ? s - 10 : 8) * k, height: (horiz ? 8 : s - 10) * k }} />;
      })}
      <Text style={{ position: 'absolute', left: (ox + (CW - 1) * s) * k, top: (oy + (CH - 1) * s) * k, width: s * k, height: s * k, textAlign: 'center', fontSize: s * 0.6 * k }}>🏠</Text>
      <Oc x={ox + (px + 0.5) * s} y={oy + (py + 0.5) * s} size={s * 1.3} k={k} />
    </View>;
  },
};

const SPECS: Record<string, Spec> = { rise: RISE, maze: MAZE };
export const ADVENTURES = Object.keys(SPECS);

export function Adventure({ id, ...rest }: {
  id: string; onAgain: () => void; onHub: () => void; Result: Parameters<typeof ArcadeEngine>[0]['Result'];
}) {
  return <ArcadeEngine spec={SPECS[id]} {...rest} />;
}
