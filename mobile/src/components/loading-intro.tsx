// The opening animation: the badge's arms spin in out of nothing, then G, ee and K pop in,
// and m and y land last. The same layers and timeline as the desktop (src/mygeeky/gui/splash.py).
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, type ImageSourcePropType, Pressable, StyleSheet, useWindowDimensions } from 'react-native';
import { INTRO, type LayerName, type Track } from '../lib/intro-frames';
import { C } from '../lib/theme';

const LAYERS: [LayerName, ImageSourcePropType][] = [
  ['ring', require('../../assets/loader/loader_ring.png')],
  ['G', require('../../assets/loader/loader_G.png')],
  ['ee', require('../../assets/loader/loader_ee.png')],
  ['K', require('../../assets/loader/loader_K.png')],
  ['m', require('../../assets/loader/loader_m.png')],
  ['y', require('../../assets/loader/loader_y.png')],
];
const BADGE = '#151521';
const SECONDS = INTRO.times[INTRO.times.length - 1];

function along(t: Animated.Value, values: number[]) {
  return t.interpolate({ inputRange: INTRO.times, outputRange: values, extrapolate: 'clamp' });
}

function turn(t: Animated.Value, values: number[]) {
  return t.interpolate({ inputRange: INTRO.times, outputRange: values.map((v) => `${v}deg`), extrapolate: 'clamp' });
}

function poseStyle(t: Animated.Value, f: Track, size: number) {
  return {
    opacity: along(t, f.opacity),
    transform: [
      { translateX: along(t, f.dx.map((v) => v * size)) },
      { translateY: along(t, f.dy.map((v) => v * size)) },
      { rotate: turn(t, f.turn) },
      { scale: along(t, f.scale) },
    ],
  };
}

export function LoadingIntro({ onDone }: { onDone: () => void }) {
  const { width, height } = useWindowDimensions();
  const size = Math.round(Math.min(width, height) * 0.62);
  const [t] = useState(() => new Animated.Value(0));
  const [fade] = useState(() => new Animated.Value(1));
  const finished = useRef(false);

  const finish = () => {
    if (finished.current) return;
    finished.current = true;
    Animated.timing(fade, { toValue: 0, duration: 280, useNativeDriver: true }).start(() => onDone());
  };

  useEffect(() => {
    const run = Animated.timing(t, { toValue: SECONDS, duration: SECONDS * 1000, easing: Easing.linear, useNativeDriver: true });
    run.start(({ finished: ended }) => { if (ended) setTimeout(finish, 250); });
    return () => run.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Animated.View style={[StyleSheet.absoluteFill, st.screen, { opacity: fade }]}>
      {/* a tap skips it */}
      <Pressable style={st.center} onPress={finish} accessibilityLabel="myGeeKy is starting. Tap to skip.">
        <Animated.View style={{ width: size, height: size }}>
          <Animated.View style={[st.layer, { borderRadius: size / 2, backgroundColor: BADGE, opacity: along(t, INTRO.badge.opacity) }]} />
          {LAYERS.map(([name, src]) => {
            const f = INTRO[name];
            const [cx, cy] = INTRO.centres[name];
            // in pixels, as an array: React Native's string parser takes only whole-number
            // percentages, so "50.13%" reads as x=50, y=13%, z=13% and throws
            const origin = [cx * size, cy * size, 0];
            return [
              <Animated.Image key={name} source={src} resizeMode="contain"
                style={[st.layer, { transformOrigin: origin }, poseStyle(t, f, size)]} />,
              // the bright flash: the same shape in white, fading out
              <Animated.Image key={`${name}-glow`} source={src} resizeMode="contain" tintColor="#ffffff"
                style={[st.layer, { transformOrigin: origin }, poseStyle(t, f, size),
                  { opacity: along(t, f.glow.map((g) => g * 0.45)) }]} />,
            ];
          })}
        </Animated.View>
      </Pressable>
    </Animated.View>
  );
}

const st = StyleSheet.create({
  screen: { backgroundColor: C.bg, zIndex: 100 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  layer: { position: 'absolute', left: 0, top: 0, width: '100%', height: '100%' },
});
