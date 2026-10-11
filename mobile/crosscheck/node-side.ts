import { newKeypair, openBox, seal, BOX_LEN, validPublicKey } from './signal-crypto.ts';

const [step, ...args] = process.argv.slice(2);
if (step === 'keys') {
  const [priv, pub] = newKeypair();
  console.log(JSON.stringify({ priv, pub, BOX_LEN, valid: validPublicKey(pub) }));
} else if (step === 'open-and-reply') {
  const [priv, box, pythonPub] = args;
  const plain = openBox(priv, box);
  const opened = plain ? new TextDecoder().decode(plain) : null;
  const reply = seal(pythonPub, new TextEncoder().encode('{"from":"phone","to":"desktop","type":"thanks"}'));
  const flipped = box.slice(0, 50) + (box[50] === 'A' ? 'B' : 'A') + box.slice(51);
  const wrongKey = openBox(newKeypair()[0], box);
  console.log(JSON.stringify({ opened, reply, tamperedOpens: openBox(priv, flipped) !== null, wrongKeyOpens: wrongKey !== null }));
}
