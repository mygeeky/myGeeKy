// Grow → Skills, drawn: directions (where the field is going: a launch pad, bridges and a horizon), next steps, bridges (a flow from your skills to rising ones), the ladder (your rising
// strengths joined to new rising skills) and your lens (what your feed sees against the world) -- the desktop's
// gui/skillviews_ui.py. lib/skills.ts shapes() works out every number (the same as skills.shapes).
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import type { Direction, Link, Shapes } from '../lib/skills';
import { C } from '../lib/theme';

const YOURS = C.dark ? '#3987e5' : '#2a78d6';
const RISING = C.dark ? '#d95926' : '#eb6834';
const BOTH = C.dark ? '#199e70' : '#1baf7a';
const short = (s: string, n = 16) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const column = (n: number, top: number, h: number) => (n === 1 ? [top + h / 2] : Array.from({ length: n }, (_, i) => top + (i * h) / (n - 1)));

function Flow({ flow, width }: { flow: Shapes['flow']; width: number }) {
  const { left, right, bands } = flow;
  const H = Math.min(210, 40 + 28 * Math.max(left.length, right.length)), gap = 5, lx = width * 0.34, rx = width * 0.62, mid = (lx + rx) / 2;
  const total = bands.reduce((a, b) => a + b[2], 0) || 1;
  const lw = Object.fromEntries(left.map((n) => [n, bands.filter((b) => b[0] === n).reduce((a, b) => a + b[2], 0)]));
  const rw = Object.fromEntries(right.map((n) => [n, bands.filter((b) => b[1] === n).reduce((a, b) => a + b[2], 0)]));
  const scale = (H - 12 - gap * (Math.max(left.length, right.length) - 1)) / total;
  const ly: Record<string, number> = {}, ry: Record<string, number> = {};
  let y = 6;
  for (const n of left) { ly[n] = y; y += lw[n] * scale + gap; }
  y = 6;
  for (const n of right) { ry[n] = y; y += rw[n] * scale + gap; }
  const lcur = { ...ly }, rcur = { ...ry };
  const paths = [...bands].sort((a, b) => left.indexOf(a[0]) - left.indexOf(b[0]) || right.indexOf(a[1]) - right.indexOf(b[1])).map(([a, b, k]) => {
    const t = k * scale, y1 = lcur[a], y2 = rcur[b];
    lcur[a] += t; rcur[b] += t;
    return { key: `${a}>${b}`, d: `M${lx},${y1} C${mid},${y1} ${mid},${y2} ${rx},${y2} L${rx},${y2 + t} C${mid},${y2 + t} ${mid},${y1 + t} ${lx},${y1 + t} Z` };
  });
  return (
    <Svg width={width} height={H}>
      {paths.map((p) => <Path key={p.key} d={p.d} fill={RISING} fillOpacity={0.3} />)}
      {left.map((n) => (
        <G key={`l${n}`}>
          <Rect x={lx - 5} y={ly[n]} width={5} height={Math.max(2, lw[n] * scale)} rx={2} fill={YOURS} />
          <SvgText x={lx - 9} y={ly[n] + (lw[n] * scale) / 2 + 3.5} fontSize={10.5} fill={C.text} textAnchor="end">{short(n, 17)}</SvgText>
        </G>
      ))}
      {right.map((n) => (
        <G key={`r${n}`}>
          <Rect x={rx} y={ry[n]} width={5} height={Math.max(2, rw[n] * scale)} rx={2} fill={RISING} />
          <SvgText x={rx + 9} y={ry[n] + (rw[n] * scale) / 2 + 3.5} fontSize={10.5} fill={C.text}>{short(n, 17)}</SvgText>
        </G>
      ))}
    </Svg>
  );
}

type Aimed = Direction & { line: string; pad: string; closeness: number };
const PAPER = C.dark ? '#191824' : '#ffffff';

/** Your skills on the ground; each direction a rocket launched from the one it's most tied to (gui LaunchPadView). */
function LaunchPad({ dirs, pads, width }: { dirs: Aimed[]; pads: string[]; width: number }) {
  const ground = 250, rows = dirs.filter((d) => d.pad);
  const topG = Math.max(2, ...rows.map((d) => d.growth)) * 1.1, topM = Math.max(1, ...rows.map((d) => d.mentions));
  const alt = (g: number) => ground - 20 - (Math.log(Math.max(g, 1)) / Math.log(Math.max(topG, 1.5))) * (ground - 50);
  const px = (i: number) => 24 + ((i + 0.5) * (width - 48)) / Math.max(pads.length, 1);
  const seen: Record<string, number> = {}, placed: [number, number][] = [];
  return (
    <Svg width={width} height={ground + 26}>
      <Rect x={0} y={0} width={width} height={ground} rx={8} fill={C.text} fillOpacity={0.04} />
      {[2, 4, 8].filter((g) => g < topG).map((g) => (
        <G key={g}>
          <Line x1={0} x2={width} y1={alt(g)} y2={alt(g)} stroke={C.muted} strokeDasharray="2 4" strokeOpacity={0.6} />
          <SvgText x={width - 3} y={alt(g) - 3} fontSize={9} fill={C.muted} textAnchor="end">×{g}</SvgText>
        </G>
      ))}
      <Line x1={0} x2={width} y1={ground} y2={ground} stroke={C.muted} strokeWidth={1.5} />
      {pads.map((name, i) => (
        <G key={name}>
          <Rect x={px(i) - 13} y={ground} width={26} height={5} rx={2} fill={YOURS} />
          <SvgText x={px(i)} y={ground + 19} fontSize={10} fontWeight="700" fill={C.text} textAnchor="middle">{short(name, 12)}</SvgText>
        </G>
      ))}
      {rows.map((d) => {
        const i = pads.indexOf(d.pad), k = (seen[d.pad] = (seen[d.pad] ?? -1) + 1);
        const x = Math.max(14, Math.min(width - 14, px(i) + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 22));
        const y = alt(d.growth), r = 5 + 6 * Math.sqrt(d.mentions / topM), ly = y - r * 1.5 - 5;
        const label = !placed.some(([a, b]) => Math.abs(a - x) < 76 && Math.abs(b - ly) < 12);
        if (label) placed.push([x, ly]);
        return (
          <G key={d.name}>
            <Path d={`M${px(i)},${ground} C${px(i)},${(ground + y) / 2} ${x},${(ground + y) / 2 + 20} ${x},${y + r}`} fill="none" stroke={RISING} strokeOpacity={0.35} strokeWidth={2} strokeDasharray="3 3" />
            <Path d={`M${x},${y - r * 1.5} C${x + r * 0.9},${y - r * 0.6} ${x + r * 0.8},${y + r * 0.6} ${x + r * 0.55},${y + r} L${x - r * 0.55},${y + r} C${x - r * 0.8},${y + r * 0.6} ${x - r * 0.9},${y - r * 0.6} ${x},${y - r * 1.5} Z`} fill={RISING} />
            <Path d={`M${x - r * 0.35},${y + r} L${x},${y + r * 1.9} L${x + r * 0.35},${y + r} Z`} fill="#f6b54a" />
            <Circle cx={x} cy={y - r * 0.3} r={r * 0.28} fill={PAPER} />
            {label ? <SvgText x={Math.max(40, Math.min(width - 40, x))} y={ly} fontSize={9.5} fontWeight="700" fill={C.text} textAnchor="middle">{short(d.name, 18)}</SvgText> : null}
          </G>
        );
      })}
    </Svg>
  );
}

/** You at the bottom, your skills as spokes; closer = more of its preprints mention that skill (gui HorizonView). */
function Horizon({ dirs, pads, width }: { dirs: Aimed[]; pads: string[]; width: number }) {
  const H = 256, cy = H - 18, cx = width / 2, R = Math.min(width / 2 - 24, H - 44), rows = dirs.filter((d) => d.pad);
  const ang = (i: number) => Math.PI * (0.24 + 0.52 * (pads.length === 1 ? 0.5 : i / (pads.length - 1)));
  const topG = Math.max(1.5, ...rows.map((d) => d.growth));
  const seen: Record<string, number> = {}, placed: [number, number][] = [];
  const arc = (f: number) => `M${cx - R * f},${cy} A${R * f},${R * f} 0 0 1 ${cx + R * f},${cy}`;
  return (
    <Svg width={width} height={H}>
      {([[0.33, 'a short step'], [0.66, 'a stretch'], [1, 'a leap']] as [number, string][]).map(([f, w]) => (
        <G key={w}>
          <Path d={arc(f)} fill="none" stroke={C.muted} strokeOpacity={0.6} strokeDasharray={f < 1 ? '2 4' : undefined} />
          <SvgText x={cx + R * f} y={cy + 12} fontSize={9} fill={C.muted} textAnchor="middle">{w}</SvgText>
        </G>
      ))}
      {pads.map((name, i) => {
        const a = ang(i);
        return (
          <G key={name}>
            <Line x1={cx} y1={cy} x2={cx - Math.cos(a) * R} y2={cy - Math.sin(a) * R} stroke={YOURS} strokeOpacity={0.3} />
            <SvgText x={Math.max(40, Math.min(width - 40, cx - Math.cos(a) * (R + 10)))} y={cy - Math.sin(a) * (R + 10) - 2} fontSize={10} fontWeight="700" fill={YOURS} textAnchor="middle">{short(name, 13)}</SvgText>
          </G>
        );
      })}
      <Circle cx={cx} cy={cy} r={13} fill={BOTH} fillOpacity={0.2} stroke={BOTH} strokeWidth={1.5} />
      <SvgText x={cx} y={cy + 4} fontSize={10} fontWeight="800" fill={C.text} textAnchor="middle">you</SvgText>
      {rows.map((d) => {
        const k = (seen[d.pad] = (seen[d.pad] ?? -1) + 1);
        const a = ang(pads.indexOf(d.pad)) + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 0.13;
        const dist = 0.22 + 0.78 * (1 - d.closeness), x = cx - Math.cos(a) * R * dist, y = cy - Math.sin(a) * R * dist;
        const r = 4 + (6 * Math.log(Math.max(d.growth, 1))) / Math.log(topG), ly = y - r - 5;
        const label = !placed.some(([p, q]) => Math.abs(p - x) < 74 && Math.abs(q - ly) < 11);
        if (label) placed.push([x, ly]);
        return (
          <G key={d.name}>
            <Circle cx={x} cy={y} r={r} fill={RISING} stroke={PAPER} strokeWidth={1.5} />
            {label ? <SvgText x={Math.max(40, Math.min(width - 40, x))} y={ly} fontSize={9.5} fill={C.text} textAnchor="middle">{short(d.name, 16)}</SvgText> : null}
          </G>
        );
      })}
    </Svg>
  );
}

function Ladder({ ladder, width }: { ladder: Shapes['ladder']; width: number }) {
  const { left, right, links } = ladder;
  const H = 24 + 21 * Math.max(left.length, right.length, 2), lx = width * 0.36, rx = width * 0.6, mid = (lx + rx) / 2;
  const ly = column(left.length, 26, H - 34), ry = column(right.length, 26, H - 34);
  const top = Math.max(1, ...links.map((l: Link) => l[2]));
  return (
    <Svg width={width} height={H}>
      <SvgText x={lx} y={10} fontSize={9} fontWeight="800" fill={C.muted} textAnchor="end">YOURS, RISING</SvgText>
      <SvgText x={rx} y={10} fontSize={9} fontWeight="800" fill={C.muted}>NEW, RISING</SvgText>
      {links.map(([a, b, k]) => {
        const y1 = ly[left.indexOf(a)], y2 = ry[right.indexOf(b)];
        return <Path key={`${a}>${b}`} d={`M${lx},${y1} C${mid},${y1} ${mid},${y2} ${rx},${y2}`} fill="none" stroke={RISING}
                     strokeOpacity={0.2 + (0.6 * k) / top} strokeWidth={1 + (4 * k) / top} />;
      })}
      {left.map((n, i) => (
        <G key={`l${n}`}>
          <Circle cx={lx} cy={ly[i]} r={4} fill={BOTH} />
          <SvgText x={lx - 9} y={ly[i] + 3.5} fontSize={10.5} fill={C.text} textAnchor="end">{short(n, 17)}</SvgText>
        </G>
      ))}
      {right.map((n, i) => (
        <G key={`r${n}`}>
          <Circle cx={rx} cy={ry[i]} r={4} fill={RISING} />
          <SvgText x={rx + 9} y={ry[i] + 3.5} fontSize={10.5} fill={C.text}>{short(n, 17)}</SvgText>
        </G>
      ))}
    </Svg>
  );
}

function Lens({ lens, width }: { lens: Shapes['lens']; width: number }) {
  const ROW = 21;
  const rows = [...(lens.mine.length ? [{ head: 'YOU SEE MORE' }, ...lens.mine.map((r) => ({ r }))] : []),   // an empty half gets no heading
    ...(lens.world.length ? [{ head: 'THE WORLD SEES MORE' }, ...lens.world.map((r) => ({ r }))] : [])] as
    ({ head: string; r?: undefined } | { r: Shapes['lens']['mine'][number]; head?: undefined })[];
  const top = Math.max(1e-9, ...[...lens.mine, ...lens.world].flatMap((r) => [r.mine, r.world]));
  const x0 = width * 0.42, w = width * 0.54;
  return (
    <Svg width={width} height={ROW * rows.length + 4}>
      {rows.map((row, i) => {
        const y = i * ROW + ROW / 2;
        if (row.head) return <SvgText key={row.head} x={0} y={y + 5} fontSize={9} fontWeight="800" fill={C.muted}>{row.head}</SvgText>;
        const r = row.r!, xm = x0 + (r.mine / top) * w, xw = x0 + (r.world / top) * w;
        return (
          <G key={r.name}>
            <SvgText x={x0 - 10} y={y + 3.5} fontSize={10.5} fill={r.yours ? BOTH : C.text} textAnchor="end">{short(r.name, 18)}</SvgText>
            <Line x1={xm} x2={xw} y1={y} y2={y} stroke={C.muted} strokeWidth={2} strokeOpacity={0.5} />
            <Circle cx={xm} cy={y} r={4.5} fill={YOURS} />
            <Circle cx={xw} cy={y} r={4.5} fill={RISING} />
          </G>
        );
      })}
    </Svg>
  );
}

export function SkillViews({ shapes, onPath, started }: { shapes: Shapes; onPath?: (name: string) => void; started?: Set<string> }) {
  const [width, setWidth] = useState(0);
  const top = Math.max(1, ...shapes.next.map((n) => n.weight));
  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
      {width > 0 && shapes.directions.length && shapes.aim.pads.length ? <>
        <Text style={st.head}>🚀 DIRECTIONS</Text>
        <Text style={st.muted}>Where your field is heading: rising for sure across new preprints, and tied to what you know, even if your feed hasn&apos;t shown them yet. Each rocket launches from the skill of yours it&apos;s most tied to: higher grows faster, bigger has more preprints.</Text>
        <LaunchPad dirs={shapes.directions} pads={shapes.aim.pads} width={width} />
        {shapes.aim.bands.length ? <>
          <Text style={[st.muted, { marginTop: 8 }]}>Which of your skills lead where: bands as wide as the preprints that mention both.</Text>
          <Flow flow={shapes.aim} width={width} />
        </> : null}
        <Text style={[st.muted, { marginTop: 8 }]}>How far each is from you: the closer, the more of its preprints mention that skill of yours.</Text>
        <Horizon dirs={shapes.directions} pads={shapes.aim.pads} width={width} />
      </> : null}
      {shapes.next.length ? <>
        <Text style={st.head}>🧭 NEXT STEPS</Text>
        <Text style={st.muted}>What to learn, and the skill of yours that leads there.</Text>
        {shapes.next.map((n, i) => (
          <View key={n.name} style={st.step}>
            <Text style={st.num}>{i + 1}</Text>
            <View style={{ flex: 1 }}>
              <Text style={st.name}>{n.name}{n.beyond ? <Text style={st.tag}>  🌍 beyond your usual</Text> : n.sure ? <Text style={st.tag}>  📈 sure it&apos;s rising</Text> : null}</Text>
              <Text style={st.muted}>{n.via ? `via ${n.via}${n.more ? ` and ${n.more} more of yours` : ''}` : 'nothing of yours leads here yet'}</Text>
            </View>
            <View style={st.track}><View style={[st.fill, { width: `${Math.round((100 * n.weight) / top)}%` }]} /></View>
          </View>
        ))}
      </> : null}
      {width > 0 && shapes.flow.bands.length ? <>
        <Text style={st.head}>🌉 BRIDGES FROM WHAT YOU KNOW</Text>
        <Text style={st.muted}>Wider bands: more documents mention both.</Text>
        <Flow flow={shapes.flow} width={width} />
      </> : null}
      {width > 0 && shapes.ladder.left.length && shapes.ladder.links.length ? <>
        <Text style={st.head}>🪜 RISING WITH YOU</Text>
        <Text style={st.muted}>Your skills that are rising too, and the new ones they appear with.</Text>
        <Ladder ladder={shapes.ladder} width={width} />
      </> : null}
      {width > 0 && (shapes.lens.mine.length || shapes.lens.world.length) ? <>
        <Text style={st.head}>🔍 YOUR LENS</Text>
        <Text style={st.muted}>How often a skill shows in what myGeeKy reads for you, against new preprints across the field. A wide gap is your bubble: rising skills are measured on the world&apos;s side.</Text>
        <View style={st.legend}>
          <Text style={st.muted}><Text style={{ color: YOURS }}>●</Text> your feed   <Text style={{ color: RISING }}>●</Text> the world   <Text style={{ color: BOTH }}>●</Text> names in green are yours</Text>
        </View>
        <Lens lens={shapes.lens} width={width} />
      </> : null}
      {onPath && (shapes.directions.length || shapes.next.length) ? <>
        <Text style={st.head}>🧭 START A PROTOCOL</Text>
        <Text style={st.muted}>Turn a direction or a next step into stages you can follow.</Text>
        {[...shapes.directions.map((d) => ({ name: d.name, why: d.line, chip: `×${d.growth}` })),
          ...shapes.next.map((n) => ({ name: n.name, chip: '',
            why: n.via ? `via ${n.via}${n.more ? ` and ${n.more} more of yours` : ''}` : 'nothing of yours leads here yet' }))].map((x) => {
          const done = !!started?.has(x.name);
          return (
            <View key={x.name} style={st.dir}>
              <View style={st.dirTop}>
                <Text style={[st.name, { flex: 1 }]}>{x.name}</Text>
                {x.chip ? <Text style={st.growth}>{x.chip}</Text> : null}
              </View>
              <Text style={st.muted}>{x.why}</Text>
              <Pressable disabled={done} onPress={() => onPath(x.name)} style={({ pressed }) => [st.btn, (pressed || done) && { opacity: 0.6 }]}>
                <Text style={st.btnText}>{done ? '✓ In your protocols' : '🧭 Make it a protocol'}</Text>
              </Pressable>
            </View>
          );
        })}
      </> : null}
    </View>
  );
}

const st = StyleSheet.create({
  head: { color: C.text, fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, marginTop: 16, marginBottom: 2 },
  muted: { color: C.muted, fontSize: 12, marginBottom: 4 },
  step: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.line },
  num: { color: C.muted, fontSize: 11, width: 14 },
  name: { color: C.text, fontSize: 13.5, fontWeight: '700' },
  tag: { color: C.green, fontSize: 11.5, fontWeight: '600' },
  track: { width: 54, height: 7, borderRadius: 4, backgroundColor: C.line, overflow: 'hidden' },
  fill: { height: 7, borderRadius: 4, backgroundColor: RISING },
  legend: { marginBottom: 2 },
  dir: { backgroundColor: C.card, borderLeftWidth: 3, borderLeftColor: RISING, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, marginBottom: 6 },
  dirTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  growth: { color: RISING, fontSize: 12.5, fontWeight: '800' },
  btn: { alignSelf: 'flex-start', backgroundColor: C.cardHi, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, marginTop: 2 },
  btnText: { color: C.text, fontSize: 12, fontWeight: '700' },
});
