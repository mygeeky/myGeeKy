// The 🎯 Chances planet: verified jobs, funding and conferences that myGeeKy's maker
// checked by hand. Matched to you here, on the phone; each one disappears after its
// deadline. 👍/👎 teach your model, 🚩 tells the maker one looks fake.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActionSheetIOS, Alert, Linking, Modal, Platform, Pressable, ScrollView, StyleSheet, Text,
  View } from 'react-native';
import { quickProfile, useApp } from '../lib/app-state';
import { countriesIn } from '../lib/countries';
import { type Item, JOB_TYPES, languagesOf, type ListName, loadLists, type Lists, ranked, type Ranked,
  reportLinks, type Said, VOTE_KIND } from '../lib/curated';
import * as seasons from '../lib/seasons';
import { C } from '../lib/theme';
import * as taste from '../lib/taste';
import { GCard, Hidden, s, Thumbs } from './growth-parts';
import { Empty, open, Segments } from './ui';

type Mode = 'seasons' | 'jobs' | 'funding' | 'conferences';
type ListMode = Exclude<Mode, 'seasons'>;
const MODES: [Mode, string][] = [['seasons', 'Seasons'], ['jobs', 'Jobs'], ['funding', 'Funding'],
  ['conferences', 'Conferences']];
const EVERYWHERE = 'Everywhere';
const EMOJI: Record<string, string> = { phd: '🎓', postdoc: '🔬', master: '📘', job: '💼', internship: '🧪', fellowship: '🏅',
  faculty: '🏛', engineer: '🛠' };
const ABOUT: Record<Mode, string> = {
  seasons: 'Scholarships and programmes that come back every year. The preparing takes longer than the applying, so these say what is coming, not only what is open.',
  jobs: 'PhD places, postdocs and research jobs that myGeeKy checked are real. Nobody learns what you looked at.',
  funding: 'Grants, fellowships, scholarships and travel grants for your field.',
  conferences: 'Conferences in your field: the abstract deadline and what students get.',
};
const NONE: Record<Mode, string> = {
  seasons: 'Nothing in this period. Step forward to see what is coming.',
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

function Translations({ it, onClose }: { it: Item; onClose: () => void }) {
  // English is the record: it is the English title and the deadline sentence that were checked word for
  // word against the page. This is a reading aid beside that, and says so at the bottom. Everything it
  // shows came down with the lists, so it works with no connection.
  const codes = languagesOf(it);
  const [code, setCode] = useState(codes[0] ?? '');
  const said: Said | undefined = it.translations?.[code];
  const dir = said?.rtl ? 'right' : 'left';
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={t.backdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} accessibilityLabel="Close" />
        <View style={t.sheet}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={t.tabs}>
            {codes.map((c) => (
              <Pressable key={c} onPress={() => setCode(c)} style={[t.tab, c === code && t.tabOn]}>
                <Text style={[t.tabText, c === code && t.tabTextOn]}>{it.translations?.[c]?.name}</Text>
              </Pressable>
            ))}
          </ScrollView>
          <ScrollView contentContainerStyle={{ paddingBottom: 20 }}>
            {said ? <>
              <Text style={[t.title, { textAlign: dir }]}>{said.title}</Text>
              {(['summary', 'who', 'amount', 'student'] as const).map((f) => (said[f]
                ? <Text key={f} style={[t.body, { textAlign: dir }]}>{said[f]}</Text> : null))}
            </> : null}
            <Text style={t.note}>Translated by machine, from the English below — which is what myGeeKy
              checked, word for word, against the page itself.</Text>
            <Text style={t.english}>{it.title}</Text>
            <Pressable onPress={() => open(it.url)}><Text style={t.link}>Open the page ↗</Text></Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const t = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#17171f', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16,
    maxHeight: '82%' },
  tabs: { gap: 7, paddingBottom: 12 },
  tab: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.1)' },
  tabOn: { backgroundColor: 'rgba(255,111,216,0.35)' },
  tabText: { color: C.muted, fontSize: 13 },
  tabTextOn: { color: '#ffffff', fontWeight: '700' },
  title: { color: C.text, fontSize: 16, fontWeight: '700', marginBottom: 8 },
  body: { color: C.text, fontSize: 14, marginBottom: 7, lineHeight: 20 },
  note: { color: C.muted, fontSize: 11, marginTop: 16, lineHeight: 16 },
  english: { color: C.muted, fontSize: 12, marginTop: 6, fontStyle: 'italic' },
  link: { color: '#ff6fd8', fontSize: 13, marginTop: 14 },
});

function Chance({ kind, it, onVote }: { kind: ListMode; it: Ranked; onVote: (up: boolean) => Promise<number> }) {
  const bits = kind === 'jobs' ? [JOB_TYPES[it.type ?? 'job'], it.org, it.place, it.remote ? 'remote possible' : '']
    : kind === 'funding' ? [it.org, it.amount]
    : [it.place, [it.starts, it.ends && it.ends !== it.starts ? `to ${it.ends}` : ''].filter(Boolean).join(' ')];
  const soon = it.daysLeft !== null && it.daysLeft <= 7;
  const [saying, setSaying] = useState(false);
  const codes = languagesOf(it);
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
      {codes.length ? (
        // the languages name themselves, in their own scripts: someone who cannot read this card can
        // still see that it is for them, which an English word like "Translate" would not manage
        <Pressable onPress={() => setSaying(true)} accessibilityLabel="Read in another language" hitSlop={6}>
          <Text style={s.muted}>🌍 {codes.map((c) => it.translations?.[c]?.name).join(' · ')}</Text>
        </Pressable>) : null}
      {saying ? <Translations it={it} onClose={() => setSaying(false)} /> : null}
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

// --------------------------------------------------------------------------- seasons
const STATE: Record<string, [string, 'good' | 'warn' | 'muted']> = {
  open: ['🟢', 'good'], soon: ['🟡', 'warn'], later: ['⚪', 'muted'], unknown: ['⚪', 'muted'],
};

/** One recurring programme: where it stands, what it wants prepared, and the sentence that proves it
 *  ever ran. A future date is always labelled as expected -- next year's call has no page yet. */
function SeasonCard({ it }: { it: seasons.Dated }) {
  const [why, setWhy] = useState(false);
  const [mark, tone] = STATE[it.when.state] ?? STATE.unknown;
  const occurrence = it.occurrence;
  const said = seasons.noticeText(it.when);
  const bits = [it.org, it.through && `through ${it.through}`, it.goes_to && `in ${it.goes_to}`,
    it.levels.length ? it.levels.join(' · ') : ''].filter(Boolean);
  const years = it.when.years;
  return (
    <GCard>
      <View style={s.head}>
        <Pressable style={{ flex: 1 }} onPress={() => open(it.url)}>
          <Text style={s.title}>{mark} {it.title}</Text>
        </Pressable>
      </View>
      {bits.length ? <Text style={s.muted}>{bits.join(' · ')}</Text> : null}
      <Text style={tone === 'good' ? s.good : tone === 'warn' ? s.warn : s.muted}>{said}</Text>
      {it.summary ? <Text style={s.body}>{it.summary}</Text> : null}
      {it.for.length ? <Text style={s.muted}>Open to: {it.for.join(', ')}</Text> : null}
      {it.prepare.length && seasons.prepareNow(it) ? (
        <View style={{ marginTop: 6 }}>
          <Text style={s.warn}>Worth starting now — {it.prepare_weeks} week
            {it.prepare_weeks === 1 ? '' : 's'} of paperwork:</Text>
          {it.prepare.slice(0, 5).map((step, i) => (
            <Text key={i} style={s.muted}>· {step}</Text>
          ))}
        </View>
      ) : null}
      <View style={[s.row, { justifyContent: 'space-between' }]}>
        <Text style={s.muted}>
          {years ? `seen ${years} year${years === 1 ? '' : 's'}` : 'not seen yet'}
          {occurrence?.confirmed ? ' · this one was read on the page' : ''}
        </Text>
        {occurrence?.quote ? (
          <Pressable onPress={() => setWhy(!why)} accessibilityLabel="Why myGeeKy believes this" hitSlop={8}>
            <Text style={s.link}>{why ? 'Hide the proof' : 'Why?'}</Text>
          </Pressable>
        ) : null}
      </View>
      {why && occurrence ? (
        <View style={{ marginTop: 6 }}>
          <Text style={s.muted}>“{occurrence.quote}”</Text>
          <Pressable onPress={() => open(occurrence.url)}>
            <Text style={s.link}>The page it came from ↗</Text>
          </Pressable>
        </View>
      ) : null}
    </GCard>
  );
}

/** Which period to look at, and where to look. Both sit ABOVE the kinds, because both apply to all of
 *  them: a filter under one tab reads as belonging to that tab alone. */
function Picker<T extends string>({ value, options, onChange, label }: {
  value: T; options: [T, string][]; onChange: (v: T) => void; label: string;
}) {
  if (options.length < 2) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={p.row}
               accessibilityLabel={label}>
      {options.map(([v, text]) => (
        <Pressable key={v} onPress={() => onChange(v)} style={[p.chip, v === value && p.chipOn]}>
          <Text style={[p.chipText, v === value && p.chipTextOn]} numberOfLines={1}>{text}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const p = StyleSheet.create({
  row: { gap: 6, paddingVertical: 6, paddingRight: 16 },
  chip: { paddingHorizontal: 11, paddingVertical: 6, borderRadius: 13, backgroundColor: 'rgba(255,255,255,0.08)' },
  chipOn: { backgroundColor: 'rgba(244,114,182,0.35)' },
  chipText: { color: C.muted, fontSize: 12.5 },
  chipTextOn: { color: '#ffffff', fontWeight: '700' },
});

export function ChancesView() {
  const { settings, profile } = useApp();
  const [mode, setMode] = useState<Mode>('jobs');
  const [lists, setLists] = useState<Lists | null>(null);
  const [data, setData] = useState<{ items: Ranked[]; hidden: number }>({ items: [], hidden: 0 });
  const [country, setCountry] = useState(EVERYWHERE);
  // null until somebody picks: the period shown is then DERIVED, so the picker needs no effect to set
  // itself up and cannot cascade a render when the windows change underneath it
  const [picked, setPicked] = useState<string | null>(null);
  const weights = useMemo(() => profile?.weights ?? (settings ? quickProfile(settings).weights : {}), [profile, settings]);

  useEffect(() => {
    loadLists().then(setLists).catch(() => undefined);
  }, []);
  const rank = useCallback(async () => {
    if (lists && mode !== 'seasons') setData(await ranked(mode as ListMode, lists, weights));
  }, [lists, mode, weights]);
  useEffect(() => {
    Promise.resolve().then(rank);           // after this render, not inside it
  }, [rank]);

  // Seasons come out of the same downloaded file, read here rather than ranked: a season is placed by
  // its dates, not by how well it matches you.
  const windows = useMemo(() => (lists ? seasons.windows(seasons.seasonsOf(lists)) : []), [lists]);
  const offered = useMemo(() => seasons.around(windows), [windows]);
  const showing = (picked ? offered.find((w) => w.id === picked) : undefined)
    ?? offered[seasons.current(offered)] ?? offered[0];

  // Every country anything on this screen is actually in, so the filter can never offer an empty one.
  const places = useMemo(() => {
    if (!lists) return [];
    const listed = [...lists.jobs, ...lists.conferences];
    const going = windows.flatMap((w) => w.seasons.map((x) => ({ country: x.goes_to })));
    return countriesIn([...listed, ...going]);
  }, [lists, windows]);
  const inCountry = useCallback((place: string) =>
    country === EVERYWHERE || !place || place === country, [country]);

  const shown = mode === 'seasons' ? [] : data.items.filter((it) => inCountry(it.country ?? ''));
  const heldBack = mode === 'seasons' ? 0 : data.items.length - shown.length;
  const inSeason = (showing?.seasons ?? []).filter((x) => inCountry(x.goes_to));
  const kind = mode === 'seasons' ? null : VOTE_KIND[mode as ListMode];

  return (
    <View>
      {/* Both pickers sit ABOVE the kinds, because both apply to all of them: a filter under one tab
          reads as belonging to that tab alone. */}
      <Picker label="Where" value={country} options={[[EVERYWHERE, '🌍 Everywhere'] as [string, string],
        ...places.map((c) => [c, c] as [string, string])]} onChange={setCountry} />
      {mode === 'seasons' && offered.length ? (
        <Picker label="Which period" value={showing?.id ?? ''}
          options={offered.map((w) => [w.id, `${w.now ? '▸ ' : ''}${w.label}`] as [string, string])}
          onChange={setPicked} />
      ) : null}
      <View style={{ marginHorizontal: -16 }}><Segments value={mode} options={MODES} onChange={setMode} /></View>
      <Text style={s.muted}>{ABOUT[mode]}{mode === 'seasons' ? '' : ' Each one disappears after its deadline.'} 👍 / 👎 teach your model; 🚩 tells the maker one looks fake.</Text>

      {mode === 'seasons' ? (<>
        {!lists ? <Empty>Loading…</Empty> : !inSeason.length ? <Empty>{NONE.seasons}</Empty> : null}
        {inSeason.map((it) => <SeasonCard key={`${it.id}${it.occurrence?.opens ?? ''}`} it={it} />)}
      </>) : (<>
        {!lists ? <Empty>Loading…</Empty> : !shown.length ? <Empty>{NONE[mode]}</Empty> : null}
        {shown.map((it) => (
          <Chance key={it.id} kind={mode as ListMode} it={it} onVote={async (up) => {
            const v = await taste.vote(kind!, it.id, up, `${it.title} ${it.summary}`, it.keywords);
            if (v < 0) rank();
            return v;
          }} />
        ))}
        {heldBack ? <Text style={s.muted}>{heldBack} more elsewhere — tap 🌍 Everywhere to see them.</Text> : null}
        <Hidden n={data.hidden} onShow={async () => { await taste.unhide(kind!); rank(); }} />
      </>)}
    </View>
  );
}
