// The 🎯 Chances planet: verified jobs, funding and conferences that myGeeKy's maker
// checked by hand. Matched to you here, on the phone; each one disappears after its
// deadline. 👍/👎 teach your model, 🚩 tells the maker one looks fake.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActionSheetIOS, Alert, Linking, Platform, Pressable, Text, View } from 'react-native';
import { quickProfile, useApp } from '../lib/app-state';
import { type Item, JOB_TYPES, type ListName, loadLists, type Lists, ranked, type Ranked, reportLinks, VOTE_KIND } from '../lib/curated';
import * as taste from '../lib/taste';
import { GCard, Hidden, s, Thumbs } from './growth-parts';
import { Empty, open, Segments } from './ui';

type Mode = 'jobs' | 'funding' | 'conferences';
const MODES: [Mode, string][] = [['jobs', 'Jobs'], ['funding', 'Funding'], ['conferences', 'Conferences']];
const EMOJI: Record<string, string> = { phd: '🎓', postdoc: '🔬', master: '📘', job: '💼', internship: '🧪', fellowship: '🏅',
  faculty: '🏛', engineer: '🛠' };
const ABOUT: Record<Mode, string> = {
  jobs: 'PhD places, postdocs and research jobs that myGeeKy checked are real. Nobody learns what you looked at.',
  funding: 'Grants, fellowships, scholarships and travel grants for your field.',
  conferences: 'Conferences in your field: the abstract deadline and what students get.',
};
const NONE: Record<Mode, string> = {
  jobs: "No open verified jobs right now. New ones are added by hand once they're checked.",
  funding: 'No open funding calls right now. New ones show up here by themselves.',
  conferences: 'No upcoming conferences right now. New ones show up here by themselves.',
};

export function closes(days: number | null): string {
  if (days === null) return '';
  if (days <= 0) return 'closes today';
  if (days === 1) return 'closes tomorrow';
  return days <= 60 ? `closes in ${days} days` : `closes in ${Math.floor(days / 30)} months`;
}

function report(kind: ListName, it: Item) {
  const links = reportLinks(kind, it);
  const msg = 'Tell myGeeKy\'s maker, who checks it and takes it down. A GitHub issue is public; an email is private.';
  if (Platform.OS === 'ios') {
    ActionSheetIOS.showActionSheetWithOptions(
      { title: 'Looks fake, or no longer real?', message: msg, options: ['Report on GitHub', 'Email support', 'Cancel'], cancelButtonIndex: 2 },
      (i) => { if (i === 0) Linking.openURL(links.issue); if (i === 1) Linking.openURL(links.email); });
  } else {
    Alert.alert('Looks fake, or no longer real?', msg, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Email support', onPress: () => Linking.openURL(links.email) },
      { text: 'Report on GitHub', onPress: () => Linking.openURL(links.issue) },
    ]);
  }
}

function Chance({ kind, it, onVote }: { kind: Mode; it: Ranked; onVote: (up: boolean) => Promise<number> }) {
  const bits = kind === 'jobs' ? [JOB_TYPES[it.type ?? 'job'], it.org, it.place, it.remote ? 'remote possible' : '']
    : kind === 'funding' ? [it.org, it.amount]
    : [it.place, [it.starts, it.ends && it.ends !== it.starts ? `to ${it.ends}` : ''].filter(Boolean).join(' ')];
  const soon = it.daysLeft !== null && it.daysLeft <= 7;
  const emoji = kind === 'jobs' ? EMOJI[it.type ?? 'job'] ?? '💼' : kind === 'funding' ? '💶' : '🎤';
  return (
    <GCard>
      <View style={s.head}>
        <Pressable style={{ flex: 1 }} onPress={() => open(it.url)}>
          <Text style={s.title}>{emoji} {it.title}</Text>
        </Pressable>
        <Thumbs vote={it.vote} onVote={onVote} />
      </View>
      {bits.filter(Boolean).length ? <Text style={s.muted}>{bits.filter(Boolean).join(' · ')}</Text> : null}
      {it.original_title && it.language
        ? <Text style={s.muted}>🌍 Translated from {it.language} · {it.original_title}</Text> : null}
      {it.who ? <Text style={s.muted}>Who can apply: {it.who}</Text> : null}
      {it.student ? <Text style={s.muted}>Students: {it.student}</Text> : null}
      {it.summary ? <Text style={s.body}>{it.summary}</Text> : null}
      <View style={[s.row, { justifyContent: 'space-between' }]}>
        <Text style={soon ? s.warn : s.muted}>{soon ? '⏳ ' : ''}{closes(it.daysLeft)} ({it.deadline})
          {it.match.length ? ` · matches ${it.match.slice(0, 3).join(', ')}` : ''}</Text>
        <Pressable onPress={() => report(kind, it)} accessibilityLabel="Report: looks fake" hitSlop={8}>
          <Text style={{ fontSize: 16 }}>🚩</Text>
        </Pressable>
      </View>
    </GCard>
  );
}

export function ChancesView() {
  const { settings, profile } = useApp();
  const [mode, setMode] = useState<Mode>('jobs');
  const [lists, setLists] = useState<Lists | null>(null);
  const [data, setData] = useState<{ items: Ranked[]; hidden: number }>({ items: [], hidden: 0 });
  const weights = useMemo(() => profile?.weights ?? (settings ? quickProfile(settings).weights : {}), [profile, settings]);

  useEffect(() => {
    loadLists().then(setLists).catch(() => undefined);
  }, []);
  const rank = useCallback(async () => {
    if (lists) setData(await ranked(mode, lists, weights));
  }, [lists, mode, weights]);
  useEffect(() => {
    Promise.resolve().then(rank);           // after this render, not inside it
  }, [rank]);

  const kind = VOTE_KIND[mode];
  return (
    <View>
      <View style={{ marginHorizontal: -16 }}><Segments value={mode} options={MODES} onChange={setMode} /></View>
      <Text style={s.muted}>{ABOUT[mode]} Each one disappears after its deadline. 👍 / 👎 teach your model; 🚩 tells the maker one looks fake.</Text>
      {!lists ? <Empty>Loading…</Empty> : !data.items.length ? <Empty>{NONE[mode]}</Empty> : null}
      {data.items.map((it) => (
        <Chance key={it.id} kind={mode} it={it} onVote={async (up) => {
          const v = await taste.vote(kind, it.id, up, `${it.title} ${it.summary}`, it.keywords);
          if (v < 0) rank();
          return v;
        }} />
      ))}
      <Hidden n={data.hidden} onShow={async () => { await taste.unhide(kind); rank(); }} />
    </View>
  );
}
