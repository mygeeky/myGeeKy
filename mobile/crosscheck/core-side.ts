import { newKeypair } from './signal-crypto.ts';
import { isoNow, mergeIntoBeacon, openSignals, parseBeacon, sealSignal } from './signals-core.ts';
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
}
