/* GeekOc in three dimensions. Needs THREE (r128 UMD) and geekoc.js loaded first.
 *
 * WHY THIS EXISTS BESIDE THE SVG ONE, NOT INSTEAD OF IT
 *
 * The flat engine is 48 KB with no dependencies, renders to a string, and makes a favicon. Three.js is
 * an order of magnitude bigger, needs WebGL, and cannot produce an .svg file for a Play Store listing.
 * So geekoc.js stays the character's source of truth: the poses, the faces, the physics and the moves
 * all live there and are shared. This file is a second RENDERER of the same rig, for the places where
 * depth earns its weight -- a hero on the site, a title card in a video.
 *
 * What the third dimension actually buys, beyond looking nicer:
 *
 *   - the eight arms radiate AROUND him instead of fanning in a plane, which is what an octopus does
 *     and what no amount of 2D fiddling achieves;
 *   - he can swim towards and away from the camera, not only left and right;
 *   - and the pale underside stops being a problem. In flat drawing, deciding which face of a curling
 *     arm is "underneath" took three attempts and a per-bead rule. Here it is a surface normal: a ring
 *     vertex pointing down is belly, one pointing up is skin, and the arm can tie itself in a knot
 *     without the question ever becoming ambiguous.
 *
 * The cartoon look survives the move with two standard tricks: a toon material (banded light, not
 * smooth), and an inverted hull for the outline -- the same mesh grown slightly and drawn inside-out,
 * so the back faces show as a dark rim exactly where the silhouette is.
 */
(function (root) {
  'use strict';

  var G = root.GeekOc;
  var SEGS = 22;                 // beads along an arm, matching the flat rig
  var RING = 10;                 // vertices around a tentacle; 10 reads round and stays cheap
  var rad = function (d) { return d * Math.PI / 180; };
  var lerp = function (a, b, t) { return a + (b - a) * t; };
  var clamp = function (v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; };

  var SKIN = {
    light: 0x9a5cf0, mid: 0x8b45e0, dark: 0x7430cf, deep: 0x5f23b4,
    belly: 0xffc457, outline: 0x2b1053, glass: 0x7fd8ff, ink: 0x1a1428, white: 0xffffff,
  };

  /* The eight arms, placed AROUND the body rather than across it. `az` is the compass bearing each one
   * leaves on, `pitch` how steeply it sets off downwards, and `curl` how far it hooks back up. The two
   * at the front and the two at the back are shorter, so the silhouette from any angle still reads as
   * a fan rather than a bush. */
  var ARMS3 = [];
  for (var n = 0; n < 8; n++) {
    var az = n * 45 + 22.5;
    var side = Math.abs(Math.sin(rad(az)));          // 1 at the sides, 0 front and back
    ARMS3.push({
      az: az,
      pitch: 62 + (1 - side) * 14,
      len: 150 + side * 46,
      w: 30 + side * 7,
      curl: 92 + side * 40,
    });
  }

  // --------------------------------------------------------------------- the spine, in three dimensions
  /* The flat `walk` turns a heading in a plane; this turns a DIRECTION about an axis. Same idea, same
   * tip-weighted curl, one more dimension: the arm leaves along its bearing, pitched down, and bends
   * back up about the horizontal axis across that bearing. */
  function walk3(arm, curl, lenK, t, phase) {
    var N = SEGS;
    var out = new THREE.Vector3(Math.sin(rad(arm.az)), 0, Math.cos(rad(arm.az)));
    var axis = new THREE.Vector3().crossVectors(out, new THREE.Vector3(0, 1, 0)).normalize();
    var dir = out.clone().multiplyScalar(Math.cos(rad(arm.pitch)))
      .add(new THREE.Vector3(0, -Math.sin(rad(arm.pitch)), 0)).normalize();

    var p = out.clone().multiplyScalar(26).add(new THREE.Vector3(0, -34, 0));
    var step = (arm.len * lenK) / N;
    var weights = [], total = 0, i;
    for (i = 1; i <= N; i++) {
      var k = i / N, w = 0.25 + k * k * 2.2;         // the turn gathers towards the tip
      weights.push(w);
      total += w;
    }
    var spine = [p.clone()];
    for (i = 1; i <= N; i++) {
      dir.applyAxisAngle(axis, rad(curl) * weights[i - 1] / total);
      // a slow travelling wave, so a resting arm breathes instead of freezing
      dir.applyAxisAngle(out, Math.sin(phase + i * 0.4) * 0.012);
      p = p.clone().add(dir.clone().multiplyScalar(step));
      spine.push(p.clone());
    }
    return spine;
  }

  // --------------------------------------------------------------------- one tentacle as a mesh
  /* Rings of vertices swept along the spine with a parallel-transport frame -- carrying the previous
   * ring's up-vector forward rather than recomputing it -- because a Frenet frame spins wildly wherever
   * a curve straightens, and a spinning frame twists the belly stripe into a barber's pole. */
  function tube(spine, w, colours) {
    var N = spine.length - 1;
    var pos = [], col = [], idx = [], nor = [];
    var up = new THREE.Vector3(0, 1, 0);
    var prevUp = null;
    var belly = new THREE.Color(colours.belly);
    var skin = new THREE.Color(colours.skin);
    var down = new THREE.Vector3(0, -1, 0);

    for (var i = 0; i <= N; i++) {
      var ahead = spine[Math.min(i + 1, N)], behind = spine[Math.max(i - 1, 0)];
      var tan = new THREE.Vector3().subVectors(ahead, behind).normalize();
      var u = prevUp ? prevUp.clone() : (Math.abs(tan.y) > 0.95 ? new THREE.Vector3(0, 0, 1) : up.clone());
      u.sub(tan.clone().multiplyScalar(u.dot(tan)));             // keep it square to the arm
      if (u.lengthSq() < 1e-6) u.set(0, 0, 1);
      u.normalize();
      prevUp = u.clone();
      var v = new THREE.Vector3().crossVectors(tan, u).normalize();
      var k = i / N;
      var r = (w * Math.max(0.10, 1 - 0.56 * k - 0.34 * k * k)) / 2;

      for (var j = 0; j < RING; j++) {
        var a = (j / RING) * Math.PI * 2;
        var nrm = u.clone().multiplyScalar(Math.cos(a)).add(v.clone().multiplyScalar(Math.sin(a)));
        var pt = spine[i].clone().add(nrm.clone().multiplyScalar(r));
        pos.push(pt.x, pt.y, pt.z);
        nor.push(nrm.x, nrm.y, nrm.z);
        /* THE UNDERSIDE, for free. A vertex whose normal points downwards is belly; one pointing up is
         * skin. In the flat engine this took a per-bead rule and three attempts, because "underneath"
         * had to be guessed from the curve. Here it is just a dot product, and it stays right however
         * the arm twists. */
        var facing = clamp((nrm.dot(down) - 0.12) / 0.5, 0, 1);
        var c = skin.clone().lerp(belly, facing * (k > 0.06 ? 1 : 0));
        col.push(c.r, c.g, c.b);
      }
    }
    for (i = 0; i < N; i++) {
      for (var j2 = 0; j2 < RING; j2++) {
        var a0 = i * RING + j2, b0 = i * RING + (j2 + 1) % RING;
        var c0 = a0 + RING, d0 = b0 + RING;
        idx.push(a0, c0, b0, b0, c0, d0);
      }
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    geo.setIndex(idx);
    return geo;
  }

  // --------------------------------------------------------------------- the body
  /* The mantle is the flat character's own silhouette, revolved. Taking the profile from the same
   * numbers is what keeps the two renderers recognisably the same creature. */
  function mantle() {
    var pts = [];
    for (var i = 0; i <= 24; i++) {
      var t = i / 24;
      // the 2D head path's right-hand edge, from crown to hem, in the 3D scale
      var y = lerp(150, -146, t);
      var bulge = Math.sin(Math.min(1, Math.max(0, (y + 146) / 296)) * Math.PI * 0.92 + 0.14);
      pts.push(new THREE.Vector2(Math.max(0.6, 136 * bulge * 0.74), y));
    }
    return new THREE.LatheGeometry(pts, 48);
  }

  function toon(colour, vertexColours) {
    return new THREE.MeshToonMaterial({
      color: colour, vertexColors: !!vertexColours,
    });
  }

  /* The dark rim: the same mesh, grown a little and drawn inside out, so only its back faces show --
   * and they show exactly on the silhouette. Cheaper and far steadier than an edge-detect pass. */
  function hull(geo, grow) {
    var m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      color: SKIN.outline, side: THREE.BackSide,
    }));
    m.scale.setScalar(1 + grow);
    return m;
  }

  // --------------------------------------------------------------------- the whole thing
  function create(canvas, opts) {
    opts = opts || {};
    var scene = new THREE.Scene();
    scene.background = null;

    var camera = new THREE.PerspectiveCamera(32, 1.9, 1, 4000);
    camera.position.set(0, 90, 760);
    camera.lookAt(0, -10, 0);

    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(root.devicePixelRatio || 1, 2));

    scene.add(new THREE.AmbientLight(0xffffff, 0.72));
    var key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(-180, 320, 420);
    scene.add(key);
    var rim = new THREE.DirectionalLight(0xff6fd8, 0.35);
    rim.position.set(320, -60, -260);
    scene.add(rim);

    var him = new THREE.Group();
    scene.add(him);

    // the body, and its rim
    var body = new THREE.Mesh(mantle(), toon(SKIN.mid));
    var bodyEdge = hull(body.geometry, 0.045);
    him.add(bodyEdge, body);

    // the face rides on the front of the mantle
    var face = new THREE.Group();
    face.position.set(0, 18, 1);
    him.add(face);

    [-40, 40].forEach(function (dx) {
      var white = new THREE.Mesh(new THREE.SphereGeometry(30, 24, 18), toon(SKIN.white));
      white.position.set(dx, 0, 74);
      white.scale.set(1, 1, 0.55);
      var pupil = new THREE.Mesh(new THREE.SphereGeometry(13, 18, 14), toon(SKIN.ink));
      pupil.position.set(dx + (dx > 0 ? 3 : -3), -2, 92);
      pupil.scale.set(1, 1, 0.5);
      var lens = new THREE.Mesh(new THREE.TorusGeometry(39, 5.5, 10, 36), toon(SKIN.glass));
      lens.position.set(dx, 0, 86);
      face.add(white, pupil, lens);
    });
    var bridge = new THREE.Mesh(new THREE.TorusGeometry(13, 4.6, 8, 20, Math.PI), toon(SKIN.glass));
    bridge.position.set(0, 2, 90);
    face.add(bridge);

    var mouth = new THREE.Mesh(new THREE.TorusGeometry(22, 4.2, 8, 24, Math.PI), toon(SKIN.outline));
    mouth.position.set(0, -44, 76);
    mouth.rotation.z = Math.PI;
    face.add(mouth);

    // the arms: one group each, rebuilt every frame from the simulation
    var arms = ARMS3.map(function () {
      var g = new THREE.Group();
      him.add(g);
      return { group: g, mesh: null, edge: null };
    });

    var api = {
      scene: scene, camera: camera, renderer: renderer, him: him, arms: arms,
      t: 0, chains: null, spin: 0,
      /* The same verlet bargain as the flat version, in three dimensions: pull every bead towards where
       * the pose says it belongs, hold the segments at their length, damp it so it settles. */
      step: function (pose, dt) {
        dt = Math.min(dt || 1 / 60, 0.05);
        api.t += dt;
        var p = (typeof pose === 'string' ? G.POSES[pose] : pose) || G.POSES.idle;
        var k = dt * 60;
        var want = ARMS3.map(function (arm, i) {
          var c = arm.curl * (0.5 + 0.5 * Math.abs((p.curl[i] || 90) / 150));
          return walk3(arm, c, p.len || 1, api.t, api.t * 1.5 + i * 0.8);
        });
        if (!api.chains) {
          api.chains = want.map(function (s) {
            return s.map(function (q) { return { p: q.clone(), prev: q.clone() }; });
          });
        }
        api.chains.forEach(function (chain, ai) {
          var target = want[ai];
          for (var i = 1; i < chain.length; i++) {
            var b = chain[i];
            var vel = new THREE.Vector3().subVectors(b.p, b.prev).multiplyScalar(0.87);
            b.prev.copy(b.p);
            var hold = 0.24 * (1 - 0.5 * (i / chain.length)) * k;
            b.p.add(vel).add(new THREE.Vector3().subVectors(target[i], b.p).multiplyScalar(hold));
            b.p.y -= 0.5 * (i / chain.length) * k;                 // a little weight
          }
          for (var pass = 0; pass < 2; pass++) {
            chain[0].p.copy(target[0]);
            for (var i2 = 1; i2 < chain.length; i2++) {
              var a = chain[i2 - 1].p, bb = chain[i2].p;
              var want0 = target[i2].distanceTo(target[i2 - 1]);
              var d = new THREE.Vector3().subVectors(bb, a);
              var m = d.length() || 1;
              bb.sub(d.multiplyScalar((m - want0) / m));
            }
          }
        });
        api.rebuild();
        return api;
      },
      rebuild: function () {
        api.chains.forEach(function (chain, i) {
          var spine = chain.map(function (b) { return b.p; });
          var geo = tube(spine, ARMS3[i].w, { skin: SKIN.dark, belly: SKIN.belly });
          var slot = arms[i];
          if (slot.mesh) {
            slot.group.remove(slot.mesh, slot.edge);
            slot.mesh.geometry.dispose();
            slot.edge.geometry.dispose();
          }
          slot.mesh = new THREE.Mesh(geo, toon(0xffffff, true));
          slot.edge = new THREE.Mesh(tube(spine, ARMS3[i].w * 1.22, { skin: SKIN.outline, belly: SKIN.outline }),
                                     new THREE.MeshBasicMaterial({ color: SKIN.outline, side: THREE.BackSide }));
          slot.group.add(slot.edge, slot.mesh);
        });
      },
      /* Turn him on the spot, or carry him across the scene. */
      place: function (x, y, z, turn) {
        him.position.set(x || 0, y || 0, z || 0);
        if (turn != null) him.rotation.y = turn;
        return api;
      },
      resize: function (w, h) {
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        return api;
      },
      draw: function () {
        renderer.render(scene, camera);
        return api;
      },
      dispose: function () {
        renderer.dispose();
        scene.traverse(function (o) {
          if (o.geometry) o.geometry.dispose();
          if (o.material) o.material.dispose();
        });
      },
    };
    return api;
  }

  root.GeekOc3D = { create: create, ARMS3: ARMS3, SKIN: SKIN, walk3: walk3, tube: tube, mantle: mantle };
})(typeof window !== 'undefined' ? window : globalThis);
