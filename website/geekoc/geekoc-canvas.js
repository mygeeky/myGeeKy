/* Draw GeekOc onto a 2D canvas. Needs geekoc.js loaded first.
 *
 * WHY THIS EXISTS
 *
 * The page used to animate him by building an SVG string and dropping it into innerHTML once a frame.
 * Measured, the JavaScript in that loop costs 0.31 ms against a 16.7 ms budget -- the physics, the
 * rebuild and the string together. So the stutter was never the simulation. It was what happened next:
 * the browser threw away and re-parsed 7,591 characters of SVG, rebuilt about thirty DOM nodes, and
 * re-resolved a gradient and two clip paths from <defs>, sixty times a second. Style recalculation and
 * layout run on every one of those frames, and none of it can be composited on the GPU.
 *
 * Canvas has no DOM. The same paths are drawn as Path2D objects -- Path2D takes SVG path syntax
 * verbatim, so the geometry does not change at all, only what consumes it -- and the whole character
 * becomes about thirty fill calls into one element the compositor already owns.
 *
 * geekoc.js stays the source of truth and keeps its markup() writer: a string is still what a file, a
 * favicon, a video frame and React's dangerouslySetInnerHTML all want. This is the renderer for the
 * one case a string is wrong for, which is sixty times a second.
 */
(function (root) {
  'use strict';

  /* Path2D objects are rebuilt each frame because the geometry genuinely changes each frame -- the arms
   * are a simulation. Constructing one is cheap; it is the DOM that was not. */
  function P(d) { return new Path2D(d); }

  function dot(ctx, c, fill) {
    ctx.beginPath();
    ctx.arc(c.cx, c.cy, c.r, 0, 6.2832);
    ctx.fillStyle = fill || c.fill;
    ctx.fill();
  }

  function line(ctx, d, colour, w) {
    if (!d || !w) return;
    ctx.strokeStyle = colour;
    ctx.lineWidth = w;
    ctx.stroke(P(d));
  }

  function draw(ctx, p, opts) {
    opts = opts || {};
    var ink = p.outline, ow = p.outlineWidth;
    ctx.save();
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    /* He is mirrored about his OWN centre when he turns, not the canvas's, which is what flipT carries.
     * Parsing it back out is ugly but keeps the one source of truth in the engine. */
    if (p.flipT) {
      var m = /translate\(([-\d.]+),0\) scale\(-1,1\)/.exec(p.flipT);
      if (m) { ctx.translate(Number(m[1]), 0); ctx.scale(-1, 1); }
    }

    /* TWO PASSES OVER THE ARMS, which is how eight of them sit on one body without black wedges
     * between. Pass one lays every arm down in the outline colour, filled AND stroked, so they merge
     * into a single dark silhouette. Pass two paints the fills over it, erasing every internal seam
     * and leaving one continuous rim. Drawn one arm at a time instead, the V where two arms overlap is
     * narrower than their two outlines put together and fills in solid black. */
    ctx.fillStyle = ink;
    ctx.strokeStyle = ink;
    ctx.lineWidth = ow;
    p.backArms.forEach(function (a) { var q = P(a.d); ctx.fill(q); ctx.stroke(q); });
    p.backArms.forEach(function (a) { ctx.fillStyle = a.fill; ctx.fill(P(a.d)); });

    p.backStripes.forEach(function (s) { ctx.fillStyle = s.fill; ctx.fill(P(s.d)); });
    p.backSuckers.forEach(function (s) { dot(ctx, s); });

    // the mantle, with the light falling from above rather than a flat wash
    var h = P(p.headD);
    var g = ctx.createLinearGradient(0, p.headTop || 0, 0, p.headBottom || 460);
    g.addColorStop(0, p.skinLight);
    g.addColorStop(1, p.skinDark);
    ctx.fillStyle = g;
    ctx.fill(h);
    if (ow) { ctx.strokeStyle = ink; ctx.lineWidth = ow; ctx.stroke(h); }

    p.spots.forEach(function (s) { dot(ctx, s, s.fill); });

    (p.frontArms || []).forEach(function (a) {
      var q = P(a.d);
      ctx.fillStyle = a.fill; ctx.fill(q);
      if (ow) { ctx.strokeStyle = ink; ctx.lineWidth = ow; ctx.stroke(q); }
    });
    (p.frontStripes || []).forEach(function (s) { ctx.fillStyle = s.fill; ctx.fill(P(s.d)); });
    (p.frontSuckers || []).forEach(function (s) { dot(ctx, s); });

    // ------------------------------------------------------------------ the face
    ['eyeL', 'eyeR'].forEach(function (side) {
      var e = p[side];
      dot(ctx, { cx: e.x, cy: e.y, r: e.r }, '#ffffff');
      if (ow) { ctx.strokeStyle = ink; ctx.lineWidth = ow; ctx.beginPath();
                ctx.arc(e.x, e.y, e.r, 0, 6.2832); ctx.stroke(); }
      dot(ctx, { cx: e.px, cy: e.py, r: e.pr }, p.inkColour);
      dot(ctx, { cx: e.gx, cy: e.gy, r: e.gr }, '#ffffff');

      /* The lid is a rectangle CLIPPED to the eye, so it covers a circle without being drawn as one --
       * the same trick the SVG does with a clipPath, minus the <defs> the browser had to re-resolve. */
      if (e.ly + e.lh > e.y - e.r) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(e.x, e.y, e.r, 0, 6.2832);
        ctx.clip();
        ctx.fillStyle = p.lidFill;
        ctx.fillRect(e.lx, e.ly, e.lw, e.lh);
        ctx.restore();
      }
      if (e.shut > 0.4) line(ctx, e.lashD, p.inkColour, 4);
    });

    if (p.browOpacity > 0.05) {
      ctx.globalAlpha = p.browOpacity;
      line(ctx, p.browLD, p.inkColour, 5);
      line(ctx, p.browRD, p.inkColour, 5);
      ctx.globalAlpha = 1;
    }

    // the glasses, last, so nothing sits on top of them
    ['lensL', 'lensR'].forEach(function (k) {
      ctx.strokeStyle = p.glassColour;
      ctx.lineWidth = p.rim;
      ctx.beginPath();
      ctx.arc(p[k].cx, p[k].cy, p.lensR2, 0, 6.2832);
      ctx.stroke();
    });
    line(ctx, p.bridgeD, p.glassColour, p.bridgeW);
    line(ctx, p.templeLD, p.glassColour, p.rim);
    line(ctx, p.templeRD, p.glassColour, p.rim);

    var mo = p.mouth;
    if (mo.fill && mo.fill !== 'none') {
      var q2 = P(mo.d);
      ctx.fillStyle = mo.fill; ctx.fill(q2);
      if (ow) { ctx.strokeStyle = ink; ctx.lineWidth = ow; ctx.stroke(q2); }
    } else {
      line(ctx, mo.d, mo.stroke || ink, 7);
    }

    ctx.restore();
  }

  /* A canvas that stays sharp on a retina screen and keeps one stage's worth of the world in view,
   * whatever shape the element happens to be. `view` is [x, y, w, h] in the character's own units --
   * an SVG viewBox by another name. */
  function stage(canvas, view) {
    var ctx = canvas.getContext('2d');
    var vw = view[2], vh = view[3];
    return {
      ctx: ctx,
      fit: function () {
        var box = canvas.getBoundingClientRect();
        if (!box.width) return false;
        var dpr = Math.min(root.devicePixelRatio || 1, 2);
        canvas.width = Math.round(box.width * dpr);
        canvas.height = Math.round(box.height * dpr);
        this.dpr = dpr;
        this.box = box;
        return true;
      },
      clear: function () {
        var box = this.box || canvas.getBoundingClientRect();
        var dpr = this.dpr || 1;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // contain: the whole stage visible, centred, never stretched
        var k = Math.min(box.width / vw, box.height / vh) * dpr;
        ctx.setTransform(k, 0, 0, k,
                         (canvas.width - vw * k) / 2 - view[0] * k,
                         (canvas.height - vh * k) / 2 - view[1] * k);
      },
    };
  }

  root.GeekOcCanvas = { draw: draw, stage: stage };
})(typeof window !== 'undefined' ? window : globalThis);
