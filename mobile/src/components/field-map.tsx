// "Your field": everyone on Signals and every call that fits you, placed by how close they are
// to your work. Folded, a thin ruler (calls above the line, people below; further right =
// closer). Unfolded, a radar with you in the middle. Tap a dot to open it. Same layout as the
// desktop (src/mygeeky/gui/signals_ui.py).
import { useState } from 'react';
import { Image, type LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { C, ink } from '../lib/theme';

export type Dot = { id: string; login: string; label: string; fit: number; call: boolean };

const PALETTE = ['#ff6fd8', '#8b6dff', '#4fd1ff', '#3ddc97', '#f6b44a', '#ff8f6b'];
const colorOf = (s: string) => PALETTE[[...s].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];
const initials = (s: string) => s.replace(/[-_]/g, ' ').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
const ME = require('../../assets/icon.png');

const FOLDED = 62;
const R = 8;

function rulerSpots(dots: Dot[], w: number, h: number) {
  const left = 26;
  const right = w - 26;
  const mid = h / 2;
  const out: { dot: Dot; x: number; y: number }[] = [];
  for (const [isCall, rows] of [[true, [mid - 11, mid - 25]], [false, [mid + 11, mid + 25]]] as const) {
    const ends = rows.map(() => -1e9);
    for (const dot of dots.filter((d) => d.call === isCall).sort((a, b) => a.fit - b.fit)) {
      const x = left + Math.min(Math.max(dot.fit, 0), 0.97) * (right - left);
      let row = ends.findIndex((e) => x - e >= 2 * R + 3);
      if (row < 0) row = ends.indexOf(Math.min(...ends));
      ends[row] = x;
      out.push({ dot, x, y: Math.max(R + 1, Math.min(h - R - 1, rows[row])) });
    }
  }
  return out;
}

function radarSpots(dots: Dot[], size: number) {
  const c = size / 2;
  const radius = size / 2 - 14;
  return dots.map((dot, k) => {
    const dist = radius * (0.2 + 0.78 * (1 - Math.min(Math.max(dot.fit, 0), 1)));
    const a = ((k * 137.5 + 20) * Math.PI) / 180;
    return { dot, x: c + dist * Math.cos(a), y: c + dist * Math.sin(a) };
  });
}

export function FieldMap({ dots, selected, unfolded, onPick }: {
  dots: Dot[]; selected: string | null; unfolded: boolean; onPick: (id: string | null) => void;
}) {
  const [w, setW] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width);
  const size = Math.min(w, 320);
  const h = unfolded ? size : FOLDED;
  const spots = w ? (unfolded ? radarSpots(dots, size) : rulerSpots(dots, w, FOLDED)) : [];
  const r = unfolded ? R + 3 : R;
  return (
    <View onLayout={onLayout} style={{ height: h, alignItems: unfolded ? 'center' : undefined }}>
      {w ? (
        <View style={{ width: unfolded ? size : w, height: h }}>
          {unfolded ? (
            <>
              {[1, 0.75, 0.5, 0.25].map((f) => (
                <View key={f} style={[st.ring, { width: (size - 28) * f, height: (size - 28) * f, borderRadius: size,
                  left: size / 2 - ((size - 28) * f) / 2, top: size / 2 - ((size - 28) * f) / 2 }]} />
              ))}
              <Image source={ME} style={[st.me, { left: size / 2 - 17, top: size / 2 - 17 }]} />
            </>
          ) : (
            <>
              <View style={[st.axis, { left: 26, right: 26, top: FOLDED / 2 - 1 }]} />
              {[0.25, 0.5, 0.75].map((f) => <View key={f} style={[st.tick, { left: 26 + f * (w - 52), top: FOLDED / 2 - 4 }]} />)}
              <Text style={[st.far, { top: FOLDED / 2 - 7 }]}>far</Text>
              <Image source={ME} style={[st.meSmall, { left: w - 23, top: FOLDED / 2 - 9 }]} />
            </>
          )}
          {spots.map(({ dot, x, y }) => (
            <Pressable key={dot.id} onPress={() => onPick(selected === dot.id ? null : dot.id)} hitSlop={6}
                       accessibilityLabel={`${dot.call ? 'Project calling' : 'Person'}: ${dot.label}, ${Math.round(dot.fit * 100)}% fit`}
                       style={[st.dot, { left: x - r, top: y - r, width: 2 * r, height: 2 * r, borderRadius: dot.call ? 4 : r,
                         backgroundColor: colorOf(dot.login), borderColor: selected === dot.id ? C.pink : C.bg,
                         borderWidth: selected === dot.id ? 2 : 1 }]}>
              <Text style={[st.ini, { fontSize: r * 0.8 }]}>{initials(dot.login)}</Text>
            </Pressable>
          ))}
          {!dots.length ? <Text style={st.none}>Nobody on Signals yet</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  axis: { position: 'absolute', height: 2, borderRadius: 1, backgroundColor: 'rgba(139,109,255,0.7)' },
  tick: { position: 'absolute', width: 1, height: 8, backgroundColor: ink(0.3) },
  far: { position: 'absolute', left: 0, width: 24, textAlign: 'center', color: C.muted, fontSize: 9 },
  meSmall: { position: 'absolute', width: 18, height: 18, borderRadius: 9 },
  me: { position: 'absolute', width: 34, height: 34, borderRadius: 17 },
  ring: { position: 'absolute', borderWidth: 1, borderStyle: 'dashed', borderColor: ink(0.16) },
  dot: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  ini: { color: '#15151f', fontWeight: '800' },
  none: { position: 'absolute', left: 0, right: 0, top: 22, textAlign: 'center', color: C.muted, fontSize: 12 },
});
