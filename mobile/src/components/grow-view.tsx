// The 🌱 Grow planet: Rising Skills (what's growing in your field and missing from
// you), Protocols, Learn (curated resources), Wins (new stars, forks, citations)
// and Collaborators (fellow users who complement you). Everything is matched here,
// on the phone; 👍/👎 teach your model.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { quickProfile, timeAgo, useApp } from '../lib/app-state';
import { matches, type Match } from '../lib/collab';
import { loadLists, type Lists, ranked, RESOURCE_TYPES, type Ranked } from '../lib/curated';
import { collabAsked, isSetUp, loadBeacons, type Parsed, send, signalsData } from '../lib/signals';
import { load as loadProtocols } from '../lib/protocols';
import { type Doc, fieldDocs, find, note, ownText, rising, type Rising, type RisingResult, shapes, skillsIn } from '../lib/skills';
import { SkillViews } from './skill-views';
import * as taste from '../lib/taste';
import { C } from '../lib/theme';
import { recent, refreshWins, type WinsState, loadWins } from '../lib/wins';
import { Button, GCard, Hidden, s, Thumbs } from './growth-parts';
import { ProtocolsView } from './protocols-view';
import { QuizView } from './quiz-view';
import { HighlightsView } from './highlights-view';
import { Empty, open, Segments } from './ui';
import { GeekLoader, useHold } from './geek-loader';

export type GrowMode = 'highlights' | 'skills' | 'paths' | 'quiz' | 'learn' | 'wins' | 'collab';
type Mode = GrowMode;
const MODES: [Mode, string][] = [['highlights', 'Highlights'], ['skills', 'Skills'], ['paths', 'Protocols'], ['quiz', 'Quiz'], ['learn', 'Learn'],
  ['wins', 'Wins'], ['collab', 'People']];
const ABOUT: Record<Mode, string> = {
  highlights: 'Research articles picked by the maker, each retold as a short news article in plain words: what they found, '
    + 'who did it, what they did and with which tools. Tap one to read it in your language.',
  skills: "Skills growing in your field that you don't show yet. 👍 / 👎 teach it what to suggest; 🧭 turns one into steps.",
  paths: 'A skill as stages, e.g. R basics → statistics with R → data analysis → a real project. A short check skips what you know. '
    + 'Reviewed ones come from the maker; for any other skill myGeeKy builds one from GitHub and papers. Change it, then 📤 publish it.',
  quiz: "Ten questions from a protocol's own bank: half basics, then applied, then a few real pitfalls. Each one shows the "
    + 'source it came from once you answer. Only your best counts, one attempt a day, and it stays on this phone.',
  learn: "Free courses, books, tutorials and repos picked by myGeeKy's maker, matched to you and your rising skills.",
  wins: 'New stars and forks on your repos, and new citations of your papers. Checked once a day.',
  collab: "Fellow myGeeKy users whose skills complement yours. 🤝 is sealed: they only see it if they pick you too.",
};

function SkillCard({ sk, started, onVote, onPath }: { sk: Rising; started: boolean; onVote: (up: boolean) => Promise<number>;
  onPath: () => void }) {
  return (
    <GCard>
      <View style={s.head}>
        <Text style={s.title}>{sk.name}{sk.rising ? <Text style={{ color: C.green, fontSize: 12 }}>  📈 rising</Text> : null}</Text>
        <Thumbs vote={sk.vote} onVote={onVote} />
      </View>
      <Text style={s.muted}>{[...sk.reasons, 'not in your profile yet'].join('; ')}</Text>
      {note(sk) ? <Text style={[s.muted, sk.rising && { color: C.green }]}>{note(sk)}</Text> : null}
      {sk.examples.map((e) => (
        <Pressable key={e.url} onPress={() => open(e.url)}><Text style={s.link} numberOfLines={1}>e.g. {e.title}</Text></Pressable>
      ))}
      <View style={s.row}>
        <Button label={started ? '✓ In your protocols' : '🧭 Make it a protocol'} onPress={onPath} disabled={started} />
      </View>
    </GCard>
  );
}

function ResourceCard({ r, onVote }: { r: Ranked; onVote: (up: boolean) => Promise<number> }) {
  const teaches = (r.skills ?? []).slice(0, 4).map((n) => find(n)?.name ?? n);
  return (
    <GCard>
      <View style={s.head}>
        <Pressable style={{ flex: 1 }} onPress={() => open(r.url)}>
          <Text style={s.title}>{RESOURCE_TYPES[r.type ?? 'website'] ?? '🌐'} {r.title}</Text>
        </Pressable>
        <Thumbs vote={r.vote} onVote={onVote} />
      </View>
      {r.summary ? <Text style={s.body}>{r.summary}</Text> : null}
      <Text style={s.muted}>{[r.level, teaches.length ? `teaches ${teaches.join(', ')}` : ''].filter(Boolean).join(' · ')}</Text>
    </GCard>
  );
}

/** `mode`/`onMode`: the part shown, when the orbit or the dock chooses it (home.tsx); else the view keeps its own. */
export function GrowView({ mode: shown, onMode }: { mode?: Mode; onMode?: (m: Mode) => void } = {}) {
  const { settings, token, profile } = useApp();
  const me = settings?.username ?? '';
  const [own, setOwn] = useState<Mode>('highlights');
  const mode = shown ?? own;
  const setMode = (m: Mode) => { setOwn(m); onMode?.(m); };
  // 🏁 pressed on a protocol: which quiz the 🏆 Quiz tab opens when it appears
  const [openQuiz, setOpenQuiz] = useState<{ pid: string; stage: string } | null>(null);
  const [lists, setLists] = useState<Lists | null>(null);
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [wins, setWins] = useState<WinsState | null>(null);
  const [startedSkills, setStartedSkills] = useState<Set<string>>(new Set());
  const [startWith, setStartWith] = useState<{ skill: string; goal: string } | null>(null);
  const [skills, setSkills] = useState<RisingResult | null>(null);
  const [resources, setResources] = useState<{ items: Ranked[]; hidden: number }>({ items: [], hidden: 0 });
  const [people, setPeople] = useState<{ people: Match[]; hidden: number } | null>(null);
  const [users, setUsers] = useState<Parsed[]>([]);
  const [signals, setSignals] = useState<boolean | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const holdSkills = useHold(!skills), holdLists = useHold(!lists), holdPeople = useHold(busy || !people);
  const weights = useMemo(() => profile?.weights ?? (settings ? quickProfile(settings).weights : {}), [profile, settings]);
  const keywords = useMemo(() => [...(settings?.keywords ?? []), ...(settings?.topics ?? [])], [settings]);

  // what's saved first, then the day's read of your stars and citations (when it's due)
  useEffect(() => {
    loadLists().then(setLists).catch(() => undefined);
    fieldDocs().then(setDocs).catch(() => setDocs([]));
    loadWins().then(setWins).catch(() => undefined);
    refreshWins(me, settings?.orcid || settings?.openalex || '', token).then(setWins).catch(() => undefined);
  }, [me, settings?.orcid, settings?.openalex, token]);

  // the planets keep reading your field while you're elsewhere: look again when you come back to it
  useEffect(() => {
    if (mode === 'skills' || mode === 'learn' || mode === 'paths') fieldDocs().then(setDocs).catch(() => undefined);
  }, [mode]);

  const mine = useMemo(() => ownText(keywords, profile?.field ?? [], wins ?? { wins: [], myRepos: [], myPapers: [] }),
    [keywords, profile, wins]);

  const rank = useCallback(async () => {
    if (!docs || !lists) return;
    const r = await rising({ docs, mine, weights, github: !!me });
    setSkills(r);
    const extra = Object.fromEntries(r.skills.slice(0, 6).map((x) => [x.name.toLowerCase(), 0.7]));
    setResources(await ranked('resources', lists, weights, extra));
  }, [docs, lists, mine, weights, me]);
  useEffect(() => {
    Promise.resolve().then(rank);           // after this render, not inside it
  }, [rank]);

  const loadPeople = useCallback(async () => {
    if (!me) return;
    const ok = await isSetUp();
    setSignals(ok);
    if (!ok) return;
    setBusy(true);
    try {
      const found = await loadBeacons(me, token);
      setUsers(found);
      const sd = await signalsData(me, weights, found, [], 0);
      const r = skills ?? (docs ? await rising({ docs, mine, weights, github: true, save: false }) : null);
      const have = new Set([...skillsIn(mine), 'Git']);
      setPeople(await matches(sd.people, have, new Set((r?.skills ?? []).map((x) => x.name)), await collabAsked(),
        (r?.strengths ?? []).map((x) => x.name)));
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't reach GitHub.");
    } finally {
      setBusy(false);
    }
  }, [me, token, weights, skills, docs, mine]);
  useEffect(() => {
    if (mode === 'collab' && people === null) Promise.resolve().then(loadPeople);
  }, [mode, people, loadPeople]);

  useEffect(() => {
    if (lists) loadProtocols(lists).then((st) => setStartedSkills(new Set(Object.values(st).map((e) => e.protocol.skill))))
      .catch(() => undefined);
  }, [lists, mode]);
  const started = startedSkills;
  const onPath = (name: string) => {
    setStartWith({ skill: name, goal: '' });
    setMode('paths');
  };
  const onStarted = useCallback(() => setStartWith(null), []);
  const vote = (kind: taste.Kind, id: string, text: string, tags: string[], again: () => void) => async (up: boolean) => {
    const v = await taste.vote(kind, id, up, text, tags);
    if (v < 0) again();
    return v;
  };

  return (
    <View>
      {onMode ? null : <View style={{ marginHorizontal: -16 }}><Segments value={mode} options={MODES} onChange={setMode} /></View>}
      <Text style={s.muted}>{ABOUT[mode]}</Text>
      {note ? <Text style={s.warn}>{note}</Text> : null}

      {mode === 'highlights' ? <HighlightsView items={lists ? lists.highlights : null} onLearn={(skill) => onPath(skill)} /> : null}

      {mode === 'skills' ? (
        holdSkills || !skills ? <GeekLoader text="Reading your field…" /> : (
          <View>
            {!skills.skills.length ? <Empty>No rising skills yet. They come from what myGeeKy read about your field: open Papers, Repos and AI models once, then come back.</Empty> : null}
            {skills.skills.length || skills.directions.length ? <SkillViews shapes={shapes(skills)} onPath={onPath} started={started} /> : null}
            {skills.skills.length ? <Text style={s.section}>ALL SUGGESTIONS</Text> : null}
            {skills.skills.map((sk) => (
              <SkillCard key={sk.name} sk={sk} started={started.has(sk.name)} onPath={() => onPath(sk.name)}
                         onVote={vote('skill', sk.name, sk.name, [sk.name], rank)} />
            ))}
            <Hidden n={skills.hidden} onShow={async () => { await taste.unhide('skill'); rank(); }} />
            {skills.strengths.length ? <Text style={s.section}>💪 YOUR STRENGTHS THAT ARE RISING TOO</Text> : null}
            {skills.strengths.slice(0, 5).map((sk) => (
              <GCard key={sk.name}><Text style={s.title}>{sk.name}</Text><Text style={s.muted}>{sk.reasons.join('; ')}; you already show it</Text></GCard>
            ))}
          </View>
        )
      ) : null}

      {mode === 'paths' ? (
        <ProtocolsView lists={lists} docs={docs ?? []} repos={wins?.myRepos ?? []} profile={mine} token={token} weights={weights}
                       startWith={startWith} onStarted={onStarted}
                       onQuiz={(pid, stage) => { setOpenQuiz({ pid, stage }); setMode('quiz'); }} />
      ) : null}

      {mode === 'quiz' ? (
        <QuizView lists={lists} onStart={(skill) => onPath(skill)} open={openQuiz}
                  onOpened={() => setOpenQuiz(null)} />
      ) : null}

      {mode === 'learn' ? (
        <View>
          {resources.items.slice(0, 30).map((r) => (
            <ResourceCard key={r.id} r={r} onVote={vote('resource', r.id, r.title, [...(r.skills ?? []), ...r.keywords], rank)} />
          ))}
          {!resources.items.length ? (holdLists ? <GeekLoader /> : <Empty>No learning resources yet.</Empty>) : null}
          <Hidden n={resources.hidden} onShow={async () => { await taste.unhide('resource'); rank(); }} />
        </View>
      ) : null}

      {mode === 'wins' ? (
        <View>
          {wins?.updatedAt ? <Text style={s.muted}>checked {timeAgo(wins.updatedAt)}</Text> : null}
          {wins && recent(wins).length ? recent(wins).map((w) => (
            <Pressable key={w.id} onPress={() => open(w.citing?.url || w.url)}>
              <GCard>
                <Text style={s.title}>{w.kind === 'stars' ? '⭐' : w.kind === 'forks' ? '🍴' : '📚'} {w.text}</Text>
                {w.citing?.title ? <Text style={s.muted}>newest: {w.citing.by ? `${w.citing.by}: ` : ''}{w.citing.title}</Text> : null}
                <Text style={s.muted}>{timeAgo(w.at)}</Text>
              </GCard>
            </Pressable>
          )) : (
            <Empty>No wins in the last 30 days yet. The first check only sets the starting point; from then on every new star,
              fork and citation shows up here.{!me ? ' Add GitHub for stars and forks.' : ''}{!settings?.orcid ? ' Add your ORCID for citations.' : ''}</Empty>
          )}
        </View>
      ) : null}

      {mode === 'collab' ? (
        !me ? <Empty>Collaborator matching uses Signals, which needs GitHub: add it in You → Settings.</Empty>
        : signals === false ? <Empty>Collaborator matching uses Signals: turn it on in the Signals planet, and people who complement you show up here.</Empty>
        : holdPeople || !people ? <GeekLoader text="Finding people…" />
        : (
          <View>
            {!people.people.length ? <Empty>Nobody on Signals complements you yet. As more people join myGeeKy, matches show up here.</Empty> : null}
            {people.people.map((p) => (
              <GCard key={p.login}>
                <View style={s.head}>
                  {p.avatar ? <Image source={{ uri: `${p.avatar}${p.avatar.includes('?') ? '&' : '?'}s=80` }}
                                     style={{ width: 34, height: 34, borderRadius: 17 }} /> : null}
                  <Pressable style={{ flex: 1 }} onPress={() => open(`https://github.com/${p.login}`, 'person')}>
                    <Text style={s.title}>{p.login}</Text>
                    {p.status ? <Text style={s.muted}>{p.status}</Text> : null}
                  </Pressable>
                  <Thumbs vote={p.vote} onVote={vote('collaborator', p.login, p.interests.join(' ; '), p.interests,
                    () => { setPeople(null); })} />
                </View>
                {p.theyBring.length ? <Text style={s.good}>They bring: {p.theyBring.slice(0, 5).join(', ')}</Text> : null}
                {p.youBring.length ? <Text style={s.muted}>You bring: {p.youBring.slice(0, 5).join(', ')}</Text> : null}
                {p.shared.length ? <Text style={s.muted}>Both into: {p.shared.slice(0, 5).join(', ')}</Text> : null}
                <View style={s.row}>
                  <Button accent={!p.asked} disabled={p.asked || !p.canReceive} label={p.asked ? '🤝 Asked' : "🤝 I'd like to collaborate"}
                          onPress={async () => {
                            const to = users.find((u) => u.owner === p.login);
                            if (!to) return;
                            try {
                              await send(me, to, 'collab');
                              setPeople({ ...people, people: people.people.map((x) => x.login === p.login ? { ...x, asked: true } : x) });
                              setNote("Sent: you'll both know if they pick you too.");
                            } catch (e) {
                              setNote(e instanceof Error ? e.message : "Couldn't send it.");
                            }
                          }} />
                  <Text style={s.muted}>they only see it if they pick you too</Text>
                </View>
              </GCard>
            ))}
            <Hidden n={people.hidden} onShow={async () => { await taste.unhide('collaborator'); setPeople(null); }} />
          </View>
        )
      ) : null}
    </View>
  );
}
