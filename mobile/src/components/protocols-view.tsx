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
import * as Q from '../lib/quiz';
import type { Doc } from '../lib/skills';
import * as taste from '../lib/taste';
import { C, tint } from '../lib/theme';
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

const KIND_COLOR: Record<string, string> = { repo: '#a78bfa', article: '#38bdf8', book: '#f59e0b', course: '#34d399',
  tutorial: '#34d399', video: '#f472b6', guide: '#fb923c', website: '#94a3b8', search: '#94a3b8' };
const LEVEL_COLOR: Record<string, string> = { easy: '#34d399', medium: '#38bdf8', tricky: '#fb923c' };
const statusColor = (status: string) => (status === 'done' || status === 'known' ? C.green : status === 'current' ? C.violet : C.muted);

/** The protocol as a road map: numbered circles on a line. The chosen step makes room for itself -- its
 *  column stretches to show its whole name, in bold -- and the others close up around it with a short name. */
function StepBar({ steps, selected, onSelect }: { steps: P.Step[]; selected: string; onSelect: (id: string) => void }) {
  const done = (x: P.Step) => x.status === 'done' || x.status === 'known';
  const n = steps.length;
  return (
    <View style={st.road}>
      {steps.map((x, i) => {
        const chosen = x.id === selected;
        const on = x.status !== 'todo';
        return (
          <Pressable key={x.id} onPress={() => onSelect(x.id)} style={[st.stepCol, { flex: chosen ? Math.max(2.2, n / 2) : 1 }]}
                     accessibilityLabel={`Step ${x.number}: ${x.title}, ${x.statusLabel}`} accessibilityState={{ selected: chosen }}>
            {/* the road: the half before this circle, and the half after it */}
            {i > 0 ? <View style={[st.roadHalf, { left: 0, backgroundColor: done(steps[i - 1]) ? C.green : tint(0.14) }]} /> : null}
            {i < n - 1 ? <View style={[st.roadHalf, { right: 0, backgroundColor: done(x) ? C.green : tint(0.14) }]} /> : null}
            <View style={[st.ring, chosen && { borderColor: C.text }]}>
              <View style={[st.dot, { backgroundColor: on ? statusColor(x.status) : '#3a3a4a' }]}>
                <Text style={st.dotText}>{done(x) ? '✓' : x.number}</Text>
              </View>
            </View>
            <Text style={[st.stepLabel, chosen && st.stepLabelOn]} numberOfLines={chosen ? 2 : 1}>{x.title}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function Dots({ steps }: { steps: P.Step[] }) {
  return (
    <View style={{ flexDirection: 'row', gap: 4, marginTop: 6 }}>
      {steps.map((x) => <View key={x.id} style={[st.miniDot, { backgroundColor: x.status === 'todo' ? tint(0.12) : statusColor(x.status) }]} />)}
    </View>
  );
}

/** One link inside a step: what it is, its name, the facts that help you choose, and one clear button. */
function ResourceCard({ r, vote, onVote }: { r: P.Resource; vote: number; onVote: ((up: boolean) => Promise<number>) | null }) {
  const color = KIND_COLOR[r.kind] ?? C.muted;
  return (
    <View style={st.resCard}>
      <View style={[st.resIcon, { backgroundColor: `${color}33` }]}><Text style={{ fontSize: 18 }}>{r.icon}</Text></View>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text style={[st.resLabel, { color, flex: 1 }]}>{r.label.toUpperCase()}</Text>
          {onVote ? <Thumbs vote={vote} onVote={onVote} /> : null}
        </View>
        <Pressable onPress={() => open(r.url)}><Text style={[s.title, { fontSize: 14.5 }]}>{r.title}</Text></Pressable>
        {r.subtitle ? <Text style={s.muted}>{r.subtitle}</Text> : null}
        {r.blurb ? <Text style={s.body} numberOfLines={3}>{r.blurb}</Text> : null}
        <Pressable onPress={() => open(r.url)} style={[st.resBtn, { backgroundColor: `${color}2e` }]} accessibilityRole="link">
          <Text style={st.resBtnText}>{r.action}  ↗</Text>
        </Pressable>
      </View>
    </View>
  );
}

function StepPanel({ step, steps, onSelect, onCheck, onAct, votes }: {
  step: P.Step; steps: P.Step[]; onSelect: (id: string) => void; onCheck: () => void;
  onAct: (what: 'tick' | 'untick' | 'notReally' | 'undo') => void; votes: Record<string, taste.Vote> }) {
  const color = statusColor(step.status);
  const i = steps.findIndex((x) => x.id === step.id);
  return (
    <View style={st.panel}>
      <Text style={st.kicker}>STEP {step.number} OF {steps.length} · {step.roleLabel.toUpperCase()}</Text>
      <View style={[s.head, { alignItems: 'center' }]}>
        <Text style={[s.title, { fontSize: 17 }]}>{step.title}</Text>
        <Text style={[st.chip, { color: step.status === 'todo' ? C.text : color, backgroundColor: `${color}22` }]}>{step.statusLabel}</Text>
      </View>
      {step.why ? <Text style={s.muted}>{step.why}</Text> : null}
      <View style={s.row}>
        {step.canCheck ? <Button label="🎓 I know this: check me" onPress={onCheck} /> : null}
        {!step.auto ? <Button accent={step.status === 'current'} label={step.status === 'done' ? '↩ Not done' : '☑ Mark as done'}
                              onPress={() => onAct(step.status === 'done' ? 'untick' : 'tick')} /> : null}
        {step.how === 'evidence' && !step.auto ? <Pressable onPress={() => onAct('notReally')}><Text style={s.link}>Not really</Text></Pressable> : null}
        {step.overruled || step.how === 'self' ? <Pressable onPress={() => onAct('undo')}><Text style={s.link}>Undo</Text></Pressable> : null}
      </View>
      {step.resources.map((r) => (
        <ResourceCard key={r.url} r={r} vote={taste.voteOf(votes, 'resource', r.url)}
                      onVote={r.kind === 'search' ? null : (up) => taste.vote('resource', r.url, up, `${r.link.title} ${r.link.note}`, [])} />
      ))}
      {!step.resources.length && !step.auto ? <Text style={s.muted}>No links yet: ✏️ Edit to add one.</Text> : null}
      <View style={[s.row, { justifyContent: 'space-between' }]}>
        {i > 0 ? <Pressable onPress={() => onSelect(steps[i - 1].id)} style={{ flex: 1 }}><Text style={s.link} numberOfLines={1}>← {steps[i - 1].title}</Text></Pressable> : <View />}
        {i < steps.length - 1 ? <Pressable onPress={() => onSelect(steps[i + 1].id)} style={{ flex: 1, alignItems: 'flex-end' }}>
          <Text style={s.link} numberOfLines={1}>{steps[i + 1].title} →</Text></Pressable> : null}
      </View>
    </View>
  );
}


/** One quiz question, as plain as it can be: which step it belongs to and how hard it is, the question
 *  (with its code set apart), and four answers as full-width buttons. Once you answer, the one you picked
 *  turns green or red, the right one is always marked, and the card opens up: why that answer is right,
 *  the source it was written from with the sentence quoted from it, and 🚩 if the question looks wrong. */
function QuestionCard({ q, picked, flagged, onPick, onFlag }: { q: Q.Question; picked: number | null; flagged: boolean;
  onPick: ((i: number) => void) | null; onFlag: (() => void) | null }) {
  const color = LEVEL_COLOR[q.level] ?? C.violet;
  const done = picked != null;
  const ok = picked === q.answer;
  return (
    <View>
      <View style={[s.row, { marginTop: 0, alignItems: 'center' }]}>
        <Text style={s.muted}>{q.number} of {q.of}</Text>
        <Text style={[st.chip, { color, backgroundColor: `${color}22` }]}>{q.levelIcon} {q.levelLabel}</Text>
        <Text style={[s.muted, { flex: 1 }]} numberOfLines={1}>{q.kindIcon} {q.stageTitle}</Text>
        {onFlag ? (
          <Pressable onPress={onFlag} hitSlop={8} accessibilityLabel="This question looks wrong">
            <Text style={s.muted}>{flagged ? '🚩 flagged' : '🚩'}</Text>
          </Pressable>
        ) : null}
      </View>
      <Text style={[s.body, { fontSize: 15, fontWeight: '700', marginTop: 8 }]}>{q.text}</Text>
      {q.code ? <Text style={st.code}>{q.code}</Text> : null}
      {q.options.map((o, i) => {
        const mine = picked === i;
        const style = [st.answer,
          done && i === q.answer ? { backgroundColor: 'rgba(52,211,153,0.16)', borderColor: C.green } : null,
          done && mine && !ok ? { backgroundColor: 'rgba(248,113,113,0.16)', borderColor: '#f87171' } : null];
        return (
          <Pressable key={i} onPress={() => (done || !onPick ? null : onPick(i))} style={style} disabled={done}
                     accessibilityState={{ selected: mine, disabled: done }}>
            <Text style={s.body}>{String.fromCharCode(65 + i)}.  {o}</Text>
          </Pressable>
        );
      })}
      {done ? (
        <View style={{ marginTop: 8 }}>
          <Text style={[s.title, { fontSize: 14, color: ok ? C.green : '#f87171' }]}>{ok ? '✓ Right' : '✗ Not this one'}</Text>
          {q.why ? <Text style={s.body}>{q.why}</Text> : null}
          {q.source.quote ? <Text style={st.quote}>“{q.source.quote}”</Text> : null}
          {q.resource ? <><Text style={[s.section, { marginBottom: 0 }]}>WHERE THIS COMES FROM</Text>
            <ResourceCard r={q.resource} vote={0} onVote={null} /></> : null}
        </View>
      ) : null}
    </View>
  );
}

/** Your score as a ring is a desktop luxury; on the phone it's a big number, then where you stood per step. */
function Result({ attempt, bestBefore }: { attempt: Q.Attempt; bestBefore: number }) {
  return (
    <View>
      <Text style={[s.title, { fontSize: 30, color: attempt.passed ? C.green : C.text }]}>{Math.round(attempt.score * 100)}%</Text>
      <Text style={s.body}>{attempt.right} of {attempt.total} right</Text>
      {attempt.perfect ? <Text style={[s.body, { color: C.green }]}>🏴 100%: a clean sweep.</Text>
        : attempt.passed ? <Text style={[s.body, { color: C.green }]}>Passed. Take it again tomorrow to push it higher.</Text>
        : <Text style={s.muted}>Not yet. The steps below show where to look; the links under each one are a good place to start.</Text>}
      <Text style={s.muted}>Your best for this protocol: {Math.round(attempt.best * 100)}%
        {attempt.improved && bestBefore > 0 ? ` (was ${Math.round(bestBefore * 100)}%)` : ''}. Only your best counts.</Text>
      <View style={[s.row, { marginTop: 8 }]}>
        {attempt.byLevel.map((lv) => (
          <Text key={lv.level} style={[st.chip, { color: LEVEL_COLOR[lv.level], backgroundColor: `${LEVEL_COLOR[lv.level]}22` }]}>
            {lv.icon} {lv.label} {lv.right}/{lv.total}
          </Text>
        ))}
      </View>
      {attempt.byStage.length > 1 ? (
        <View style={{ marginTop: 8 }}>
          <Text style={s.section}>BY STEP</Text>
          {attempt.byStage.map((g) => (
            <View key={g.stage} style={s.hiddenRow}>
              <Text style={[s.body, { flex: 1 }]} numberOfLines={1}>{g.title}</Text>
              <Text style={[s.body, { color: g.right === g.total ? C.green : C.muted, fontWeight: '700' }]}>
                {g.right === g.total ? '✓' : `${g.right}/${g.total}`}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** One dot per question: the ones you answered, the one you're on, and the ones still to come. */
export function QuestionDots({ questions, at, answers, attempt }: {
  questions: Q.Question[]; at: number; answers: number[]; attempt: Q.Attempt | null }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginVertical: 8 }}>
      {questions.map((q, i) => {
        const done = answers[i] >= 0;
        const colour = !done ? tint(0.14)
          : attempt ? (answers[i] === q.answer ? C.green : '#f87171') : C.violet;
        return <View key={q.id} style={[st.dotMark, { backgroundColor: colour },
          i === at && !attempt ? st.dotNow : null]} />;
      })}
    </View>
  );
}

/** A whole attempt, drawn inside the 🏆 Quiz tab (never a pop-up): which protocol it is for, a dot per
 *  question, the question itself, and one button to go on. When it's finished the same card shows the
 *  result. It draws; the tab owns what happens next. */
export function QuizRunView({ quiz, stage, onClose, onDone }: { quiz: Q.Quiz; stage: string; onClose: () => void;
  onDone: (attempt: Q.Attempt) => Promise<void> }) {
  const [at, setAt] = useState(0);
  const [answers, setAnswers] = useState<number[]>(quiz.questions.map(() => -1));
  const [attempt, setAttempt] = useState<Q.Attempt | null>(null);
  const [bestBefore, setBestBefore] = useState(0);
  const [flagged, setFlagged] = useState<string[]>([]);
  const q = quiz.questions[at];
  const last = at === quiz.questions.length - 1;
  const flagIt = async () => {
    const on = await Q.flag(q.id, !flagged.includes(q.id));
    setFlagged(on ? [...flagged, q.id] : flagged.filter((x) => x !== q.id));
    if (on) {
      Alert.alert('This question looks wrong', "Thanks: it's left out of your next attempts.\n\nTell the maker too? It opens a "
        + 'public GitHub issue, sent with your own account when you press Submit. It holds the question, not your answers.', [
        { text: 'Not now', style: 'cancel' }, { text: 'Tell the maker', onPress: () => open(Q.reportUrl(q)) }]);
    }
  };
  const forward = async () => {
    if (!last) { setAt(at + 1); return; }
    const saved = await Q.load();
    const before = saved.best[quiz.protocol]?.score ?? 0;
    setBestBefore(before);
    // a fresh copy: the questions carry the answers, and a prop is never changed in place
    const marked = Q.mark({ ...quiz, questions: quiz.questions.map((x) => ({ ...x })) }, answers, before);
    setAttempt(marked);
    await onDone(marked);
  };
  return (
    <GCard>
      <View style={s.head}>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>🏆 {quiz.title}</Text>
          <Text style={s.muted}>{attempt ? 'Your score' : `Question ${q.number} of ${q.of}`}
            {q.stageTitle && !attempt ? ` · ${q.stageTitle}` : ''}</Text>
        </View>
        <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Leave this quiz">
          <Text style={{ color: C.muted, fontSize: 18 }}>×</Text>
        </Pressable>
      </View>
      <QuestionDots questions={quiz.questions} at={at} answers={answers} attempt={attempt} />
      {attempt ? (
        <View>
          <Result attempt={attempt} bestBefore={bestBefore} />
          <Text style={s.muted}>{stage ? (attempt.passed ? 'This step is marked as known.' : '')
            : 'One attempt a day, so a score means something. Only your best counts.'}</Text>
          <View style={s.row}><Button accent label="← Back to the quizzes" onPress={onClose} /></View>
        </View>
      ) : (
        <View>
          <QuestionCard q={q} picked={answers[at] < 0 ? null : answers[at]} flagged={flagged.includes(q.id)}
                        onPick={(i) => setAnswers(answers.map((x, k) => (k === at ? i : x)))} onFlag={flagIt} />
          <View style={s.row}>
            <Button accent label={last ? 'See your score' : 'Next question →'} disabled={answers[at] < 0}
                    onPress={forward} />
            <Text style={s.muted}>{quiz.questions.length - at} to go</Text>
          </View>
        </View>
      )}
    </GCard>
  );
}

/** The quiz line on a protocol: how many questions it has, your best score, and the button to take it. */
function QuizRow({ counts, best, canTry, why, onTake, onShare }: { counts: Record<string, number>; best: Q.Best | null;
  canTry: boolean; why: string; onTake: () => void; onShare: () => void }) {
  const total = counts.total ?? 0;
  const mix = Q.LEVELS.filter((lv) => counts[lv]).map((lv) => `${counts[lv]} ${lv}`).join(' · ');
  return (
    <View style={st.quizRow}>
      <View style={[s.head, { alignItems: 'center' }]}>
        <Text style={[s.title, { fontSize: 13.5, color: best ? (best.score >= 1 ? C.green : C.text) : C.text }]}>
          {best ? `🏆 Your best: ${best.score >= 1 ? '🏴 100%' : `${Math.round(best.score * 100)}%`}` : '🏆 Quiz'}
        </Text>
        <Text style={s.muted}>{total ? `${total} questions${mix ? ` (${mix})` : ''}` : 'no questions for this one yet'}</Text>
      </View>
      <View style={[s.row, { marginTop: 4 }]}>
        {total && canTry ? <Button accent={!best} label={`🏁 Take the quiz (${Math.min(Q.PER_ATTEMPT, total)} questions)`}
                                   onPress={onTake} /> : null}
        {total && !canTry ? <Text style={s.muted}>{why}</Text> : null}
        {best ? <Button label="🌍 Show my result" onPress={onShare} /> : null}
      </View>
    </View>
  );
}

export function ProtocolsView({ lists, docs, repos, profile, token, startWith, onStarted, onQuiz }: {
  lists: Lists | null; docs: Doc[]; repos: MyRepo[]; profile: string; token: string | null;
  startWith: { skill: string; goal: string } | null; onStarted: () => void;
  onQuiz: (pid: string, stage: string) => void }) {
  const [state, setState] = useState<P.State>({});
  const [votes, setVotes] = useState<Record<string, taste.Vote>>({});
  const [skill, setSkill] = useState('');
  const [goal, setGoal] = useState('');
  const [building, setBuilding] = useState(false);
  const [editing, setEditing] = useState('');
  const [ask, setAsk] = useState<Ask | null>(null);
  const [check, setCheck] = useState<{ pid: string; stage: Stage } | null>(null);
  const [note, setNote] = useState('');
  const [openId, setOpenId] = useState('');                 // one protocol open; the others fold to one line
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [quizInfo, setQuizInfo] = useState<Record<string, { counts: Record<string, number>; best: Q.Best | null;
    canTry: boolean; why: string }>>({});

  const reload = useCallback(async () => {
    if (!lists) return;
    const loaded = await P.load(lists);
    setState(loaded);
    setVotes(await taste.load());
    const saved = await Q.load();
    const info: Record<string, { counts: Record<string, number>; best: Q.Best | null; canTry: boolean; why: string }> = {};
    for (const e of Object.values(loaded)) {
      const pid = e.protocol.id;
      const can = await Q.canTry(pid);
      info[pid] = { counts: await Q.counts(pid, e.protocol.based_on), best: saved.best[pid] ?? null,
        canTry: can.ok, why: can.why };
    }
    setQuizInfo(info);
  }, [lists]);
  useEffect(() => { Promise.resolve().then(reload); }, [reload]);

  const buildOne = useCallback(async (sk: string, gl: string) => {
    if (!lists || !sk.trim()) return;
    setBuilding(true);
    setNote('');
    try {
      const p = await P.build(sk.trim(), gl.trim(), lists, token, docs);
      setOpenId(await P.start(lists, p));
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
  const shown = views.some((v) => v.id === openId) || openId === '-' ? openId
    : (views.find((v) => !v.finished) ?? views[0])?.id ?? '';

  // the quiz itself lives in the 🏆 Quiz tab, so pressing 🏁 here simply moves there
  const takeQuiz = (pid: string, stage = '') => onQuiz(pid, stage);

  const shareScores = () => {
    Alert.alert('Show my result on mygeeky.org',
      'Nothing about you is online. A score can follow you into a job application, so this is yours to choose — and you '
      + 'agree to it from your own GitHub account, which is what makes it provable.\n\nThe choice lives in myGeeKy on your '
      + 'computer, where it can show you exactly what would appear before anything is sent.', [{ text: 'OK' }]);
  };

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
        const isOpen = shown === v.id;
        const steps = v.stages.map((x, n) => P.stepOf(x, n + 1));
        const step = steps.find((x) => x.id === chosen[v.id]) ?? steps.find((x) => x.status === 'current') ?? steps[0];
        if (!isOpen) {
          return (
            <Pressable key={v.id} onPress={() => setOpenId(v.id)} accessibilityLabel={`Open ${v.title}`}>
              <GCard>
                <View style={s.head}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.title}>{v.finished ? '🏁' : '🧭'} {v.title}  <Text style={s.muted}>{v.doneCount}/{v.total}</Text></Text>
                    <Text style={[s.muted, v.source === 'reviewed' && { color: C.green }]}>{SOURCE[v.source]}</Text>
                    <Dots steps={steps} />
                  </View>
                  <Text style={{ color: C.muted, fontSize: 18 }}>›</Text>
                </View>
              </GCard>
            </Pressable>
          );
        }
        return (
          <GCard key={v.id}>
            <View style={s.head}>
              <Pressable style={{ flex: 1 }} onPress={() => setOpenId('-')} accessibilityLabel="Fold">
                <Text style={s.title}>{v.finished ? '🏁' : '🧭'} {v.title}  <Text style={s.muted}>{v.doneCount}/{v.total}</Text></Text>
                <Text style={[s.muted, v.source === 'reviewed' && { color: C.green }]}>
                  {SOURCE[v.source]}{v.source === 'mine' && v.based_on ? ' · changed from a reviewed one' : ''}</Text>
              </Pressable>
              <Pressable onPress={() => Alert.alert('Stop this protocol', 'Your progress and your changes to it are removed.', [
                { text: 'Cancel', style: 'cancel' }, { text: 'Stop it', style: 'destructive', onPress: () => act(() => P.stop(lists, v.id)) }])}
                         accessibilityLabel="Stop this protocol" hitSlop={8}>
                <Text style={{ color: C.muted, fontSize: 18 }}>×</Text>
              </Pressable>
            </View>
            {v.summary && !ed ? <Text style={s.muted}>{v.summary}</Text> : null}
            <View style={s.row}>
              <Button label={ed ? '✅ Done editing' : '✏️ Edit'} onPress={() => setEditing(ed ? '' : v.id)} />
              <Button label="📤 Publish" onPress={() => publish(v.id, v.title)} />
            </View>
            {!ed && quizInfo[v.id] ? (
              <QuizRow counts={quizInfo[v.id].counts} best={quizInfo[v.id].best} canTry={quizInfo[v.id].canTry}
                       why={quizInfo[v.id].why} onTake={() => takeQuiz(v.id)} onShare={shareScores} />
            ) : null}
            {!ed && step ? (
              <View>
                <StepBar steps={steps} selected={step.id} onSelect={(id) => setChosen({ ...chosen, [v.id]: id })} />
                <StepPanel step={step} steps={steps} votes={votes} onSelect={(id) => setChosen({ ...chosen, [v.id]: id })}
                           onCheck={async () => {
                             const saved = await Q.load();
                             const drawn = await Q.draw(v, Q.PER_ATTEMPT, saved.flags, step.id);
                             if (drawn.questions.length) onQuiz(v.id, step.id);   // opens in the 🏆 Quiz tab
                             else setCheck({ pid: v.id, stage: step.stage });
                           }}
                           onAct={(what) => act(() => (what === 'tick' || what === 'untick' ? P.tick(lists, v.id, step.id, what === 'tick')
                             : P.markKnown(lists, v.id, step.id, what === 'notReally' ? 'no' : null)))} />
              </View>
            ) : null}
            {ed ? v.stages.map((st2, i) => {
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
            }) : null}
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
  stageNow: { backgroundColor: tint(0.05) },
  item: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, marginLeft: 10 },
  road: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 10 },
  stepCol: { alignItems: 'center', paddingHorizontal: 2, minWidth: 0 },
  roadHalf: { position: 'absolute', top: 18, width: '50%', height: 3 },
  ring: { width: 38, height: 38, borderRadius: 19, borderWidth: 2, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center' },
  dot: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  dotText: { color: '#fff', fontWeight: '800', fontSize: 13 },
  stepLabel: { color: C.muted, fontSize: 10.5, textAlign: 'center', marginTop: 4, lineHeight: 13, alignSelf: 'stretch' },
  stepLabelOn: { color: C.text, fontWeight: '800', fontSize: 12, lineHeight: 15 },
  miniDot: { width: 9, height: 9, borderRadius: 5 },
  panel: { borderTopWidth: 1, borderTopColor: C.line, paddingTop: 10, marginTop: 4 },
  kicker: { color: C.muted, fontSize: 10.5, fontWeight: '800', letterSpacing: 0.8 },
  chip: { fontSize: 11.5, fontWeight: '800', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, overflow: 'hidden' },
  resCard: { flexDirection: 'row', gap: 10, backgroundColor: tint(0.05), borderRadius: 12, padding: 10, marginTop: 8 },
  resIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  resLabel: { fontSize: 10.5, fontWeight: '800', letterSpacing: 0.7 },
  resBtn: { alignSelf: 'flex-start', borderRadius: 9, paddingHorizontal: 12, paddingVertical: 7, marginTop: 8 },
  resBtnText: { color: C.text, fontSize: 13, fontWeight: '700' },
  answer: { backgroundColor: tint(0.06), borderWidth: 1, borderColor: 'transparent', borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 9, marginTop: 6 },
  code: { color: C.text, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 12.5,
    backgroundColor: tint(0.07), borderRadius: 8, padding: 9, marginTop: 8 },
  quote: { color: C.muted, fontSize: 12.5, fontStyle: 'italic', backgroundColor: tint(0.06),
    borderRadius: 8, padding: 8, marginTop: 8 },
  quizRow: { backgroundColor: tint(0.06), borderRadius: 10, padding: 9, marginTop: 8 },
  dotMark: { width: 9, height: 9, borderRadius: 5 },
  dotNow: { width: 13, height: 13, borderRadius: 7, borderWidth: 2, borderColor: C.text },
});
