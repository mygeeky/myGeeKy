// Grow → 🗂️ Data: public datasets to practise and train on, ordered for you (your field, the skills rising for you,
// easy ones first), with a field picker -- the desktop's Data part (gui/qt_panel.py `_render_datasets`).
// lib/datasets.ts reads and ranks the list; 👍/👎 teach your model like everywhere else.
import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { FIELDS, loadDatasets, rank, type Dataset, type Ranked, sizeText } from '../lib/datasets';
import type { Weights } from '../lib/interests';
import * as taste from '../lib/taste';
import { C } from '../lib/theme';
import { GeekLoader, useHold } from './geek-loader';
import { GCard, Hidden, s, Thumbs } from './growth-parts';
import { Empty, open } from './ui';

const CHOICES = ['for you', '', ...FIELDS];
const label = (f: string) => (f === 'for you' ? '✨ For you' : f === '' ? 'All' : f);

function DatasetCard({ d, onVote }: { d: Ranked; onVote: (up: boolean) => Promise<number> }) {
  const meta = [d.field, d.level, sizeText(d.size_mb), d.formats.slice(0, 3).join(', ').toUpperCase(),
    d.license + (d.nc ? ' (non-commercial)' : '')].filter(Boolean).join(' · ');
  return (
    <GCard>
      <View style={s.head}>
        <Pressable style={{ flex: 1 }} onPress={() => open(d.url)}><Text style={s.title}>{d.title}</Text></Pressable>
        <Thumbs vote={d.vote} onVote={onVote} />
      </View>
      <Text style={s.body}>Practise: {d.why}</Text>
      <Text style={s.muted}>{meta}</Text>
      {d.for.length ? <Text style={[s.muted, { color: C.green }]}>📈 teaches {d.for.join(', ')}, rising for you</Text>
        : d.skills.length ? <Text style={s.muted}>teaches {d.skills.slice(0, 4).join(', ')}</Text> : null}
      <View style={st.row}>
        {d.download ? <Pressable onPress={() => open(d.download)} style={st.btn}><Text style={st.btnText}>⬇ Download</Text></Pressable> : null}
        <Pressable onPress={() => open(d.url)} style={st.btn}><Text style={st.btnText}>{d.download ? 'Page' : '⬇ Get it'}</Text></Pressable>
        {d.tutorial ? <Pressable onPress={() => open(d.tutorial)} style={st.btn}><Text style={st.btnText}>📘 Tutorial</Text></Pressable> : null}
        <Text style={[s.muted, { marginLeft: 'auto' }]}>{d.source}</Text>
      </View>
    </GCard>
  );
}

export function DatasetsView({ weights, wanted }: { weights: Weights; wanted: string[] }) {
  const [all, setAll] = useState<Dataset[] | null>(null);
  const [field, setField] = useState('for you');
  const [shown, setShown] = useState<{ items: Ranked[]; hidden: number }>({ items: [], hidden: 0 });
  const hold = useHold(all === null);
  useEffect(() => { loadDatasets().then(setAll).catch(() => setAll([])); }, []);
  const again = useCallback(async () => {
    if (!all) return;
    const votes = await taste.load();
    const v = Object.fromEntries(all.map((d) => [d.id, taste.voteOf(votes, 'dataset', d.id)]));
    const r = rank(all, weights, wanted, field, v);
    // nothing matches you yet: show everything rather than an empty page
    setShown(field === 'for you' && !r.items.length ? rank(all, weights, wanted, '', v) : r);
  }, [all, weights, wanted, field]);
  useEffect(() => { Promise.resolve().then(again); }, [again]);
  if (hold || all === null) return <GeekLoader text="Finding data to practise on…" />;
  return (
    <View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16 }} contentContainerStyle={{ paddingHorizontal: 16, gap: 6 }}>
        {CHOICES.map((f) => (
          <Pressable key={f || 'all'} onPress={() => setField(f)} style={[st.chip, field === f && st.chipOn]}>
            <Text style={[st.chipText, field === f && { color: C.text }]}>{label(f)}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <Text style={[s.muted, { marginTop: 6 }]}>{all.length} datasets, each open, documented and downloadable without a login.</Text>
      {shown.items.map((d) => (
        <DatasetCard key={d.id} d={d} onVote={async (up) => {
          const v = await taste.vote('dataset', d.id, up, d.title, d.skills);
          if (v < 0) again();
          return v;
        }} />
      ))}
      {!shown.items.length ? <Empty>No datasets in this field yet.</Empty> : null}
      <Hidden n={shown.hidden} onShow={async () => { await taste.unhide('dataset'); again(); }} />
    </View>
  );
}

const st = StyleSheet.create({
  chip: { paddingHorizontal: 11, paddingVertical: 6, borderRadius: 14, backgroundColor: C.card, borderWidth: 1, borderColor: C.line },
  chipOn: { backgroundColor: C.cardHi, borderColor: C.green },
  chipText: { color: C.muted, fontSize: 12.5, fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  btn: { backgroundColor: C.cardHi, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  btnText: { color: C.text, fontSize: 12, fontWeight: '700' },
});
