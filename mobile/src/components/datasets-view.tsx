// Grow → 🗂️ Data: public datasets to practise and train on, ordered for you (your field, the skills rising for you,
// easy ones first). The fields are planets in the navigation (nav-tree.ts), not tabs here -- the desktop's
// gui/datasets_ui.py.
// lib/datasets.ts reads and ranks the list; 👍/👎 teach your model like everywhere else.
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { loadDatasets, loadRadar, radarRank, type RadarRanked, type RadarState, radarSeen, rank, refreshRadar, type Dataset, type Ranked,
  sizeText } from '../lib/datasets';
import type { Weights } from '../lib/interests';
import * as taste from '../lib/taste';
import { C } from '../lib/theme';
import { GeekLoader, useHold } from './geek-loader';
import { GCard, Hidden, s, Thumbs } from './growth-parts';
import { Empty, open } from './ui';

const label = (f: string) => (f === 'for you' ? '✨ For you' : f === 'new' ? '🆕 New on your topics' : f === '' ? 'All' : f);

function RadarCard({ d, onVote }: { d: RadarRanked; onVote: (up: boolean) => Promise<number> }) {
  const meta = [d.source, d.date, sizeText(d.size_mb), d.license + (d.nc ? ' (non-commercial)' : '')].filter(Boolean).join(' · ');
  return (
    <GCard>
      <View style={s.head}>
        <Pressable style={{ flex: 1 }} onPress={() => open(d.url)}><Text style={s.title}>{d.new ? '🆕 ' : ''}{d.title}</Text></Pressable>
        <Thumbs vote={d.vote} onVote={onVote} />
      </View>
      {d.about ? <Text style={s.body} numberOfLines={4}>{d.about}</Text> : null}
      <Text style={s.muted}>{meta}</Text>
      <Text style={[s.muted, { color: C.green }]}>matches “{d.term}”</Text>
      <View style={st.row}><Pressable onPress={() => open(d.url)} style={st.btn}><Text style={st.btnText}>Open</Text></Pressable></View>
    </GCard>
  );
}

/** 🆕 New on your topics: what the radar found on your keywords lately (lib/datasets.ts refreshRadar). */
function RadarList({ keywords, weights }: { keywords: string[]; weights: Weights }) {
  const [st, setSt] = useState<RadarState | null>(null);
  const [shown, setShown] = useState<{ items: RadarRanked[]; hidden: number }>({ items: [], hidden: 0 });
  useEffect(() => {
    let live = true;
    loadRadar().then((x) => live && setSt(x)).catch(() => undefined);
    refreshRadar(keywords, weights).then((x) => live && setSt(x)).catch(() => undefined);
    return () => { live = false; };
  }, [keywords, weights]);
  const again = useCallback(async () => {
    if (!st) return;
    const votes = await taste.load();
    const v = Object.fromEntries((st.items ?? []).map((i) => [i.id, taste.voteOf(votes, 'dataset', i.id)]));
    const r = radarRank(st, weights, v, new Date().toISOString().slice(0, 10));
    setShown(r);
    radarSeen(r.items.map((i) => i.id)).catch(() => undefined);      // shown: no longer 🆕 next time
  }, [st, weights]);
  useEffect(() => { Promise.resolve().then(again); }, [again]);
  if (!st) return <GeekLoader text="Looking for new data on your topics…" />;
  return (
    <View>
      <Text style={[s.muted, { marginTop: 4 }]}>Public datasets just out on your keywords ({(st.terms ?? []).map((x) => `“${x}”`).join(', ') || 'your keywords'}), from Zenodo, NCBI GEO and Figshare, checked once a day: open, no login, on topic.</Text>
      {shown.items.map((d) => (
        <RadarCard key={d.id} d={d} onVote={async (up) => {
          const v = await taste.vote('dataset', d.id, up, d.title, [d.term]);
          if (v < 0) again();
          return v;
        }} />
      ))}
      {!shown.items.length ? <Empty>Nothing new on your keywords yet. myGeeKy looks once a day.</Empty> : null}
      <Hidden n={shown.hidden} onShow={async () => { await taste.unhide('dataset'); again(); }} />
    </View>
  );
}

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

export function DatasetsView({ field, weights, wanted, keywords }: { field: string; weights: Weights; wanted: string[]; keywords: string[] }) {
  if (field === 'new') return <RadarList keywords={keywords} weights={weights} />;
  return <DatasetList field={field} weights={weights} wanted={wanted} />;
}

function DatasetList({ field, weights, wanted }: { field: string; weights: Weights; wanted: string[] }) {
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
