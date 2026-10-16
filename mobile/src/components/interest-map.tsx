// "Your interest map": you in the middle, your research field on the inner ring, what you're
// into lately on the middle ring (bigger = stronger, gently pulsing), and today's new territory on a
// dashed outer ring, all slowly turning. Tap a point for what it is. Same layout as the
// desktop (InterestMap in src/mygeeky/gui/qt_panel.py).
import { useEffect, useState } from 'react';
import { AccessibilityInfo, type LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { C } from '../lib/theme';

export const MAP_FIELD = '#7fd8ff';    // your research field
export const MAP_LEARNED = '#ff6fd8';  // what you're into lately
export const MAP_EXPLORE = '#9b87ff';  // today's new territory

type Node = { ring: 0 | 1 | 2; label: string; size: number; color: string; tip: string; angle: number };

const HEIGHT = 300;
const SQUASH = 0.86;
const SPEED = [0.05, -0.035, 0.022];
const FONT = 10;
const LINE = 13;
const textWidth = (s: string) => s.length * FONT * 0.56;   // no measuring pass: a close-enough estimate

// "Genetic Mapping and Diversity in ..." -> "Genetic Mapping"
const short = (topic: string) =>
  topic.split(/\s+/).filter((w) => !['and', 'in', 'of', 'the', 'for'].includes(w.toLowerCase())).slice(0, 2).join(' ');

function buildNodes(field: string[], learned: [string, number][], explore: string[]): Node[] {
  const top = Math.max(...learned.map(([, w]) => w), 0) || 1;
  const nodes: Omit<Node, 'angle'>[] = [
    ...field.slice(0, 6).map((t) => ({ ring: 0 as const, label: short(t), size: 8, color: MAP_FIELD,
      tip: `${t}\nYour research field (OpenAlex topics, Scholar interests, your topics)` })),
    ...learned.slice(0, 10).map(([t, w]) => ({ ring: 1 as const, label: t, size: 5 + 9 * (w / top), color: MAP_LEARNED,
      tip: `${t}\nWhat you're into lately: strength ${w}, learned from your clicks, follows, stars and forks` })),
    ...explore.slice(0, 4).map((t) => ({ ring: 2 as const, label: t, size: 6, color: MAP_EXPLORE,
      tip: `${t}\nNew territory today: outside your usual interests, on purpose` })),
  ];
  return nodes.map((n) => {
    const members = nodes.filter((m) => m.ring === n.ring);
    const step = (2 * Math.PI) / Math.max(members.length, 1);
    // each ring starts half a step further round, so labels fall between, not on top
    return { ...n, angle: step * members.indexOf(n) + (n.ring * step) / 2 + n.ring * 0.35 };
  });
}

type Rect = { l: number; t: number; r: number; b: number };
const hits = (a: Rect, b: Rect) => a.l < b.r + 2 && a.r > b.l - 2 && a.t < b.b + 1 && a.b > b.t - 1;

export function InterestMap({ center, field, learned, explore }: {
  center: string; field: string[]; learned: [string, number][]; explore: string[];
}) {
  const [w, setW] = useState(0);
  const [phase, setPhase] = useState(0);
  const [intro, setIntro] = useState(0);
  const [picked, setPicked] = useState<Node | null>(null);

  useEffect(() => {
    let still = false;
    let timer: ReturnType<typeof setInterval> | undefined;
    const started = Date.now();
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (still) return;
      if (reduce) { setIntro(1); return; }
      timer = setInterval(() => {
        const t = Math.min((Date.now() - started) / 1400, 1);
        setIntro(1 - (1 - t) ** 3);
        setPhase((p) => p + 0.05);
      }, 50);
    }).catch(() => setIntro(1));
    return () => { still = true; if (timer) clearInterval(timer); };
  }, []);

  const nodes = buildNodes(field, learned, explore);
  const cx = w / 2;
  const cy = HEIGHT / 2;
  const r = Math.min(w, HEIGHT) / 2 - 18;
  const radii = [r * 0.38, r * 0.72, r * 0.98];
  const placed = nodes.map((n) => {
    const a = n.angle + phase * SPEED[n.ring];
    const rr = radii[n.ring] * intro;
    const size = n.ring === 1 ? n.size * (1 + 0.12 * Math.sin(phase * 2.2 + n.angle * 3)) : n.size;
    return { n, x: cx + Math.cos(a) * rr, y: cy + Math.sin(a) * rr * SQUASH, size };
  });

  // labels last, so none collides with another label or a point: lately-into first, then new
  // territory, then your field; each tries outward, inward, above, below -- and a label with no
  // free spot is left to the tap rather than drawn on top of another
  const taken: Rect[] = placed.map(({ x, y, size }) => ({ l: x - size, t: y - size, r: x + size, b: y + size }));
  taken.push({ l: cx - 24, t: cy - 24, r: cx + 24, b: cy + 24 });
  const labels: { key: string; text: string; x: number; y: number; color: string }[] = [];
  for (const { n, x, y, size } of [...placed].sort((a, b) => [1, 2, 0].indexOf(a.n.ring) - [1, 2, 0].indexOf(b.n.ring))) {
    const text = n.label.length <= 20 ? n.label : `${n.label.slice(0, 19)}…`;
    const tw = textWidth(text);
    const outX = x >= cx ? x + size + 4 : x - size - 4 - tw;
    const inX = x >= cx ? x - size - 4 - tw : x + size + 4;
    const own = taken[placed.findIndex((p) => p.n === n)];
    for (const [lx, ly] of [[outX, y - LINE / 2], [inX, y - LINE / 2], [x - tw / 2, y - size - LINE - 1], [x - tw / 2, y + size + 1]]) {
      const rect = { l: lx, t: ly, r: lx + tw, b: ly + LINE };
      if (rect.l < 1 || rect.r > w - 1 || rect.t < 0 || rect.b > HEIGHT) continue;
      if (taken.some((o) => o !== own && hits(rect, o))) continue;
      taken.push(rect);
      labels.push({ key: `${n.ring}${n.label}`, text, x: lx, y: ly, color: n.ring < 2 ? C.text : MAP_EXPLORE });
      break;
    }
  }

  const initials = (center || 'you').replace(/-/g, ' ').split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]).join('').toUpperCase() || 'Y';
  return (
    <>
      <View onLayout={(e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width)} style={{ height: HEIGHT }}>
        {w ? (
          <>
            {radii.map((rad, i) => (
              <View key={`ring${i}`} style={[st.ring, {
                left: cx - rad * intro, top: cy - rad * intro, width: 2 * rad * intro, height: 2 * rad * intro, borderRadius: rad,
                borderStyle: i === 2 ? 'dashed' : 'solid', borderColor: i < 2 ? 'rgba(240,240,245,0.12)' : 'rgba(240,240,245,0.16)',
                transform: [{ scaleY: SQUASH }] }]} />
            ))}
            {/* threads from you to each point */}
            {placed.map(({ n, x, y }) => {
              const len = Math.hypot(x - cx, y - cy);
              return <View key={`thread${n.ring}${n.label}`} style={[st.thread, {
                left: (cx + x) / 2 - len / 2, top: (cy + y) / 2 - 0.5, width: len, backgroundColor: n.color,
                opacity: n.ring < 2 ? 0.16 : 0.11, transform: [{ rotate: `${Math.atan2(y - cy, x - cx)}rad` }] }]} />;
            })}
            {/* the points: a soft glow, a core */}
            {placed.map(({ n, x, y, size }) => (
              <Pressable key={`dot${n.ring}${n.label}`} onPress={() => setPicked(picked?.tip === n.tip ? null : n)} hitSlop={8}
                         accessibilityLabel={n.tip.replace('\n', ': ')}
                         style={[st.hit, { left: x - size * 2.6, top: y - size * 2.6, width: size * 5.2, height: size * 5.2 }]}>
                <View style={[st.glow, { width: size * 5.2, height: size * 5.2, borderRadius: size * 2.6, backgroundColor: n.color }]} />
                <View style={[st.glow, { width: size * 3.4, height: size * 3.4, borderRadius: size * 1.7, backgroundColor: n.color, opacity: 0.16 }]} />
                <View style={[{ width: 2 * size, height: 2 * size, borderRadius: size },
                  n.ring === 2 ? { borderWidth: 1.4, borderStyle: 'dashed', borderColor: n.color } : { backgroundColor: n.color },
                  picked?.tip === n.tip && st.pickedDot]} />
              </Pressable>
            ))}
            {labels.map((l) => (
              <Text key={l.key} pointerEvents="none" numberOfLines={1}
                    style={[st.label, { left: l.x, top: l.y, width: textWidth(l.text) + 8, color: l.color }]}>{l.text}</Text>
            ))}
            {/* you */}
            <View pointerEvents="none" style={[st.halo, { left: cx - 34, top: cy - 34 }]} />
            <View pointerEvents="none" style={[st.me, { left: cx - 16, top: cy - 16 }]}>
              <Text style={st.meText}>{initials.slice(0, 2)}</Text>
            </View>
          </>
        ) : null}
      </View>
      {picked ? <Text style={st.tip}>{picked.tip}</Text> : null}
    </>
  );
}

const st = StyleSheet.create({
  ring: { position: 'absolute', borderWidth: 1 },
  thread: { position: 'absolute', height: 1 },
  hit: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  glow: { position: 'absolute', opacity: 0.1 },
  pickedDot: { borderWidth: 2, borderColor: C.text },
  label: { position: 'absolute', fontSize: FONT, lineHeight: LINE },
  halo: { position: 'absolute', width: 68, height: 68, borderRadius: 34, backgroundColor: 'rgba(255,111,216,0.16)' },
  me: { position: 'absolute', width: 32, height: 32, borderRadius: 16, backgroundColor: C.pink, borderWidth: 2,
    borderColor: C.violet, alignItems: 'center', justifyContent: 'center' },
  meText: { color: '#ffffff', fontSize: 11, fontWeight: '800' },
  tip: { color: C.muted, fontSize: 12, lineHeight: 17, textAlign: 'center', marginTop: 4 },
});
