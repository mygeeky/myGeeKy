// Grow → 🗂️ Data: public datasets to practise and train on, ordered for you (your field, the skills rising for you,
// easy ones first). The fields are planets in the navigation (nav-tree.ts), not tabs here -- the desktop's
// gui/datasets_ui.py.
// lib/datasets.ts reads and ranks the list; 👍/👎 teach your model like everywhere else.
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { loadDatasets, rank, type Dataset, type Ranked, sizeText } from '../lib/datasets';
import type { Weights } from '../lib/interests';
import * as taste from '../lib/taste';
import { C } from '../lib/theme';
import { GeekLoader, useHold } from './geek-loader';
import { GCard, Hidden, s, Thumbs } from './growth-parts';
import { Empty, open } from './ui';

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

export function DatasetsView({ field, weights, wanted }: { field: string; weights: Weights; wanted: string[] }) {
  const [all, setAll] = useState<Dataset[] | null>(null);
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
      <Text style={[s.muted, { marginTop: 4 }]}>{label(field)}: of {all.length} datasets, each open, documented and downloadable without a login.</Text>
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
  row: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  btn: { backgroundColor: C.cardHi, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  btnText: { color: C.text, fontSize: 12, fontWeight: '700' },
});
