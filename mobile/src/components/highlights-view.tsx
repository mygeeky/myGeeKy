// Grow -> Highlights: research articles retold by the maker as short news articles, and a sheet to read one in any of its
// languages -- the desktop's gui/highlights_ui.py. What a Highlight holds is lib/highlight-shape.ts. Opening a
// story counts as reading a paper (badges, My month) and teaches your model its words, as on the desktop.
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { logClick } from '../lib/badges';
import { type Highlight, languages, readIn } from '../lib/highlight-shape';
import { recordInterest } from '../lib/model-repo';
import { C } from '../lib/theme';
import { Empty, open } from './ui';
import { GeekLoader, useHold } from './geek-loader';

export function metaLine(h: Highlight): string {
  const m = h.meta;
  return [m.journal, m.published, m.open_access ? 'open access' : '', m.lead ? `led by ${m.lead}` : ''].filter(Boolean).join(' · ');
}

function Story({ h, onClose, onLearn }: { h: Highlight; onClose: () => void; onLearn: (skill: string) => void }) {
  const [code, setCode] = useState('en');
  const story = readIn(h, code);
  const dir = story.rtl ? ({ textAlign: 'right', writingDirection: 'rtl' } as const) : null;
  const L = story.labels;
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={st.backdrop}>
        <View style={st.sheet}>
          <View style={st.bar}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
              {languages(h).map(([c, name]) => (
                <Pressable key={c} onPress={() => setCode(c)} style={[st.lang, c === code && st.langOn]}>
                  <Text style={[st.langText, c === code && { color: C.text, fontWeight: '800' }]}>{name}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <Pressable onPress={onClose} hitSlop={12}><Text style={st.close}>✕</Text></Pressable>
          </View>
          <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
            <Text style={[st.kind, dir]}>✨ {h.coverage === 'full' ? L.full : L.abstract}</Text>
            <Text style={[st.title, dir]}>{story.title}</Text>
            {story.hook ? <Text style={[st.hook, dir]}>{story.hook}</Text> : null}
            {metaLine(h) ? <Text style={st.meta}>{metaLine(h)}</Text> : null}
            {story.body.map((para, i) => (                 /* a news article: one idea a paragraph, no headings */
              <Text key={i} style={[st.body, i === 0 && st.lead, dir]}>{para}</Text>
            ))}
            {h.skills.length ? (
              <View>
                <Text style={[st.head, dir]}>{L.learn.toUpperCase()}</Text>
                <View style={st.chips}>
                  {h.skills.map((skill) => (
                    <Pressable key={skill} onPress={() => { onClose(); onLearn(skill); }} style={st.chip}>
                      <Text style={st.chipText}>🧭 {skill}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            ) : null}
          </ScrollView>
          <Pressable onPress={() => open(h.url)} style={({ pressed }) => [st.read, pressed && { opacity: 0.85 }]}>
            <Text style={st.readText}>{L.read} ↗</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

export function HighlightsView({ items, onLearn }: { items: Highlight[] | null; onLearn: (skill: string) => void }) {
  const [shown, setShown] = useState<Highlight | null>(null);
  const hold = useHold(!items);
  const read = (h: Highlight) => {
    logClick('paper');
    recordInterest({ kind: 'news', text: `${h.title} ${h.hook}`, topics: h.keywords, source: h.doi || h.id }).catch(() => undefined);
    setShown(h);
  };
  if (hold || !items) return <GeekLoader />;
  if (!items.length) return <Empty>No Highlights yet. They arrive with the lists, a few a week.</Empty>;
  return (
    <View>
      {items.map((h) => (
        <Pressable key={h.id} onPress={() => read(h)} style={({ pressed }) => [st.card, pressed && { opacity: 0.85 }]}>
          <Text style={st.kind}>✨ {h.coverage === 'full' ? 'From the full article' : 'From the abstract only'}</Text>
          <Text style={st.cardTitle}>{h.title}</Text>
          {h.hook ? <Text style={st.cardHook}>{h.hook}</Text> : null}
          {metaLine(h) ? <Text style={st.meta}>{metaLine(h)}</Text> : null}
          {languages(h).length > 1 ? <Text style={st.meta}>🌍 readable in {languages(h).length} languages</Text> : null}
        </Pressable>
      ))}
      {shown ? <Story h={shown} onClose={() => setShown(null)} onLearn={onLearn} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: C.card, borderRadius: 14, padding: 14, marginTop: 10, borderLeftWidth: 3, borderLeftColor: C.pink },
  kind: { color: C.pink, fontSize: 11, fontWeight: '800' },
  cardTitle: { color: C.text, fontSize: 16, fontWeight: '800', marginTop: 4 },
  cardHook: { color: C.text, fontSize: 13.5, marginTop: 4, lineHeight: 19 },
  meta: { color: C.muted, fontSize: 12, marginTop: 6 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: C.sheet, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 16, maxHeight: '92%' },
  bar: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  lang: { borderRadius: 999, paddingHorizontal: 11, paddingVertical: 6, backgroundColor: C.card },
  langOn: { backgroundColor: 'rgba(255,111,216,0.3)' },
  langText: { color: C.muted, fontSize: 13 },
  close: { color: C.muted, fontSize: 18, paddingHorizontal: 4 },
  title: { color: C.text, fontSize: 21, fontWeight: '800', marginTop: 6, lineHeight: 27 },
  hook: { color: C.text, fontSize: 15, fontStyle: 'italic', marginTop: 6, lineHeight: 21 },
  head: { color: C.cyan, fontSize: 11, fontWeight: '800', letterSpacing: 0.6, marginTop: 16 },
  body: { color: C.text, fontSize: 15, lineHeight: 23, marginTop: 12 },
  lead: { fontSize: 16, lineHeight: 24 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  chip: { backgroundColor: C.card, borderRadius: 999, paddingHorizontal: 11, paddingVertical: 7 },
  chipText: { color: C.text, fontSize: 13, fontWeight: '700' },
  read: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 13, alignItems: 'center', marginTop: 8 },
  readText: { color: '#fff', fontSize: 15, fontWeight: '800' },
});
