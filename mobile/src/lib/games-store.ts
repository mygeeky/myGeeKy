// Your games on this phone: the pack they play and your progress, on the GEMS rules (lib/gems.ts), the desktop's
// gems_store.py. The pack is data/games.json (identical to the desktop's); progress is kept on the phone, and
// `finish` is the one door a round goes through: it records the round, saves it and tells your Model what you played
// (model-repo recordTerms, kind "play", sent with your other events at the next sync).
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as G from './gems';
import { recordTerms } from './model-repo';

const KEY = 'mygeeky.games.progress';
let pack: { items: G.Item[] } | null = null;

export function loadPack(): { items: G.Item[] } {
  if (!pack) {
    const shipped = require('../data/games.json') as { items: G.Item[] };
    pack = G.validate(shipped).length ? { items: [] } : shipped;      // a pack that fails its checks is never played
  }
  return pack;
}

export type Question = { id: string; protocol: string; kind: string; q: string; options: string[]; why: string; source?: { title?: string } };
let bank: Question[] | null = null;
export function questions(): Question[] {
  bank ??= ((require('../data/questions.json') as { questions: Question[] }).questions ?? []).filter((q) => q.kind === 'choice');
  return bank;
}

export async function loadProgress(): Promise<G.Progress> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    const p = raw ? JSON.parse(raw) : null;
    return p && p.version === 1 ? p : G.emptyProgress();
  } catch {
    return G.emptyProgress();
  }
}

const today = () => new Date().toISOString().slice(0, 10);

/** The items one round of `game` plays from `kind`: gems.pick with your weights, your progress and your level. */
export async function roundItems(game: string, kind: string, n: number, weights: Record<string, number>): Promise<G.Item[]> {
  const prog = await loadProgress();
  const stats = prog.games[game];
  const level = G.levelOf(stats?.xp ?? 0);
  const day = today();
  const lower: Record<string, number> = {};
  for (const [t, w] of Object.entries(weights)) lower[t.toLowerCase()] = w;
  return G.pick(G.itemsOf(loadPack(), kind), n, prog, lower, day, G.seedOf(`${day}:${game}:${stats?.plays ?? 0}`), level);
}

/** A round ended: record it, save it, teach the Model. The summary, with what you know and what you're learning. */
export async function finish(game: string, answers: G.Answer[], seconds: number, bonus = 0) {
  const [prog, summary] = G.record(await loadProgress(), game, answers, seconds, today(), bonus);
  try { await AsyncStorage.setItem(KEY, JSON.stringify(prog)); } catch { /* the round still counts on screen */ }
  recordTerms('play', G.modelTerms(answers, seconds), `game:${game}`).catch(() => undefined);
  return { ...summary, ...G.mastery(prog) } as Record<string, any> & { knows: string[]; learning: string[] };
}

export async function badgeCounts(): Promise<Record<string, number>> {
  return G.badgeCounts(await loadProgress());
}

export async function summary() {
  return G.summaryOf(await loadProgress());
}
