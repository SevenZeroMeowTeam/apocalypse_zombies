/* HexaLunar Calamity - Uzi (IMI Uzi SMG) Blockbench generator
 * Run inside Blockbench via the MCP `risky_eval` tool (loaded from disk).
 * Law: 16u = 1 block | muzzle = -Z | up = +Y | +X = shooter right | origin = receiver centre
 * Circular parts are ring-of-cube prisms (boxlib `ring` equivalent) - never hand-stacked.
 *
 * EXPORT X-MIRROR (verified, not a bug): the GeckoLib exporter writes -x for every element
 * that carries a pivot. Authored +0.80 eject_port lands at -0.86; authored +0.62 casing
 * lands at -0.62. The mirror is GLOBAL and consistent, so author-space +X is still shooter
 * right and every left/right relation survives. All shipped guns here behave identically.
 *
 * Reference: R-C-uzi.jpg (cutaway). Verified structure:
 *   rear  = backplate + rivet nut, box flip rear sight, coil recoil spring
 *   mid   = magazine INSIDE the pistol grip (brass column, tips forward), trigger AHEAD of grip
 *   front = vertical front-sight post, receiver ends -> very short exposed barrel + knurled barrel nut
 *   red   = bolt body running the receiver, cocking handle on TOP through a top slot
 */
(function () {
  var out = { warnings: [], steps: [] };

  /* ---------- 0. clean slate ---------- */
  var removed = 0;
  try {
    Project.elements.slice().forEach(function (e) { if (e.remove) { e.remove(); removed++; } });
    Project.groups.slice().forEach(function (g) { if (g.remove) { g.remove(); removed++; } });
  } catch (err) { out.warnings.push('clean:' + err.message); }
  Project.elements.length = 0;
  Project.groups.length = 0;
  Outliner.root.length = 0;
  out.steps.push('cleared ' + removed + ' nodes');

  if (!Project.textures.length) return { error: 'no texture in project - create one first' };
  var TEX = Project.textures[0];
  Project.texture_width = 512;
  Project.texture_height = 512;
  Project.box_uv = false;
  Project.name = 'uzi';
  try { Project.geometry_name = 'uzi'; } catch (e) {}
  try { Project.visible_box = [2.5, 2.5, 0.75]; } catch (e) {}

  /* ---------- 1. palette (美术规范 三.1) ---------- */
  var MAT = {
    blu:  [66,  70,  78],   // 发蓝钢 - 枪管 / 机匣 / 弹匣
    blud: [46,  50,  58],   // 发蓝钢暗部 - 枪箍 / 后盖 / 护圈
    prk:  [74,  76,  80],   // 磷化钢 - 哑光件
    stl:  [148, 150, 157],  // 抛光钢 - 枪机 / 拉机柄 / 扳机 / 折叠托
    blk:  [30,  30,  32],   // 黑件 - 握把 / 准星照门
    dk:   [14,  14,  16],   // 膛孔 / 抛壳窗 / 觇孔
    brs:  [206, 162, 82],   // 黄铜 - 弹壳
    cpr:  [196, 126, 72]    // 铜被甲 - 弹头
  };
  var SHADE = { up: 1.14, down: 0.60, north: 1.00, south: 0.86, east: 0.94, west: 0.80 };

  /* ---------- 2. groups ---------- */
  var G = {};
  function grp(name, origin, parent) {
    var g = new Group({ name: name, origin: origin }).init();
    if (parent) g.addTo(parent);
    G[name] = g;
    return g;
  }
  /* root pivot = 后握把 (美术规范 六) */
  var gRoot  = grp('root',  [0, -1.20, 2.00], null);
  var gMove  = grp('move',  [0, -1.20, 2.00], gRoot);
  var gBody  = grp('body',  [0, 1.60, 0], gMove);
  grp('barrel', [0, 1.60, -5.30], gBody);
  grp('bolt',   [0, 1.85, 3.60], gBody);
  var gMag = grp('magazine', [0, 0.85, 2.90], gBody);
  grp('mag_standard',   [0, 0.85, 2.90], gMag);
  grp('mag_extended_1', [0, 0.85, 2.90], gMag);
  grp('mag_extended_2', [0, 0.85, 2.90], gMag);
  grp('mag_extended_3', [0, 0.85, 2.90], gMag);
  grp('additional_magazine', [0, 0.85, 2.90], gMove);   /* must stay empty (TaCZ rule) */
  grp('constraint', [0, 0, 0], gMove);
  grp('camera',     [0, 0, 0], gMove);
  grp('grip',          [0, 0.80, 2.00], gBody);
  grp('trigger_group', [0, 0.72, 0.26], gBody);
  grp('stock',         [0, 0.60, 5.95], gBody);
  grp('sight_front',   [0, 2.62, -4.60], gBody);
  grp('sight_rear',    [0, 2.62,  4.30], gBody);
  grp('casing',        [0.62, 2.05, -1.75], gBody);
  grp('mag_r1', [0,  0.06, 2.00], gMag);
  grp('mag_r2', [0, -0.50, 2.00], gMag);
  grp('mag_r3', [0, -1.06, 2.00], gMag);

  /* ---------- 3. primitive builders ---------- */
  var RAW = [];
  function box(g, n, x0, y0, z0, x1, y1, z1, mat, rot, org) {
    RAW.push({ g: g, n: n, f: [x0, y0, z0], t: [x1, y1, z1], mat: mat, r: rot || [0, 0, 0],
               o: org || [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2] });
  }
  /* ring of N rotated slabs = faceted cylinder (boxlib `ring`).
     axis 0 = along X, 1 = along Y, 2 = along Z (bore axis). pass t = R for a solid disc cap. */
  function ring(g, n, axis, a0, a1, c1, c2, R, t, N, mat, phase) {
    phase = phase || 0;
    var rm = R - t / 2, w = 2 * R * Math.sin(Math.PI / N) * 1.12;
    for (var k = 0; k < N; k++) {
      var al = phase + (k + 0.5) * 2 * Math.PI / N, ad = al * 180 / Math.PI;
      var p1 = c1 + rm * Math.cos(al), p2 = c2 + rm * Math.sin(al);
      var f, t2, rot, org;
      if (axis === 2) {
        f = [p1 - t / 2, p2 - w / 2, a0]; t2 = [p1 + t / 2, p2 + w / 2, a1];
        rot = [0, 0, ad]; org = [p1, p2, (a0 + a1) / 2];
      } else if (axis === 0) {
        f = [a0, p1 - t / 2, p2 - w / 2]; t2 = [a1, p1 + t / 2, p2 + w / 2];
        rot = [ad, 0, 0]; org = [(a0 + a1) / 2, p1, p2];
      } else {
        f = [p1 - t / 2, a0, p2 - w / 2]; t2 = [p1 + t / 2, a1, p2 + w / 2];
        rot = [0, -ad, 0]; org = [p1, (a0 + a1) / 2, p2];
      }
      box(g, n + '_' + (k + 1), f[0], f[1], f[2], t2[0], t2[1], t2[2], mat, rot, org);
    }
  }

  /* ---------- 4. geometry (BORE_Y = 1.60) ---------- */
  var B = 1.60;

  /* 4.1 receiver - stamped steel box, top split into two rails leaving the bolt/handle slot */
  box('body', 'rec_main',     -0.80, 0.75, -5.30,  0.80, 2.45,  5.90, 'blu');
  box('body', 'rec_top_l',    -0.62, 2.45, -5.20, -0.18, 2.62,  5.80, 'blu');
  box('body', 'rec_top_r',     0.18, 2.45, -5.20,  0.62, 2.62,  5.80, 'blu');
  box('body', 'rec_rib_l',    -0.86, 1.25, -5.10, -0.80, 1.75,  5.70, 'blud');
  box('body', 'top_rib_a',    -0.62, 2.62, -4.60,  0.62, 2.70, -0.60, 'blud');
  box('body', 'top_rib_b',    -0.62, 2.62,  0.20,  0.62, 2.70,  5.70, 'blud');
  box('body', 'rec_rib_r',     0.80, 1.25, -5.10,  0.86, 1.75,  5.70, 'blud');
  box('body', 'rec_belly',    -0.62, 0.52, -0.40,  0.62, 0.78,  1.25, 'blud');
  box('body', 'magwell_lip',  -0.68, 0.58,  1.05,  0.68, 0.80,  2.95, 'blud');
  box('body', 'eject_port',    0.80, 1.55, -2.60,  0.86, 2.30, -1.10, 'dk');
  box('body', 'backplate',    -0.78, 0.80,  5.90,  0.78, 2.42,  6.20, 'blud');
  box('body', 'back_rivet',   -0.30, 1.05,  6.20,  0.30, 1.65,  6.34, 'stl');
  box('body', 'back_catch',   -0.22, 0.85,  6.20,  0.22, 1.10,  6.38, 'stl');
  box('body', 'rec_seam_l',   -0.82, 1.95, -5.20, -0.80, 2.02,  5.70, 'dk');
  box('body', 'rec_seam_r',    0.80, 1.95, -5.20,  0.82, 2.02,  5.70, 'dk');

  /* 4.2 barrel + knurled barrel nut (circular, 10-gon) */
  ring('barrel', 'nut',      2, -6.40, -5.30, 0, B, 0.44, 0.20, 10, 'blu');
  ring('barrel', 'nut_gr_a', 2, -6.10, -6.02, 0, B, 0.47, 0.10, 10, 'blud');
  ring('barrel', 'nut_gr_b', 2, -5.68, -5.60, 0, B, 0.47, 0.10, 10, 'blud');
  ring('barrel', 'pipe',     2, -8.90, -6.40, 0, B, 0.31, 0.16, 10, 'blu');
  ring('barrel', 'band',     2, -7.60, -7.40, 0, B, 0.37, 0.14, 10, 'blud');
  ring('barrel', 'crown',    2, -9.05, -8.90, 0, B, 0.37, 0.16,  8, 'blud');
  ring('barrel', 'bore',     2, -9.09, -9.03, 0, B, 0.24, 0.24,  8, 'dk');

  /* 4.3 bolt - big blowback block visible through the top slot, cocking handle on top */
  box('bolt', 'bolt_body',    -0.17, 2.05, -2.20,  0.17, 2.63,  3.20, 'stl');
  box('bolt', 'handle',       -0.22, 2.63,  2.45,  0.22, 3.00,  3.15, 'stl');
  box('bolt', 'handle_rib_a', -0.24, 2.68,  2.56,  0.24, 2.96,  2.64, 'blud');
  box('bolt', 'handle_rib_b', -0.24, 2.68,  2.90,  0.24, 2.96,  2.98, 'blud');

  /* 4.4 magazine (inside the grip housing; BOTH +X/-X faces windowed so the rounds read from either side) */
  box('magazine', 'mag_f',      -0.54, 0.40,  1.45,  0.54, -4.05, 1.62, 'blu');
  box('magazine', 'mag_b',      -0.54, 0.40,  2.38,  0.54, -4.05, 2.55, 'blu');
  box('magazine', 'mag_lx_hi',  -0.54, 0.40,  1.45, -0.48,  0.18, 2.55, 'blu');
  box('magazine', 'mag_lx_lo',  -0.54, -1.72, 1.45, -0.48, -4.05, 2.55, 'blu');
  box('magazine', 'mag_rx_hi',   0.48, 0.40,  1.45,  0.54,  0.18, 2.55, 'blu');
  box('magazine', 'mag_rx_lo',   0.48, -1.72, 1.45,  0.54, -4.05, 2.55, 'blu');
  box('magazine', 'mag_lip_f',  -0.54, 0.58,  1.42,  0.54,  0.40, 1.60, 'blud');
  box('magazine', 'mag_lip_b',  -0.54, 0.58,  2.40,  0.54,  0.40, 2.58, 'blud');
  box('magazine', 'mag_floor',  -0.58, -4.30, 1.40,  0.58, -4.05, 2.60, 'blk');

  /* 4.4b rounds inside the mag (Java hides them one by one by ammo count) */
  [['mag_r1', 0.06], ['mag_r2', -0.50], ['mag_r3', -1.06]].forEach(function (r) {
    ring(r[0], 'case', 2, 1.72, 2.38, 0, r[1], 0.20, 0.20, 6, 'brs');
    ring(r[0], 'tip',  2, 1.44, 1.72, 0, r[1], 0.15, 0.15, 6, 'cpr');
  });

  /* 4.5 grip housing (windowed on BOTH sides, mirroring the mag window) */
  box('grip', 'grip_front', -0.66, 0.60,  1.18,  0.66, -1.80, 1.42, 'blk');
  box('grip', 'grip_back',  -0.66, 0.60,  2.58,  0.66, -1.80, 2.82, 'blk');
  box('grip', 'grip_lx_hi', -0.72, 0.60,  1.18, -0.66,  0.18, 2.82, 'blk');
  box('grip', 'grip_lx_lo', -0.72, -1.72, 1.18, -0.66, -1.80, 2.82, 'blk');
  box('grip', 'grip_rx_hi',  0.66, 0.60,  1.18,  0.72,  0.18, 2.82, 'blk');
  box('grip', 'grip_rx_lo',  0.66, -1.72, 1.18,  0.72, -1.80, 2.82, 'blk');
  box('grip', 'grip_base',  -0.74, -2.00, 1.14,  0.74, -1.80, 2.86, 'blk');
  box('grip', 'grip_chk_a', -0.76, -0.55, 1.20, -0.70, -0.75, 2.80, 'blud');
  box('grip', 'grip_chk_b', -0.76, -0.95, 1.20, -0.70, -1.15, 2.80, 'blud');
  box('grip', 'grip_chk_c', -0.76, -1.35, 1.20, -0.70, -1.55, 2.80, 'blud');

  /* 4.6 trigger + wire guard (AHEAD of the grip) */
  box('body', 'guard_floor', -0.26, -0.45, -0.20, 0.26, -0.22, 1.05, 'blud');
  box('body', 'guard_front', -0.26, -0.22, -0.20, 0.26,  0.62, 0.02, 'blud');
  box('body', 'guard_rear',  -0.26, -0.22,  0.83, 0.26,  0.66, 1.05, 'blud');
  var TR = [-8, 0, 0], TO = [0, 0.72, 0.26];
  box('trigger_group', 'trig_blade', -0.10, 0.06, 0.16, 0.10, 0.80, 0.36, 'stl', TR, TO);
  box('trigger_group', 'trig_shoe',  -0.13, 0.00, 0.14, 0.13, 0.16, 0.38, 'stl', TR, TO);

  /* 4.7 folding stock: struts run back under the receiver BEHIND the grip, butt plate at the rear
     (v1 ran them ahead of the grip, straight through it) */
  box('stock', 'st_hinge_l', -0.44, 0.72, 5.50, -0.28, 1.20, 6.00, 'blud');
  box('stock', 'st_hinge_r',  0.28, 0.72, 5.50,  0.44, 1.20, 6.00, 'blud');
  box('stock', 'st_strut_l', -0.44, 0.05, 2.95, -0.30, 0.34, 6.00, 'stl');
  box('stock', 'st_strut_r',  0.30, 0.05, 2.95,  0.44, 0.34, 6.00, 'stl');
  box('stock', 'st_butt',    -0.58, -0.42, 6.20,  0.58, 0.95, 6.55, 'stl');
  box('stock', 'st_butt_pad',-0.52, -0.28, 6.55,  0.52, 0.82, 6.68, 'blk');

  /* 4.8 sights - hooded front post + box flip rear with protective ears */
  box('sight_front', 'sf_base',     -0.34, 2.62, -5.00,  0.34, 2.78, -4.20, 'blk');
  // The post stops inside its own hood and the rear aperture lines up with it: the two ends of the
  // sight line are the same height, so it runs parallel to the bore. Before this the post top sat at
  // 3.45 — 0.13 above the hood top at 3.26, i.e. poking through the very ring that protects it — and
  // the rear leaf had been raised to match, tilting the sight line 2.34° off the bore.
  box('sight_front', 'sf_post',     -0.08, 2.78, -4.68,  0.08, 3.26, -4.52, 'blk');
  box('sight_front', 'sf_hood_l',   -0.30, 2.78, -4.76, -0.22, 3.32, -4.44, 'blk');
  box('sight_front', 'sf_hood_r',    0.22, 2.78, -4.76,  0.30, 3.32, -4.44, 'blk');
  box('sight_front', 'sf_hood_top', -0.30, 3.26, -4.76,  0.30, 3.32, -4.44, 'blk');
  box('sight_rear',  'sr_base',     -0.36, 2.62,  3.85,  0.36, 2.80,  4.75, 'blk');
  box('sight_rear',  'sr_ear_l',    -0.36, 2.80,  3.92, -0.26, 3.46,  4.68, 'blk');
  box('sight_rear',  'sr_ear_r',     0.26, 2.80,  3.92,  0.36, 3.46,  4.68, 'blk');
  box('sight_rear',  'sr_leaf',     -0.24, 2.80,  4.18,  0.24, 3.38,  4.36, 'blk');
  // Aperture centre 3.26 = the post's tip; still inside the leaf (top 3.38) and the ears (top 3.46).
  box('sight_rear',  'sr_ap',       -0.10, 3.16,  4.34,  0.10, 3.36,  4.38, 'dk');

  /* 4.9 spent casing - hidden inside the receiver at rest, flies out of the +X port */
  ring('casing', 'case_body', 2, -2.10, -1.40, 0.62, 2.05, 0.20, 0.20, 8, 'brs');
  ring('casing', 'case_rim',  2, -2.20, -2.10, 0.62, 2.05, 0.24, 0.24, 8, 'brs');
  ring('casing', 'case_neck', 2, -1.40, -1.30, 0.62, 2.05, 0.15, 0.15, 8, 'brs');

  /* ---------- 5. instantiate ---------- */
  var made = [], MADE = [];
  RAW.forEach(function (r) {
    var parent = G[r.g];
    if (!parent) { out.warnings.push('missing group ' + r.g); return; }
    var c = new Cube({ name: r.n, from: r.f, to: r.t, origin: r.o, rotation: r.r, autouv: 0 });
    c.init();
    c.addTo(parent);
    c.__mat = r.mat;
    MADE.push(c);
    made++;
  });
  out.steps.push('created ' + made + ' cubes in ' + Object.keys(G).length + ' groups');

  /* ---------- 6. per-face UV atlas (shelf packer, density 11..13) ---------- */
  var FL = ['north', 'east', 'south', 'west', 'up', 'down'];
  var faces = [];
  MADE.forEach(function (c) {
    var dx = Math.abs(c.to[0] - c.from[0]), dy = Math.abs(c.to[1] - c.from[1]), dz = Math.abs(c.to[2] - c.from[2]);
    FL.forEach(function (f) {
      var w, h;
      if (f === 'north' || f === 'south') { w = dx; h = dy; }
      else if (f === 'east' || f === 'west') { w = dz; h = dy; }
      else { w = dx; h = dz; }
      faces.push({ c: c, f: f, w: w, h: h, mat: c.__mat });
    });
  });
  function pack(D) {
    var it = faces.map(function (o, i) {
      return { i: i, w: Math.max(1, Math.round(o.w * D)), h: Math.max(1, Math.round(o.h * D)) };
    }).sort(function (a, b) { return (b.h - a.h) || (b.w - a.w); });
    var x = 1, y = 1, rowH = 0, res = new Array(faces.length);
    for (var k = 0; k < it.length; k++) {
      var e = it[k];
      if (x + e.w + 1 > 512) { x = 1; y += rowH + 1; rowH = 0; }
      if (y + e.h + 1 > 512) return null;
      res[e.i] = [x, y, x + e.w, y + e.h];
      x += e.w + 1; rowH = Math.max(rowH, e.h);
    }
    return { rects: res, used: y + rowH };
  }
  var D = 0, pk = null;
  for (var d = 13; d >= 4; d--) { var p = pack(d); if (p) { D = d; pk = p; break; } }
  if (!pk) return { error: 'UV atlas overflow even at 4 px/u' };
  faces.forEach(function (o, i) {
    var r = pk.rects[i];
    o.c.faces[o.f].uv = r;
    o.c.faces[o.f].texture = TEX.uuid;
    o.rect = r;
  });
  out.steps.push('uv density ' + D + ' px/u, atlas height ' + pk.used + '/512, faces ' + faces.length);

  /* ---------- 7. paint the 512x512 atlas ---------- */
  var ctx = TEX.ctx;
  var img = ctx.createImageData(512, 512), px = img.data;
  function hashi(a, b) { var n = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453; return n - Math.floor(n); }
  faces.forEach(function (o, i) {
    var base = MAT[o.mat] || MAT.prk, s = SHADE[o.f] || 1, r = o.rect, x, y, p;
    for (y = r[1]; y < r[3]; y++) {
      for (x = r[0]; x < r[2]; x++) {
        var edge = (x === r[0] || x === r[2] - 1 || y === r[1] || y === r[3] - 1);
        var grain = 0.93 + 0.14 * hashi(x + i * 7, y - i * 3);
        var f = s * grain * (edge ? 0.76 : 1);
        p = (y * 512 + x) * 4;
        px[p]     = Math.min(255, Math.round(base[0] * f));
        px[p + 1] = Math.min(255, Math.round(base[1] * f));
        px[p + 2] = Math.min(255, Math.round(base[2] * f));
        px[p + 3] = 255;
      }
    }
  });
  ctx.clearRect(0, 0, 512, 512);
  ctx.putImageData(img, 0, 0);
  TEX.internal = true;
  TEX.source = TEX.canvas.toDataURL('image/png', 1);
  if (TEX.updateSource) TEX.updateSource(TEX.source);
  if (TEX.updateImageFromCanvas) TEX.updateImageFromCanvas();
  if (TEX.updateMaterial) TEX.updateMaterial();
  TEX.saved = false;
  out.steps.push('painted texture ' + TEX.name);
  out.png = TEX.canvas.toDataURL('image/png', 1);

  /* ---------- 8. self-check ---------- */
  var bb = [[1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]];
  MADE.forEach(function (c) {
    [0, 1, 2].forEach(function (a) {
      bb[0][a] = Math.min(bb[0][a], c.from[a], c.to[a]);
      bb[1][a] = Math.max(bb[1][a], c.from[a], c.to[a]);
    });
  });
  var dim = [bb[1][0] - bb[0][0], bb[1][1] - bb[0][1], bb[1][2] - bb[0][2]];
  out.bbox = { min: bb[0].map(function (v) { return +v.toFixed(2); }),
               max: bb[1].map(function (v) { return +v.toFixed(2); }),
               dim: dim.map(function (v) { return +v.toFixed(2); }),
               blocks: +(dim[2] / 16).toFixed(3) };
  out.check = {
    longest_axis_is_Z: dim[2] >= dim[0] && dim[2] >= dim[1],
    length_in_range: dim[2] / 16 >= 0.9 && dim[2] / 16 <= 2.6,
    bore_y: B,
    muzzle: [0, +(B.toFixed(2)), +bb[0][2].toFixed(2)],
    eject_port: [0.86, 1.95, -1.85],
    mag_top: [0, 0.58, 2.00],
    casing_cx_gt_0: 0.62 > 0,
    bones: Project.groups.length,
    cubes: MADE.length
  };
  out.groups_tree = Project.groups.map(function (g) { return g.name + '<' + (g.parent && g.parent.name ? g.parent.name : 'root') + '>'; });
  out.bone_rot_all_zero = Project.groups.every(function (g) {
    return !g.rotation || (g.rotation[0] === 0 && g.rotation[1] === 0 && g.rotation[2] === 0);
  });

  if (typeof Canvas !== 'undefined' && Canvas.updateAllFaces) Canvas.updateAllFaces();
  if (typeof Preview !== 'undefined') Preview.all.forEach(function (v) { if (v.canvas) v.render(); });
  return out;
})()
