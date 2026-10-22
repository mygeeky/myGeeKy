// The dotted ring around a planet that opens into more parts (the orbit and the folded dock): it turns slowly, so you
// can expect more inside. A planet that opened, now in the orbit's centre, is drawn without it. One turn every 14 s,
// on the native driver, only while the screen is shown, and never with the system's reduce-motion on.
// Desktop: still the old mark under the planet (PARITY.md).
import { useIsFocused } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { AccessibilityInfo, Animated, Easing } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

export const RING_GAP = 6;                 // from the planet's edge to the ring
const TURN_MS = 14000;

/** One rotation shared by every ring on the screen: a single animation, running only while it can be seen
 *  (`shown`: the rings are on screen, e.g. the dock isn't tucked away). */
export function useOrbitSpin(shown = true): Animated.AnimatedInterpolation<string> {
  const focused = useIsFocused();
  const [reduce, setReduce] = useState(false);
  const [turn] = useState(() => new Animated.Value(0));
  useEffect(() => {
    let live = true;
    AccessibilityInfo.isReduceMotionEnabled().then((r) => live && setReduce(r)).catch(() => {});
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => { live = false; sub.remove(); };
  }, []);
  useEffect(() => {
    if (!focused || reduce || !shown) return;
    const loop = Animated.loop(Animated.timing(turn, { toValue: 1, duration: TURN_MS, easing: Easing.linear, useNativeDriver: true }));
    loop.start();
    return () => { loop.stop(); };
  }, [focused, reduce, shown, turn]);
  return useMemo(() => turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }), [turn]);
}

/** The ring for a planet of `size` (place it inside the planet's view: it reaches RING_GAP beyond the edge). */
export function DashedOrbit({ size, color, spin }: { size: number; color: string; spin: Animated.AnimatedInterpolation<string> }) {
  const d = size + 2 * RING_GAP, r = size / 2 + RING_GAP - 2;
  return (
    <Animated.View pointerEvents="none" collapsable={false}
                   style={{ position: 'absolute', left: -RING_GAP - 2, top: -RING_GAP - 2, width: d, height: d, transform: [{ rotate: spin }] }}>
      <Svg width={d} height={d}>
        <Circle cx={d / 2} cy={d / 2} r={r} fill="none" stroke={color} strokeWidth={2} strokeDasharray="3 4" strokeLinecap="round" />
      </Svg>
    </Animated.View>
  );
}
