// 🛠 Admin, the maker's part of "You", on the phone: a glance, nothing more. Downloads, stars, people on Signals and how
// much is waiting on the computer, as numbers: no names, no email addresses, no buttons that change anything. Reviewing,
// inviting, writing and publishing all happen on the computer (the desktop's admin tab). It shows only for the account
// GitHub says owns the connected data repo (lib/admin.ts adminLogin), so it needs no lock of its own.
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { StatTiles } from './model-plots';
import { s, Section, timeAgo } from './ui';
import { type AdminData, funnel, loadAdmin, loadListings, pendingActions, quizStatus, withPending } from '../lib/admin';
import { loadLists } from '../lib/curated';
import { C } from '../lib/theme';

type Glance = { data: AdminData; review: number; quizBatches: number };

export function AdminPart() {
  const [got, setGot] = useState<Glance | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setNote('');
    try {
      const [data, pending, lists] = await Promise.all([loadAdmin(), pendingActions(), loadLists().catch(() => null)]);
      if (!data) {
        setGot(null);
        setNote('Nothing to show: admin_prospects.json is not in your data repo yet, or this is not the maker\'s account.');
        return;
      }
      const [listings, quiz] = await Promise.all([loadListings(pending), quizStatus(lists)]);
      setGot({ data: { ...data, people: withPending(data.people, pending) }, review: listings?.toReview.length ?? 0,
               quizBatches: (quiz?.rows ?? []).filter((r) => r.spotCheck).length });
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Could not read your data repo.');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { Promise.resolve().then(refresh); }, [refresh]);             // after this render, not inside it

  if (!got) return <Text style={s.small}>{loading ? 'Reading your data repo…' : note}</Text>;
  const { data, review, quizBatches } = got;
  const ad = data.adoption;
  const f = funnel(data.people);
  const fmt = (v: number | null) => (v === null ? '–' : String(v));
  return (
    <>
      <View style={[s.row, { alignItems: 'center', justifyContent: 'space-between' }]}>
        <Text style={[s.small, { flex: 1 }]}>{data.updatedAt ? `updated ${timeAgo(data.updatedAt)} on your computer` : ''}</Text>
        <Text style={a.link} onPress={loading ? undefined : refresh}>{loading ? 'Refreshing…' : 'Refresh'}</Text>
      </View>
      {note ? <Text style={[s.small, { color: C.amber, marginTop: 4 }]}>{note}</Text> : null}

      <Section>📈 DOWNLOADS AND USE</Section>
      <StatTiles tiles={[[fmt(ad.pypi_week), 'PyPI / week'], [fmt(ad.installer_downloads), 'installs (.exe)'],
        [fmt(ad.stars), 'stars'], [fmt(ad.signals_users), 'on Signals']]} />

      <Section>🖥 WAITING ON YOUR COMPUTER</Section>
      <Text style={s.small}>
        {review} listings to review · {quizBatches} quiz batches to spot-check · {data.inbox.length} ideas in the inbox ·{' '}
        {data.keywordRequests.length} keywords to teach · invites: {f.invited} sent, {f.joined} joined
      </Text>
      <Text style={[s.small, { marginTop: 6 }]}>Reviewing, inviting, writing and publishing are done in the computer&apos;s admin tab.</Text>
    </>
  );
}

const a = StyleSheet.create({
  link: { color: C.cyan, fontSize: 14 },
});
