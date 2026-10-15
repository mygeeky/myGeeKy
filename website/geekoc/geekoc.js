/* GeekOc — a parametric octopus. No dependencies, no build step, no framework.
 *
 * The point of this file: GeekOc is never DRAWN twice. There is one body and eight tentacles, and every
 * pose is a handful of NUMBERS fed through the same functions. That is what makes him flexible:
 *
 *   - a pose is data, so a new one is six numbers, not a new drawing;
 *   - two poses can be mixed, so he can be anywhere BETWEEN waving and pointing;
 *   - anything can be animated, because animating is just moving the numbers;
 *   - he can hold any number of things, look anywhere, at any size, in any colour.
 *
 * A tentacle is built by walking along a spine, turning a little at every step (that is `curl`), then
 * offsetting left and right by a width that tapers to the tip. That is why the arms look boneless
 * instead of like rotated sticks -- an octopus arm has no elbow, so a rig made of joints is wrong.
 *
 *   const g = GeekOc.build({ pose: 'wave', t: performance.now() / 1000 });
 *   svg.innerHTML = GeekOc.markup(g);
 *
 * Every function is pure: give it the same numbers, get the same picture. Nothing here touches the DOM
 * except `markup`, which returns a string.
 */
(function (root) {
  'use strict';

  var TAU = Math.PI * 2;
  var rad = function (deg) { return deg * Math.PI / 180; };
  var lerp = function (a, b, t) { return a + (b - a) * t; };
  var clamp = function (v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; };
  var round = function (n) { return Math.round(n * 10) / 10; };

  // --------------------------------------------------------------------- the look
  var SKIN = {
    light: '#a98cff', mid: '#8b6bf5', dark: '#6442d8', deep: '#5b3bcc',
    glass: '#7fd8ff', ink: '#1a1428', mouth: '#2a1f3d', sucker: '#c7b2ff', white: '#ffffff',
  };

  /* The eight arms before any pose touches them.
   *
   * `at` is WHERE the arm leaves the body -- its place on the lower rim, in degrees with 90 at the
   * bottom. `dir` is WHICH WAY it sets off, which is a different number: an octopus arm leaves the body
   * sideways and then hangs, so the outermost arm is attached far out at 152 but travels at 112, nearly
   * straight down. Tying the two together is what made the first attempt splay like a starfish.
   * `w` is the width at the root; the two middle arms are fattest because they are nearest the viewer. */
  var ARMS = [
    { at: 152, dir: 112, len: 104, w: 20, back: true },
    { at: 133, dir: 103, len: 112, w: 22, back: true },
    { at: 115, dir: 98, len: 118, w: 24 },
    { at: 99, dir: 94, len: 122, w: 25 },
    { at: 81, dir: 86, len: 122, w: 25 },
    { at: 65, dir: 82, len: 118, w: 24 },
    { at: 47, dir: 77, len: 112, w: 22, back: true },
    { at: 28, dir: 68, len: 104, w: 20, back: true },
  ];

  /* A pose says, per arm, how far to swing from its resting direction (`swing`), how much the arm coils
   * along its length (`curl`), and how long it is (`len`, as a multiplier). Everything else -- where the
   * eyes look, the mouth, the brow -- is three more numbers. That is a whole pose. */
  /* A pose says, per arm, how far to swing from its resting direction (`swing`), how much the arm coils
   * along its length (`curl`), and how long it is (`len`, as a multiplier). Everything else -- where the
   * eyes look, the mouth, the brow, the eyelids -- is four more numbers. That is a whole pose.
   *
   * SIGNS, because they are the thing that is easy to get backwards: angles run clockwise on screen with
   * 0 right, 90 down, 180 left, 270 up. So a LEFT arm spreads outward and rises on POSITIVE swing, and a
   * RIGHT arm on NEGATIVE. Curl is the same turn applied gradually down the arm's own length. */
  var POSES = {
    idle:    { swing: [0, 0, 0, 0, 0, 0, 0, 0], curl: [30, 22, 13, 5, -5, -13, -22, -30],
               len: 1, look: [0, 0], mouth: 'smile', brow: 0, lids: 0 },
    wave:    { swing: [2, 1, 0, 0, 0, 0, -54, -104], curl: [30, 22, 13, 5, -5, -13, -34, -46],
               len: 1, look: [0.25, -0.12], mouth: 'grin', brow: 0.3, lids: 0 },
    point:   { swing: [2, 1, 0, 0, 0, 0, -34, -62], curl: [30, 22, 13, 5, -5, -13, -18, -20],
               len: 0.98, look: [0.55, 0.05], mouth: 'smile', brow: 0.15, lids: 0 },
    think:   { swing: [4, 2, 0, 0, 0, 0, -56, -116], curl: [30, 22, 13, 5, -5, -13, -34, -70],
               len: 0.95, look: [-0.18, -0.4], mouth: 'flat', brow: 0.5, lids: 0.25 },
    cheer:   { swing: [82, 54, 16, 2, -2, -16, -54, -82], curl: [26, 20, 13, 5, -5, -13, -20, -26],
               len: 1.02, look: [0, -0.15], mouth: 'open', brow: 0.8, lids: 0 },
    sleep:   { swing: [8, 4, 2, 0, 0, -2, -4, -8], curl: [52, 40, 24, 10, -10, -24, -40, -52],
               len: 0.88, look: [0, 0.2], mouth: 'tiny', brow: -0.2, lids: 1 },
    present: { swing: [46, 31, 14, 4, -4, -14, -31, -46], curl: [22, 16, 10, 4, -4, -10, -16, -22],
               len: 0.98, look: [0, -0.1], mouth: 'grin', brow: 0.25, lids: 0 },
  };

  /* Mix two poses. This is the whole reason a pose is numbers: GeekOc can be 40% of the way from
   * thinking to cheering, which no set of hand-drawn pictures can ever be. */
  function mix(a, b, t) {
    t = clamp(t, 0, 1);
    var out = { swing: [], curl: [], len: lerp(a.len, b.len, t),
                look: [lerp(a.look[0], b.look[0], t), lerp(a.look[1], b.look[1], t)],
                brow: lerp(a.brow, b.brow, t), lids: lerp(a.lids, b.lids, t),
                mouth: t < 0.5 ? a.mouth : b.mouth };
    for (var i = 0; i < 8; i++) {
      out.swing.push(lerp(a.swing[i], b.swing[i], t));
      out.curl.push(lerp(a.curl[i], b.curl[i], t));
    }
    return out;
  }

  // --------------------------------------------------------------------- one tentacle
  /* Walk a spine, turning `curl` degrees in total along the way, then wrap it in an outline that tapers
   * from `w` to a point. `wobble` is a travelling sine so a resting arm breathes instead of freezing. */
  function tentacle(x0, y0, deg, len, curl, w, wobble, phase) {
    var N = 16, a = rad(deg), step = len / N, turn = rad(curl) / N;
    var spine = [[x0, y0]], x = x0, y = y0, i;
    for (i = 1; i <= N; i++) {
      a += turn + Math.sin(phase + i * 0.42) * wobble * 0.012;
      x += step * Math.cos(a);
      y += step * Math.sin(a);
      spine.push([x, y]);
    }
    var left = [], right = [];
    for (i = 0; i <= N; i++) {
      var p = spine[i];
      var ahead = spine[Math.min(i + 1, N)], behind = spine[Math.max(i - 1, 0)];
      var dx = ahead[0] - behind[0], dy = ahead[1] - behind[1];
      var m = Math.hypot(dx, dy) || 1;
      var k = i / N;
      // thickness falls away as a curve, not a straight line: a straight taper reads as a cone
      var r = (w * (1 - k * k * 0.96)) / 2;
      left.push([p[0] - (dy / m) * r, p[1] + (dx / m) * r]);
      right.push([p[0] + (dy / m) * r, p[1] - (dx / m) * r]);
    }
    var d = 'M' + left.map(function (p) { return round(p[0]) + ' ' + round(p[1]); }).join('L');
    d += 'L' + right.reverse().map(function (p) { return round(p[0]) + ' ' + round(p[1]); }).join('L') + 'Z';
    return { d: d, tip: spine[N], spine: spine };
  }

  // --------------------------------------------------------------------- the whole character
  /* `build` turns a pose (by name, or an object, or a mix) into every number the markup needs. It never
   * touches the DOM, so the same call works in a browser, in Node for a video render, and in a test. */
  function build(opts) {
    opts = opts || {};
    var t = opts.t || 0;
    var pose = typeof opts.pose === 'string' ? POSES[opts.pose] || POSES.idle : opts.pose || POSES.idle;
    var cx = 200, cy = 150;                 // the head's centre, in a 400x400 box
    var breathe = opts.still ? 0 : Math.sin(t * 1.5) * 1;

    var arms = [], i;
    for (i = 0; i < 8; i++) {
      var base = ARMS[i];
      var ang = base.dir + (pose.swing[i] || 0);
      // where the arm leaves the body: its own spot on the ellipse of the mantle's lower edge
      var ax = cx + Math.cos(rad(base.at)) * 98;
      var ay = cy + Math.sin(rad(base.at)) * 112;
      var arm = tentacle(ax, ay, ang, base.len * (pose.len || 1), pose.curl[i] || 0, base.w,
                         opts.still ? 0 : 1, t * 1.6 + i * 0.8);
      arms.push({ d: arm.d, tip: arm.tip, back: !!base.back, fill: base.back ? SKIN.deep : SKIN.dark });
    }

    // a blink is its own clock, so it never lines up with the breathing and look mechanical
    var cycle = opts.still ? 0.5 : (t % 5.4) / 5.4;
    var blink = cycle > 0.955 && cycle < 0.985 ? 1 : 0;
    var lids = clamp(Math.max(pose.lids || 0, blink), 0, 1);

    var look = pose.look || [0, 0];
    var eyes = [-42, 42].map(function (dx) {
      return { x: cx + dx, y: cy + 22, px: cx + dx + look[0] * 9, py: cy + 22 + look[1] * 9 + breathe * 0.3,
               lid: lids };
    });

    return {
      arms: arms, eyes: eyes, lids: lids, breathe: breathe, pose: pose,
      head: { cx: cx, cy: cy + breathe },
      mouth: mouthPath(pose.mouth, cx, cy + 68 + breathe),
      brow: pose.brow || 0,
      skin: opts.skin || SKIN,
      holding: opts.holding || [],
    };
  }

  function mouthPath(kind, x, y) {
    if (kind === 'grin')  return { d: 'M' + (x - 26) + ' ' + (y - 4) + 'C' + (x - 12) + ' ' + (y + 16) + ' ' + (x + 12) + ' ' + (y + 16) + ' ' + (x + 26) + ' ' + (y - 6), fill: 'none' };
    if (kind === 'open')  return { d: 'M' + (x - 20) + ' ' + (y - 6) + 'C' + (x - 14) + ' ' + (y + 20) + ' ' + (x + 14) + ' ' + (y + 20) + ' ' + (x + 20) + ' ' + (y - 6) + 'Z', fill: SKIN.mouth };
    if (kind === 'flat')  return { d: 'M' + (x - 18) + ' ' + (y + 2) + 'C' + (x - 6) + ' ' + (y - 3) + ' ' + (x + 6) + ' ' + (y - 3) + ' ' + (x + 18) + ' ' + (y + 2), fill: 'none' };
    if (kind === 'tiny')  return { d: 'M' + (x - 9) + ' ' + y + 'C' + (x - 4) + ' ' + (y + 7) + ' ' + (x + 4) + ' ' + (y + 7) + ' ' + (x + 9) + ' ' + y, fill: 'none' };
    return { d: 'M' + (x - 22) + ' ' + (y - 2) + 'C' + (x - 10) + ' ' + (y + 13) + ' ' + (x + 10) + ' ' + (y + 13) + ' ' + (x + 22) + ' ' + (y - 4), fill: 'none' };
  }

  // --------------------------------------------------------------------- the picture
  /* Markup, not DOM calls: a string drops into innerHTML on a page, into a React dangerouslySetInnerHTML,
   * into a file for a video render, or into a .svg on disk. One renderer, every use. */
  function markup(g, opts) {
    opts = opts || {};
    var s = g.skin, id = opts.id || 'go';
    var back = g.arms.filter(function (a) { return a.back; });
    var front = g.arms.filter(function (a) { return !a.back; });
    var cx = g.head.cx, cy = g.head.cy;
    var out = [];

    out.push('<defs>');
    out.push('<linearGradient id="' + id + '-skin" x1="0" y1="0" x2="0.3" y2="1">' +
             '<stop offset="0" stop-color="' + s.light + '"/><stop offset="1" stop-color="' + s.dark + '"/></linearGradient>');
    g.eyes.forEach(function (e, i) {
      out.push('<clipPath id="' + id + '-eye' + i + '"><circle cx="' + e.x + '" cy="' + e.y + '" r="30"/></clipPath>');
    });
    out.push('</defs>');

    back.forEach(function (a) { out.push('<path d="' + a.d + '" fill="' + a.fill + '"/>'); });

    out.push('<path d="' + head(cx, cy) + '" fill="url(#' + id + '-skin)"/>');
    out.push('<ellipse cx="' + cx + '" cy="' + (cy + 42) + '" rx="86" ry="60" fill="#fff" opacity=".10"/>');

    front.forEach(function (a) { out.push('<path d="' + a.d + '" fill="' + a.fill + '"/>'); });

    g.eyes.forEach(function (e, i) {
      var drop = 30 + e.lid * 62;
      out.push('<g clip-path="url(#' + id + '-eye' + i + ')">' +
        '<circle cx="' + e.x + '" cy="' + e.y + '" r="30" fill="' + s.white + '"/>' +
        '<circle cx="' + round(e.px) + '" cy="' + round(e.py) + '" r="12.5" fill="' + s.ink + '"/>' +
        '<circle cx="' + round(e.px - 4.5) + '" cy="' + round(e.py - 5) + '" r="4.4" fill="' + s.white + '" opacity=".95"/>' +
        '<rect x="' + (e.x - 34) + '" y="' + (e.y - 92 + drop) + '" width="68" height="62" fill="' + s.mid + '"/>' +
        '</g>');
    });

    // the glasses: deliberately heavier than looks right here, so they survive a 32px favicon
    out.push('<g fill="none" stroke="' + s.glass + '" stroke-width="11" stroke-linecap="round">' +
      '<circle cx="' + (cx - 42) + '" cy="' + (cy + 22) + '" r="38"/>' +
      '<circle cx="' + (cx + 42) + '" cy="' + (cy + 22) + '" r="38"/>' +
      '<path d="M' + (cx - 4) + ' ' + (cy + 18) + 'C' + (cx - 1) + ' ' + (cy + 11) + ' ' + (cx + 1) + ' ' + (cy + 11) + ' ' + (cx + 4) + ' ' + (cy + 18) + '" stroke-width="9"/>' +
      '<path d="M' + (cx - 80) + ' ' + (cy + 16) + 'C' + (cx - 94) + ' ' + (cy + 10) + ' ' + (cx - 104) + ' ' + (cy + 12) + ' ' + (cx - 110) + ' ' + (cy + 20) + '"/>' +
      '<path d="M' + (cx + 80) + ' ' + (cy + 16) + 'C' + (cx + 94) + ' ' + (cy + 10) + ' ' + (cx + 104) + ' ' + (cy + 12) + ' ' + (cx + 110) + ' ' + (cy + 20) + '"/></g>');

    if (g.brow > 0.05) {
      out.push('<g fill="none" stroke="' + s.ink + '" stroke-width="5" stroke-linecap="round" opacity="' + round(clamp(g.brow, 0, 1)) + '">' +
        '<path d="M' + (cx - 60) + ' ' + (cy - 26 - g.brow * 5) + 'C' + (cx - 50) + ' ' + (cy - 34 - g.brow * 7) + ' ' + (cx - 32) + ' ' + (cy - 34 - g.brow * 7) + ' ' + (cx - 24) + ' ' + (cy - 26 - g.brow * 4) + '"/>' +
        '<path d="M' + (cx + 24) + ' ' + (cy - 26 - g.brow * 4) + 'C' + (cx + 32) + ' ' + (cy - 34 - g.brow * 7) + ' ' + (cx + 50) + ' ' + (cy - 34 - g.brow * 7) + ' ' + (cx + 60) + ' ' + (cy - 26 - g.brow * 5) + '"/></g>');
    }

    out.push('<path d="' + g.mouth.d + '" fill="' + g.mouth.fill + '" stroke="' +
             (g.mouth.fill === 'none' ? s.mouth : 'none') + '" stroke-width="6.5" stroke-linecap="round"/>');

    // whatever he is holding rides on the arm TIPS, so it follows the pose by itself
    g.holding.forEach(function (item, i) {
      var arm = g.arms[item.arm != null ? item.arm : i];
      if (!arm) return;
      out.push('<g transform="translate(' + round(arm.tip[0]) + ',' + round(arm.tip[1]) + ')">' + item.svg + '</g>');
    });

    return out.join('');
  }

  function head(cx, cy) {
    return 'M' + cx + ' ' + (cy - 102) + 'C' + (cx + 84) + ' ' + (cy - 102) + ' ' + (cx + 132) + ' ' + (cy - 38) +
      ' ' + (cx + 132) + ' ' + (cy + 34) + 'C' + (cx + 132) + ' ' + (cy + 94) + ' ' + (cx + 96) + ' ' + (cy + 130) +
      ' ' + (cx + 58) + ' ' + (cy + 142) + 'L' + (cx - 58) + ' ' + (cy + 142) + 'C' + (cx - 96) + ' ' + (cy + 130) +
      ' ' + (cx - 132) + ' ' + (cy + 94) + ' ' + (cx - 132) + ' ' + (cy + 34) + 'C' + (cx - 132) + ' ' + (cy - 38) +
      ' ' + (cx - 84) + ' ' + (cy - 102) + ' ' + cx + ' ' + (cy - 102) + 'Z';
  }

  /* Everything the picture needs, as plain values ready to bind into markup -- no HTML string anywhere.
   *
   * `markup` above is for the places that want a string (a .svg file on disk, a video frame, innerHTML on
   * a plain page). `parts` is for the places that build real elements: React, Vue, Svelte, a template
   * engine, or anything that would rather bind `d="{arm.d}"` than inject HTML. Same numbers, same
   * character, two shapes -- which is why one file can serve the site, the app and the renderer. */
  function parts(opts) {
    var g = build(opts);
    var s = g.skin, cx = g.head.cx, cy = g.head.cy;
    var eye = function (i) {
      var e = g.eyes[i];
      return { x: round(e.x), y: round(e.y), px: round(e.px), py: round(e.py),
               gx: round(e.px - 4.5), gy: round(e.py - 5),
               lx: round(e.x - 34), ly: round(e.y - 92 + 30 + e.lid * 62) };
    };
    return {
      backArms: g.arms.filter(function (a) { return a.back; }),
      frontArms: g.arms.filter(function (a) { return !a.back; }),
      arms: g.arms,
      headD: head(cx, cy),
      bellyY: round(cy + 42),
      eyeL: eye(0), eyeR: eye(1),
      lensL: { cx: round(cx - 42), cy: round(cy + 22) },
      lensR: { cx: round(cx + 42), cy: round(cy + 22) },
      bridgeD: 'M' + (cx - 4) + ' ' + (cy + 18) + 'C' + (cx - 1) + ' ' + (cy + 11) + ' ' +
               (cx + 1) + ' ' + (cy + 11) + ' ' + (cx + 4) + ' ' + (cy + 18),
      templeLD: 'M' + (cx - 80) + ' ' + (cy + 16) + 'C' + (cx - 94) + ' ' + (cy + 10) + ' ' +
                (cx - 104) + ' ' + (cy + 12) + ' ' + (cx - 110) + ' ' + (cy + 20),
      templeRD: 'M' + (cx + 80) + ' ' + (cy + 16) + 'C' + (cx + 94) + ' ' + (cy + 10) + ' ' +
                (cx + 104) + ' ' + (cy + 12) + ' ' + (cx + 110) + ' ' + (cy + 20),
      mouth: { d: g.mouth.d, fill: g.mouth.fill,
               stroke: g.mouth.fill === 'none' ? s.mouth : 'none' },
      brow: g.brow,
      browLD: 'M' + (cx - 60) + ' ' + round(cy - 26 - g.brow * 5) + 'C' + (cx - 50) + ' ' + round(cy - 34 - g.brow * 7) +
              ' ' + (cx - 32) + ' ' + round(cy - 34 - g.brow * 7) + ' ' + (cx - 24) + ' ' + round(cy - 26 - g.brow * 4),
      browRD: 'M' + (cx + 24) + ' ' + round(cy - 26 - g.brow * 4) + 'C' + (cx + 32) + ' ' + round(cy - 34 - g.brow * 7) +
              ' ' + (cx + 50) + ' ' + round(cy - 34 - g.brow * 7) + ' ' + (cx + 60) + ' ' + round(cy - 26 - g.brow * 5),
      browOpacity: round(clamp(g.brow, 0, 1)),
      pose: g.pose, skin: s, raw: g,
    };
  }

  /* A whole standalone <svg> string, for a file, a page, or a video frame. */
  function svg(opts) {
    opts = opts || {};
    var g = build(opts);
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="' + (opts.size || 400) +
      '" height="' + (opts.size || 400) + '" role="img" aria-label="' +
      (opts.label || 'GeekOc, a friendly octopus in thick glasses') + '">' + markup(g, opts) + '</svg>';
  }

  /* Play a sequence of poses, easing between them. Returns a stop function. The page passes a callback
   * that takes markup -- so the same loop drives a DOM node, a canvas, or a frame dump for video. */
  function play(steps, draw, opts) {
    opts = opts || {};
    var ease = function (k) { return k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; };
    var start = null, stopped = false;
    function frame(now) {
      if (stopped) return;
      if (start === null) start = now;
      var t = (now - start) / 1000;
      var total = steps.reduce(function (n, s) { return n + s.hold + s.blend; }, 0);
      var at = opts.loop === false ? Math.min(t, total - 0.001) : t % total;
      var i = 0, acc = 0;
      while (i < steps.length && acc + steps[i].hold + steps[i].blend <= at) { acc += steps[i].hold + steps[i].blend; i++; }
      var step = steps[i] || steps[steps.length - 1];
      var into = at - acc;
      var from = POSES[step.pose] || step.pose;
      var pose = from;
      if (into > step.hold && step.blend > 0) {
        var next = steps[(i + 1) % steps.length];
        pose = mix(from, POSES[next.pose] || next.pose, ease((into - step.hold) / step.blend));
      }
      draw(markup(build({ pose: pose, t: t, holding: opts.holding, skin: opts.skin, id: opts.id })), t);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return function () { stopped = true; };
  }

  root.GeekOc = { POSES: POSES, ARMS: ARMS, SKIN: SKIN, build: build, parts: parts, markup: markup,
                  svg: svg, mix: mix, play: play, tentacle: tentacle, TAU: TAU };
})(typeof window !== 'undefined' ? window : globalThis);
