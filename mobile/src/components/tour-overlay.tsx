// GeeKOc's tour over the app (the desktop's gui/tour_ui.py; which stops and their words: lib/tour.ts). The screen
// dims, a spotlight sits on the page's planet in the orbit (or on a Settings section), and GeeKOc -- arms swimming
// -- says one thing beside it. Next, Back, Skip. The first time, his first bubble asks for the tours' language.
// Home does the moving (onGo opens the page and the orbit, or scrolls Settings); the places a spotlight can sit
// register themselves here with spot('id').
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Path, Rect, SvgXml } from 'react-native-svg';
import * as T from '../lib/tour';

const LANG_KEY = 'mygeeky.tour.lang';
const SEEN_KEY = 'mygeeky.tour.seen';
export const tourLang = async (): Promise<string> => (await AsyncStorage.getItem(LANG_KEY)) ?? '';
export const setTourLang = (lang: string) => AsyncStorage.setItem(LANG_KEY, lang);
export const tourSeen = async (): Promise<number> => Number((await AsyncStorage.getItem(SEEN_KEY)) ?? 0) || 0;
export const setTourSeen = (v: number) => AsyncStorage.setItem(SEEN_KEY, String(v));

// the places a spotlight can sit: a planet (its node id) or a Settings section ('settings:cv')
type Measurable = { measureInWindow: (cb: (x: number, y: number, w: number, h: number) => void) => void };
const spots = new Map<string, Measurable>();
export const spot = (id: string) => (r: Measurable | null) => { if (r) spots.set(id, r); };   // a gone one measures 0: ignored
export const spotOf = (id: string): Measurable | undefined => spots.get(id);

type Moves = { viewBox: string; fps: number; poses: Record<string, { parts: string[]; frames: number[][] }> };
let moves: Moves | null = null;
const loadMoves = (): Moves => (moves ??= require('../data/geekoc_moves.json') as Moves);   // only once a tour opens

/** GeeKOc in one pose, his arms swimming (tools/geekoc_poses.py made the frames); still with reduce motion. */
export function GeekMover({ pose, size }: { pose: string; size: number }) {
  const m = loadMoves();
  const p = m.poses[pose] ?? m.poses.wave;
  const frames = useMemo(() => p.frames.map((f) => `<svg viewBox="${m.viewBox}">${f.map((i) => p.parts[i]).join('')}</svg>`), [p, m.viewBox]);
  const [n, setN] = useState(0);
  const [still, setStill] = useState(false);
  useEffect(() => { AccessibilityInfo.isReduceMotionEnabled().then(setStill).catch(() => undefined); }, []);
  useEffect(() => {
    if (still) return;
    const t = setInterval(() => setN((k) => (k + 1) % frames.length), 1000 / m.fps);
    return () => clearInterval(t);
  }, [frames.length, m.fps, still]);
  return <SvgXml xml={frames[still ? 0 : n % frames.length]} width={size} height={size} />;
}

type Hole = { x: number; y: number; w: number; h: number };

export function TourOverlay({ steps, kind, onGo, onDone }: {
  steps: string[]; kind: string; onGo: (target: string) => void; onDone: (finished: boolean) => void;
}) {
  const [i, setI] = useState(0);
  const [lang, setLang] = useState<string | null>(null);         // null: still loading; '' : ask first
  const [aimed, setAimed] = useState<(Hole & { key: string }) | null>(null);   // the spotlight, for the stop it was aimed at
  const [box, setBox] = useState({ x: 0, y: 0, w: 0, h: 0 });   // this overlay, in the window
  const root = useRef<View>(null);
  useEffect(() => { tourLang().then(setLang).catch(() => setLang('')); }, []);
  const stop = steps[i];
  const target = lang ? T.at(stop) : '';
  const key = `${i}:${target}`;
  const hole: Hole | null = aimed?.key === key ? aimed : null;

  useEffect(() => {                       // move the app to the stop, then aim once it has settled
    if (!target) return;
    onGo(target);
    const t = setTimeout(() => {
      const s = spotOf(target);
      if (!s) return;
      s.measureInWindow((x, y, w, h) => {
        if (!w || !h) return;
        const band = target.startsWith('settings:');            // a heading: the band of settings under it
        setAimed({ key, x: (band ? 12 : x - 6) - box.x, y: y - 6 - box.y, w: band ? box.w - 24 : w + 12, h: (band ? h + 110 : h + 12) });
      });
    }, target.startsWith('settings:') ? 900 : 550);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, i, box.w]);

  if (lang === null) return null;
  const l = T.langOf(lang || 'en'), rtl = T.rtl(l) && !!lang, last = i === steps.length - 1;
  const dir = rtl ? ({ writingDirection: 'rtl', textAlign: 'right' } as const) : null;
  const next = () => (last ? onDone(true) : setI(i + 1));
  const pick = (code: string) => { setTourLang(code).catch(() => undefined); setLang(code); };
  const H = box.h, W = box.w;
  const place = !hole ? { top: H * 0.24 } : hole.y > H * 0.45 ? { bottom: H - hole.y + 10 } : { top: hole.y + hole.h + 10 };
  const shade = hole
    ? `M0 0H${W}V${H}H0Z M${hole.x + 14} ${hole.y}H${hole.x + hole.w - 14}Q${hole.x + hole.w} ${hole.y} ${hole.x + hole.w} ${hole.y + 14}V${hole.y + hole.h - 14}Q${hole.x + hole.w} ${hole.y + hole.h} ${hole.x + hole.w - 14} ${hole.y + hole.h}H${hole.x + 14}Q${hole.x} ${hole.y + hole.h} ${hole.x} ${hole.y + hole.h - 14}V${hole.y + 14}Q${hole.x} ${hole.y} ${hole.x + 14} ${hole.y}Z`
    : `M0 0H${W}V${H}H0Z`;

  return (
    <View ref={root} style={[StyleSheet.absoluteFill, st.over]} onStartShouldSetResponder={() => true}
          onLayout={() => root.current?.measureInWindow((x, y, w, h) => setBox({ x, y, w, h }))}>
      {W ? (
        <Svg width={W} height={H} style={StyleSheet.absoluteFill} pointerEvents="none">
          <Path d={shade} fill="rgba(6,4,16,0.72)" fillRule="evenodd" />
          {hole ? <Rect x={hole.x} y={hole.y} width={hole.w} height={hole.h} rx={14} fill="none" stroke="#ff6fd8" strokeWidth={2.5} /> : null}
        </Svg>
      ) : null}
      {W ? (
        <View style={[st.bubbleRow, place, rtl && { flexDirection: 'row-reverse' }]}>
          <GeekMover pose={lang ? T.pose(stop) : 'wave'} size={78} />
          <View style={st.say}>
            {!lang ? (
              <>
                <Text style={st.path}>GeeKOc</Text>
                <Text style={st.text}>{['en', 'fr', 'ar', 'zh'].map((c) => T.ui('pick', c)).join('\n')}</Text>
                <View style={st.langs}>
                  {Object.entries(T.LANGS).map(([code, name]) => (
                    <Pressable key={code} onPress={() => pick(code)} style={st.lang} accessibilityRole="button">
                      <Text style={st.langText}>{name}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            ) : (
              <>
                <Text style={[st.path, dir]}>{target ? pathOf(target) : 'GeeKOc'}</Text>
                <Text style={[st.text, dir]}>{T.text(stop, l, kind)}</Text>
                {T.phrase(stop, l) ? <Text style={[st.phrase, dir]}>{T.phrase(stop, l)}</Text> : null}
                <View style={st.dots}>{steps.map((s, n) => <View key={s + n} style={[st.dot, n === i && st.dotOn]} />)}</View>
                <View style={[st.row, rtl && { flexDirection: 'row-reverse' }]}>
                  {!last ? <Pressable onPress={() => onDone(false)} style={st.ghost} accessibilityRole="button"><Text style={st.ghostText}>{T.ui('skip', l)}</Text></Pressable> : null}
                  {i ? <Pressable onPress={() => setI(i - 1)} style={st.ghost} accessibilityRole="button"><Text style={st.ghostText}>{T.ui('back', l)}</Text></Pressable> : null}
                  <Pressable onPress={next} style={st.go} accessibilityRole="button"><Text style={st.goText}>{T.ui(last ? 'done' : 'next', l)}</Text></Pressable>
                </View>
              </>
            )}
          </View>
        </View>
      ) : null}
    </View>
  );
}

// what a stop's place is called on screen ("Chances › Seasons"), set by Home (it knows the tree)
let namer: (target: string) => string = () => '';
export const nameSpots = (fn: (target: string) => string) => { namer = fn; };
const pathOf = (target: string) => namer(target);

const st = StyleSheet.create({
  over: { zIndex: 100, elevation: 100 },          // above everything, raised planets and buttons too (Android draws elevation on top)
  bubbleRow: { position: 'absolute', left: 10, right: 10, flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  say: { flex: 1, backgroundColor: '#fbf9ff', borderRadius: 16, padding: 12, gap: 4,
         shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 12, elevation: 10 },
  path: { color: '#7c3aed', fontSize: 11, fontWeight: '800' },
  text: { color: '#1d1838', fontSize: 14, lineHeight: 20 },
  phrase: { color: '#7c3aed', fontSize: 15, fontWeight: '800', lineHeight: 21 },
  dots: { flexDirection: 'row', gap: 4, marginTop: 4 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#d8d0f5' },
  dotOn: { backgroundColor: '#7c3aed' },
  row: { flexDirection: 'row', justifyContent: 'flex-end', gap: 6, marginTop: 4 },
  go: { backgroundColor: '#7c3aed', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  goText: { color: '#fff', fontWeight: '800', fontSize: 13 },
  ghost: { paddingHorizontal: 10, paddingVertical: 8 },
  ghostText: { color: '#6b6394', fontWeight: '700', fontSize: 13 },
  langs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  lang: { flexBasis: '47%', flexGrow: 1, backgroundColor: '#efe9ff', borderRadius: 10, paddingVertical: 10, alignItems: 'center' },
  langText: { color: '#1d1838', fontSize: 14, fontWeight: '700' },
});
