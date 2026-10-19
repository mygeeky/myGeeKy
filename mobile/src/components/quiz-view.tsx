// 🏆 Quiz, inside 🌱 Grow: every protocol's quiz in one place, with your best scores. Taking one opens
// the same sheet as the 🏁 button on a protocol (protocols-view.tsx), so there is one quiz, two ways in.
//
// Ten questions per attempt, drawn at random from that protocol's own bank: half basics, then applied,
// then a few of the mistakes people really make. Only your best counts, one attempt a day, and nothing
// leaves the phone unless you choose to share a score.
import { useCallback, useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import type { Lists } from '../lib/curated';
import type { Protocol } from '../lib/protocol-shape';
import * as P from '../lib/protocols';
import * as Q from '../lib/quiz';
import { C } from '../lib/theme';
import { Button, GCard, s } from './growth-parts';
import { QuizRunView } from './protocols-view';
import { Empty } from './ui';
import { logDid } from '../lib/badges';
import { GeekLoader, useHold } from './geek-loader';

export type QuizRow = {
  id: string; title: string; skill: string; mine: boolean; counts: Record<string, number>;
  best: Q.Best | null; score: number; canTry: boolean; whyNot: string; flagged: number;
};

/** Everything the tab shows: yours first, then reviewed protocols you could start. */
export async function overview(lists: Lists, state: P.State): Promise<{
  rows: QuizRow[]; waiting: string[]; taken: number; average: number; perfect: number; flagged: number;
}> {
  const saved = await Q.load();
  const flags = new Set(saved.flags);
  const rows: QuizRow[] = [];
  const waiting: string[] = [];
  const seen = new Set<string>();

  const row = async (p: Protocol, mine: boolean): Promise<QuizRow | null> => {
    const counts = await Q.counts(p.id, p.based_on ?? '');
    if (!counts.total) return null;
    const best = saved.best[p.id] ?? null;
    const can = mine ? await Q.canTry(p.id) : { ok: false, why: '' };
    const qs = await Q.forProtocol(p.id, p.based_on ?? '');
    return { id: p.id, title: p.title, skill: p.skill, mine, counts, best, score: best?.score ?? 0,
      canTry: can.ok, whyNot: can.why, flagged: qs.filter((q) => flags.has(q.id)).length };
  };

  for (const e of Object.values(state)) {
    seen.add(e.protocol.id);
    const r = await row(e.protocol, true);
    if (r) rows.push(r); else waiting.push(e.protocol.title);
  }
  for (const p of lists.protocols) {
    if (seen.has(p.id)) continue;
    const r = await row(p, false);
    if (r) rows.push(r);
  }
  const done = rows.filter((r) => r.best);
  return { rows, waiting, taken: done.length,
    average: done.length ? Math.round((done.reduce((a, r) => a + r.score, 0) / done.length) * 1e4) / 1e4 : 0,
    perfect: done.filter((r) => r.score >= 1).length, flagged: flags.size };
}

function QuizCard({ row, onTake, onStart }: { row: QuizRow; onTake: () => void; onStart: () => void }) {
  const mix = Q.LEVELS.filter((lv) => row.counts[lv]).map((lv) => `${row.counts[lv]} ${lv}`).join(' · ');
  const asked = Math.min(Q.PER_ATTEMPT, row.counts.total ?? 0);
  return (
    <GCard>
      <View style={s.head}>
        <Text style={[s.title, { flex: 1 }]}>
          {row.best ? (row.score >= 1 ? '🏴' : '🏆') : '🏆'} {row.title}
        </Text>
        {row.best ? (
          <Text style={[s.title, { color: row.score >= Q.PASS ? C.green : C.text }]}>
            {Math.round(row.score * 100)}%
          </Text>
        ) : null}
      </View>
      <Text style={s.muted}>
        {row.counts.total} questions{mix ? ` (${mix})` : ''}
        {row.best ? ' · your best counts' : ''}
        {row.flagged ? ` · ${row.flagged} flagged by you` : ''}
      </Text>
      <View style={s.row}>
        {row.canTry ? <Button accent={!row.best} label={`🏁 Take the quiz (${asked} questions)`} onPress={onTake} /> : null}
        {!row.mine ? <Button label="🧭 Start this protocol" onPress={onStart} /> : null}
        {row.mine && !row.canTry ? <Text style={s.muted}>{row.whyNot}</Text> : null}
      </View>
    </GCard>
  );
}

export function QuizView({ lists, onStart, open, onOpened }: {
  lists: Lists | null; onStart: (skill: string) => void;
  open: { pid: string; stage: string } | null; onOpened: () => void }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof overview>> | null>(null);
  const [state, setState] = useState<P.State>({});
  const [quiz, setQuiz] = useState<Q.Quiz | null>(null);
  const [stage, setStage] = useState('');
  const [note, setNote] = useState('');

  const reload = useCallback(async () => {
    if (!lists) return;
    const loaded = await P.load(lists);
    setState(loaded);
    setData(await overview(lists, loaded));
  }, [lists]);
  useEffect(() => { Promise.resolve().then(reload); }, [reload]);

  // one quiz, three ways in (🏁 here, 🏁 on a protocol, 🎓 on a step) and one place it is drawn: here
  const take = useCallback(async (pid: string, forStage = '') => {
    const loaded = Object.keys(state).length || !lists ? state : await P.load(lists);
    const entry = loaded[pid];
    if (!entry) { setNote('Start that protocol first, then its quiz is yours to take.'); return; }
    const saved = await Q.load();
    const drawn = await Q.draw(entry.protocol, Q.PER_ATTEMPT, saved.flags, forStage);
    if (!drawn.questions.length) { setNote('No questions left for this one that you have not flagged.'); return; }
    setStage(forStage);
    setQuiz(drawn);
  }, [state, lists]);

  // 🏁 pressed on a protocol, or 🎓 on one of its steps: that quiz opens here
  useEffect(() => {
    if (!open) return;
    const { pid, stage: wanted } = open;
    onOpened();
    Promise.resolve().then(() => take(pid, wanted));
  }, [open, onOpened, take]);

  const hold = useHold(!lists || !data);
  if (hold || !lists || !data) return <GeekLoader />;
  if (quiz) {                       // a quiz is being taken: it lives here, in this tab
    return (
      <QuizRunView quiz={quiz} stage={stage}
                   onClose={() => { setQuiz(null); setStage(''); Promise.resolve().then(reload); }}
                   onDone={async (attempt) => {
                     logDid('quiz');
                     if (stage) {
                       if (attempt.passed) {
                         await P.answerQuizScore(lists, quiz.protocol, stage, attempt.score);
                         logDid('skill');
                       }
                     } else {
                       await Q.record(attempt);
                     }
                     await reload();
                   }} />
    );
  }
  const share = Q.share();
  const mine = data.rows.filter((r) => r.mine);
  const others = data.rows.filter((r) => !r.mine);
  return (
    <View>
      <Text style={s.muted}>
        Ten questions drawn at random from a protocol&apos;s own bank: {share.easy} basics, {share.medium} applied
        and {share.tricky} of the mistakes people really make. Every question comes from one of that
        protocol&apos;s links and shows you that source, with the sentence that proves the answer, once
        you&apos;ve answered. Only your best counts, one attempt a day, and your answers stay on this phone.
      </Text>
      {data.taken ? (
        <>
          <Text style={s.section}>🏆 YOUR SCORES</Text>
          <Text style={s.body}>
            {data.taken} quiz{data.taken === 1 ? '' : 'zes'} taken · average {Math.round(data.average * 100)}%
            {data.perfect ? ` · ${data.perfect} at 100% 🏴` : ''}
          </Text>
        </>
      ) : null}
      {!data.rows.length ? (
        <Empty>
          No quizzes yet. Questions are written and checked on the maker&apos;s side and arrive with the lists,
          so the reviewed protocols get them first.
        </Empty>
      ) : null}
      {mine.length ? <Text style={s.section}>🧭 YOUR PROTOCOLS</Text> : null}
      {mine.map((r) => (
        <QuizCard key={r.id} row={r} onTake={() => take(r.id)} onStart={() => onStart(r.skill)} />
      ))}
      {others.length ? <Text style={s.section}>✓ REVIEWED PROTOCOLS WITH A QUIZ</Text> : null}
      {others.map((r) => (
        <QuizCard key={r.id} row={r} onTake={() => take(r.id)} onStart={() => onStart(r.skill)} />
      ))}
      {data.waiting.length ? (
        <Text style={s.muted}>
          {data.waiting.length} of your protocols {data.waiting.length === 1 ? 'has' : 'have'} no questions yet
          ({data.waiting.slice(0, 3).join(', ')}{data.waiting.length > 3 ? '…' : ''}).
        </Text>
      ) : null}
      {note ? <Text style={s.warn}>{note}</Text> : null}
    </View>
  );
}
