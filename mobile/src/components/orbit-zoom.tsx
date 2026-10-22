// The orbit, zoomed: the level you're at in the centre, its planets around it (lib/nav-tree.ts). Tap a planet with
// parts and it flies to the centre while its parts circle around it; tap a page to open it. Going back is always
// clear: a coloured "‹ Back to World" at the top left, the trail beside it (tap any step), and an ↑ on the centre
// planet, which goes up a level too. The panel's planet row moves the same way (qt_panel.py _nav_tap).
// A planet that opens into more parts wears a slowly turning dotted ring (components/dashed-orbit.tsx); in the centre it
// doesn't.
import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { level, path, type Node } from '../lib/nav-tree';
import { DashedOrbit, RING_GAP, useOrbitSpin } from './dashed-orbit';
import { C, tint } from '../lib/theme';

/** The orbit's height for a screen width: the rings take this share, the rest is for the list. */
export function orbitHeight(width: number) {
  return Math.round(410 * (width / 390) * 0.765);
}

export const darker = (hex: string) => {
  const n = parseInt(hex.slice(1), 16), k = 0.62;
  const ch = (s: number) => Math.round(((n >> s) & 255) * k).toString(16).padStart(2, '0');
  return `#${ch(16)}${ch(8)}${ch(0)}`;
};

export function OrbitZoom({ width, height, at, open, counts, onTap, onJump, youLetter, hint }: {
  width: number; height: number; at: Node; open: Node | null; counts: Record<string, number>;
  onTap: (id: string) => void; onJump: (id: string) => void; youLetter: string; hint: boolean;
}) {
  const lvl = level(at);
  const spin = useOrbitSpin();
  const onPath = new Set(path(open).map((n) => n.id));
  const trail = path(at);
  const cx = width / 2, cy = height / 2 + 18;
  const R = Math.min(width * 0.33, (height - 70) * 0.42);
  const P = Math.round(Math.max(44, Math.min(54, width * 0.13)));
  const center = Math.round(P * 1.35);
  // a crowded ring (Data has 11 fields): planets and labels shrink to the room each one has on the circle
  const gap = (2 * Math.PI * R) / Math.max(at.children.length, 1);
  const p = Math.round(Math.max(34, Math.min(P, gap * 0.6))), labelW = Math.round(Math.min(88, gap * 1.15));
  const root = !at.parent;
  return (
    <View style={{ width, height }}>
      <View pointerEvents="none" style={[st.ring, { left: cx - R, top: cy - R, width: 2 * R, height: 2 * R, borderRadius: R }]} />

      <View style={st.nav}>
        {lvl.back ? (
          <Pressable onPress={() => onTap('back')} style={({ pressed }) => [st.back, { backgroundColor: darker(lvl.back!.color) }, pressed && { opacity: 0.8 }]}
                     accessibilityRole="button" accessibilityLabel={`Back to ${lvl.back.label}`} hitSlop={6}>
            <View style={st.backIcon}><Ionicons name="chevron-back" size={14} color="#fff" /></View>
            <Text style={st.backText} numberOfLines={1}>Back to {lvl.back.label}</Text>
          </Pressable>
        ) : null}
        <Text style={st.trail} numberOfLines={1}>
          {trail.map((n, i) => (
            <Text key={n.id}>
              {i ? ' › ' : ''}
              <Text onPress={() => onJump(n.id)} style={i === trail.length - 1 ? st.here : null}>{i ? n.label : 'Home'}</Text>
            </Text>
          ))}
        </Text>
      </View>

      <Pressable onPress={() => !root && onTap('back')} disabled={root}
                 accessibilityRole="button" accessibilityLabel={root ? 'Home' : `${at.label}: tap to go back to ${lvl.back?.label}`}
                 style={[st.center, { left: cx - center / 2, top: cy - center / 2, width: center, height: center, borderRadius: center / 2,
                                      borderColor: at.color, shadowColor: at.color }]}>
        {root ? <>
          <Text style={{ color: C.text, fontSize: 22, fontWeight: '800' }}>{youLetter}</Text>
          <Text style={st.youText}>HOME</Text>
        </> : <Ionicons name={at.icon as never} size={Math.round(center * 0.42)} color={at.color} />}
        {!root ? <View style={st.up}><Ionicons name="arrow-up" size={12} color={C.bg} /></View> : null}
      </Pressable>
      {!root ? <Text pointerEvents="none" style={[st.centerLabel, { left: cx - 60, top: cy + center / 2 + 3 }]} numberOfLines={1}>{at.label}</Text> : null}

      {at.children.map((n, i) => {
        const a = -Math.PI / 2 + (i / at.children.length) * Math.PI * 2;
        const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
        const on = onPath.has(n.id);
        const count = counts[n.id] ?? 0;
        return (
          <Pressable key={n.id} onPress={() => onTap(n.id)} accessibilityRole="button"
                     accessibilityLabel={`${n.label}${count ? `, ${count} new` : ''}${n.children.length ? `, ${n.children.length} parts` : ''}`}
                     style={{ position: 'absolute', left: x - labelW / 2, top: y - p / 2, width: labelW, alignItems: 'center' }}>
            <View style={[st.planet, { width: p, height: p, borderRadius: p / 2, borderColor: n.color, backgroundColor: on ? n.color : C.raised },
                          on && { shadowColor: n.color, shadowOpacity: 0.8, shadowRadius: 12, elevation: 8 }]}>
              {n.children.length ? <DashedOrbit size={p} color={n.color} spin={spin} /> : null}
              <Ionicons name={n.icon as never} size={Math.round(p * 0.44)} color={on ? '#0d0d16' : n.color} />
              {count ? <View style={st.count}><Text style={st.countText}>{count > 99 ? '99+' : count}</Text></View> : null}
            </View>
            <Text style={[st.label, on && { color: C.text }, p < P && { fontSize: 11 }, n.children.length > 0 && { marginTop: 3 + RING_GAP }]} numberOfLines={1}>{n.label}</Text>
          </Pressable>
        );
      })}

      {hint ? (
        <View pointerEvents="none" style={[st.hint, { left: cx - 110, top: height - 30 }]}>
          <Text style={st.hintText}>{root ? 'Tap a planet to go in' : 'Tap a planet · ↑ goes back'}</Text>
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  ring: { position: 'absolute', borderWidth: 1, borderStyle: 'dashed', borderColor: tint(0.16) },
  nav: { position: 'absolute', left: 12, right: 12, top: 6, flexDirection: 'row', alignItems: 'center', gap: 8, zIndex: 2 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 5, paddingRight: 12, paddingVertical: 5, borderRadius: 999,
    shadowColor: '#000', shadowOpacity: 0.3, shadowRadius: 8, elevation: 4 },
  backIcon: { width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(255,255,255,0.25)', alignItems: 'center', justifyContent: 'center' },
  backText: { color: '#fff', fontSize: 13, fontWeight: '800' },
  trail: { flex: 1, color: C.muted, fontSize: 11.5 },
  here: { color: C.text, fontWeight: '800' },
  center: { position: 'absolute', borderWidth: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: C.raised,
    shadowOpacity: 0.7, shadowRadius: 18, elevation: 10 },
  youText: { color: C.muted, fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  up: { position: 'absolute', top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: C.text, alignItems: 'center', justifyContent: 'center' },
  centerLabel: { position: 'absolute', width: 120, textAlign: 'center', color: C.text, fontSize: 12, fontWeight: '800' },
  planet: { borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  count: { position: 'absolute', top: -5, right: -7, minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9,
    backgroundColor: C.text, alignItems: 'center', justifyContent: 'center' },
  countText: { color: C.bg, fontSize: 10, fontWeight: '800' },
  label: { color: C.muted, fontSize: 11, fontWeight: '700', marginTop: 3 },
  hint: { position: 'absolute', width: 220, borderRadius: 999, backgroundColor: C.text, paddingVertical: 6, alignItems: 'center' },
  hintText: { color: C.bg, fontSize: 12, fontWeight: '700' },
});
