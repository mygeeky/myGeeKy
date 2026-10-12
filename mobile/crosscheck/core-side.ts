import { newKeypair } from './signal-crypto.ts';
import { addCall, callsIn, isoNow, mergeIntoBeacon, newCall, openSignals, parseBeacon, sealSignal } from './signals-core.ts';
import { readFileSync } from 'node:fs';

const [step, file] = process.argv.slice(2);
const input = JSON.parse(readFileSync(file, 'utf8'));
if (step === 'phone-joins-and-sends') {
  // Alice's phone: its own key; adds itself to Alice's beacon and sends Bob a "thanks"
  const [priv, pub] = newKeypair();
  const boxes = sealSignal('alice', 'bob', input.bobKeys, 'thanks', undefined, isoNow());
  const merged = mergeIntoBeacon(input.aliceBeacon, pub, boxes);
  let full: string | null = null;
  try {
    mergeIntoBeacon({ ...input.aliceBeacon, keys: input.fourKeys }, pub, []);
  } catch (e) {
    full = (e as Error).message;
  }
  console.log(JSON.stringify({ phonePriv: priv, phonePub: pub, merged, refusedWhenFull: full }));
} else if (step === 'phone-reads') {
  // Alice's phone reads Bob's beacon and opens what's for her
  const parsed = parseBeacon(input.bobBeacon, 'bob');
  const got = parsed ? openSignals(parsed, 'alice', input.phonePriv) : null;
  const copied = parsed ? openSignals({ ...parsed, owner: 'mallory' }, 'alice', input.phonePriv) : null;
  console.log(JSON.stringify({ parsedKeys: parsed?.keys.length, got, copiedBoxOpens: copied?.length }));
} else if (step === 'calls') {
  // the same rules both ways: which calls count, a call made here, and an "I'm in"
  const verdicts = input.candidates.map((c: unknown) => callsIn({ calls: [c] }).length === 1);
  const made = newCall('gwas-qc', '  A second pair of eyes​ on LD pruning. ', ['PLINK', 'gwas', 'plink'], 'any', 'hours', 60);
  const withCall = mergeIntoBeacon(input.aliceBeacon, input.alicePhonePub, [], Date.now(),
    { calls: addCall(callsIn(input.aliceBeacon), made) });
  let tooMany: string | null = null;
  try {
    addCall(callsIn(withCall), newCall('gwas-qc', 'Same repo again, please help.', ['x'], 'any', 'hours', 30));
  } catch (e) {
    tooMany = (e as Error).message;
  }
  const bob = parseBeacon(input.bobBeacon, 'bob');
  const boxes = sealSignal('alice', 'bob', bob!.keys, 'join', undefined, isoNow(), bob!.calls[0].id,
    ['snakemake', 'python', 'r', 'x'.repeat(40)]);
  const fromBob = parseBeacon(input.bobJoined, 'bob');
  const opened = openSignals(fromBob!, 'alice', input.alicePhonePriv);
  console.log(JSON.stringify({ verdicts, made, withCall, tooMany, bobCalls: bob!.calls, joinBoxes: boxes, opened }));
}
