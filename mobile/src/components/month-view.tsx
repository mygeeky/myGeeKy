// My month: your rank on its ladder, your month in eight drawings with GeekOc, and this month's card to share -- the
// desktop's gui/month_ui.py. The counting and every drawing come from lib/month.ts and lib/month-viz.ts (the same as
// the desktop's month.py and monthviz.py). The card is shared as a
// 1080 x 1350 picture through the phone's own share sheet: you choose where it goes; nothing is posted for you.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Sharing from 'expo-sharing';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { type LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { SvgXml } from 'react-native-svg';
import { captureRef } from 'react-native-view-shot';
import geekocData from '../data/geekoc.json';
import { useApp } from '../lib/app-state';
import { earned, TIERS } from '../lib/badges';
import { loadLists } from '../lib/curated';
import { cachedBrain, localEvents, queuedUsage, savingLink } from '../lib/model-repo';
import * as M from '../lib/month';
import * as MV from '../lib/month-viz';
import { myGitHub, refreshMyGitHub } from '../lib/my-github';
import * as P from '../lib/protocols';
import { loadReceived, loadSent } from '../lib/signals';
import { C } from '../lib/theme';
import { loadWins } from '../lib/wins';
import { useToast } from './toast';
import { GeekLoader, useHold } from './geek-loader';
import { badgeCounts as gameBadges } from '../lib/games-store';

const POSES = geekocData.poses as Record<string, string>;
const CARD_MAX = 380;
const RANK_SEEN_KEY = 'mygeeky.rank.seen';

type Records = { usage: unknown[]; events: unknown[]; wins: unknown[]; terms: unknown[]; myRepos: Record<string, string> };

/** What this phone knows you did: your computers' usage, follows and interest terms once your data repo is
 *  connected, plus this phone's own lines not yet sent; and your wins. */
async function records(): Promise<Records> {
  const brain = (await savingLink()) ? (await cachedBrain())?.data : null;
  const [queued, wins, local] = await Promise.all([queuedUsage(), loadWins().catch(() => null), localEvents().catch(() => [])]);
  return {
    usage: [...(brain?.usage ?? []), ...queued], events: brain?.eventKinds ?? [], wins: wins?.wins ?? [],
    terms: [...(brain?.recent ?? []), ...local],
    myRepos: Object.fromEntries((wins?.myRepos ?? []).map((r) => [r.name, r.language])),
  };
}

/** Everything the eight drawings need besides the records (protocols, badges, signals, GitHub events). */
async function extras(keywords: number) {
  const [lists, sent, received, gh] = await Promise.all([
    loadLists().catch(() => null), loadSent().catch(() => []), loadReceived(), myGitHub()]);
  const state: P.State = lists ? await P.load(lists).catch(() => ({})) : {};
  const views = Object.values(state).map((e) => P.view(e, {}));
  const protocols = [...views.filter((v) => v.doneCount < v.total), ...views.filter((v) => v.doneCount >= v.total)].map((v) => ({
    title: v.title, steps: v.stages.map((st) => [st.title, st.status === 'done' || st.status === 'known'] as [string, boolean]) }));
  const level = (t: string) => TIERS.indexOf(t as typeof TIERS[number]) + 1;
  const badges = (await earned(keywords, [], undefined, await gameBadges().catch(() => ({}))).catch(() => [])).filter((b) => b.tier)
    .sort((a, b) => level(b.tier) - level(a.tier) || (a.name < b.name ? -1 : 1)).map((b) => [b.emoji, b.name, b.tier]);
  return { protocols, badges, sent, received, github: gh.events ?? [], langs: gh.langs ?? {} };
}

type Extras = Awaited<ReturnType<typeof extras>>;
// The last records, kept while the app runs: opening You again shows them at once, then refreshes quietly.
const last: { data: Records | null; more: Extras | null } = { data: null, more: null };
const REVEAL_MS = 90;          // the drawings appear one after another, so the rank and card show first

function heightOf(svg: string): number {
  return Number(/viewBox="0 0 \d+ (\d+)"/.exec(svg)?.[1] ?? 200);
}

/** Your rank's name if it went up since you were last told ("" if not); the first time only remembers. */
export async function rankNews(): Promise<string> {
  const r = await records();
  const now = new Date();
  const s = M.summary(r.usage, r.events, r.wins, now.getFullYear(), now.getMonth() + 1);
  const raw = await AsyncStorage.getItem(RANK_SEEN_KEY);
  const before = raw === null ? null : Number(raw);
  if (before !== s.rank) await AsyncStorage.setItem(RANK_SEEN_KEY, String(s.rank));
  return before !== null && Number.isFinite(before) && s.rank > before ? s.rank_name : '';
}

export function MonthView() {
  const toast = useToast();
  const { settings, token } = useApp();
  const username = settings?.username ?? '', keywords = settings?.keywords.length ?? 0;
  const [more, setMoreState] = useState<Extras | null>(last.more);
  const setMore = useCallback((m: Extras) => { last.more = m; setMoreState(m); }, []);
  const today = new Date();
  const thisMonth: [number, number] = [today.getFullYear(), today.getMonth() + 1];
  const [shown, setShown] = useState<[number, number]>(thisMonth);
  const [data, setDataState] = useState<Records | null>(last.data);
  const setData = useCallback((d: Records) => { last.data = d; setDataState(d); }, []);
  const [reveal, setReveal] = useState(0);
  const holdMonth = useHold(!data);
  const [hidden, setHidden] = useState<string[]>([]);
  const [width, setWidth] = useState(0);
  const [sharing, setSharing] = useState(false);
  const shot = useRef<View>(null);

  useEffect(() => { records().then(setData).catch(() => setData({ usage: [], events: [], wins: [], terms: [], myRepos: {} })); }, [setData]);
  useEffect(() => {
    extras(keywords).then(setMore).catch(() => undefined);
    refreshMyGitHub(username, token).then((read) => (read ? extras(keywords).then(setMore) : undefined)).catch(() => undefined);
  }, [username, keywords, token, setMore]);
  const stats = useMemo(() => (data && more ? MV.stats({
    has_github: !!username, github: more.github, repo_langs: { ...more.langs, ...data.myRepos }, wins: data.wins,
    events: [...data.terms, ...data.events.filter((e) => (e as { kind?: string }).kind === 'follow' && !(data.terms as { at?: string; kind?: string }[])
      .some((t) => t.kind === 'follow' && t.at === (e as { at?: string }).at))],
    usage: data.usage, protocols: more.protocols, badges: more.badges, sent: more.sent, received: more.received,
  }, shown[0], shown[1], -new Date().getTimezoneOffset()) : null), [data, more, shown, username]);
  const s = useMemo(() => (data ? M.summary(data.usage, data.events, data.wins, shown[0], shown[1]) : null), [data, shown]);
  const first = useMemo(() => (data ? M.firstMonth(data.usage, data.events) ?? thisMonth : thisMonth),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data]);
  const card = useMemo(() => (s ? M.cardSvg(s, POSES[M.cardPose(s)] ?? '', hidden) : ''), [s, hidden]);
  const ladder = useMemo(() => (s ? M.ladderSvg(s.points, !C.dark) : ''), [s]);
  const drawings = useMemo(() => (stats ? MV.DIVES.map(([key, title, , draw]) => {
    const svg = draw(stats, POSES);
    return { key, title, svg, h: heightOf(svg), said: MV.say(stats, key) };
  }) : []), [stats]);
  useEffect(() => {
    if (!drawings.length || reveal >= drawings.length) return;
    const t = setTimeout(() => setReveal(reveal + 1), REVEAL_MS);
    return () => clearTimeout(t);
  }, [drawings, reveal]);

  const move = (step: number) => {
    let [y, m] = shown;
    m += step;
    if (m < 1) [y, m] = [y - 1, 12];
    if (m > 12) [y, m] = [y + 1, 1];
    setShown([y, m]);
    setHidden([]);
  };
  const before = (a: [number, number], b: [number, number]) => a[0] < b[0] || (a[0] === b[0] && a[1] < b[1]);

  const share = useCallback(async () => {
    if (!shot.current) return;
    setSharing(true);
    try {
      const uri = await captureRef(shot, { format: 'png', width: 1080, height: 1350, result: 'tmpfile' });
      if (!(await Sharing.isAvailableAsync())) {
        toast("This phone can't share pictures from myGeeKy.");
        return;
      }
      await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share your month', UTI: 'public.png' });
    } catch {
      toast("Couldn't make the picture. Try again.");
    } finally {
      setSharing(false);
    }
  }, [toast]);

  if (holdMonth || !s) return <GeekLoader text="Counting your month…" />;
  const cardW = Math.min(width, CARD_MAX);
  return (
    <View onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}>
      <View style={st.nav}>
        <Pressable onPress={() => move(-1)} disabled={!before(first, shown)} hitSlop={10}
                   style={[st.arrow, !before(first, shown) && st.off]}><Text style={st.arrowText}>‹</Text></Pressable>
        <Text style={st.title}>{s.month_name} {s.year}</Text>
        <Pressable onPress={() => move(1)} disabled={!before(shown, thisMonth)} hitSlop={10}
                   style={[st.arrow, !before(shown, thisMonth) && st.off]}><Text style={st.arrowText}>›</Text></Pressable>
      </View>
      <Text style={st.rank}>🎖  {M.rankLine(s)}</Text>
      <Text style={st.muted}>{M.monthLine(s)}</Text>
      {width > 0 ? <SvgXml xml={ladder} width={width} height={(width * 170) / 640} /> : null}

      <Text style={st.head}>YOUR CARD</Text>
      {cardW > 0 ? (
        <View style={{ alignItems: 'center' }}>
          <View ref={shot} collapsable={false} style={{ width: cardW, height: cardW * 1.25, borderRadius: 14, overflow: 'hidden' }}>
            <SvgXml xml={card} width={cardW} height={cardW * 1.25} />
          </View>
        </View>
      ) : null}
      {Object.keys(s.counts).length ? <Text style={st.muted}>Show on the card (tap to hide):</Text> : null}
      <View style={st.chips}>
        {Object.entries(s.counts).map(([k, v]) => {
          const on = !hidden.includes(k);
          return (
            <Pressable key={k} onPress={() => setHidden(on ? [...hidden, k] : hidden.filter((h) => h !== k))}
                       style={[st.chip, on ? st.chipOn : null]}>
              <Text style={[st.chipText, !on && { textDecorationLine: 'line-through' }]}>
                {v} {v === 1 ? M.KINDS[k][2] : M.KINDS[k][1]}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <Pressable onPress={share} disabled={sharing} style={({ pressed }) => [st.share, (pressed || sharing) && { opacity: 0.8 }]}>
        <Text style={st.shareText}>{sharing ? 'Making the picture…' : '📤  Share my month'}</Text>
      </Pressable>
      <Text style={st.head}>YOUR MONTH IN PICTURES</Text>
      {drawings.length && width > 0 ? drawings.slice(0, reveal).map(({ key, title, svg, h, said }) => {
        const w = Math.min(width, 440);
        return (
          <View key={key} style={{ marginBottom: 16 }}>
            <Text style={st.diveTitle}>{title}</Text>
            <Text style={st.diveSay}>🐙 {said}</Text>
            <View style={{ alignItems: 'center', marginTop: 8 }}>
              <SvgXml xml={svg} width={w} height={(w * h) / 320} />
            </View>
          </View>
        );
      }) : null}
      {reveal < Math.max(drawings.length, 1) ? <GeekLoader text="Drawing your month…" size={56} /> : null}

      <Text style={st.note}>
        Points come from what you do yourself: reading, learning, building, sharing ideas and meeting people. They count
        over all your time in myGeeKy, so a rank never goes down. Worked out on this phone; nothing is sent anywhere,
        and nothing is posted for you.
      </Text>
      <Text style={st.note}>
        Points: {Object.entries(M.POINTS).sort((a, b) => a[1] - b[1]).map(([k, n]) => `${M.KINDS[k][2]} +${n}`).join(', ')}
      </Text>
    </View>
  );
}

const st = StyleSheet.create({
  nav: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  arrow: { width: 34, height: 34, borderRadius: 10, backgroundColor: C.card, alignItems: 'center', justifyContent: 'center' },
  off: { opacity: 0.3 },
  arrowText: { color: C.text, fontSize: 20, fontWeight: '800', marginTop: -2 },
  title: { flex: 1, color: C.text, fontSize: 17, fontWeight: '800', textAlign: 'center' },
  rank: { color: C.text, fontSize: 15, fontWeight: '800' },
  muted: { color: C.muted, fontSize: 12.5, marginTop: 4, marginBottom: 6 },
  head: { color: C.text, fontSize: 11, fontWeight: '800', letterSpacing: 0.8, marginTop: 14, marginBottom: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  chip: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: C.card, borderWidth: 1, borderColor: C.line },
  chipOn: { borderColor: C.violet },
  chipText: { color: C.text, fontSize: 12.5, fontWeight: '700' },
  share: { backgroundColor: C.violet, borderRadius: 14, paddingVertical: 14, alignItems: 'center', marginTop: 14 },
  shareText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  note: { color: C.muted, fontSize: 12, lineHeight: 17, marginTop: 10 },
  diveTitle: { color: C.text, fontSize: 15, fontWeight: '800' },
  diveSay: { color: C.muted, fontSize: 12.5, marginTop: 2 },
});
