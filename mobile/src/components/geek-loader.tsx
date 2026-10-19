// While something loads: GeekOc swimming (a gentle bob and drift, bubbles rising) instead of a spinner, with a
// line saying what is happening. The desktop has the same (gui/geek_loader.py). Native-driver animations only,
// so it costs the JavaScript thread nothing while the real work runs.
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';
import { SvgXml } from 'react-native-svg';
import geekoc from '../data/geekoc.json';
import { C } from '../lib/theme';

const SWIM = `<svg viewBox="0 0 620 620">${(geekoc.poses as Record<string, string>).swim ?? ''}</svg>`;

function loop(value: Animated.Value, ms: number, delay = 0) {
  return Animated.loop(Animated.sequence([
    Animated.delay(delay),
    Animated.timing(value, { toValue: 1, duration: ms, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
    Animated.timing(value, { toValue: 0, duration: ms, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
  ]));
}

export function GeekLoader({ text = 'Loading…', size = 76 }: { text?: string; size?: number }) {
  const [{ bob, drift, bubbles }] = useState(() => ({
    bob: new Animated.Value(0), drift: new Animated.Value(0), bubbles: [0, 1, 2].map(() => new Animated.Value(0)) }));
  useEffect(() => {
    const all = [loop(bob, 700), loop(drift, 1500),
      ...bubbles.map((b, i) => Animated.loop(Animated.sequence([
        Animated.delay(i * 420),
        Animated.timing(b, { toValue: 1, duration: 1300, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.timing(b, { toValue: 0, duration: 0, useNativeDriver: true }),
      ])))];
    all.forEach((a) => a.start());
    return () => all.forEach((a) => a.stop());
  }, [bob, drift, bubbles]);
  const swim = {
    transform: [
      { translateY: bob.interpolate({ inputRange: [0, 1], outputRange: [-5, 5] }) },
      { translateX: drift.interpolate({ inputRange: [0, 1], outputRange: [-14, 14] }) },
      { rotate: drift.interpolate({ inputRange: [0, 1], outputRange: ['-6deg', '6deg'] }) },
    ],
  };
  return (
    <View style={st.box} accessibilityRole="progressbar" accessibilityLabel={text}>
      <View style={{ width: size + 40, height: size + 16, alignItems: 'center', justifyContent: 'center' }}>
        {bubbles.map((b, i) => (
          <Animated.View key={i} style={[st.bubble, { left: size / 2 + 20 + (i - 1) * 12, width: 6 + i * 2, height: 6 + i * 2,
            opacity: b.interpolate({ inputRange: [0, 0.2, 1], outputRange: [0, 0.8, 0] }),
            transform: [{ translateY: b.interpolate({ inputRange: [0, 1], outputRange: [size * 0.2, -size * 0.6] }) }] }]} />
        ))}
        <Animated.View style={swim}>
          <SvgXml xml={SWIM} width={size} height={size} />
        </Animated.View>
      </View>
      {text ? <Text style={st.text}>{text}</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  box: { alignItems: 'center', paddingVertical: 18 },
  bubble: { position: 'absolute', top: '45%', borderRadius: 999, borderWidth: 1, borderColor: 'rgba(160,220,255,0.7)',
    backgroundColor: 'rgba(127,216,255,0.15)' },
  text: { color: C.muted, fontSize: 13.5, marginTop: 6 },
});

export const HOLD_MS = 800;           // once GeekOc shows up, he stays at least this long: long enough to see him

/** True while `loading`, and for at least HOLD_MS from when it began -- so the loader is seen, not flashed. */
export function useHold(loading: boolean, ms = HOLD_MS): boolean {
  const started = useRef(0);
  const [holding, setHolding] = useState(loading);
  useEffect(() => {
    if (loading) {
      started.current = Date.now();
      const t = setTimeout(() => setHolding(true), 0);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setHolding(false), Math.max(0, ms - (Date.now() - started.current)));
    return () => clearTimeout(t);
  }, [loading, ms]);
  return loading || holding;
}
