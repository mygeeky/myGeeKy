// The folded sections, as a handle that says it opens: a pill with the app's pink-to-violet edge, "Sections", what's new
// in them, and an arrow that lifts three times when it appears (then stays still: a loop would draw frames forever
// and cost battery; still from the start with reduce motion).
import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { C, tint } from '../lib/theme';

export function UnfoldHandle({ onPress, count = 0 }: { onPress: () => void; count?: number }) {
  const [lift] = useState(() => new Animated.Value(0));
  const [glow] = useState(() => new Animated.Value(0));
  const [still, setStill] = useState(false);
  useEffect(() => { AccessibilityInfo.isReduceMotionEnabled().then(setStill).catch(() => undefined); }, []);
  useEffect(() => {
    if (still) return;
    const once = Animated.sequence([
      Animated.parallel([
        Animated.timing(lift, { toValue: -4, duration: 260, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.timing(glow, { toValue: 1, duration: 260, useNativeDriver: true }),
      ]),
      Animated.parallel([
        Animated.timing(lift, { toValue: 0, duration: 420, easing: Easing.bounce, useNativeDriver: true }),
        Animated.timing(glow, { toValue: 0, duration: 520, useNativeDriver: true }),
      ]),
      Animated.delay(380),
    ]);
    const run = Animated.loop(once, { iterations: 3 });
    run.start();
    return () => run.stop();
  }, [still, lift, glow]);
  return (
    <Pressable onPress={onPress} style={st.wrap} hitSlop={10} accessibilityRole="button"
               accessibilityLabel={`Show the sections${count ? `, ${count} new` : ''}`}>
      {({ pressed }) => (
        <View style={[st.pill, pressed && { opacity: 0.75 }]}>
          <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, st.halo, { opacity: glow }]} />
          <View style={[st.edge, { borderLeftColor: C.pink, borderTopColor: C.pink, borderRightColor: C.violet, borderBottomColor: C.violet }]} />
          <Animated.View style={{ transform: [{ translateY: lift }] }}>
            <Ionicons name="chevron-up" size={15} color={C.pink} />
          </Animated.View>
          <Text style={st.text}>Sections</Text>
          {count ? <View style={st.count}><Text style={st.countText}>{count > 99 ? '99+' : count}</Text></View> : null}
        </View>
      )}
    </Pressable>
  );
}

const st = StyleSheet.create({
  wrap: { height: 40, alignItems: 'center', justifyContent: 'center' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, height: 30, borderRadius: 15,
          backgroundColor: C.raised, overflow: 'hidden' },
  edge: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: 15, borderWidth: 1.5 },
  halo: { borderRadius: 15, backgroundColor: tint(0.16) },
  text: { color: C.text, fontSize: 12.5, fontWeight: '800', letterSpacing: 0.3 },
  count: { minWidth: 18, height: 18, borderRadius: 9, paddingHorizontal: 5, backgroundColor: C.pink, alignItems: 'center', justifyContent: 'center' },
  countText: { color: '#fff', fontSize: 10.5, fontWeight: '800' },
});
