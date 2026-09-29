/* 莫辛-纳甘 M91/30 —— 几何生成器（在 Blockbench 内跑）
 *
 * 标定（美术规范.md 一·关键轴线 + 七·自检）：
 *   枪口  {0, 1.75, -17.35}   ← Java 弹道/枪口火焰锚点，硬约束
 *   抛壳点 {0.90, 2.10, -1.95} ← 弹壳骨静止位，硬约束
 *   膛线轴 Y = 1.75（BORE）
 *   全长 22.9u（1.43 格）→ 比例尺 53.8 mm/单位（真机 1232mm）
 *   模型原点落在机匣后端（mm 933 ≈ z 0.00），root/move/body 控制器在机匣中心 REC_MID=-2.55
 *
 * 文献标定（莫辛-纳甘 M91/30，1:1 真机尺寸 ÷ 53.8）：
 *   全长 1232mm / 枪管 730mm / 5 发弹仓 / 7.62x54R / 圆形机匣 / 直拉机柄 /
 *   前准星为柱式带护罩（刃顶 +50mm）、后照门为切线式表尺（战斗缺口 +35mm，铰链在座前端，向后展开）
 *
 * 跑法（MCP risky_eval）：
 *   (function(){var fs=require('fs');return (0,eval)(fs.readFileSync('F:/mcmod/tools/mosin_nagant_bb_gen.js','utf8'));})()
 */
(function () {

  var fs = (typeof require === 'function') ? require('fs') : null;

  // ============================================================ 0. 标定常数
  var MMOS = 53.8;                 // mm / 模型单位
  var ZM   = -17.35;               // 枪口 Z
  var BORE = 1.75;                 // 膛线轴 Y
  function Z(mm) { return ZM + mm / MMOS; }
  function Y(mm) { return BORE + mm / MMOS; }
  var ZREC_F = Z(665), ZREC_R = Z(930);            // 机匣前后端
  var REC_MID = { x: 0, y: BORE, z: (ZREC_F + ZREC_R) / 2 };
  var S = 12;                      // 贴图密度 px/单位（美术规范四）
  var TEXW = 512;
  var ART = 'F:/mcmod/art/mosin_nagant/';
  var RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/';

  // 色板（美术规范.md 三·色板：逐条对齐参考色号）
  var MAT = {
    BLUE:    [66, 70, 78],      // 发蓝钢（枪管/机匣/弹仓）= mosin_m9130_v3.BLUE
    BLUE_D:  [46, 50, 58],      // 发蓝钢暗部（枪箍/表尺/护圈）= mosin_m9130_v3.BLUE_D
    STEEL:   [148, 150, 157],   // 抛光钢（枪机体/拉机柄/扳机/通条/托底板）
    STEEL_D: [96, 100, 106],    // 白钢暗部
    DARK:    [14, 14, 16],      // 膛孔 / 镜筒挡板黑
    SIGHT:   [30, 30, 32],      // 准星 / 照门黑
    WOOD:    [208, 152, 86],    // 蜜色桦木（莫辛 v3）= mosin_m9130_v3.WOOD
    WOOD_D:  [150, 104, 54],    // 木纹暗条
    WOOD_L:  [232, 184, 120],   // 木受光
    BRS:     [206, 162, 82],    // 黄铜（弹壳）= awp_v2.BRASS
    CPR:     [196, 126, 72]     // 铜被甲（弹头）= awp_v2.COPPER
  };
  var SHADE = { north: 0.92, south: 1.06, east: 1.00, west: 0.86, up: 1.10, down: 0.70 };
  var FACES = ['north', 'east', 'south', 'west', 'up', 'down'];

  // ============================================================ 2. 清场
  var report = { steps: [], warns: [], fails: [] };
  function step(s) { report.steps.push(s); }
  function warn(s) { report.warns.push(s); }
  function fail(s) { report.fails.push(s); }

  if (typeof Undo === 'undefined' || typeof Project === 'undefined') {
    return { ok: false, fails: ['不在 Blockbench 作用域（缺 Undo/Project）'] };
  }
  // BB 5.2：Project.elements 恒为空、Cube.all 不登记、root 不在 Group.all —— 方块只能从骨骼树收集
  function allCubes() {
    var out = [], seen = {};
    function push(list) {
      (list || []).forEach(function (c) {
        if (c instanceof Cube) { if (!seen[c.uuid]) { seen[c.uuid] = 1; out.push(c); } }
        else if (c && c.children) push(c.children);
      });
    }
    if (typeof Group !== 'undefined' && Group.all) Group.all.forEach(function (g) { push(g.children); });
    return out;
  }

  var preEls = allCubes();
  Undo.initEdit({ elements: preEls, outliner: true, textures: Texture.all.slice() });

  preEls.forEach(function (e) { try { e.remove(); } catch (err) {} });
  Group.all.slice().forEach(function (g) { if (g.name !== 'root') g.remove(); });
  (Project.textures || []).slice().forEach(function (t) { t.remove(); });
  step('清场：方块/骨骼/贴图归零');
  Project.box_uv = false;   // 陷阱：box_uv 为真会覆盖逐面 UV（症状：UV 退化成 [8,8,9,9]）
  Project.texture_width = TEXW;
  Project.texture_height = TEXW;
  try { Project.visible_box = [2.6, 1.8, 0.2]; } catch (e) {}   // GeckoLib 剔除用；1x1 会把长枪裁掉

  // 陷阱：BB 5.2 的 root 组不在 Group.all 里；若沿用 find() 会每次都新建一根 root，
    //       重复跑脚本就会在 Outliner 顶层堆出多根同名 root（导出后 geo 里出现重复骨骼）。
    //       正确做法：直接看 Outliner.root，保留第一根、删掉其余、一根都没有时再新建。
    var roots = (typeof Outliner !== 'undefined' && Outliner.root)
      ? Outliner.root.filter(function (e) { return e && e.type === 'group' && e.name === 'root'; })
      : [];
    roots.slice(1).forEach(function (g) { try { g.remove(); } catch (err) {} });
    var ROOT = roots[0] || null;
    if (!ROOT) { ROOT = new Group({ name: 'root', origin: [0, 0, 0] }); ROOT.addTo('root'); }
    ROOT.origin = [0, BORE, REC_MID.z];

  function mkGroup(name, origin, parent) {
    var g = new Group({ name: name, origin: origin.slice(), children: [] });
    if (typeof g.init === 'function') { try { g.init(); } catch (e) { g.addTo(parent || ROOT); } }
    if (parent !== undefined && parent !== null) { g.addTo(parent); }
    return g;
  }

  // ============================================================ 3. 方块登记
  var RAW = [];
  function addCube(g, name, from, to, mat, opt) {
    opt = opt || {};
    var c = new Cube({
      name: name,
      from: from.slice(),
      to: to.slice(),
      origin: opt.origin ? opt.origin.slice() : [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2, (from[2] + to[2]) / 2],
      rotation: opt.rotation ? opt.rotation.slice() : [0, 0, 0],
      autouv: 0,
      box_uv: false
    });
    // BB 5.2：addTo() 只挂骨骼树，不登记进 Project.elements —— 不 init() 的话
    // Codecs.project.compile() 会编出 elements:0 的空 bbmodel（方块全丢）
    if (typeof c.init === 'function') { try { c.init(); } catch (e) {} }
    c.addTo(g);
    RAW.push({ cube: c, mat: mat, faces: opt.faces || null });
    return c;
  }
  // 八角环 / 实心八角柱：axis=2 → 沿 Z；t = 壁厚（t>=R 即实心）
  function ring(g, base, axis, a0, a1, c1, c2, R, t, mat, opt) {
    opt = opt || {};
    var N = opt.N || 8, made = [];
    for (var i = 0; i < N; i++) {
      var ad = (i + 0.5) * (360 / N);
      if (opt.skip && opt.skip.some(function (s) { return Math.abs(((ad - s) % 360 + 540) % 360 - 180) < 2; })) continue;
      var w = 2 * R * Math.sin(Math.PI / N) * 1.12;
      var rr = R - t / 2;
      var from, to;
      if (axis === 2) {
        from = [c1 + Math.cos(ad * Math.PI / 180) * rr - t / 2, c2 + Math.sin(ad * Math.PI / 180) * rr - w / 2, a0];
        to   = [c1 + Math.cos(ad * Math.PI / 180) * rr + t / 2, c2 + Math.sin(ad * Math.PI / 180) * rr + w / 2, a1];
      } else if (axis === 0) {
        from = [a0, c1 + Math.cos(ad * Math.PI / 180) * rr - t / 2, c2 + Math.sin(ad * Math.PI / 180) * rr - w / 2];
        to   = [a1, c1 + Math.cos(ad * Math.PI / 180) * rr + t / 2, c2 + Math.sin(ad * Math.PI / 180) * rr + w / 2];
      } else {
        from = [c1 + Math.cos(ad * Math.PI / 180) * rr - w / 2, a0, c2 + Math.sin(ad * Math.PI / 180) * rr - t / 2];
        to   = [c1 + Math.cos(ad * Math.PI / 180) * rr + w / 2, a1, c2 + Math.sin(ad * Math.PI / 180) * rr + t / 2];
      }
      var rot = axis === 2 ? [0, 0, ad] : (axis === 0 ? [ad, 0, 0] : [0, ad, 0]);
      made.push(addCube(g, base + '_' + i, from, to, mat, {
        rotation: rot,
        faces: opt.faces || null
      }));
    }
    return made;
  }

  // ============================================================ 4. 骨骼树
  var G = {};
  G.root = ROOT;
  G.move = mkGroup('move', [0, BORE, REC_MID.z], G.root);
  G.body = mkGroup('body', [0, BORE, REC_MID.z], G.move);
  G.constraint = mkGroup('constraint', [0, BORE, REC_MID.z], G.body);
  G.camera = mkGroup('camera', [0, BORE, REC_MID.z], G.body);
  G.barrel = mkGroup('barrel', [0, BORE, ZREC_F], G.body);
  G.receiver = mkGroup('receiver', [0, BORE, REC_MID.z], G.body);
  G.bolt = mkGroup('bolt', [0, BORE, Z(820)], G.body);
  G.rear_sight = mkGroup('rear_sight', [0, Y(28), Z(600)], G.body);
  G.magazine = mkGroup('magazine', [0, Y(-36), Z(900)], G.body);
  G.floorplate = mkGroup('floorplate', [0, Y(-59), Z(800)], G.magazine);
  G.follower = mkGroup('follower', [0, Y(-52), Z(850)], G.magazine);
  G.trigger = mkGroup('trigger', [0, Y(-40), Z(942)], G.body);
  G.stock = mkGroup('stock', [0, Y(-30), Z(940)], G.body);
  G.casing = mkGroup('casing', [0.90, 2.10, -1.95], G.body);
  G.round_in = mkGroup('round_in', [0, Y(48), Z(690)], G.body);
  G.additional_magazine = mkGroup('additional_magazine', [0, Y(-36), Z(850)], G.body);
  for (var ri = 1; ri <= 5; ri++) {
    G['mag_r' + ri] = mkGroup('mag_r' + ri, [0, 0, 0], G.magazine);
  }
  step('骨骼：' + (Project.groups.length) + ' 根');

  // 弹仓 5 发交错堆（真机 ≤5；Y 从上往下，X 左右交错）
  var ROUND_STACK = [
    { x: -0.07, mm: -16 },
    { x:  0.07, mm: -16 },
    { x: -0.07, mm: -30 },
    { x:  0.07, mm: -30 },
    { x: -0.07, mm: -44 }
  ];

  // ============================================================ 5. 枪管组（barrel）
  // 裸露枪管 mm 0..665，锥度 R 0.145→0.185（真机 Ø15→Ø22）；壁厚 0.06，中空，枪口有暗膛
  var BBSEG = [[0, 180, 0.145], [180, 380, 0.155], [380, 540, 0.165], [540, 665, 0.185]];
  BBSEG.forEach(function (sg, i) {
    ring(G.barrel, 'bbl_' + i, 2, Z(sg[0]), Z(sg[1]), 0, BORE, sg[2], 0.06, 'BLUE',
      { faces: { west: 'BLUE_D' } });
  });
  // 枪口暗膛（孔芯）+ 枪口圈
  ring(G.barrel, 'bbl_bore', 2, Z(0), Z(7), 0, BORE, 0.100, 0.10, 'DARK', { faces: { north: 'DARK' } });
  ring(G.barrel, 'bbl_collar', 2, Z(6), Z(19), 0, BORE, 0.168, 0.045, 'STEEL', {});
  // 通条（枪管下方，真机 mm 60..610，Ø8mm）
  addCube(G.barrel, 'rod_main', [-0.075, Y(-33), Z(60)], [0.075, Y(-18), Z(610)], 'STEEL_D');
  // 前准星座 + 护罩 + 刃（刃顶 Y(50) = 视线前端）
  addCube(G.barrel, 'fs_base', [-0.16, Y(6), Z(12)], [0.16, Y(20), Z(78)], 'BLUE');
  addCube(G.barrel, 'fs_ear_l', [-0.155, Y(20), Z(30)], [-0.100, Y(46), Z(62)], 'BLUE_D');
  addCube(G.barrel, 'fs_ear_r', [0.100, Y(20), Z(30)], [0.155, Y(46), Z(62)], 'BLUE_D');
  addCube(G.barrel, 'fs_blade', [-0.035, Y(20), Z(36)], [0.035, Y(50), Z(54)], 'STEEL');
  addCube(G.barrel, 'fs_lug', [-0.06, Y(-24), Z(22)], [0.06, Y(-12), Z(46)], 'BLUE');
  // 枪管箍（方口，绕护木/上护木）
  function collar(g, nm, mmA, mmB, hw, yT, yB, mat) {
    addCube(g, nm + '_top', [-hw, Y(yT - 9), Z(mmA)], [hw, Y(yT), Z(mmB)], mat);
    addCube(g, nm + '_bot', [-hw, Y(yB), Z(mmA)], [hw, Y(yB + 9), Z(mmB)], mat);
    addCube(g, nm + '_l', [-hw, Y(yB), Z(mmA)], [-hw + 8 / MMOS, Y(yT), Z(mmB)], mat);
    addCube(g, nm + '_r', [hw - 8 / MMOS, Y(yB), Z(mmA)], [hw, Y(yT), Z(mmB)], mat);
  }
  collar(G.barrel, 'band_f', 250, 282, 0.335, 18, -56, 'STEEL');
  collar(G.barrel, 'band_r', 470, 502, 0.345, 6, -64, 'STEEL');
  addCube(G.barrel, 'band_f_loop', [-0.40, Y(-16), Z(258)], [-0.325, Y(0), Z(274)], 'BLUE_D');   // 背带环
  addCube(G.barrel, 'band_r_spring', [-0.05, Y(-66), Z(504)], [0.05, Y(-58), Z(566)], 'STEEL_D'); // 箍簧

  // 上护木（木壳罩住枪管上半，mm 258..662）
  (function () {
    var N = 5, R = 0.25, t = 0.11, a0 = Z(258), a1 = Z(662);
    for (var i = 0; i < N; i++) {
      var ad = 20 + i * (140 / (N - 1));             // 20°..160°，只做上半圈
      var w = 2 * R * Math.sin(Math.PI / 8) * 1.15;
      var rr = R - t / 2;
      addCube(G.stock, 'hg_' + i,
        [0 + Math.cos(ad * Math.PI / 180) * rr - t / 2, BORE + Math.sin(ad * Math.PI / 180) * rr - w / 2, a0],
        [0 + Math.cos(ad * Math.PI / 180) * rr + t / 2, BORE + Math.sin(ad * Math.PI / 180) * rr + w / 2, a1],
        'WOOD', { rotation: [0, 0, ad] });
    }
  })();

  // ============================================================ 6. 机匣组（receiver）
  // 圆形机匣 Ø27mm → 八角 Ø0.50，壁厚 0.07；右侧 mm 706..796 开抛壳窗（跳过 +X 两片）
  ring(G.receiver, 'rec_f', 2, ZREC_F, Z(706), 0, BORE, 0.25, 0.07, 'BLUE', { faces: { west: 'BLUE_D' } });
  ring(G.receiver, 'rec_win', 2, Z(706), Z(796), 0, BORE, 0.25, 0.07, 'BLUE',
    { skip: [22.5, 337.5], faces: { west: 'BLUE_D' } });
  ring(G.receiver, 'rec_r', 2, Z(796), ZREC_R, 0, BORE, 0.25, 0.07, 'BLUE', { faces: { west: 'BLUE_D' } });
  // 抛壳窗上下唇
  addCube(G.receiver, 'rec_win_lo', [0.10, Y(-8), Z(706)], [0.26, Y(4), Z(796)], 'BLUE_D');
  addCube(G.receiver, 'rec_win_hi', [0.10, Y(24), Z(706)], [0.26, Y(30), Z(796)], 'BLUE_D');
  // 装填桥（机匣前环顶面，漏夹/桥夹导槽）
  addCube(G.receiver, 'rec_bridge', [-0.24, Y(15), Z(676)], [0.24, Y(28), Z(722)], 'BLUE');
  addCube(G.receiver, 'rec_clip_slot', [-0.19, Y(26), Z(680)], [0.19, Y(30), Z(718)], 'SIGHT');
  // 机匣后端/闭锁台
  addCube(G.receiver, 'rec_tang', [-0.20, Y(-12), Z(905)], [0.20, Y(6), Z(934)], 'BLUE_D');

  // ============================================================ 7. 枪机组（bolt）
  // 枪机体：膛线轴上的实心八角，R 0.16（真机 Ø17mm），mm 690..870
  ring(G.bolt, 'bolt_body', 2, Z(690), Z(870), 0, BORE, 0.16, 0.16, 'STEEL', { faces: { west: 'STEEL_D' } });
  // 抽壳钩（右侧细条）
  addCube(G.bolt, 'bolt_ext', [0.10, Y(8), Z(690)], [0.20, Y(16), Z(860)], 'STEEL_D');
  // 直拉机柄：根座 + 横杆 + 尾球（mm 800..845，向 +X 伸出）
  addCube(G.bolt, 'bolt_hroot', [0.14, Y(-6), Z(800)], [0.30, Y(24), Z(845)], 'BLUE');
  addCube(G.bolt, 'bolt_hbar', [0.30, Y(0), Z(806)], [0.56, Y(18), Z(840)], 'STEEL', { faces: { up: 'STEEL', down: 'STEEL_D' } });
  addCube(G.bolt, 'bolt_hknob', [0.56, Y(-3), Z(803)], [0.68, Y(22), Z(843)], 'STEEL');
  // 尾端待击块（枪机后端露出机匣后 20mm）
  ring(G.bolt, 'bolt_cock', 2, Z(870), Z(950), 0, BORE, 0.20, 0.20, 'STEEL', { faces: { south: 'STEEL_D' } });

  // ============================================================ 8. 后照门（rear_sight）
  // 座：mm 596..676（跨在机匣前环上）　表尺片铰链在座前端（mm 600），向后展开（战斗缺口 +35mm）
  addCube(G.receiver, 'rs_base', [-0.17, Y(10), Z(596)], [0.17, Y(28), Z(676)], 'BLUE');
  addCube(G.rear_sight, 'rs_leaf', [-0.13, Y(28), Z(600)], [0.13, Y(34), Z(674)], 'BLUE_D');
  addCube(G.rear_sight, 'rs_scale', [-0.02, Y(32), Z(604)], [0.02, Y(35), Z(660)], 'SIGHT');
  addCube(G.rear_sight, 'rs_slider', [-0.15, Y(27), Z(612)], [0.15, Y(36), Z(630)], 'STEEL_D');
  addCube(G.rear_sight, 'rs_ear_l', [-0.075, Y(34), Z(660)], [-0.020, Y(48), Z(674)], 'BLUE');
  addCube(G.rear_sight, 'rs_ear_r', [0.020, Y(34), Z(660)], [0.075, Y(48), Z(674)], 'BLUE');
  addCube(G.rear_sight, 'rs_notch', [-0.020, Y(34), Z(660)], [0.020, Y(45), Z(674)], 'SIGHT');

  // ============================================================ 9. 弹仓组（magazine）
  addCube(G.magazine, 'mag_body', [-0.26, Y(-58), Z(800)], [0.26, Y(-12), Z(900)], 'BLUE_D');
  addCube(G.magazine, 'mag_lip', [-0.26, Y(-12), Z(806)], [0.26, Y(-6), Z(894)], 'BLUE');
  addCube(G.floorplate, 'fp_plate', [-0.24, Y(-62), Z(800)], [0.24, Y(-56), Z(900)], 'STEEL');
  addCube(G.floorplate, 'fp_screw', [-0.06, Y(-64), Z(806)], [0.06, Y(-56), Z(818)], 'STEEL_D');
  addCube(G.follower, 'fol_plate', [-0.22, Y(-54), Z(804)], [0.22, Y(-48), Z(896)], 'STEEL_D');
  ROUND_STACK.forEach(function (rs, i) {
    var g = G['mag_r' + (i + 1)];
    var y0 = Y(rs.mm - 9), y1 = Y(rs.mm + 9);
    // 弹壳（黄铜）在前，弹头（铜被甲）在后 = -Z 方向
    addCube(g, 'r' + (i + 1) + '_case', [rs.x - 0.11, y0, Z(832)], [rs.x + 0.11, y1, Z(884)], 'BRS');
    addCube(g, 'r' + (i + 1) + '_tip', [rs.x - 0.09, y0 + 0.02, Z(816)], [rs.x + 0.09, y1 - 0.02, Z(834)], 'CPR');
    g.origin = [rs.x, (y0 + y1) / 2, (Z(816) + Z(884)) / 2];
  });

  // ============================================================ 10. 扳机组（trigger）
  addCube(G.body, 'tg_front', [-0.07, Y(-78), Z(900)], [0.07, Y(-52), Z(914)], 'STEEL');
  addCube(G.body, 'tg_beam', [-0.09, Y(-88), Z(900)], [0.09, Y(-78), Z(1002)], 'STEEL');
  addCube(G.body, 'tg_rear', [-0.07, Y(-78), Z(988)], [0.07, Y(-52), Z(1002)], 'STEEL');
  addCube(G.body, 'tg_lug', [-0.10, Y(-86), Z(896)], [0.10, Y(-70), Z(906)], 'BLUE_D');
  addCube(G.trigger, 'trg_blade', [-0.055, Y(-86), Z(934)], [0.055, Y(-44), Z(950)], 'BLUE');
  addCube(G.trigger, 'trg_top', [-0.075, Y(-44), Z(936)], [0.075, Y(-30), Z(952)], 'BLUE_D');

  // ============================================================ 11. 枪托组（stock）
  // 文献剖面（mm 相对枪口, 半宽, 上缘, 下缘；上下缘为相对膛线轴的 mm）
  var STOCK_PROFILE = [
    [250, 0.30,   -4,  -54],
    [470, 0.31,   -4,  -62],
    [620, 0.32,   -5,  -70],
    [700, 0.32,   -6,  -74],
    [800, 0.31,   -8,  -76],
    [900, 0.29,  -16,  -80],
    [940, 0.28,  -24,  -82],
    [1000, 0.27, -28,  -84],
    [1060, 0.27, -30,  -88],
    [1080, 0.29, -30,  -98],
    [1150, 0.34, -28, -128],
    [1232, 0.42, -20, -150]
  ];
  function lerp(a, b, t) { return a + (b - a) * t; }
  for (var pi = 0; pi < STOCK_PROFILE.length - 1; pi++) {
    var pa = STOCK_PROFILE[pi], pb = STOCK_PROFILE[pi + 1];
    var n = Math.max(1, Math.round((pb[0] - pa[0]) / 62));
    for (var k = 0; k < n; k++) {
      var t0 = k / n, t1 = (k + 1) / n, tm = (t0 + t1) / 2;
      var mm0 = lerp(pa[0], pb[0], t0), mm1 = lerp(pa[0], pb[0], t1);
      var hw = lerp(pa[1], pb[1], tm), tp = lerp(pa[2], pb[2], tm), bt = lerp(pa[3], pb[3], tm);
      addCube(G.stock, 'stk_' + pi + '_' + k, [-hw, Y(bt), Z(mm0)], [hw, Y(tp), Z(mm1)], 'WOOD',
        { faces: { up: 'WOOD_L', west: 'WOOD_D' } });
    }
  }
  // 托底板（白钢）+ 附品仓盖 + 背带槽
  addCube(G.stock, 'butt_plate', [-0.43, Y(-150), Z(1224)], [0.43, Y(-19), Z(1232)], 'STEEL');
  addCube(G.stock, 'butt_trap', [-0.14, Y(-96), Z(1226)], [0.14, Y(-56), Z(1232)], 'STEEL_D');
  addCube(G.stock, 'butt_trap_scr', [-0.035, Y(-58), Z(1228)], [0.035, Y(-50), Z(1232)], 'SIGHT');
  addCube(G.stock, 'butt_slot', [-0.29, Y(-74), Z(1064)], [0.29, Y(-58), Z(1104)], 'SIGHT');
  addCube(G.stock, 'stk_rc', [-0.20, Y(-86), Z(946)], [0.20, Y(-30), Z(952)], 'BLUE_D');   // 托颈后接座

  // ============================================================ 12. 弹壳 / 装填弹
  addCube(G.casing, 'cas_body', [0.82, 2.00, -2.45], [0.98, 2.20, -1.61], 'BRS');
  addCube(G.casing, 'cas_tip', [0.845, 2.03, -1.63], [0.955, 2.17, -1.45], 'CPR');
  addCube(G.round_in, 'rin_case', [-0.11, Y(39), Z(672)], [0.11, Y(57), Z(724)], 'BRS');
  addCube(G.round_in, 'rin_tip', [-0.09, Y(41), Z(656)], [0.09, Y(55), Z(674)], 'CPR');

  step('几何：' + RAW.length + ' 个方块');

  // ============================================================ 13. 贴图（512²）与逐面 UV 打包
  var TEX = new Texture({ name: 'mosin_nagant.png', width: TEXW, height: TEXW, internal: true });
  TEX.add(false);
  try { if (TEX.canvas.width !== TEXW) { TEX.canvas.width = TEXW; TEX.canvas.height = TEXW; } } catch (e) {}
  report.canvas = TEX.canvas.width + 'x' + TEX.canvas.height;
  var ctx = TEX.canvas.getContext('2d');
  ctx.clearRect(0, 0, TEXW, TEXW);
  ctx.imageSmoothingEnabled = false;

  // 13.1/13.2 逐面矩形（尺寸 = 世界尺寸 x 密度，单面上限 UVCAP）+ 货架装箱
  //          放不下就降一档密度重试（美术规范 二·装箱：不许把面画小来塞图集）
  var UVCAP = 120;
  function buildItems(dens) {
    var list = [];
    RAW.forEach(function (rec, ci) {
      var c = rec.cube;
      var d = [c.to[0] - c.from[0], c.to[1] - c.from[1], c.to[2] - c.from[2]];
      FACES.forEach(function (f) {
        var w, h;
        if (f === 'north' || f === 'south') { w = d[0]; h = d[1]; }
        else if (f === 'east' || f === 'west') { w = d[2]; h = d[1]; }
        else { w = d[0]; h = d[2]; }
        var pw = Math.min(UVCAP, Math.max(1, Math.round(Math.abs(w) * dens)));
        var ph = Math.min(UVCAP, Math.max(1, Math.round(Math.abs(h) * dens)));
        var mat = (rec.faces && rec.faces[f]) ? rec.faces[f] : rec.mat;
        list.push({ ci: ci, f: f, w: pw, h: ph, mat: mat });
      });
    });
    return list;
  }
  function pack(list) {
    list.sort(function (a, b) { return (b.h - a.h) || (b.w - a.w); });
    var PAD = 1, shelfY = PAD, shelfH = 0, curX = PAD, used = 0, over = false;
    list.forEach(function (it) {
      if (curX + it.w + PAD > TEXW) { shelfY += shelfH + PAD; shelfH = 0; curX = PAD; }
      it.u0 = curX; it.v0 = shelfY; it.u1 = curX + it.w; it.v1 = shelfY + it.h;
      curX += it.w + PAD;
      if (it.h > shelfH) shelfH = it.h;
      if (it.v1 > used) used = it.v1;
      if (it.v1 + PAD > TEXW) over = true;
    });
    return { used: used, over: over };
  }
  var items = null, used = 0, dens = S;
  for (var dtry = S; dtry >= 8; dtry--) {
    var cand = buildItems(dtry);
    var pk = pack(cand);
    if (!pk.over) { items = cand; used = pk.used; dens = dtry; break; }
    warn('density ' + dtry + ' 图集放不下（用掉 ' + pk.used + ' px），降一档重试');
  }
  if (!items) { fail('降到 8 px/单位仍放不下，需拆分长件'); items = buildItems(8); used = pack(items).used; }
  S = dens;
  step('UV 打包：' + items.length + ' 面 @ density ' + dens + '，使用高度 ' + used + 'px');

  // 13.3 画（确定性噪声，不用 Math.random，保证可复现）
  function hash2(x, y, s) {
    var n = (x * 374761393 + y * 668265263 + s * 1442695040888963407) | 0;
    n = (n ^ (n >> 13)) * 1274126177;
    return ((n ^ (n >> 16)) >>> 0) / 4294967295;
  }
  function paintRect(it) {
    var base = MAT[it.mat] || MAT.BLUE, k = SHADE[it.f] || 1;
    var isWood = it.mat.indexOf('WOOD') === 0;
    var isMetal = !isWood && it.mat.indexOf('BRS') !== 0 && it.mat.indexOf('CPR') !== 0;
    for (var y = it.v0; y < it.v1; y++) {
      for (var x = it.u0; x < it.u1; x++) {
        var r = base[0], g = base[1], b = base[2], m = 1;
        if (isWood) {
          var g1 = hash2(x, y, 7);
          if ((x + y * 5) % 13 === 0) m *= 0.88;              // 纵向木纹
          if (g1 < 0.10) m *= 0.80;
          if ((y * 3 + x) % 31 === 0) m *= 0.86;
        } else if (isMetal) {
          var n1 = hash2(x, y, 3);
          m *= 0.95 + n1 * 0.10;                              // 磨光
          if ((x + y) % 17 === 0) m *= 0.94;
        } else {
          m *= 0.97 + hash2(x, y, 5) * 0.06;
        }
        m *= k;
        var w = it.u1 - it.u0, hh = it.v1 - it.v0;
        if (w > 3 && hh > 3 && (x === it.u0 || x === it.u1 - 1 || y === it.v0 || y === it.v1 - 1)) m *= 0.90;
        ctx.fillStyle = 'rgb(' + Math.max(0, Math.min(255, r * m | 0)) + ',' +
                                  Math.max(0, Math.min(255, g * m | 0)) + ',' +
                                  Math.max(0, Math.min(255, b * m | 0)) + ')';
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }
  items.forEach(paintRect);
  try { if (typeof TEX.updateChangesAfterEdit === 'function') TEX.updateChangesAfterEdit(); } catch (e) {}
  try { if (typeof TEX.update === 'function') TEX.update(); } catch (e) {}

  // 13.4 写回 cube.uv（6 面 x 4 角，BB 面序 north/east/south/west/up/down）
  var byCube = {};
  items.forEach(function (it) { (byCube[it.ci] = byCube[it.ci] || {})[it.f] = it; });
  RAW.forEach(function (rec, ci) {
    var c = rec.cube, flat = [];
    FACES.forEach(function (f) {
      var it = byCube[ci][f];
      flat.push(it.u0, it.v0, it.u1, it.v1);
      try {
        if (c.faces && c.faces[f]) {
          c.faces[f].texture = TEX.uuid;      // 陷阱：贴图字段要 UUID，给 0 会退回彩虹占位图
          if ('uv' in c.faces[f]) { c.faces[f].uv = [it.u0, it.v0]; c.faces[f].uv_size = [it.u1 - it.u0, it.v1 - it.v0]; }
        }
      } catch (e) { /* 老版本 Face 没有 uv 字段，靠 cube.uv */ }
    });
    c.uv = flat;
    c.box_uv = false;
    c.autouv = 0;
  });

  // 13.5 写盘（art/ 与 resources/ 同一份字节）
  try { globalThis.__mosin_png = TEX.canvas.toDataURL('image/png', 1); } catch (e) { fail('取 PNG 失败：' + e.message); }
  var pngPath = ART + 'mosin_nagant.png';
  var resPng = RES + 'textures/item/mosin_nagant.png';
  var written = [];
  try {
    if (fs) {
      var url = TEX.canvas.toDataURL('image/png', 1);
      var buf = Buffer.from(url.split(',')[1], 'base64');
      [ART, ART + 'ref/', RES + 'geo/', RES + 'animations/', RES + 'textures/item/', RES + 'models/item/']
        .forEach(function (p) { try { fs.mkdirSync(p, { recursive: true }); } catch (e) {} });
      fs.writeFileSync(pngPath, buf);
      fs.writeFileSync(resPng, buf);
      written.push(pngPath, resPng);
      report.png_bytes = buf.length;
    } else { step('PNG 交给外层包装器写盘（间接 eval 作用域没有 require）'); }
  } catch (e) { fail('写 PNG 失败：' + e.message); }
  step('贴图落盘：' + written.join(' , '));

  // ============================================================ 14. 自检
  function cBounds(list) {
    var b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    list.forEach(function (c) {
      var v = [];
      try { v = c.getGlobalVertexPositions ? c.getGlobalVertexPositions() : []; } catch (e) { v = []; }
      if (!v || !v.length) v = [[c.from[0], c.from[1], c.from[2]], [c.to[0], c.to[1], c.to[2]]];
      v.forEach(function (p) { for (var k = 0; k < 3; k++) { if (p[k] < b[k]) b[k] = p[k]; if (p[k] > b[k + 3]) b[k + 3] = p[k]; } });
    });
    return b;
  }
  function dist2Box(pt, b) {
    if (!isFinite(b[0])) return null;
    var d = 0;
    for (var k = 0; k < 3; k++) {
      var lo = b[k], hi = b[k + 3], v = pt[k];
      var e = (v < lo) ? (lo - v) : ((v > hi) ? (v - hi) : 0);
      d += e * e;
    }
    return Math.sqrt(d);
  }
  var info = {};
  info.groups = {};
  Project.groups.forEach(function (g) {
    var cubes = g.children.filter(function (c) { return c instanceof Cube; });
    var b = cBounds(cubes);
    var d = dist2Box(g.origin, b);
    info.groups[g.name] = { cubes: cubes.length, pivot: g.origin.map(function (v) { return +v.toFixed(3); }),
                            dist: d === null ? null : +d.toFixed(3),
                            bbox: isFinite(b[0]) ? b.map(function (v) { return +v.toFixed(2); }) : null };
    if (Math.abs(g.rotation[0]) + Math.abs(g.rotation[1]) + Math.abs(g.rotation[2]) > 1e-6) {
      fail('骨骼 ' + g.name + ' 带旋转 ' + JSON.stringify(g.rotation));
    }
    if (d !== null && d > 4.0) fail('骨骼 ' + g.name + ' pivot 离自身几何 ' + d.toFixed(2) + 'u > 4u');
  });
  var ALL = allCubes();
  var all = cBounds(ALL);
  info.bbox = all.map(function (v) { return +v.toFixed(2); });
  info.length_u = +(all[5] - all[2]).toFixed(2);
  info.length_blocks = +((all[5] - all[2]) / 16).toFixed(3);
  info.height_u = +(all[4] - all[1]).toFixed(2);
  info.width_u = +(all[3] - all[0]).toFixed(2);
  info.cubes = ALL.length;
  info.groups_n = Project.groups.length;

  // 枪口锚点
  var muz = cBounds(ALL.filter(function (c) { return /^bbl_/.test(c.name); }));
  info.muzzle = { y: +((muz[1] + muz[4]) / 2).toFixed(2), z: +muz[2].toFixed(2) };
  if (Math.abs(muz[2] - ZM) > 0.02) fail('枪口 Z 应为 ' + ZM + '，实测 ' + muz[2].toFixed(3));
  // 前准星刃顶 = 瞄准线前端
  var fb = cBounds(ALL.filter(function (c) { return c.name === 'fs_blade'; }));
  info.front_sight_top = +fb[4].toFixed(2);
  if (Math.abs(fb[4] - Y(50)) > 0.02) fail('前准星刃顶 ' + fb[4].toFixed(2) + ' ≠ ' + Y(50).toFixed(2));
  // 后照门战斗缺口（+34mm 缺底面 = 瞄准线后端）
  var rsb = cBounds(ALL.filter(function (c) { return /^rs_ear_/.test(c.name); }));
  info.rear_notch_floor = +rsb[1].toFixed(3);
  info.sight_line_rear = +Y(34).toFixed(3);
  if (Math.abs(rsb[1] - Y(34)) > 0.02) fail('后照门缺口底面 ' + rsb[1].toFixed(3) + ' ≠ ' + Y(34).toFixed(3) + '（战斗表尺 +34mm）');
  // 抛壳锚点
  var cb = cBounds(G.casing.children.filter(function (c) { return c instanceof Cube; }));
  info.casing_center = [+((cb[0] + cb[3]) / 2).toFixed(2), +((cb[1] + cb[4]) / 2).toFixed(2), +((cb[2] + cb[5]) / 2).toFixed(2)];
  if (Math.abs(info.casing_center[0] - 0.90) > 0.03 || Math.abs(info.casing_center[1] - 2.10) > 0.03 ||
      Math.abs(info.casing_center[2] + 1.95) > 0.04) {
    fail('弹壳静止位 ' + JSON.stringify(info.casing_center) + ' ≠ 锚点 {0.90, 2.10, -1.95}');
  }
  if (cb[0] <= 0.25) fail('抛壳几何必须在 +X 抛壳区，实测最小 X=' + cb[0].toFixed(2));
  // 弹仓 5 发
  var rs2 = [];
  for (var q = 1; q <= 5; q++) {
    var rb = cBounds(G['mag_r' + q].children.filter(function (c) { return c instanceof Cube; }));
    rs2.push([+((rb[1] + rb[4]) / 2).toFixed(2), +rb[0].toFixed(2)]);
    if (!(rb[1] > Y(-58) - 0.01 && rb[4] < Y(-6) + 0.01)) fail('第 ' + q + ' 发在弹仓外：Y ' + rb[1].toFixed(2) + '..' + rb[4].toFixed(2));
  }
  info.rounds_y = rs2;
  // 最低点 = 托底板下缘（真机 -150mm）
  info.lowest = +all[1].toFixed(2);
  if (all[1] < Y(-150) - 0.01) fail('有几何低于托底 ' + Y(-150).toFixed(2) + '，实测 ' + all[1].toFixed(2));
  // 机匣段不许挂空（Z <= -0.30 的零件最低不许低于护圈底 Y(-88)）
  ALL.forEach(function (c) {
    if (c.from && c.from[2] <= -0.30 && c.from[1] < Y(-88) - 0.01) fail('机匣段挂空：' + c.name + ' 最低 Y=' + c.from[1].toFixed(2));
  });
  // 预算
  if (info.cubes > 600) fail('方块 ' + info.cubes + ' 超预算 600');
  if (info.groups_n > 40) fail('骨骼 ' + info.groups_n + ' 超预算 40');
  // 贴图尺寸
  if (TEX.canvas.width !== 512 || TEX.canvas.height !== 512) fail('画布不是 512²');

  info.ok = report.fails.length === 0;
  report.info = info;
  step('自检：' + (info.ok ? '通过' : report.fails.length + ' 条不通过'));

  Undo.finishEdit('mosin_nagant 生成');
  try { Canvas.updateAll(); } catch (e) {}

  try { globalThis.__mosin_report = report; } catch (e) {}
  if (fs) { try { fs.writeFileSync(ART + '_gen_report.json', JSON.stringify(report, null, 2)); } catch (e) {} }

  return {
    ok: info.ok,
    steps: report.steps,
    warns: report.warns,
    fails: report.fails,
    cubes: info.cubes,
    groups: info.groups_n,
    faces: items.length,
    tex_height_used: used,
    length_u: info.length_u,
    length_blocks: info.length_blocks,
    bbox: info.bbox,
    muzzle: info.muzzle,
    front_sight_top: info.front_sight_top,
    rear_notch_floor: info.rear_notch_floor,
    casing_center: info.casing_center,
    lowest: info.lowest,
    pivots: Object.keys(info.groups).reduce(function (o, k) { o[k] = info.groups[k].pivot; return o; }, {})
  };
})()