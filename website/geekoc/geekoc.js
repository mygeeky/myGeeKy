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
    light: '#9a5cf0', mid: '#8b45e0', dark: '#7430cf', deep: '#5f23b4',
    belly: '#ffc457', spot: '#6a28c0',
    outline: '#2b1053', outlineWidth: 7,
    glass: '#7fd8ff', ink: '#1a1428', mouth: '#2b1053', sucker: '#ffe0a3', white: '#ffffff',
  };

  /* Where the darker freckles sit on the mantle, as fractions of its box. Fixed rather than random, so
   * the same octopus turns up every time -- a mascot that reshuffles its own spots is two mascots. */
  var SPOTS = [
    [-0.46, -0.30, 0.070], [-0.20, -0.52, 0.048], [0.12, -0.56, 0.062], [0.44, -0.34, 0.054],
    [-0.58, 0.04, 0.050], [0.60, -0.02, 0.066], [-0.34, 0.40, 0.058], [0.30, 0.44, 0.050],
    [0.02, 0.60, 0.044], [-0.62, 0.34, 0.038], [0.56, 0.32, 0.042], [-0.06, -0.14, 0.036],
  ];

  /* The eight arms before any pose touches them.
   *
   * `at` is WHERE the arm leaves the body -- its place on the lower rim, in degrees with 90 at the
   * bottom. `dir` is WHICH WAY it sets off, which is a different number: an octopus arm leaves the body
   * sideways and then hangs, so the outermost arm is attached far out at 152 but travels at 112, nearly
   * straight down. Tying the two together is what made the first attempt splay like a starfish.
   * `w` is the width at the root; the two middle arms are fattest because they are nearest the viewer. */
  var ARMS = [
    /* `dir` is close to straight down for ALL of them on purpose. An arm that sets off sideways
     * travels across the height where the mantle narrows, and pops out beside his mouth -- which is
     * exactly what it looked like. Leaving downwards clears the body first; the curl does the
     * spreading afterwards, below the chin, where there is nothing to cross. */
    /* The eight have to SEPARATE, not just fan. Two arms that leave from nearly the same place in
     * nearly the same direction travel side by side for their whole length, and because each carries
     * its own outline the overlap reads as damage rather than as depth -- one arm's dark edge cutting
     * across the other's band. So each step inwards is a real step: the roots are spread, the headings
     * differ by at least ten degrees, and the inner pair is SHORTER and hangs almost straight, where
     * the outer pair is long and sweeps. Nothing runs alongside anything. */
    { spot: -1.00, dir: 126, len: 206, w: 52, back: true },
    { spot: -0.70, dir: 114, len: 212, w: 57, back: true },
    { spot: -0.40, dir: 102, len: 196, w: 61, back: true },
    { spot: -0.16, dir: 92, len: 150, w: 63, back: true },
    { spot: 0.16, dir: 88, len: 150, w: 63, back: true },
    { spot: 0.40, dir: 78, len: 196, w: 61, back: true },
    { spot: 0.70, dir: 66, len: 212, w: 57, back: true },
    { spot: 1.00, dir: 54, len: 206, w: 52, back: true },
  ];

  /* The drawing grid. Real tentacles need the room: at the old 400 the arms either escaped the box or
   * had to be stubby, and stubby arms on an octopus read as legs. Everything is in these units, so a
   * caller only ever sets a pixel width. */
  var BOX = 620;

  /* The head is drawn at this fraction of the grid. Shrinking it is what leaves room for arms that
   * are actually tentacles: an octopus's arms are far longer than its mantle, and the first rig had them
   * at about the mantle's own height, which read as a blob with feet. */
  var HEAD = 0.98;

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
  /* FACES, kept apart from poses on purpose.
   *
   * A body pose says what the arms are doing; a face says what he is feeling. Tangling them means
   * "waving" can only ever be happy, and "thinking" can only ever be puzzled -- so seven poses would
   * have to become seventy to cover the combinations. Separated, any face goes on any pose: a worried
   * wave and a proud point are each one line.
   *
   * `lids` is 0 open, 1 shut, and takes a PAIR for a wink. `look` is -1..1 across and up. */
  var FACES = {
    happy:     { mouth: 'smile', brow: 0.3, lids: 0, look: [0, 0] },
    excited:   { mouth: 'open', brow: 0.8, lids: 0, look: [0, -0.15] },
    curious:   { mouth: 'smile', brow: 0.45, lids: 0, look: [0.5, -0.1] },
    thinking:  { mouth: 'flat', brow: 0.5, lids: 0.25, look: [-0.2, -0.4] },
    proud:     { mouth: 'grin', brow: 0.2, lids: 0.15, look: [0, -0.05] },
    surprised: { mouth: 'oh', brow: 1, lids: 0, look: [0, -0.1] },
    shy:       { mouth: 'tiny', brow: 0.1, lids: 0.35, look: [-0.45, 0.25] },
    wink:      { mouth: 'grin', brow: 0.3, lids: [0, 1], look: [0.15, 0] },
    sleepy:    { mouth: 'tiny', brow: -0.2, lids: 1, look: [0, 0.2] },
    worried:   { mouth: 'worried', brow: 0.65, lids: 0.1, look: [-0.25, 0.1] },
  };

  var POSES = {
    idle:    { swing: [0, 0, 0, 0, 0, 0, 0, 0], curl: [152, 124, 96, 34, -34, -96, -124, -152],
               len: 1, face: 'happy' },
    wave:    { swing: [0, 0, 0, 0, 0, -6, -18, -44], curl: [152, 124, 96, 34, -34, -92, -92, -72],
               len: 1, face: 'excited' },
    point:   { swing: [0, 0, 0, 0, 0, -4, -12, 14], curl: [152, 124, 96, 34, -34, -90, -80, -28],
               len: 1, face: 'curious' },
    think:   { swing: [0, 0, 0, 0, 0, -8, -24, -38], curl: [152, 124, 96, 34, -34, -104, -120, -150],
               len: 0.97, face: 'thinking' },
    cheer:   { swing: [24, 15, 5, 0, 0, -5, -15, -24], curl: [146, 120, 94, 36, -36, -94, -120, -146],
               len: 1.05, face: 'excited' },
    sleep:   { swing: [-22, -14, -5, 0, 0, 5, 14, 22], curl: [116, 96, 78, 28, -28, -78, -96, -116],
               len: 0.92, face: 'sleepy' },
    present: { swing: [5, 3, 0, 0, 0, 0, -3, -5], curl: [120, 100, 80, 30, -30, -80, -100, -120],
               len: 1.05, face: 'proud' },
  };

  /* Mix two poses. This is the whole reason a pose is numbers: GeekOc can be 40% of the way from
   * thinking to cheering, which no set of hand-drawn pictures can ever be. */
  function mix(a, b, t) {
    t = clamp(t, 0, 1);
    var out = { swing: [], curl: [], len: lerp(a.len, b.len, t), face: t < 0.5 ? a.face : b.face };
    for (var i = 0; i < 8; i++) {
      out.swing.push(lerp(a.swing[i], b.swing[i], t));
      out.curl.push(lerp(a.curl[i], b.curl[i], t));
    }
    return out;
  }

  /* Mixing two FACES, which is what lets a smile fall rather than cut. `lids` may be a number or a pair
   * (a wink), so both are widened to a pair before blending -- otherwise a wink mixed with anything
   * throws away the eye it was winking. */
  function mixFace(a, b, t) {
    t = clamp(t, 0, 1);
    var pair = function (v) { return Array.isArray(v) ? v : [v, v]; };
    var la = pair(a.lids), lb = pair(b.lids);
    return {
      mouth: t < 0.5 ? a.mouth : b.mouth,
      brow: lerp(a.brow, b.brow, t),
      lids: [lerp(la[0], lb[0], t), lerp(la[1], lb[1], t)],
      look: [lerp(a.look[0], b.look[0], t), lerp(a.look[1], b.look[1], t)],
    };
  }

  // --------------------------------------------------------------------- one tentacle
  /* Walk a spine, turning `curl` degrees in total along the way, then wrap it in an outline that tapers
   * from `w` to a point. `wobble` is a travelling sine so a resting arm breathes instead of freezing. */
  var SEGS = 22;

  /* WALK: the shape an arm WANTS to be, worked out from the numbers. The turn is weighted towards the
   * tip (k^2, normalised so `curl` still means total degrees), which is what makes a tentacle coil into
   * a spiral rather than bend like a banana: an octopus arm is near-straight where it leaves the body
   * and tightest at the very end. */
  function walk(x0, y0, deg, len, curl, wobble, phase) {
    var N = SEGS, a = rad(deg), step = len / N, i;
    var weights = [], total = 0;
    for (i = 1; i <= N; i++) {
      var k = i / N, wgt = 0.25 + k * k * 2.2;
      weights.push(wgt);
      total += wgt;
    }
    var spine = [[x0, y0]], x = x0, y = y0;
    for (i = 1; i <= N; i++) {
      a += rad(curl) * weights[i - 1] / total + Math.sin(phase + i * 0.34) * wobble * 0.009;
      x += step * Math.cos(a);
      y += step * Math.sin(a);
      spine.push([x, y]);
    }
    return spine;
  }

  /* SKIN: an outline around a spine, whatever produced it. Splitting this from `walk` is what lets the
   * physics below drive the same arms -- it hands over a spine and gets the same octopus back. */
  function skin(spine, w) {
    var N = spine.length - 1, left = [], right = [], norms = [], widths = [], i;
    for (i = 0; i <= N; i++) {
      var p = spine[i];
      var ahead = spine[Math.min(i + 1, N)], behind = spine[Math.max(i - 1, 0)];
      var dx = ahead[0] - behind[0], dy = ahead[1] - behind[1];
      var m = Math.hypot(dx, dy) || 1;
      var nx = -dy / m, ny = dx / m, kk = i / N;
      // ends at 18% of its root width: a needle point reads as a spike, not a tentacle
      var r = (w * (1 - 0.82 * kk * kk)) / 2;
      norms.push([nx, ny]);
      widths.push(r);
      left.push([p[0] + nx * r, p[1] + ny * r]);
      right.push([p[0] - nx * r, p[1] - ny * r]);
    }
    var tipN = norms[N], tipR = widths[N], tipP = spine[N], cap = [];
    var base = Math.atan2(tipN[1], tipN[0]);
    for (i = 1; i < 8; i++) {
      var ang = base - Math.PI * i / 8;
      cap.push([tipP[0] + Math.cos(ang) * tipR, tipP[1] + Math.sin(ang) * tipR]);
    }
    var say = function (q) { return round(q[0]) + ' ' + round(q[1]); };
    var head2 = spine[0], aim = Math.atan2(spine[1][1] - head2[1], spine[1][0] - head2[0]) * 180 / Math.PI;
    if (aim < 0) aim += 360;
    return { d: 'M' + left.map(say).join('L') + 'L' + cap.map(say).join('L') +
                'L' + right.reverse().map(say).join('L') + 'Z',
             tip: tipP, spine: spine, norms: norms, widths: widths,
             // which face of the arm the suckers ride on: the one pointing DOWN and outward, away from
             // the curl, so they stay underneath however the arm hooks
             side: aim > 90 && aim < 270 ? -1 : 1 };
  }

  /* The pale underside with its rings of suckers -- the single thing that says "octopus" fastest, and
   * the reason the reference art reads at a glance. It runs along one side of the spine, the side the
   * arm curls towards, so it stays visible however the arm turns. */
  function underside(arm, skin, how) {
    how = how || {};
    var from = how.from != null ? how.from : 0.08;     // where the band starts, across the arm
    var to = how.to != null ? how.to : 0.66;           // ...and where it ends
    var every = how.every || 4;                        // a cup every N beads
    var cup = how.cup != null ? how.cup : 0.34;        // how big a cup is, against the arm's half-width
    var flip = how.flip ? -1 : 1;                      // true puts the band on top instead
    var inner = [], outer = [], dots = [], i;
    var N = arm.spine.length - 1;

    /* WHICH FACE IS UNDERNEATH is decided PER BEAD, not once for the whole arm.
     *
     * An arm that curls through half a turn has its underside swap sides along its own length: the face
     * that points down near the body points up once the tip has hooked over. Choosing from the arm's
     * starting direction -- which is what this did -- put the suckers on top of six arms out of eight.
     *
     * So at each bead take whichever normal points DOWN the screen. Near the top of a hook both normals
     * are nearly horizontal and the choice would flutter from bead to bead, tearing the band in half,
     * so when a normal is flatter than this the previous bead's choice is carried forward. */
    var sides = [], carry = 1;
    for (i = 0; i <= N; i++) {
      var ny = arm.norms[i][1];
      if (Math.abs(ny) > 0.34) carry = ny > 0 ? 1 : -1;
      sides.push(carry * flip);
    }

    /* WHERE THE SIDE CHANGES, PINCH THE BAND TO NOTHING.
     *
     * An arm that hooks far enough really does swap which face is underneath, part way along. Drawing
     * straight through the swap twists the ribbon into a bowtie: the two edges cross, and the shape
     * renders as a spur poking out through the arm's outline. Fading the band's width to zero at the
     * swap makes the two halves meet at a point instead, which is invisible.
     *
     * The last beads fade too. At the tip the arm's half-width is about five units while the outline is
     * six wide, so a band drawn to full width there has nowhere to hide and spills past the rounded cap.
     */
    var fade = [];
    for (i = 0; i <= N; i++) {
      var f = Math.min(1, (N - i) / 2.5);              // ...to nothing at the very tip
      for (var j = 1; j <= N; j++) {
        if (sides[j] !== sides[j - 1]) f = Math.min(f, Math.abs(i - j + 0.5) / 2.5);
      }
      fade.push(Math.max(0, Math.min(1, f)));
    }

    for (i = 0; i <= N; i++) {
      var p = arm.spine[i], n = arm.norms[i], r = arm.widths[i] * fade[i], s = sides[i];
      inner.push([p[0] + n[0] * r * from * s, p[1] + n[1] * r * from * s]);
      outer.push([p[0] + n[0] * r * to * s, p[1] + n[1] * r * to * s]);
      // fewer, bigger rings: a dense dotted line reads as texture, where an octopus should read as a
      // row of distinct cups.
      if (i > 2 && i % every === 0 && r > 5 && fade[i] > 0.85) {
        var mid = (from + to) / 2;
        dots.push({ cx: round(p[0] + n[0] * r * mid * s), cy: round(p[1] + n[1] * r * mid * s),
                    r: round(r * cup) });
      }
    }
    var say = function (p) { return round(p[0]) + ' ' + round(p[1]); };
    return { d: 'M' + inner.map(say).join('L') + 'L' + outer.reverse().map(say).join('L') + 'Z',
             fill: skin.belly, dots: dots };
  }

  // --------------------------------------------------------------------- the whole character
  /* `build` turns a pose (by name, or an object, or a mix) into every number the markup needs. It never
   * touches the DOM, so the same call works in a browser, in Node for a video render, and in a test. */
  function build(opts) {
    opts = opts || {};
    var t = opts.t || 0;
    var pose = typeof opts.pose === 'string' ? POSES[opts.pose] || POSES.idle : opts.pose || POSES.idle;
    // the face: asked for by name, else the one the pose prefers, else happy
    var face = opts.face;
    face = typeof face === 'string' ? FACES[face] || FACES.happy : face || FACES[pose.face] || FACES.happy;

    // every size is a multiplier, so the dashboard can tune the whole character without touching a path
    /* RATIO is the one knob that matters for how he reads: a big head on short arms is a baby, a
     * small head on long arms is a spider. It scales the two against each other from a single number,
     * so the silhouette stays balanced -- `head` and `arm` are still there underneath for anyone who
     * wants to break that deliberately. 1 is the drawn proportion; above 1 is more head. */
    var ratio = opts.ratio != null ? opts.ratio : 1;
    var headK = (opts.head != null ? opts.head : HEAD) * Math.pow(ratio, 0.6);
    var armK = (opts.arm != null ? opts.arm : 1) / Math.pow(ratio, 0.55);
    var thickK = (opts.thick != null ? opts.thick : 1) * Math.pow(ratio, 0.25);
    var cx = BOX / 2, cy = 248;
    var breathe = opts.still ? 0 : Math.sin(t * 1.5) * 1;

    var arms = [], i;
    for (i = 0; i < 8; i++) {
      var base = ARMS[i];
      var ang = base.dir + (pose.swing[i] || 0);
      /* Where an arm leaves the body: along the SKIRT, under the mantle -- not at its widest point,
       * which made them read as arms growing out of his cheeks. `spot` is -1 (far left) to 1 (far
       * right) across the underside, and the ends ride a little higher because the belly curves up.
       *
       * The start is then pushed 34 units back INSIDE the body. The join is what was ugly: an arm that
       * begins exactly on the rim shows its own outline as a dark seam across the edge. Beginning it
       * well inside, and drawing the mantle over the top, hides every join under the body. */
      var ax = cx + base.spot * 68 * headK;
      var ay = cy + (146 - Math.abs(base.spot) * 22) * headK;
      var into = rad(base.dir + (pose.swing[i] || 0));
      ax -= Math.cos(into) * 48 * headK;
      ay -= Math.sin(into) * 48 * headK;
      var spine = (opts.spines && opts.spines[i])
        || walk(ax, ay, ang, (base.len + 48) * (pose.len || 1) * armK, pose.curl[i] || 0,
                opts.still ? 0 : 1, t * 1.6 + i * 0.8);
      var arm = skin(spine, base.w * thickK);
      /* EVERY arm is drawn behind the mantle. Two of them used to be in front, and they began at
       * mouth height -- so the pair nearest the middle sat across his smile. Putting them behind fixes
       * that and the join in one move: nothing of an arm's blunt start, or its outline, ever crosses
       * the body. Depth is carried by shade and by draw order instead of by overlap, which is how the
       * reference art does it too. */
      arms.push({ d: arm.d, tip: arm.tip, spine: arm.spine, norms: arm.norms, widths: arm.widths,
                  side: arm.side, back: true, i: i, spot: base.spot,
                  fill: Math.abs(base.spot) > 0.55 ? SKIN.deep : SKIN.dark });
    }

    // a blink has its own clock so it never lines up with the breathing and look mechanical
    var cycle = opts.still ? 0.5 : (t % 5.4) / 5.4;
    var blinking = !opts.still && cycle > 0.955 && cycle < 0.985 ? 1 : 0;
    var want = Array.isArray(face.lids) ? face.lids : [face.lids || 0, face.lids || 0];
    var lids = [clamp(Math.max(want[0], blinking), 0, 1), clamp(Math.max(want[1], blinking), 0, 1)];

    var look = face.look || [0, 0];
    var eyeR = 30 * headK, gap = 42 * headK, eyeY = cy + 22 * headK;
    var eyes = [-gap, gap].map(function (dx, n) {
      return {
        x: cx + dx, y: eyeY, r: eyeR,
        px: cx + dx + look[0] * 9 * headK,
        py: eyeY + look[1] * 9 * headK + breathe * 0.3,
        lid: lids[n],
      };
    });

    return {
      arms: arms, eyes: eyes, lids: lids, breathe: breathe, pose: pose, face: face,
      head: { cx: cx, cy: cy + breathe, k: headK },
      mouth: mouthPath(face.mouth, cx, cy + 58 * headK + breathe, headK),
      brow: face.brow || 0,
      skin: opts.skin || SKIN,
      holding: opts.holding || [],
    };
  }

  function mouthPath(kind, x, y, k) {
    k = k || 1;
    var C = function (a, b, c, d2, fill) {
      return { d: 'M' + round(x + a[0] * k) + ' ' + round(y + a[1] * k) +
        'C' + round(x + b[0] * k) + ' ' + round(y + b[1] * k) + ' ' +
        round(x + c[0] * k) + ' ' + round(y + c[1] * k) + ' ' +
        round(x + d2[0] * k) + ' ' + round(y + d2[1] * k) + (fill && fill !== 'none' ? 'Z' : ''),
        fill: fill || 'none' };
    };
    if (kind === 'grin')    return C([-26, -4], [-12, 16], [12, 16], [26, -6]);
    if (kind === 'open')    return C([-20, -6], [-14, 20], [14, 20], [20, -6], SKIN.mouth);
    if (kind === 'oh')      return { d: 'M' + round(x) + ' ' + round(y - 11 * k) +
                                     'a' + round(9 * k) + ' ' + round(11 * k) + ' 0 1 0 0.1 0Z',
                                     fill: SKIN.mouth };
    if (kind === 'flat')    return C([-18, 2], [-6, -3], [6, -3], [18, 2]);
    if (kind === 'worried') return C([-18, 6], [-10, -6], [10, -6], [18, 6]);
    if (kind === 'tiny')    return C([-9, 0], [-4, 7], [4, 7], [9, 0]);
    return C([-22, -2], [-10, 13], [10, 13], [22, -4]);
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

  function head(cx, cy, k) {
    k = k || 1;
    var X = function (n) { return round(cx + n * k); }, Y = function (n) { return round(cy + n * k); };
    /* A wide DOME that flares at the hem, not an egg that tapers to one.
     *
     * The mantle is 268 across and 296 tall -- near enough square, where the old one was a fifth taller
     * than wide. Two things make it read as a dome rather than an egg: the top is one broad arc (the
     * first control point sits far out at 86, so the crown is round instead of pinched), and the bottom
     * does NOT narrow to a neck. It stays wide, 92 either side at the hem, so the body opens out into
     * the arms the way a real mantle does. A narrow hem is what made it look like it was balanced on
     * its tentacles instead of growing them. */
    /* A wide dome, widest at the CHEEKS and tapering below them.
     *
     * Three things separate this from the egg it was. The crown is one broad arc, so the top is round
     * rather than pinched. The widest point sits at eye level -- 136 either side at y=0 -- and the body
     * then narrows to 76 at the hem, roughly half, which is the proportion the reference keeps. And the
     * hem itself is a shallow curve, never a straight line: a flat edge made him look like a dome set
     * down on a shelf, where a mantle should swell into its arms with no seam anywhere.
     *
     * 272 across by 304 tall -- a ratio of 1.12, against the reference's 1.11. */
    return 'M' + X(0) + ' ' + Y(-140) + 'C' + X(80) + ' ' + Y(-140) + ' ' + X(136) + ' ' + Y(-84) +
      ' ' + X(136) + ' ' + Y(0) + 'C' + X(136) + ' ' + Y(62) + ' ' + X(116) + ' ' + Y(112) +
      ' ' + X(76) + ' ' + Y(142) +
      'C' + X(40) + ' ' + Y(164) + ' ' + X(-40) + ' ' + Y(164) + ' ' + X(-76) + ' ' + Y(142) +
      'C' + X(-116) + ' ' + Y(112) + ' ' + X(-136) + ' ' + Y(62) + ' ' + X(-136) + ' ' + Y(0) +
      'C' + X(-136) + ' ' + Y(-84) + ' ' + X(-80) + ' ' + Y(-140) + ' ' + X(0) + ' ' + Y(-140) + 'Z';  }

  /* Everything the picture needs, as plain values ready to bind into markup -- no HTML string anywhere.
   *
   * `markup` above is for the places that want a string (a .svg file on disk, a video frame, innerHTML on
   * a plain page). `parts` is for the places that build real elements: React, Vue, Svelte, a template
   * engine, or anything that would rather bind `d="{arm.d}"` than inject HTML. Same numbers, same
   * character, two shapes -- which is why one file can serve the site, the app and the renderer. */
  function parts(opts) {
    var g = build(opts);
    var s = g.skin, cx = g.head.cx, cy = g.head.cy, k = g.head.k;
    /* THE LID. It is a rectangle sliding down inside a clip of the eye, so it has to travel its own
     * full height PLUS the eye's: at rest its bottom edge rests on the eye's top, and shut its top edge
     * rests on the eye's top. Getting that by one lid-height is what left half the white showing --
     * the old sum closed the eye at lid 0.5 and showed the top half at 0 and the bottom half at 1. */
    var eye = function (i) {
      var e = g.eyes[i];
      var h = e.r * 2.2;                       // tall enough to cover the whole eye in one move
      return { x: round(e.x), y: round(e.y), r: round(e.r),
               px: round(e.px), py: round(e.py),
               gx: round(e.px - 4.5 * k), gy: round(e.py - 5 * k), gr: round(4.4 * k),
               pr: round(12.5 * k),
               lx: round(e.x - e.r - 6), lw: round(e.r * 2 + 12),
               // travels exactly its own height: at 0 its bottom edge rests on the eye's top edge
               // (nothing covered), at 1 its top edge does (everything covered). Any other number here
               // leaves a crescent of white, which is what "half white" looked like.
               ly: round(e.y - e.r - h + e.lid * h), lh: round(h),
               shut: e.lid > 0.55 ? round((e.lid - 0.55) / 0.45) : 0,
               lashD: 'M' + round(e.x - e.r) + ' ' + round(e.y) +
                      'C' + round(e.x - e.r * 0.4) + ' ' + round(e.y + e.r * 0.5) + ' ' +
                      round(e.x + e.r * 0.4) + ' ' + round(e.y + e.r * 0.5) + ' ' +
                      round(e.x + e.r) + ' ' + round(e.y) };
    };
    var lens = round(38 * k), rim = round(11 * k);

    // the pale undersides and their sucker rings, one per arm, in the same order as the arms
    var stripes = [], suckers = [], backStripes = [], frontStripes = [], backSuckers = [], frontSuckers = [];
    g.arms.slice().sort(function (p, q) { return Math.abs(q.spot) - Math.abs(p.spot); }).forEach(function (arm) {
      var u = underside(arm, s, opts.band);
      var band = { d: u.d, fill: u.fill, back: arm.back };
      stripes.push(band);
      backStripes.push(band);
      u.dots.forEach(function (dot) {
        var ring = { cx: dot.cx, cy: dot.cy, r: dot.r, fill: s.sucker, back: arm.back };
        suckers.push(ring);
        backSuckers.push(ring);
      });
    });

    var spots = SPOTS.map(function (sp) {
      return { cx: round(cx + sp[0] * 128 * k), cy: round(cy + sp[1] * 118 * k),
               r: round(sp[2] * 128 * k), fill: s.spot };
    });

    return {
      stripes: stripes, suckers: suckers, spots: spots,
      backStripes: backStripes, frontStripes: frontStripes,
      backSuckers: backSuckers, frontSuckers: frontSuckers,
      outline: s.outline, outlineWidth: round(s.outlineWidth * k),
      skinLight: s.light, skinMid: s.mid, skinDark: s.dark, skinDeep: s.deep,
      lidFill: s.mid, glassColour: s.glass, inkColour: s.ink,
      backArms: g.arms.slice().sort(function (p, q) { return Math.abs(q.spot) - Math.abs(p.spot); }),
      frontArms: [],
      arms: g.arms,
      headD: head(cx, cy, k),
      bellyY: round(cy + 42 * k), bellyRx: round(86 * k), bellyRy: round(60 * k),
      blushY: round(cy + 64 * k), blushX: round(82 * k),
      eyeL: eye(0), eyeR: eye(1),
      lensL: { cx: round(cx - 42 * k), cy: round(cy + 22 * k) },
      lensR: { cx: round(cx + 42 * k), cy: round(cy + 22 * k) },
      lensR2: lens, rim: rim, bridgeW: round(9 * k),
      bridgeD: 'M' + round(cx - 4 * k) + ' ' + round(cy + 18 * k) + 'C' + round(cx - k) + ' ' + round(cy + 11 * k) +
               ' ' + round(cx + k) + ' ' + round(cy + 11 * k) + ' ' + round(cx + 4 * k) + ' ' + round(cy + 18 * k),
      templeLD: 'M' + round(cx - 80 * k) + ' ' + round(cy + 16 * k) + 'C' + round(cx - 94 * k) + ' ' + round(cy + 10 * k) +
                ' ' + round(cx - 104 * k) + ' ' + round(cy + 12 * k) + ' ' + round(cx - 110 * k) + ' ' + round(cy + 20 * k),
      templeRD: 'M' + round(cx + 80 * k) + ' ' + round(cy + 16 * k) + 'C' + round(cx + 94 * k) + ' ' + round(cy + 10 * k) +
                ' ' + round(cx + 104 * k) + ' ' + round(cy + 12 * k) + ' ' + round(cx + 110 * k) + ' ' + round(cy + 20 * k),
      mouth: { d: g.mouth.d, fill: g.mouth.fill,
               stroke: g.mouth.fill === 'none' ? s.mouth : 'none' },
      brow: g.brow,
      browLD: 'M' + round(cx - 60 * k) + ' ' + round(cy - (26 + g.brow * 5) * k) + 'C' + round(cx - 50 * k) + ' ' +
              round(cy - (34 + g.brow * 7) * k) + ' ' + round(cx - 32 * k) + ' ' + round(cy - (34 + g.brow * 7) * k) +
              ' ' + round(cx - 24 * k) + ' ' + round(cy - (26 + g.brow * 4) * k),
      browRD: 'M' + round(cx + 24 * k) + ' ' + round(cy - (26 + g.brow * 4) * k) + 'C' + round(cx + 32 * k) + ' ' +
              round(cy - (34 + g.brow * 7) * k) + ' ' + round(cx + 50 * k) + ' ' + round(cy - (34 + g.brow * 7) * k) +
              ' ' + round(cx + 60 * k) + ' ' + round(cy - (26 + g.brow * 5) * k),
      browOpacity: round(clamp(g.brow, 0, 1)),
      pose: g.pose, face: g.face, skin: s, raw: g,
    };
  }

  /* A whole standalone <svg> string, for a file, a page, or a video frame. */
  function svg(opts) {
    opts = opts || {};
    var g = build(opts);
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + BOX + ' ' + BOX +
      '" width="' + (opts.size || BOX) + '" height="' + (opts.size || BOX) + '" role="img" aria-label="' +
      (opts.label || 'GeekOc, a friendly octopus in thick glasses') + '">' + markup(g, opts) + '</svg>';
  }

  // --------------------------------------------------------------------- making him alive
  /* A tentacle with WEIGHT.
   *
   * The same bargain d3-force strikes in brainny's graph: every node is pulled towards where it ought
   * to be (forceX/forceY), held at a distance from its neighbours (forceLink), and damped so the whole
   * thing settles instead of ringing (velocityDecay). Here the "nodes" are the beads of a tentacle, the
   * "link" is a fixed segment length, and the place each bead ought to be is the posed shape `walk`
   * works out. That is the entire trick, and it is what the posed-only version could never do:
   *
   *   - the arms LAG when he moves, and overshoot when he stops, because they carry momentum;
   *   - they can be pulled at, and crawl back;
   *   - they reach for the pointer, so the page feels like it noticed you;
   *   - and he still cannot leave the pose, because the spring always wins in the end.
   *
   * Verlet rather than a spring solver: position-based integration cannot explode, which matters for a
   * thing that runs unattended on a landing page for an hour.
   */
  function Life(opts) {
    opts = opts || {};
    this.opts = opts;
    this.stiff = opts.stiff != null ? opts.stiff : 0.22;    // how hard the pose pulls the arms back
    this.damp = opts.damp != null ? opts.damp : 0.86;       // velocityDecay, in d3's language
    this.droop = opts.droop != null ? opts.droop : 0.22;    // a little gravity, so arms hang
    this.reach = opts.reach != null ? opts.reach : 140;     // how near the pointer has to be to be felt
    this.pull = opts.pull != null ? opts.pull : 0.5;        // ...and how much they lean towards it
    this.t = 0;
    this.chains = null;
    this.at = null;                                          // where the pointer is, if anywhere
  }

  /* One step. `dt` in seconds; anything above a twentieth of a second is treated as a twentieth, so a
   * backgrounded tab that wakes after a minute does not fling the arms off the page. */
  Life.prototype.step = function (pose, face, dt) {
    var o = this.opts;
    dt = Math.min(dt || 1 / 60, 0.05);
    this.t += dt;
    var want = build({ pose: pose, face: face, t: this.t, arm: o.arm, thick: o.thick,
                       head: o.head, ratio: o.ratio, band: o.band });
    var k = dt * 60;                                   // everything below is tuned per 60fps frame
    var self = this;

    if (!this.chains) {                                // first frame: start settled, not falling in
      this.chains = want.arms.map(function (a) {
        return a.spine.map(function (p) { return { x: p[0], y: p[1], px: p[0], py: p[1] }; });
      });
    }

    this.chains.forEach(function (chain, ai) {
      var target = want.arms[ai].spine, n = chain.length, i;
      for (i = 1; i < n; i++) {
        var b = chain[i], tgt = target[i];
        var vx = (b.x - b.px) * self.damp, vy = (b.y - b.py) * self.damp;
        b.px = b.x;
        b.py = b.y;
        // the further down the arm, the looser the hold: a tip should flick, a root should not
        var hold = self.stiff * (1 - 0.55 * (i / n)) * k;
        b.x += vx + (tgt[0] - b.x) * hold;
        b.y += vy + (tgt[1] - b.y) * hold + self.droop * (i / n) * k;

        if (self.at) {                                  // lean towards the pointer, tips most of all
          var dx = self.at[0] - b.x, dy = self.at[1] - b.y;
          var d = Math.hypot(dx, dy);
          if (d < self.reach && d > 1) {
            var f = (1 - d / self.reach) * self.pull * (i / n) * k;
            b.x += dx / d * f * 12;
            b.y += dy / d * f * 12;
          }
        }
      }
      // hold the segments at their length, root outwards, twice: cheap and enough
      for (var pass = 0; pass < 2; pass++) {
        chain[0].x = target[0][0];
        chain[0].y = target[0][1];
        for (i = 1; i < n; i++) {
          var a0 = chain[i - 1], b0 = chain[i];
          var want0 = Math.hypot(target[i][0] - target[i - 1][0], target[i][1] - target[i - 1][1]);
          var dx0 = b0.x - a0.x, dy0 = b0.y - a0.y;
          var d0 = Math.hypot(dx0, dy0) || 1;
          var fix = (d0 - want0) / d0;
          b0.x -= dx0 * fix;
          b0.y -= dy0 * fix;
        }
      }
    });
    return this;
  };

  /* Where the pointer is, in the character's own 620-unit coordinates. Pass nothing when it leaves. */
  Life.prototype.notice = function (x, y) {
    this.at = (x == null || y == null) ? null : [x, y];
    return this;
  };

  /* Give an arm a shove -- a click, a drag, a dropped tool. */
  Life.prototype.poke = function (arm, dx, dy) {
    var chain = this.chains && this.chains[arm];
    if (!chain) return this;
    for (var i = 1; i < chain.length; i++) {
      var f = i / chain.length;
      chain[i].px -= dx * f;
      chain[i].py -= dy * f;
    }
    return this;
  };

  /* The character as it stands right now, ready to draw -- the same shape `parts` always returns. */
  Life.prototype.parts = function (pose, face) {
    var o = this.opts;
    return parts({ pose: pose, face: face, t: this.t, arm: o.arm, thick: o.thick, head: o.head,
                   ratio: o.ratio, band: o.band,
                   spines: this.chains && this.chains.map(function (chain) {
                     return chain.map(function (b) { return [b.x, b.y]; });
                   }) });
  };

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

  root.GeekOc = { POSES: POSES, FACES: FACES, ARMS: ARMS, SKIN: SKIN, HEAD: HEAD, BOX: BOX,
                  build: build, parts: parts, markup: markup, svg: svg,
                  mix: mix, mixFace: mixFace, play: play, walk: walk, skin: skin, Life: Life,
                  alive: function (o) { return new Life(o); }, head: head };
})(typeof window !== 'undefined' ? window : globalThis);
