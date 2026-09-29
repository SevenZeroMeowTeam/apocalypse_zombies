/* HexaLunar Calamity - AWM (Precision International AWM) Blockbench generator
 * Run inside Blockbench via the MCP `risky_eval` tool.
 * Law: 16u = 1 block | muzzle = -Z | up = +Y | +X = shooter right | origin = receiver centre
 * Circular parts are built as ring-of-cube primitives (boxlib `ring` equivalent), never hand-stacked.
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
  Project.name = 'awm';
  try { Project.geometry_name = 'awm'; } catch (e) {}

  /* ---------- 1. palette ---------- */
  var MAT = {
    mw:  [216, 221, 227],  // white / silver metal  (Printstream skin body)
    mwd: [163, 172, 182],  // darker metal (edges, bands, plates)
    grp: [124, 132, 141],  // gunmetal grey (rails, rings, hardware)
    drk: [74,  80,  88],   // dark steel inset
    blk: [35,  38,  43],   // polymer black (scope, grip, magazine floor, muzzle brake)
    brs: [206, 162, 82],   // brass - casing      (规范 三.1 黄铜)
    cpr: [196, 126, 72],   // copper jacket - bullet (规范 三.1 铜被甲)
    gls: [30,  90, 122]    // lens glass
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
  var gRoot = grp('root', [0, -1.07, 1.30], null);
  var gMove = grp('move', [0, -1.07, 1.30], gRoot);        // GeckoLib carry bone
  var gBody = grp('body', [0, 1.0, 0], gMove);
  var gMag  = grp('magazine', [0, 1.0, -1.45], gMove);
  grp('mag_standard',   [0, 1.0, -1.45], gMag);
  grp('mag_extended_1', [0, 1.0, -1.45], gMag);
  grp('mag_extended_2', [0, 1.0, -1.45], gMag);
  grp('mag_extended_3', [0, 1.0, -1.45], gMag);
  grp('additional_magazine', [0, 1.0, -1.45], gMove);      // must stay empty
  grp('constraint', [0, 0, 0], gMove);
  grp('camera', [0, 0, 0], gMove);
  grp('barrel', [0, 1.575, -7.0], gBody);
  grp('bolt', [0.42, 1.85, 1.45], gBody);
  var gScope = grp('scope', [0, 3.15, -1.2], gBody);
  grp('scope_elev', [0, 3.60, -3.6], gScope);
  grp('scope_wind', [0.44, 3.15, -3.6], gScope);
  grp('trigger_group', [0, 0.85, -0.20], gBody);   // pivot = trigger hinge, top of the blade
  grp('bipod', [0, 0.40, -8.6], gBody);
  grp('stock', [0, 1.60, 1.45], gMove);
  grp('grip', [0, 1.05, 1.35], gMove);

  /* ---------- 2b. loose-round parts ----------
   * casing / round_in : pivot = 自身几何中心 (规范 六.1)，静止时整体藏进机匣内部
   *                     (机匣 x ±0.85 / y 1.05..2.45)，几何中心 x = 0.45 > 0 满足自检项 E；
   *                     动画窗口里从 +X 抛壳窗穿过 AWP 同款抛壳锚点 (0.92, 1.50, -2.50)。
   * mag_spare : 备用弹匣，pivot 与 magazine 完全相同 (规范2 二.4 对额外弹匣的硬要求)，
   *             但**不叫** additional_magazine —— 那个组按 TaCZ 规则必须导出为空。
   * 无臂：模型只有部件，手持手臂由游戏的玩家手臂渲染（美术规范 十·手骨 属 TaCZ 枪包通道）。 */
  grp('casing',    [0.45, 1.92, -2.50], gBody);
  grp('round_in',  [0.45, 1.50, -4.10], gBody);
  grp('mag_spare', [0, 1.0, -1.45], gMove);

  /* ---------- 3. primitive builders ---------- */
  var RAW = [];
  function box(g, n, x0, y0, z0, x1, y1, z1, mat, rot, org) {
    RAW.push({ g: g, n: n, f: [x0, y0, z0], t: [x1, y1, z1], mat: mat, r: rot || [0, 0, 0],
               o: org || [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2] });
  }
  /* ring of N rotated slabs = faceted cylinder (boxlib `ring`).
     axis 0 = along X (ring in YZ), 1 = along Y (ring in XZ), 2 = along Z (ring in XY).
     pass t = R for a solid disc cap. */
  function ring(g, n, axis, a0, a1, c1, c2, R, t, N, mat, phase) {
    phase = phase || 0;
    var rm = R - t / 2, w = 2 * R * Math.sin(Math.PI / N) * 1.12;
    for (var k = 0; k < N; k++) {
      var al = phase + (k + 0.5) * 2 * Math.PI / N, ad = al * 180 / Math.PI;
      var p1 = c1 + rm * Math.cos(al), p2 = c2 + rm * Math.sin(al);
      var f, t2, rot, org;
      if (axis === 2) {                       // ring in XY, cylinder runs along Z
        f = [p1 - t / 2, p2 - w / 2, a0]; t2 = [p1 + t / 2, p2 + w / 2, a1];
        rot = [0, 0, ad]; org = [p1, p2, (a0 + a1) / 2];
      } else if (axis === 0) {                 // ring in YZ, cylinder runs along X
        f = [a0, p1 - t / 2, p2 - w / 2]; t2 = [a1, p1 + t / 2, p2 + w / 2];
        rot = [ad, 0, 0]; org = [(a0 + a1) / 2, p1, p2];
      } else {                                 // ring in XZ, cylinder runs along Y
        f = [p1 - t / 2, a0, p2 - w / 2]; t2 = [p1 + t / 2, a1, p2 + w / 2];
        rot = [0, -ad, 0]; org = [p1, (a0 + a1) / 2, p2];
      }
      box(g, n + '_' + (k + 1), f[0], f[1], f[2], t2[0], t2[1], t2[2], mat, rot, org);
    }
  }

  /* ---------- 4. geometry ---------- */
  var BORE = 1.575;

  /* 4.1 receiver / chassis (body) */
  box('body', 'rec_main',  -0.85, 1.05, -7.00,  0.85, 2.45, 1.45, 'mw');
  box('body', 'rec_top',   -0.62, 2.45, -6.90,  0.62, 2.72, 0.20, 'mwd');
  for (var i = 0; i < 14; i++) {
    var tz = -6.60 + i * 0.45;
    box('body', 'rail_tooth_' + i, -0.62, 2.72, tz, 0.62, 2.86, tz + 0.30, 'grp');
  }
  box('body', 'rec_belly',   -0.70, 0.85, -7.00,  0.70, 1.05, 0.85, 'mwd');   // extends to the grip front so the guard rear post lands under it
  box('body', 'forend',      -0.90, 0.95, -9.70,  0.90, 1.95, -7.00, 'mw');
  box('body', 'forend_top',  -0.62, 1.95, -9.70,  0.62, 2.15, -7.00, 'mwd');
  box('body', 'forend_vent_l1', -0.93, 1.20, -9.30, -0.86, 1.50, -8.90, 'drk');
  box('body', 'forend_vent_r1',  0.86, 1.20, -9.30,  0.93, 1.50, -8.90, 'drk');
  box('body', 'forend_vent_l2', -0.93, 1.20, -8.40, -0.86, 1.50, -8.00, 'drk');
  box('body', 'forend_vent_r2',  0.86, 1.20, -8.40,  0.93, 1.50, -8.00, 'drk');
  box('body', 'forend_rail',   -0.40, 0.70, -9.40,  0.40, 0.95, -7.20, 'grp');
  box('body', 'eject_port',     0.83, 1.55, -3.50,  0.89, 2.20, -1.70, 'drk');
  box('body', 'bolt_channel',   0.83, 1.75, -6.90,  0.89, 2.10,  1.40, 'drk');
  box('body', 'magwell',       -0.55, 0.30, -3.60,  0.55, 1.05, -1.40, 'drk');
  box('body', 'magwell_lip',   -0.60, 0.22, -3.68,  0.60, 0.45, -1.34, 'mwd');
  box('body', 'safety',        -0.52, 1.55, -1.20, -0.36, 1.90, -0.95, 'grp');
  box('body', 'mag_release',   -0.80, 0.95, -1.75, -0.62, 1.25, -1.45, 'drk');

  /* trigger guard bow - bolted to the chassis underside, so it belongs to body, not the trigger bone */
  box('body', 'guard_front', -0.30, -0.40, -1.44, 0.30, 0.90, -1.12, 'mwd');
  box('body', 'guard_floor', -0.30, -0.62, -1.44, 0.30, -0.30, 0.70, 'mwd');
  box('body', 'guard_rear',  -0.30, -0.40,  0.42, 0.30, 0.90, 0.70, 'mwd');

  /* trigger blade - own bone, hinged at the top (pivot 0,0.85,-0.20), raked 8 deg forward.
     Top tucks inside the chassis belly (0.85..1.05) so there is no air gap; tip clears the bow floor. */
  var TR = [8, 0, 0], TO = [0, 0.85, -0.20];
  box('trigger_group', 'trigger_blade', -0.10, -0.22, -0.34, 0.10, 0.90, -0.06, 'grp', TR, TO);
  box('trigger_group', 'trigger_shoe',  -0.13, -0.26, -0.37, 0.13, -0.10, -0.03, 'drk', TR, TO);

  /* 4.2 barrel + muzzle brake (10-gon) */
  ring('barrel', 'chamber',    2, -7.40, -6.90, 0, BORE, 0.62, 0.20, 10, 'mwd');
  ring('barrel', 'pipe',       2, -17.30, -7.40, 0, BORE, 0.46, 0.16, 10, 'mw');
  ring('barrel', 'pipe_band',  2, -16.60, -16.30, 0, BORE, 0.55, 0.16, 10, 'mwd');
  ring('barrel', 'brake',      2, -18.00, -17.30, 0, BORE, 0.60, 0.18, 10, 'blk');
  ring('barrel', 'brake_band1',2, -17.96, -17.82, 0, BORE, 0.67, 0.13, 10, 'grp');
  ring('barrel', 'brake_band2',2, -17.55, -17.41, 0, BORE, 0.67, 0.13, 10, 'grp');
  ring('barrel', 'bore',       2, -18.02, -17.97, 0, BORE, 0.27, 0.27, 8, 'drk');
  ring('barrel', 'pipe_collar',2, -7.62, -7.30, 0, BORE, 0.58, 0.18, 10, 'grp');

  /* 4.3 bolt (slides along Z, rotates around bore to unlock) */
  ring('bolt', 'body', 2, -0.20, 1.35, 0.42, 1.85, 0.30, 0.14, 8, 'mw');
  box('bolt', 'shroud', 0.16, 1.55, 1.35, 0.72, 2.15, 1.62, 'grp', [0, 0, 0], [0.42, 1.85, 1.45]);
  box('bolt', 'lug',    0.10, 1.58, -0.35, 0.74, 1.74, 0.00, 'grp', [0, 0, 0], [0.42, 1.85, 1.45]);
  box('bolt', 'handle_arm', 0.62, 1.68, 0.70, 1.26, 1.92, 0.98, 'mw', [0, 0, 0], [0.42, 1.85, 1.45]);
  ring('bolt', 'knob', 0, 1.26, 1.46, 1.80, 0.84, 0.26, 0.20, 6, 'blk');
  ring('bolt', 'knob_cap_a', 0, 1.46, 1.50, 1.80, 0.84, 0.24, 0.24, 6, 'grp');
  ring('bolt', 'knob_cap_b', 0, 1.22, 1.26, 1.80, 0.84, 0.24, 0.24, 6, 'grp');

  /* 4.4 magazine (duplicated into mag_standard + 3 extended slots) */
  var MAGC = [
    ['mag_body',  -0.42, -1.05, -3.35, 0.42,  0.95, -1.50, 'mwd'],
    ['mag_floor', -0.48, -1.28, -3.40, 0.48, -1.05, -1.45, 'blk'],
    ['mag_rib_l', -0.46, -0.60, -3.20, -0.42, 0.60, -1.60, 'grp'],
    ['mag_rib_r',  0.42, -0.60, -3.20,  0.46, 0.60, -1.60, 'grp'],
    ['mag_hole',   0.42, -0.35, -2.95,  0.45, -0.08, -2.72, 'blk'],
    ['mag_spine', -0.30, -1.05, -3.30,  0.30, -0.90, -1.55, 'grp']
  ];
  ['mag_standard', 'mag_extended_1', 'mag_extended_2', 'mag_extended_3'].forEach(function (slot) {
    MAGC.forEach(function (c) { box(slot, c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]); });
  });

  /* 4.5 grip (raked back 18 deg) */
  var GR = [-18, 0, 0], GO = [0, 1.05, 1.35];
  box('grip', 'grip_main',  -0.42, -1.25, 0.85, 0.42, 1.05, 1.90, 'blk', GR, GO);
  box('grip', 'grip_panel', -0.46, -1.10, 0.95, 0.46, 0.60, 1.85, 'drk', GR, GO);
  box('grip', 'grip_cap',   -0.46, -1.42, 0.90, 0.46, -1.25, 1.85, 'mwd', GR, GO);

  /* 4.6 thumbhole stock */
  box('stock', 'stock_upper', -0.60, 1.85, 1.45, 0.60, 2.50, 5.50, 'mw');
  box('stock', 'stock_lower', -0.60, 0.35, 1.45, 0.60, 1.50, 5.50, 'mw');
  box('stock', 'stock_rear',  -0.60, 0.35, 5.00, 0.60, 2.50, 5.50, 'mwd');
  box('stock', 'cheek_rest',  -0.45, 2.50, 2.30, 0.45, 2.85, 5.20, 'blk');
  box('stock', 'butt_pad',    -0.60, 0.20, 5.50, 0.60, 2.65, 5.85, 'blk');
  box('stock', 'butt_pad2',   -0.55, 0.30, 5.85, 0.55, 2.55, 5.95, 'drk');
  box('stock', 'sling_loop',  -0.68, 0.90, 4.55, -0.60, 1.15, 4.85, 'grp');
  box('stock', 'stock_rail',  -0.30, 2.85, 2.60, 0.30, 2.95, 4.90, 'grp');

  /* 4.7 scope (optical axis y = 3.15) */
  ring('scope', 'tube',      2, -5.70, -0.50, 0, 3.15, 0.44, 0.14, 10, 'blk');
  ring('scope', 'objective', 2, -6.60, -5.70, 0, 3.15, 0.62, 0.16, 10, 'blk');
  ring('scope', 'obj_rim',   2, -6.72, -6.60, 0, 3.15, 0.67, 0.12, 10, 'grp');
  ring('scope', 'eyepiece',  2, -0.50,  0.50, 0, 3.15, 0.56, 0.16, 10, 'blk');
  ring('scope', 'eye_rim',   2,  0.50,  0.62, 0, 3.15, 0.61, 0.12, 10, 'grp');
  ring('scope', 'lens_front',2, -6.76, -6.72, 0, 3.15, 0.55, 0.55, 10, 'gls');
  ring('scope', 'lens_rear', 2,  0.62,  0.66, 0, 3.15, 0.49, 0.49, 10, 'gls');
  box('scope', 'mount_front', -0.30, 2.60, -5.50, 0.30, 2.94, -4.90, 'grp');
  box('scope', 'mount_rear',  -0.30, 2.72, -2.20, 0.30, 2.98, -1.40, 'grp');
  ring('scope', 'ring_front',2, -5.45, -5.05, 0, 3.15, 0.51, 0.11, 10, 'grp');
  ring('scope', 'ring_rear', 2, -2.15, -1.75, 0, 3.15, 0.51, 0.11, 10, 'grp');
  ring('scope', 'tube_step', 2, -6.05, -5.90, 0, 3.15, 0.50, 0.12, 10, 'mwd');
  ring('scope', 'eye_step',  2, -0.62, -0.47, 0, 3.15, 0.50, 0.12, 10, 'mwd');

  /* 4.8 turrets (independent bones, mirrored per TaCZ accessory convention) */
  ring('scope_elev', 'elev_turret', 1, 3.60, 4.34, 0, -3.60, 0.34, 0.16, 8, 'blk');
  ring('scope_elev', 'elev_cap',    1, 4.34, 4.42, 0, -3.60, 0.32, 0.32, 8, 'grp');
  ring('scope_elev', 'elev_knurl',  1, 4.10, 4.26, 0, -3.60, 0.38, 0.10, 8, 'grp');
  ring('scope_wind', 'wind_turret', 0, 0.44, 1.06, 3.15, -3.60, 0.34, 0.16, 8, 'blk');
  ring('scope_wind', 'wind_cap',    0, 1.06, 1.14, 3.15, -3.60, 0.32, 0.32, 8, 'grp');
  ring('scope_wind', 'wind_knurl',  0, 0.86, 1.00, 3.15, -3.60, 0.38, 0.10, 8, 'grp');
  ring('scope', 'para_turret', 0, -1.00, -0.44, 3.15, -3.60, 0.30, 0.14, 8, 'blk');
  ring('scope', 'para_cap',    0, -1.06, -1.00, 3.15, -3.60, 0.28, 0.28, 8, 'grp');

  /* 4.9 folded bipod under the forend */
  box('bipod', 'mount',    -0.28, 0.42, -9.00, 0.28, 0.95, -8.20, 'grp');
  box('bipod', 'leg_l',    -0.72, 0.45, -8.90, -0.50, 0.65, -6.90, 'blk');
  box('bipod', 'leg_r',     0.50, 0.45, -8.90,  0.72, 0.65, -6.90, 'blk');
  box('bipod', 'foot_l',   -0.78, 0.40, -7.00, -0.46, 0.70, -6.80, 'drk');
  box('bipod', 'foot_r',    0.46, 0.40, -7.00,  0.78, 0.70, -6.80, 'drk');

  /* 4.10 空弹壳 casing —— 静止时完全藏进机匣内部，动画里从抛壳窗脱出再翻飞 */
  ring('casing', 'case_body', 2, -3.15, -1.95, 0.45, 1.92, 0.20, 0.20, 8, 'brs');
  ring('casing', 'case_neck', 2, -1.95, -1.85, 0.45, 1.92, 0.15, 0.15, 8, 'brs');
  ring('casing', 'case_rim',  2, -3.24, -3.15, 0.45, 1.92, 0.24, 0.24, 8, 'brs');

  /* 4.11 待入膛子弹 round_in —— 藏机匣内部，换弹时被枪栓从弹匣口顶进膛 */
  ring('round_in', 'rnd_case',  2, -4.85, -3.60, 0.45, 1.50, 0.18, 0.18, 8, 'brs');
  ring('round_in', 'rnd_shldr', 2, -5.05, -4.85, 0.45, 1.50, 0.15, 0.15, 8, 'brs');
  ring('round_in', 'rnd_tip',   2, -5.65, -5.05, 0.45, 1.50, 0.12, 0.12, 8, 'cpr');
  ring('round_in', 'rnd_rim',   2, -4.94, -4.85, 0.45, 1.50, 0.20, 0.20, 8, 'grp');

  /* 4.12 备用弹匣 mag_spare —— 常驻可见，贴在弹匣井左侧（左手够得到的位置） */
  var SDX = -1.03, SDY = 0.20, SDZ = 0.10;
  MAGC.forEach(function (c) {
    box('mag_spare', 'spare_' + c[0], c[1] + SDX, c[2] + SDY, c[3] + SDZ,
                                      c[4] + SDX, c[5] + SDY, c[6] + SDZ, c[7]);
  });

  /* ---------- 5. instantiate ---------- */
  var made = 0;
  RAW.forEach(function (r) {
    var parent = G[r.g];
    if (!parent) { out.warnings.push('missing group ' + r.g); return; }
    var c = new Cube({ name: r.n, from: r.f, to: r.t, origin: r.o, rotation: r.r, autouv: 0 });
    c.init();
    c.addTo(parent);
    c.__mat = r.mat;
    made++;
  });
  out.steps.push('created ' + made + ' cubes in ' + Object.keys(G).length + ' groups');

  /* ---------- 6. per-face UV atlas (shelf packer) ---------- */
  var FL = ['north', 'east', 'south', 'west', 'up', 'down'];
  var faces = [];
  Project.elements.forEach(function (c) {
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
    var base = MAT[o.mat] || MAT.grp, s = SHADE[o.f] || 1, r = o.rect, x, y, p;
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

  if (typeof Canvas !== 'undefined' && Canvas.updateAllFaces) Canvas.updateAllFaces();
  if (typeof Preview !== 'undefined') Preview.all.forEach(function (v) { if (v.canvas) v.render(); });
  out.cubes = Project.elements.length;
  out.groups = Project.groups.length;
  out.groups_tree = Project.groups.map(function (g) { return g.name + '<' + (g.parent && g.parent.name ? g.parent.name : 'root') + '>'; });
  out.MAT = null;
  return out;
})()
