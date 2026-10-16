// The rest of the desktop's Model tab (src/mygeeky/gui/qt_panel.py): the stat tiles, the room-to-
// explore donut, the follow-back AUC gauge, what the model weighs and how it got sharper over time.
import { useState } from 'react';
import { type LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop, Text as SvgText } from 'react-native-svg';
import { MAP_EXPLORE } from './interest-map';
import { timeAgo } from './ui';
import type { Brain } from '../lib/model-repo';
import { C } from '../lib/theme';

const ACCENT = C.cyan;

// gui/app.py: auc_verdict, and qt_panel.py: _auc_color
export function aucVerdict(auc: number | null): [string, string] {
  if (auc === null) return ['Untrained', 'Run mygeeky bootstrap to teach it who follows back.'];
  if (auc >= 0.8) return ['Sharp', 'Reliably tells who will follow you back.'];
  if (auc >= 0.7) return ['Good', 'Clearly better than chance at spotting follow-backs.'];
  if (auc >= 0.6) return ['Learning', 'Some signal -- more follow-backs will sharpen it.'];
  return ['Early', 'Barely above a coin flip; keep running mygeeky learn.'];
}
const aucColor = (auc: number | null) =>
  auc === null ? '#9ca3af' : auc >= 0.8 ? '#34d399' : auc >= 0.7 ? '#60a5fa' : auc >= 0.6 ? '#fbbf24' : '#f87171';

export function StatTiles({ tiles }: { tiles: [string, string][] }) {
  return (
    <View style={st.tiles}>
      {tiles.map(([value, caption]) => (
        <View key={caption} style={st.tile}>
          <Text style={st.tileValue}>{value}</Text>
          <Text style={st.tileCaption}>{caption}</Text>
        </View>
      ))}
    </View>
  );
}

function Ring({ size, stroke, share, color, children }: { size: number; stroke: number; share: number; color: string; children: React.ReactNode }) {
  const r = (size - 16) / 2;
  const c = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.12)" strokeWidth={stroke} fill="none" />
        {share > 0 ? (
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
                  strokeDasharray={`${c} ${c}`} strokeDashoffset={c * (1 - Math.min(share, 1))}
                  transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        ) : null}
      </Svg>
      {children}
    </View>
  );
}

export function ExploreDonut({ share }: { share: number }) {
  return (
    <Ring size={84} stroke={9} share={share} color={MAP_EXPLORE}>
      <Text style={st.donutText}>{Math.round(share * 100)}%</Text>
    </Ring>
  );
}

export function AucGauge({ auc }: { auc: number | null }) {
  return (
    <Ring size={112} stroke={9} share={auc ?? 0} color={aucColor(auc)}>
      <Text style={st.gaugeValue}>{auc === null ? '–' : auc.toFixed(3)}</Text>
      <Text style={st.gaugeCaption}>AUC</Text>
    </Ring>
  );
}

/** Diverging bars: right makes a follow-back more likely, left less. */
export function WeightBars({ weights }: { weights: Brain['weights'] }) {
  const [w, setW] = useState(0);
  if (!weights.length) return <Text style={st.muted}>No trained model yet.</Text>;
  const ROW = 24;
  const labelW = w * 0.42;
  const mid = labelW + (w - labelW) / 2;
  const half = (w - labelW) / 2 - 34;
  const biggest = Math.max(...weights.map((x) => Math.abs(x.weight))) || 1;
  return (
    <View onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)} style={{ height: weights.length * ROW + 4 }}>
      {w ? (
        <Svg width={w} height={weights.length * ROW + 4}>
          <Defs>
            <LinearGradient id="pos" x1="0" y1="0" x2="1" y2="0"><Stop offset="0" stopColor={ACCENT} stopOpacity="0.43" /><Stop offset="1" stopColor={ACCENT} /></LinearGradient>
            <LinearGradient id="neg" x1="1" y1="0" x2="0" y2="0"><Stop offset="0" stopColor={C.red} stopOpacity="0.43" /><Stop offset="1" stopColor={C.red} /></LinearGradient>
          </Defs>
          {weights.map((item, i) => {
            const y = i * ROW + 2;
            const positive = item.weight >= 0;
            const len = (half * Math.abs(item.weight)) / biggest;
            return [
              <SvgText key={`l${item.feature}`} x={0} y={y + ROW / 2 + 4} fill={C.text} fontSize={11}>{item.label}</SvgText>,
              <Rect key={`b${item.feature}`} x={positive ? mid : mid - len} y={y + 6} width={len} height={ROW - 12} rx={4}
                    fill={`url(#${positive ? 'pos' : 'neg'})`} />,
              <SvgText key={`v${item.feature}`} x={positive ? mid + len + 4 : mid - len - 4} y={y + ROW / 2 + 4}
                       fill={C.muted} fontSize={11} textAnchor={positive ? 'start' : 'end'}>
                {`${item.weight >= 0 ? '+' : ''}${item.weight.toFixed(2)}`}
              </SvgText>,
            ];
          })}
          <Line x1={mid} y1={0} x2={mid} y2={weights.length * ROW + 4} stroke="rgba(240,240,245,0.24)" strokeWidth={1} />
        </Svg>
      ) : null}
    </View>
  );
}

const shortDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

/** AUC over retrains: a smooth line over faint training-set-size bars, the coin-flip line, tap a point. */
export function TrendChart({ history }: { history: Brain['history'] }) {
  const [w, setW] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const rows = history.filter((h) => h.auc !== null) as (Brain['history'][number] & { auc: number })[];
  if (!rows.length) return <Text style={st.muted}>No retrains yet to chart</Text>;
  const H = 150;
  const [left, right, top, bottom] = [34, 10, 12, 18];
  const points = rows.map((h) => h.auc);
  let lo = Math.min(...points, 0.5) - 0.03;
  let hi = Math.max(...points) + 0.03;
  if (hi - lo < 0.1) hi = lo + 0.1;
  lo = Math.max(0, lo);
  hi = Math.min(1, hi);
  const plotH = H - top - bottom;
  const n = rows.length;
  const xs = rows.map((_, i) => (n === 1 ? left + (w - left - right) / 2 : left + (i / (n - 1)) * (w - left - right)));
  const ys = points.map((p) => top + (1 - (p - lo) / (hi - lo)) * plotH);
  let line = `M${xs[0]},${ys[0]}`;
  for (let i = 1; i < n; i++) {
    const cx = (xs[i - 1] + xs[i]) / 2;
    line += ` C${cx},${ys[i - 1]} ${cx},${ys[i]} ${xs[i]},${ys[i]}`;
  }
  const area = `${line} L${xs[n - 1]},${top + plotH} L${xs[0]},${top + plotH} Z`;
  const biggest = Math.max(...rows.map((h) => h.n_train), 1);
  const barW = Math.max(4, Math.min(18, ((w - left - right) / n) * 0.35));
  const chanceY = top + (1 - (0.5 - lo) / (hi - lo)) * plotH;
  const sel = picked !== null && picked < n ? rows[picked] : null;
  return (
    <>
      <View onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)} style={{ height: H }}
            onStartShouldSetResponder={() => true}
            onResponderRelease={(e) => {
              const x = e.nativeEvent.locationX;
              setPicked(xs.reduce((best, xi, i) => (Math.abs(xi - x) < Math.abs(xs[best] - x) ? i : best), 0));
            }}>
        {w ? (
          <Svg width={w} height={H}>
            <Defs>
              <LinearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><Stop offset="0" stopColor={ACCENT} stopOpacity="0.43" /><Stop offset="1" stopColor={ACCENT} stopOpacity="0" /></LinearGradient>
            </Defs>
            {[0, 1, 2].map((k) => {
              const y = top + (1 - k / 2) * plotH;
              return [
                <Line key={`g${k}`} x1={left} y1={y} x2={w - right} y2={y} stroke="rgba(240,240,245,0.10)" strokeWidth={1} />,
                <SvgText key={`t${k}`} x={left - 6} y={y + 3} fill={C.muted} fontSize={10} textAnchor="end">{(lo + ((hi - lo) * k) / 2).toFixed(2)}</SvgText>,
              ];
            })}
            {lo <= 0.5 && hi >= 0.5 ? [
              <Line key="chance" x1={left} y1={chanceY} x2={w - right} y2={chanceY} stroke={C.muted} strokeWidth={1} strokeDasharray="4 3" />,
              <SvgText key="chanceT" x={left + 4} y={chanceY - 4} fill={C.muted} fontSize={10}>chance</SvgText>,
            ] : null}
            {rows.map((h, i) => {
              const bh = (plotH * 0.45 * h.n_train) / biggest;
              return <Rect key={`bar${i}`} x={xs[i] - barW / 2} y={top + plotH - bh} width={barW} height={bh} rx={2} fill={ACCENT} fillOpacity={0.1} />;
            })}
            {n > 1 ? <Path d={area} fill="url(#fill)" /> : null}
            {n > 1 ? <Path d={line} stroke={ACCENT} strokeWidth={2.5} fill="none" strokeLinecap="round" strokeLinejoin="round" /> : null}
            {xs.map((x, i) => <Circle key={`p${i}`} cx={x} cy={ys[i]} r={i === n - 1 ? 4.5 : 3} fill={ACCENT} />)}
            <Circle cx={xs[n - 1]} cy={ys[n - 1]} r={9} fill={ACCENT} fillOpacity={0.2} />
            {picked !== null && picked < n ? <Circle cx={xs[picked]} cy={ys[picked]} r={6} stroke={C.text} strokeWidth={1.5} fill="none" /> : null}
            <SvgText x={left} y={H - 3} fill={C.muted} fontSize={10}>{shortDate(rows[0].timestamp)}</SvgText>
            {n > 1 ? <SvgText x={w - right} y={H - 3} fill={C.muted} fontSize={10} textAnchor="end">{shortDate(rows[n - 1].timestamp)}</SvgText> : null}
          </Svg>
        ) : null}
      </View>
      {sel ? (
        <Text style={st.muted}>
          {`${shortDate(sel.timestamp)} (${timeAgo(sel.timestamp)}): AUC ${sel.auc.toFixed(3)} from ${sel.n_train} examples, ${sel.n_pos} follow-backs`}
        </Text>
      ) : null}
    </>
  );
}

const st = StyleSheet.create({
  tiles: { flexDirection: 'row', gap: 6, marginTop: 4 },
  tile: { flex: 1, backgroundColor: C.card, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 6 },
  tileValue: { color: C.text, fontSize: 16, fontWeight: '600' },
  tileCaption: { color: C.muted, fontSize: 10 },
  donutText: { color: C.text, fontSize: 14, fontWeight: '700' },
  gaugeValue: { color: C.text, fontSize: 22, fontWeight: '700' },
  gaugeCaption: { color: C.muted, fontSize: 10 },
  muted: { color: C.muted, fontSize: 12, lineHeight: 17 },
});
