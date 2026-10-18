// A short message that floats over every screen for a few seconds, then fades: "✓ Your protocol is built…".
// Shown wherever you have scrolled to, and never in the way (it takes no taps). The desktop panel has the same
// (qt_panel.MyGeekyPanel._toast), with the same timing.
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { C } from '../lib/theme';

export const TOAST_MS = 4000;          // long enough to read a line, short enough not to linger
const FADE_MS = 250;

const Ctx = createContext<(text: string) => void>(() => undefined);
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [text, setText] = useState('');
  const [fade] = useState(() => new Animated.Value(0));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const insets = useSafeAreaInsets();

  const show = useCallback((t: string) => {
    if (timer.current) clearTimeout(timer.current);
    setText(t);
    Animated.timing(fade, { toValue: 1, duration: FADE_MS, useNativeDriver: true }).start();
    timer.current = setTimeout(() => {
      Animated.timing(fade, { toValue: 0, duration: FADE_MS, useNativeDriver: true }).start(() => setText(''));
    }, TOAST_MS);
  }, [fade]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  return (
    <Ctx.Provider value={show}>
      {children}
      {text ? (
        <Animated.View pointerEvents="none" style={[st.toast, { top: insets.top + 10, opacity: fade }]}
                       accessibilityLiveRegion="polite" accessibilityRole="alert">
          <Text style={st.text}>{text}</Text>
        </Animated.View>
      ) : null}
    </Ctx.Provider>
  );
}

const st = StyleSheet.create({
  toast: { position: 'absolute', left: 16, right: 16, backgroundColor: C.raised, borderColor: C.green, borderWidth: 1,
           borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, elevation: 8, shadowColor: '#000',
           shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 4 } },
  text: { color: C.text, fontSize: 14, fontWeight: '700', lineHeight: 19, textAlign: 'center' },
});
