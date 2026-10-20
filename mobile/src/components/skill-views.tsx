// Grow → Skills, drawn: next steps, bridges (a flow from your skills to rising ones), the ladder (your rising
// strengths joined to new rising skills) and your lens (what your feed sees against the world) -- the desktop's
// gui/skillviews_ui.py. lib/skills.ts shapes() works out every number (the same as skills.shapes).
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import type { Link, Shapes } from '../lib/skills';
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

export function SkillViews({ shapes }: { shapes: Shapes }) {
  const [width, setWidth] = useState(0);
  const top = Math.max(1, ...shapes.next.map((n) => n.weight));
  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
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
});
