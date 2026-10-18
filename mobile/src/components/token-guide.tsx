// A picture guide for making a GitHub token: one drawn step at a time, numbered dots underneath. The steps move on
// by themselves every few seconds and stop as soon as you swipe or tap a dot. Steps, drawings and timing come from
// data/token-guides.json (tools/token_guides.py writes it), the same file the desktop reads (gui/token_guide.py).
import { useEffect, useRef, useState } from 'react';
import { Linking, type NativeScrollEvent, type NativeSyntheticEvent, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SvgXml } from 'react-native-svg';
import guides from '../data/token-guides.json';
import { C, tint } from '../lib/theme';

type Step = { title: string; text: string; svg: string };
type Guide = { key: string; title: string; url: string; tips: string[]; steps: Step[] };
export type GuideKey = 'data' | 'signals' | 'read';

export function TokenGuide({ which }: { which: GuideKey }) {
  const guide = (guides as unknown as { guides: Record<string, Guide> }).guides[which];
  const seconds = (guides as { seconds?: number }).seconds ?? 4;
  const [at, setAt] = useState(0);
  const [auto, setAuto] = useState(true);
  const [width, setWidth] = useState(0);                     // the space it gets, measured
  const scroller = useRef<ScrollView>(null);
  const h = Math.round(width * 150 / 320);

  useEffect(() => {
    if (!auto || !guide) return undefined;
    const t = setInterval(() => setAt((i) => (i + 1) % guide.steps.length), seconds * 1000);
    return () => clearInterval(t);
  }, [auto, guide, seconds]);
  useEffect(() => { if (width) scroller.current?.scrollTo({ x: at * width, animated: true }); }, [at, width]);

  if (!guide) return null;
  const pick = (i: number) => { setAuto(false); setAt((i + guide.steps.length) % guide.steps.length); };
  const swiped = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / Math.max(width, 1));
    if (i !== at) { setAuto(false); setAt(i); }
  };
  const step = guide.steps[at];
  return (
    <View style={st.wrap} onLayout={(e) => setWidth(Math.round(e.nativeEvent.layout.width))}>
      <View style={st.head}>
        <Text style={st.title}>{guide.title}</Text>
        <Pressable onPress={() => Linking.openURL(guide.url)} hitSlop={6}><Text style={st.open}>Open GitHub ↗</Text></Pressable>
      </View>
      {width > 0 ? <ScrollView ref={scroller} horizontal pagingEnabled showsHorizontalScrollIndicator={false} style={{ width }}
                  onScrollBeginDrag={() => setAuto(false)} onMomentumScrollEnd={swiped} scrollEventThrottle={16}>
        {guide.steps.map((s, i) => (
          <View key={i} style={{ width, height: h }} accessible accessibilityLabel={`Step ${i + 1}: ${s.title}`}>
            <SvgXml xml={s.svg} width={width} height={h} />
          </View>
        ))}
      </ScrollView> : null}
      <Text style={st.stepTitle}>{at + 1}. {step.title}</Text>
      <Text style={st.text}>{step.text}</Text>
      <View style={st.dots}>
        {guide.steps.map((s, i) => (
          <Pressable key={i} onPress={() => pick(i)} hitSlop={4} accessibilityRole="button"
                     accessibilityLabel={`Step ${i + 1}: ${s.title}`} style={[st.dot, i === at && st.dotOn]}>
            <Text style={[st.dotText, i === at && st.dotTextOn]}>{i + 1}</Text>
          </Pressable>
        ))}
      </View>
      {guide.tips.map((t) => <Text key={t} style={st.tip}>• {t}</Text>)}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { marginTop: 12, marginBottom: 4 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  title: { color: C.text, fontSize: 15, fontWeight: '800', flexShrink: 1 },
  open: { color: C.cyan, fontSize: 13, fontWeight: '700' },
  stepTitle: { color: C.text, fontSize: 14, fontWeight: '700', marginTop: 8 },
  text: { color: C.muted, fontSize: 13, lineHeight: 18, marginTop: 2 },
  dots: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  dot: { width: 28, height: 28, borderRadius: 14, backgroundColor: tint(0.08), alignItems: 'center', justifyContent: 'center' },
  dotOn: { backgroundColor: '#ff6fd8' },
  dotText: { color: C.text, fontSize: 12, fontWeight: '700' },
  dotTextOn: { color: '#3a0a2e' },
  tip: { color: C.muted, fontSize: 12, lineHeight: 17, marginTop: 6 },
});
