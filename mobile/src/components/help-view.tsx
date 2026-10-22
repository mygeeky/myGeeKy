// ❓ Help, the last main (the desktop's gui/help_ui.py): start GeeKOc's tours again -- the one that fits you,
// Settings', one for each main -- and read the answers to how and why myGeeKy works, one question at a time. All
// the words come from data/tour.json (lib/tour.ts), in the tours' language, picked here.
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as T from '../lib/tour';
import { C } from '../lib/theme';
import { setTourLang, tourLang } from './tour-overlay';

function Question({ q, a, rtl }: { q: string; a: string; rtl: boolean }) {
  const [open, setOpen] = useState(false);
  const dir = rtl ? ({ writingDirection: 'rtl', textAlign: 'right' } as const) : null;
  return (
    <Pressable onPress={() => setOpen(!open)} style={st.question} accessibilityRole="button" accessibilityState={{ expanded: open }}>
      <Text style={[st.q, dir]}>{open ? '▾' : '▸'}  {q}</Text>
      {open ? <Text style={[st.a, dir]}>{a}</Text> : null}
    </Pressable>
  );
}

export function HelpView({ onStart, labelOf, lang: picked }: { onStart: (name: string) => void; labelOf: (main: string) => string; lang?: string }) {
  const [lang, setLang] = useState('en');
  useEffect(() => { tourLang().then((l) => setLang(T.langOf(l || 'en'))).catch(() => undefined); }, [picked]);
  const rtl = T.rtl(lang);
  const dir = rtl ? ({ writingDirection: 'rtl', textAlign: 'right' } as const) : null;
  const choose = (code: string) => { setLang(code); setTourLang(code).catch(() => undefined); };
  const tours: [string, string, boolean][] = [
    ['start', `🐙  ${T.ui('start_tour', lang)}`, true],
    ['settings', `⚙  ${T.ui('settings_tour', lang)}`, false],
    ...T.MAINS.map((m) => [m, T.ui('main_tour', lang, { name: labelOf(m) }), false] as [string, string, boolean]),
  ];
  return (
    <View style={{ gap: 8 }}>
      <Text style={[st.head, dir]}>{T.ui('language', lang).toUpperCase()}</Text>
      <View style={[st.langs, rtl && { flexDirection: 'row-reverse' }]}>
        {Object.entries(T.LANGS).map(([code, name]) => (
          <Pressable key={code} onPress={() => choose(code)} style={[st.lang, code === lang && st.langOn]}
                     accessibilityRole="button" accessibilityState={{ selected: code === lang }}>
            <Text style={[st.langText, code === lang && { color: '#fff' }]}>{name}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={[st.head, dir]}>{T.ui('tours', lang).toUpperCase()}</Text>
      {tours.map(([name, label, main]) => (
        <Pressable key={name} onPress={() => onStart(name)} style={({ pressed }) => [st.tour, main && st.tourMain, pressed && { opacity: 0.7 }]}
                   accessibilityRole="button">
          <Text style={[st.tourText, main && st.tourMainText, dir]}>{label}</Text>
        </Pressable>
      ))}
      <Text style={[st.head, dir]}>{T.ui('faq', lang).toUpperCase()}</Text>
      {T.faq(lang).map(([q, a]) => <Question key={q} q={q} a={a} rtl={rtl} />)}
    </View>
  );
}

const st = StyleSheet.create({
  head: { color: C.cyan, fontSize: 11, fontWeight: '800', letterSpacing: 0.8, marginTop: 10 },
  langs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  lang: { backgroundColor: C.card, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  langOn: { backgroundColor: C.violet },
  langText: { color: C.text, fontSize: 13, fontWeight: '700' },
  tour: { backgroundColor: C.card, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12 },
  tourMain: { backgroundColor: C.violet },
  tourText: { color: C.text, fontSize: 14, fontWeight: '600' },
  tourMainText: { color: '#fff', fontWeight: '800' },
  question: { backgroundColor: C.card, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, gap: 6 },
  q: { color: C.text, fontSize: 14, fontWeight: '700', lineHeight: 20 },
  a: { color: C.muted, fontSize: 13.5, lineHeight: 19 },
});
