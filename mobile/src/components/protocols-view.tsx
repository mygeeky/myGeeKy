// 🧭 Protocols, inside 🌱 Grow: a skill as ordered stages (R basics → statistics with R →
// data analysis → a real project → your own work), with a level check that skips what you
// already know. Reviewed ones come from myGeeKy's maker; for any other skill the phone
// builds one from GitHub and papers. Edit it as you like, then 📤 publish it for everyone.
import * as Clipboard from 'expo-clipboard';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput,
  View } from 'react-native';
import type { Lists } from '../lib/curated';
import { ITEM_KINDS, type Stage } from '../lib/protocol-shape';
import * as P from '../lib/protocols';
import type { Doc } from '../lib/skills';
import * as taste from '../lib/taste';
import { C } from '../lib/theme';
import type { MyRepo } from '../lib/wins';
import { Button, GCard, s, Thumbs } from './growth-parts';
import { Empty, open } from './ui';

const STATUS = { done: ['✅', 'Done'], known: ['🎓', 'You know this'], current: ['▶', 'Start here'], todo: ['○', ''] } as const;
const SOURCE = { reviewed: '✓ Reviewed', auto: 'Auto-built, not reviewed', mine: 'Yours' } as const;

type Ask = { title: string; label: string; value?: string; second?: string; onDone: (a: string, b: string) => void };

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={st.backdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} accessibilityLabel="Close" />
        <View style={st.sheet}>
          <View style={st.head}>
            <Text style={st.title}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={10}><Text style={st.cancel}>Cancel</Text></Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 28 }}>{children}</ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function AskSheet({ ask, onClose }: { ask: Ask; onClose: () => void }) {
  const [a, setA] = useState(ask.value ?? '');
  const [b, setB] = useState('');
  return (
    <Sheet title={ask.title} onClose={onClose}>
      <Text style={st.label}>{ask.label}</Text>
      <TextInput value={a} onChangeText={setA} style={st.input} autoCapitalize="none" autoFocus placeholderTextColor={C.muted} />
      {ask.second ? <><Text style={st.label}>{ask.second}</Text>
        <TextInput value={b} onChangeText={setB} style={st.input} placeholderTextColor={C.muted} /></> : null}
      <View style={s.row}><Button accent label="OK" disabled={!a.trim()} onPress={() => { onClose(); ask.onDone(a.trim(), b.trim()); }} /></View>
    </Sheet>
  );
}

function CheckSheet({ stage, onClose, onQuiz, onKnown }: { stage: Stage; onClose: () => void;
  onQuiz: (answers: number[]) => void; onKnown: () => void }) {
  const [answers, setAnswers] = useState<number[]>(stage.quiz.map(() => -1));
  const [cans, setCans] = useState<boolean[]>(stage.can.map(() => false));
  return (
    <Sheet title={`Check: ${stage.title}`} onClose={onClose}>
      {stage.quiz.length ? (
        <View>
          <Text style={s.muted}>{stage.quiz.length} questions. Get 75% right and this stage is marked as known. Your answers stay on this phone.</Text>
          {stage.quiz.map((q, n) => (
            <View key={n} style={{ marginTop: 12 }}>
              <Text style={[s.body, { fontWeight: '700' }]}>{n + 1}. {q.q}</Text>
              {q.options.map((o, i) => (
                <Pressable key={i} onPress={() => setAnswers(answers.map((x, k) => (k === n ? i : x)))}
                           style={[st.option, answers[n] === i && st.optionOn]} accessibilityState={{ selected: answers[n] === i }}>
                  <Text style={s.body}>{answers[n] === i ? '●' : '○'} {o}</Text>
                </Pressable>
              ))}
            </View>
          ))}
          <View style={s.row}><Button accent label="Check" disabled={answers.includes(-1)} onPress={() => { onClose(); onQuiz(answers); }} /></View>
        </View>
      ) : (
        <View>
          <Text style={s.muted}>Tick what you can already do. All ticked, and this stage is marked as known.</Text>
          {stage.can.map((c, i) => (
            <Pressable key={i} onPress={() => setCans(cans.map((x, k) => (k === i ? !x : x)))} style={st.option}
                       accessibilityState={{ checked: cans[i] }}>
              <Text style={s.body}>{cans[i] ? '☑' : '☐'} {c}</Text>
            </Pressable>
          ))}
          <View style={s.row}><Button accent label="I can do these" disabled={!cans.every(Boolean)} onPress={() => { onClose(); onKnown(); }} /></View>
        </View>
      )}
    </Sheet>
  );
}

export function ProtocolsView({ lists, docs, repos, profile, token, startWith, onStarted }: {
  lists: Lists | null; docs: Doc[]; repos: MyRepo[]; profile: string; token: string | null;
  startWith: { skill: string; goal: string } | null; onStarted: () => void }) {
  const [state, setState] = useState<P.State>({});
  const [votes, setVotes] = useState<Record<string, taste.Vote>>({});
  const [skill, setSkill] = useState('');
  const [goal, setGoal] = useState('');
  const [building, setBuilding] = useState(false);
  const [editing, setEditing] = useState('');
  const [ask, setAsk] = useState<Ask | null>(null);
  const [check, setCheck] = useState<{ pid: string; stage: Stage } | null>(null);
  const [note, setNote] = useState('');

  const reload = useCallback(async () => {
    if (!lists) return;
    setState(await P.load(lists));
    setVotes(await taste.load());
  }, [lists]);
  useEffect(() => { Promise.resolve().then(reload); }, [reload]);

  const buildOne = useCallback(async (sk: string, gl: string) => {
    if (!lists || !sk.trim()) return;
    setBuilding(true);
    setNote('');
    try {
      const p = await P.build(sk.trim(), gl.trim(), lists, token, docs);
      await P.start(lists, p);
      setSkill('');
      setGoal('');
      await reload();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't build it.");
    } finally {
      setBuilding(false);
    }
  }, [lists, token, docs, reload]);

  // 🧭 on a skill in Skills lands here with that skill
  useEffect(() => {
    if (startWith && lists) Promise.resolve().then(async () => { onStarted(); await buildOne(startWith.skill, startWith.goal); });
  }, [startWith, lists, buildOne, onStarted]);

  const views = useMemo(() => Object.values(state).map((e) => P.view(e, P.evidence(e.protocol, repos, profile)))
    .sort((a, b) => Number(a.finished) - Number(b.finished) || a.startedAt.localeCompare(b.startedAt)), [state, repos, profile]);
  if (!lists) return <Empty>Loading…</Empty>;
  const started = new Set(views.flatMap((v) => [v.id, v.based_on]));
  const offer = lists.protocols.filter((p) => !started.has(p.id));
  const act = async (fn: () => Promise<unknown>) => { await fn(); await reload(); };

  const publish = (pid: string, title: string) => {
    const e = state[pid];
    if (!e) return;
    Alert.alert('Publish this protocol', `Send “${title}” to myGeeKy, for everyone?\n\nThis opens a public GitHub issue in mygeeky/myGeeKy-ideas, `
      + 'sent with your GitHub account when you press Submit. It holds the stages and links, and the links you removed, so the maker can '
      + 'review it for everyone and improve the protocol model. Your progress, checks and answers are not included.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Open on GitHub', onPress: async () => {
        const out = P.publish(e);
        if (out.clipboard) {
          await Clipboard.setStringAsync(out.clipboard);
          setNote("It's too long for a link, so myGeeKy copied it: paste it on the GitHub page, then press Submit.");
        }
        open(out.url);
      } },
    ]);
  };

  return (
    <View>
      <View style={st.newRow}>
        <TextInput value={skill} onChangeText={setSkill} placeholder="A skill, e.g. R, GWAS" placeholderTextColor={C.muted} style={[st.input, { flex: 1 }]}
                   autoCapitalize="none" />
        <TextInput value={goal} onChangeText={setGoal} placeholder="for… (optional)" placeholderTextColor={C.muted} style={[st.input, { flex: 1 }]} />
      </View>
      <View style={s.row}>
        <Button accent label={building ? 'Building…' : '🧭 Build a protocol'} disabled={building || !skill.trim()} onPress={() => buildOne(skill, goal)} />
        {building ? <ActivityIndicator color={C.pink} /> : null}
      </View>
      {building ? <Text style={s.muted}>Searching GitHub and papers, and sorting what comes back into stages…</Text> : null}
      {note ? <Text style={s.warn}>{note}</Text> : null}

      {offer.length ? <Text style={s.section}>✓ REVIEWED PROTOCOLS</Text> : null}
      <View style={[s.row, { marginTop: 0 }]}>
        {offer.map((p) => <Button key={p.id} label={`🧭 ${p.title}`} onPress={() => buildOne(p.skill, p.goal)} disabled={building} />)}
      </View>

      {!views.length ? <Empty>No protocols yet. Pick a reviewed one, build one for any skill, or press 🧭 on a skill in Skills.</Empty> : (
        <Text style={s.section}>🧭 YOUR PROTOCOLS</Text>
      )}
      {views.map((v) => {
        const ed = editing === v.id;
        return (
          <GCard key={v.id}>
            <View style={s.head}>
              <View style={{ flex: 1 }}>
                <Text style={s.title}>{v.finished ? '🏁' : '🧭'} {v.title}  <Text style={s.muted}>{v.doneCount}/{v.total}</Text></Text>
                <Text style={[s.muted, v.source === 'reviewed' && { color: C.green }]}>
                  {SOURCE[v.source]}{v.source === 'mine' && v.based_on ? ' · changed from a reviewed one' : ''}</Text>
              </View>
              <Pressable onPress={() => Alert.alert('Stop this protocol', 'Your progress and your changes to it are removed.', [
                { text: 'Cancel', style: 'cancel' }, { text: 'Stop it', style: 'destructive', onPress: () => act(() => P.stop(lists, v.id)) }])}
                         accessibilityLabel="Stop this protocol" hitSlop={8}>
                <Text style={{ color: C.muted, fontSize: 18 }}>×</Text>
              </Pressable>
            </View>
            <View style={s.bar}><View style={[s.barFill, { width: `${(100 * v.doneCount) / Math.max(v.total, 1)}%` }]} /></View>
            {v.summary ? <Text style={s.muted}>{v.summary}</Text> : null}
            <View style={s.row}>
              <Button label={ed ? '✅ Done editing' : '✏️ Edit'} onPress={() => setEditing(ed ? '' : v.id)} />
              <Button label="📤 Publish" onPress={() => publish(v.id, v.title)} />
            </View>
            {v.stages.map((st2, i) => {
              const [icon, word] = STATUS[st2.status];
              const known = st2.status === 'done' || st2.status === 'known';
              return (
                <View key={st2.id} style={[st.stage, st2.status === 'current' && st.stageNow]}>
                  <View style={s.head}>
                    <Text style={[s.title, { fontSize: 14 }]}>
                      <Text style={{ color: known ? C.green : C.text }}>{icon}</Text> {i + 1}. {st2.title}
                      {word ? <Text style={s.muted}>  {word}{st2.how === 'quiz' && st2.score != null ? ` (${Math.round(st2.score * 100)}%)` : st2.how === 'self' ? ' (you said so)' : ''}</Text> : null}
                    </Text>
                  </View>
                  {ed ? (
                    <View style={s.row}>
                      <Button label="▲" onPress={() => act(() => P.moveStage(lists, v.id, st2.id, -1))} />
                      <Button label="▼" onPress={() => act(() => P.moveStage(lists, v.id, st2.id, 1))} />
                      <Button label="✎ Rename" onPress={() => setAsk({ title: 'Rename stage', label: 'New name', value: st2.title,
                        onDone: (t) => act(() => P.renameStage(lists, v.id, st2.id, t)) })} />
                      <Button label="🗑" onPress={() => act(() => P.removeStage(lists, v.id, st2.id))} />
                    </View>
                  ) : st2.role !== 'use' ? (
                    <View style={s.row}>
                      {!known && (st2.quiz.length || st2.can.length) ? <Button label="🎓 Check" onPress={() => setCheck({ pid: v.id, stage: st2 })} /> : null}
                      <Button label={st2.status === 'done' ? '↩ Not done' : '☑ Done'}
                              onPress={() => act(() => P.tick(lists, v.id, st2.id, st2.status !== 'done'))} />
                    </View>
                  ) : null}
                  {st2.role === 'use' ? <Text style={s.muted}>{known ? `Done: ${st2.why}` : st2.why || 'Ticks itself when one of your repos shows the skill'}</Text>
                    : st2.how === 'evidence' && st2.why ? (
                      <View style={s.hiddenRow}>
                        <Text style={[s.muted, { flex: 1 }]}>From your work: {st2.why}</Text>
                        <Pressable onPress={() => act(() => P.markKnown(lists, v.id, st2.id, 'no'))}><Text style={s.link}>Not really</Text></Pressable>
                      </View>
                    ) : st2.overruled || st2.how === 'self' ? (
                      <Pressable onPress={() => act(() => P.markKnown(lists, v.id, st2.id, null))}><Text style={s.link}>Undo</Text></Pressable>
                    ) : null}
                  {st2.items.map((it, k) => (
                    <View key={it.url} style={st.item}>
                      <Pressable style={{ flex: 1 }} onPress={() => open(it.url)}>
                        <Text style={s.link}>{ITEM_KINDS[it.kind] ?? '🌐'} {it.title}</Text>
                        {it.note ? <Text style={s.muted} numberOfLines={2}>{it.note}</Text> : null}
                      </Pressable>
                      {ed ? (
                        <View style={{ flexDirection: 'row', gap: 4 }}>
                          {k > 0 || i > 0 ? <Button label="▲" onPress={() => act(() => P.moveItem(lists, v.id, st2.id, it.url, -1))} /> : null}
                          {k < st2.items.length - 1 || i < v.stages.length - 1 ? <Button label="▼" onPress={() => act(() => P.moveItem(lists, v.id, st2.id, it.url, 1))} /> : null}
                          <Button label="✕" onPress={() => act(() => P.removeItem(lists, v.id, st2.id, it.url))} />
                        </View>
                      ) : !it.url.includes('github.com/search') ? (
                        <Thumbs vote={taste.voteOf(votes, 'resource', it.url)}
                                onVote={(up) => taste.vote('resource', it.url, up, `${it.title} ${it.note}`, [])} />
                      ) : null}
                    </View>
                  ))}
                  {ed ? <Pressable onPress={() => setAsk({ title: 'Add a link', label: 'Link (https://…): a repo, a paper or a page',
                    second: 'What is it? (a short title)', onDone: async (u, t) => {
                      if (!(await P.addItem(lists, v.id, st2.id, u, t))) setNote('Only https:// links can be added.');
                      await reload();
                    } })}><Text style={[s.link, { marginTop: 6 }]}>➕ Add a link</Text></Pressable> : null}
                </View>
              );
            })}
            {ed ? <View style={s.row}><Button label="➕ Add a stage" onPress={() => setAsk({ title: 'Add a stage', label: 'Name of the new stage',
              onDone: (t) => act(() => P.addStage(lists, v.id, t)) })} /></View> : null}
          </GCard>
        );
      })}
      {ask ? <AskSheet ask={ask} onClose={() => setAsk(null)} /> : null}
      {check ? <CheckSheet stage={check.stage} onClose={() => setCheck(null)}
                           onQuiz={async (a) => {
                             const sc = await P.answerQuiz(lists, check.pid, check.stage.id, a);
                             setNote(`${Math.round(sc * a.length)} of ${a.length} right. ${sc >= P.PASS ? "You know this one: it's marked as known."
                               : 'Not yet: this stage stays on your list.'}`);
                             await reload();
                           }}
                           onKnown={() => act(() => P.markKnown(lists, check.pid, check.stage.id, 'self'))} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: { backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxHeight: '85%' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  title: { color: C.text, fontSize: 16, fontWeight: '800', flex: 1 },
  cancel: { color: C.muted, fontSize: 14 },
  label: { color: C.muted, fontSize: 12.5, marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: C.card, color: C.text, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 9, fontSize: 14,
    borderWidth: 1, borderColor: C.line },
  newRow: { flexDirection: 'row', gap: 6, marginTop: 10 },
  option: { paddingVertical: 8, paddingHorizontal: 6, borderRadius: 8, marginTop: 4 },
  optionOn: { backgroundColor: 'rgba(122,92,255,0.25)' },
  stage: { marginTop: 10, padding: 8, borderRadius: 10 },
  stageNow: { backgroundColor: 'rgba(255,255,255,0.05)' },
  item: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, marginLeft: 10 },
});
