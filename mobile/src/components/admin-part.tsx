// 🛠 Admin, the maker's part of "You", on the phone: an overview only. Downloads and stars, what's waiting on the
// computer, and what TRACE noticed this week, as numbers (lib/admin.ts, from the computer's admin_summary.json): no
// names, no email addresses, no buttons that change anything, no passwords or keys. Reviewing, publishing, support
// email and everything else happen in the computer's Admin console.
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { StatTiles } from './model-plots';
import { s, Section, timeAgo } from './ui';
import { loadSummary, type Summary } from '../lib/admin';
import { C } from '../lib/theme';

export function AdminPart() {
  const [got, setGot] = useState<Summary | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setNote('');
    try {
      const sum = await loadSummary();
      setGot(sum);
      if (!sum) setNote('Nothing to show yet: open Admin on your computer once (it writes the overview into your saved data), or this isn\'t the maker\'s GitHub account.');
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Could not read your saved data.');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { Promise.resolve().then(refresh); }, [refresh]);             // after this render, not inside it

  if (!got) return <Text style={s.small}>{loading ? 'Reading your saved data…' : note}</Text>;
  const { adoption: ad, waiting: w, invites: f, trace: t } = got;
  const fmt = (v: number | null) => (v === null ? '–' : String(v));
  return (
    <>
      <View style={[s.row, { alignItems: 'center', justifyContent: 'space-between' }]}>
        <Text style={[s.small, { flex: 1 }]}>{got.updatedAt ? `updated ${timeAgo(got.updatedAt)} on your computer` : ''}</Text>
        <Text style={a.link} onPress={loading ? undefined : refresh}>{loading ? 'Refreshing…' : 'Refresh'}</Text>
      </View>

      <Section>📈 DOWNLOADS AND USE</Section>
      <StatTiles tiles={[[fmt(ad.pypi_week), 'PyPI / week'], [fmt(ad.installer_downloads), 'installs (.exe)'],
        [fmt(ad.stars), 'stars'], [fmt(ad.signals_users), 'on Signals']]} />

      <Section>🖥 WAITING ON YOUR COMPUTER</Section>
      <StatTiles tiles={[[String(w.listings + w.news + w.highlights + w.quiz_batches), 'to review'],
        [String(w.ready_to_publish), 'ready to publish'], [String(w.support), 'support emails'], [String(w.ideas), 'ideas']]} />
      <Text style={s.small}>
        {w.listings} listings · {w.news} news · {w.highlights} Highlights · {w.quiz_batches} quiz batches · {w.keywords} keywords to teach
        {got.lastPublish ? ` · last published ${timeAgo(got.lastPublish)}` : ''}
      </Text>

      <Section>⚡ TRACE THIS WEEK</Section>
      <Text style={s.small}>
        {t.triggersWeek} triggers · {t.acceptedWeek} accepted · DeepSeek today {t.spentToday} of {t.perDay}
        {t.rising.length ? `\nRising: ${t.rising.join(' · ')}` : ''}
      </Text>
      <Text style={[s.small, { marginTop: 6 }]}>Invites: {f.invited} sent, {f.joined} joined.</Text>
      <Text style={[s.small, { marginTop: 10, color: C.muted }]}>Reviewing, publishing and support email are done in the Admin console on your computer.</Text>
    </>
  );
}

const a = StyleSheet.create({
  link: { color: C.cyan, fontSize: 14 },
});
