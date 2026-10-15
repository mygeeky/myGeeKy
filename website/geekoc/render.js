#!/usr/bin/env node
/* Render GeekOc to files: still SVGs, or a numbered frame sequence for video.
 *
 *   node render.js                     one .svg per pose
 *   node render.js --frames 300        300 numbered frames of the pose loop
 *   node render.js --swim cross 360    360 frames of him swimming across, arms trailing
 *
 * The swim frames run the real physics, so the trail is the same one the page shows -- and because the
 * simulation is stepped at a fixed 1/60 regardless of how long a frame takes to write, the film is
 * identical every time it is rendered.
 *
 * The frames are a pure function of time, so the same command always produces the same film -- and a
 * frame can be re-rendered on its own without replaying what came before it.
 *
 *   ffmpeg -framerate 30 -i frames/%04d.svg -c:v libx264 -pix_fmt yuv420p geekoc.mp4
 *   (ffmpeg needs raster input: pipe each frame through resvg, rsvg-convert or sharp first.)
 */
const fs = require('fs');
const path = require('path');
require('./geekoc.js');
const G = globalThis.GeekOc;

const here = __dirname;
const args = process.argv.slice(2);
const framesAt = args.indexOf('--frames');

const swimAt = args.indexOf('--swim');
if (swimAt >= 0) {
  const move = args[swimAt + 1] || 'cross';
  const howMany = Number(args[swimAt + 2]) || 360;
  const life = G.alive({ stiff: 0.22, damp: 0.88, droop: 0.12 });
  const dir = path.join(here, 'frames');
  fs.mkdirSync(dir, { recursive: true });
  // settle him before the first frame, or the film opens with the arms falling into place
  for (let i = 0; i < 120; i++) {
    const m = life.follow(move, i / 60);
    life.step(m.pose, null, 1 / 60);
  }
  for (let f = 0; f < howMany; f++) {
    const t = 2 + f / 30;
    const m = life.follow(move, t);
    life.step(m.pose, null, 1 / 60);
    life.step(m.pose, null, 1 / 60);                 // two sim steps per frame at 30fps
    const p = life.parts(m.pose, null);
    const stage = '-245 200 1190 455';
    fs.writeFileSync(path.join(dir, String(f).padStart(4, '0') + '.svg'),
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + stage + '" width="1190" height="455">' +
      '<g transform="' + p.flipT + '">' + G.markup(p.raw, { id: 'f' + f }) + '</g></svg>');
  }
  console.log(`wrote ${howMany} frames of "${move}" to ${dir} (${(howMany / 30).toFixed(1)}s at 30fps)`);
  process.exit(0);
}

if (framesAt < 0) {
  for (const pose of Object.keys(G.POSES)) {
    const file = path.join(here, `geekoc-${pose}.svg`);
    fs.writeFileSync(file, G.svg({ pose, t: 1.4, still: true, size: 400 }));
    console.log('wrote', path.basename(file));
  }
  process.exit(0);
}

const count = Number(args[framesAt + 1]) || 300;
const fps = 30;
const script = [
  { pose: 'idle', hold: 2.6, blend: 0.9 },
  { pose: 'wave', hold: 2.2, blend: 0.9 },
  { pose: 'point', hold: 2.0, blend: 0.9 },
  { pose: 'think', hold: 2.4, blend: 0.9 },
  { pose: 'cheer', hold: 1.8, blend: 1.1 },
];
const total = script.reduce((n, s) => n + s.hold + s.blend, 0);
const dir = path.join(here, 'frames');
fs.mkdirSync(dir, { recursive: true });

for (let f = 0; f < count; f++) {
  const t = f / fps;
  const at = t % total;
  let i = 0, acc = 0;
  while (i < script.length && acc + script[i].hold + script[i].blend <= at) {
    acc += script[i].hold + script[i].blend;
    i++;
  }
  const step = script[i] || script[script.length - 1];
  const into = at - acc;
  let pose = G.POSES[step.pose];
  if (into > step.hold) {
    const k = (into - step.hold) / step.blend;
    const ease = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    pose = G.mix(pose, G.POSES[script[(i + 1) % script.length].pose], ease);
  }
  fs.writeFileSync(path.join(dir, String(f).padStart(4, '0') + '.svg'),
                   G.svg({ pose, t, size: 800 }));
}
console.log(`wrote ${count} frames to ${dir} (${(count / fps).toFixed(1)}s at ${fps}fps)`);
