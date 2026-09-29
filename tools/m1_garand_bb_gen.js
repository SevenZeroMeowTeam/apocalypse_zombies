/* HexaLunar Calamity - M1 Garand (M1 加兰德) Blockbench generator  — v3, 实测 1:1
 * Run inside Blockbench via the MCP `risky_eval` tool:
 *   (function(){var fs=require('fs');return (0,eval)(fs.readFileSync('F:/mcmod/tools/m1_garand_bb_gen.js','utf8'));})()
 *
 * 铁律: 16u = 1 block | 枪口 = -Z | 上 = +Y | 射手右侧 = +X | 原点 = 机匣中心
 * 圆形件一律 ring() 图元（= boxlib `ring`）。
 *
 * ── v3 依据（不是估的，是从 art/m1garand/ref_m1_side.png 逐列量出来的）────────────
 * 参考图为维基共享的 M1 官方侧视图（无背景，2380×1100），下半张枪口朝左。
 * 定标：剪影全长 2281px = 1100mm → 0.4822 mm/px；膛线轴 = 枪口端剪影中心。
 * 逐列取「最上面材质的切换点」，得到各部件沿枪身的真实落点（mm 自枪口）：
 *
 *   0        枪口
 *   0–156    导气筒（含前准星、刺刀座、叠枪环）
 *   156      木质前端（= 前护木前缘）
 *   326–338  下枪箍
 *   338–519  后护木
 *   519–799  机匣（519 是机匣环前切面，与「枪管 610mm 从弹底算」自洽）
 *   799–827  机匣后端 / 托颈起点
 *   827–1075 托颈 + 托身
 *   1075–1100 托底板
 *
 * 竖直（mm 相对膛线轴，取各列剪影上下缘）：
 *   前准星刃顶 +31.3 | 后照门孔心 +32.3  → 瞄准线 = +31.5mm（两者自洽，可互校）
 *   机匣顶 +16 / 机匣底 −30 / 扳机座底 −55 / 护圈底 −91
 *   护木顶 +17…+19 / 护木底 −41(156mm) → −64.7(500) → −70.9(575) → −80(700)
 *   托颈顶 −19…−31 / 托颈底 −82…−100 / 托底顶 −36 / 托底底 −176.5
 *   整枪高度 141mm = 2.26u
 *
 * 与 v2 的差异（v2 的三处结构性失真）：
 *   1) v2 机匣在 706–919mm（真机 519–799）→ 枪管长了 19cm、机匣与托颈短了 19cm
 *   2) v2 瞄准线 3.10 = 高于膛线轴 50mm（真机 31.5mm）
 *   3) v2 高/宽 = 3.76u/1.72u（真机 2.26u/0.72u）→ 1.7×/2.4× 过粗壮
 *
 * 锚点（改模型必须同步 美术规范.md 一·关键轴线 与 Java 的 WeaponMount.*）:
 *   瞄准线 SIGHT_Y = 2.80 | 枪口 {0, 2.30, -13.60} | 抛壳点 {0.30, 2.62, -4.05} | 密度 12
 * 真机尺寸: 全长 1100mm = 17.60u（枪口 Z=-13.60，托底 Z=+4.00）
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

  /* texture: create if the fresh project has none */
  if (!Project.textures.length) {
    try {
      new Texture({ name: 'm1_garand', uv_width: 512, uv_height: 512, particle: false }).add();
      out.steps.push('created texture m1_garand');
    } catch (e) { out.warnings.push('mktex:' + e.message); }
  }
  if (!Project.textures.length) return { error: 'no texture in project' };
  var TEX = Project.textures[0];
  TEX.name = 'm1_garand';
  /* 画布必须真的是 512×512：Texture 构造默认只给 16×16 */
  try { if (TEX.resize) TEX.resize(512, 512); } catch (e) { out.warnings.push('resize:' + e.message); }
  try {
    if (TEX.canvas.width !== 512 || TEX.canvas.height !== 512) {
      TEX.canvas.width = 512; TEX.canvas.height = 512;
      TEX.ctx = TEX.canvas.getContext('2d');
    }
  } catch (e2) { out.warnings.push('canvassize:' + e2.message); }
  TEX.uv_width = 512;
  TEX.uv_height = 512;
  Project.texture_width = 512;
  Project.texture_height = 512;
  out.steps.push('texture canvas ' + TEX.canvas.width + 'x' + TEX.canvas.height);
  Project.box_uv = false;
  Project.name = 'm1_garand';
  try { Project.geometry_name = 'm1_garand'; } catch (e) {}

  /* ---------- 1. palette (美术规范.md 三·1 规范色板, 容差 ±12) ---------- */
  var MAT = {
    park:  [74, 76, 80],    // 磷化钢 —— 机匣 / 枪管 / 导气杆 / 漏夹 / 导气筒
    parkd: [56, 58, 62],    // 磷化钢暗部 —— 枪箍 / 护圈 / 托底 / 表尺座
    blue:  [66, 70, 78],    // 发蓝钢 —— 枪管 / 弹仓
    blued: [46, 50, 58],    // 发蓝钢暗部
    steel: [148, 150, 157], // 抛光钢 —— 枪机体 / 拉机柄 / 扳机 / 托底钢板
    wood:  [132, 84, 44],   // 胡桃木托
    woodd: [104, 64, 32],   // 木纹暗条
    dark:  [14, 14, 16],    // 膛孔 / 深腔
    blk:   [30, 30, 32],    // 准星 / 照门
    brs:   [206, 162, 82],  // 黄铜弹壳
    cpr:   [196, 126, 72]   // 铜被甲弹头
  };
  var SHADE = { up: 1.14, down: 0.60, north: 1.00, south: 0.86, east: 0.94, west: 0.80 };

  /* ---------- 2. 坐标系常量（全部来自上面的实测表）---------- */
  var MM = 62.5;                                  // 1u = 62.5mm
  var BORE = 2.30;                                // 枪管/膛线轴 Y（= 枪口 Y）
  var SIGHT = 2.80;                               // 瞄准线 = BORE + 31.5mm
  function Z(mm) { return -13.60 + mm / MM; }     // 自枪口起算的 Z
  function Y(mm) { return BORE + mm / MM; }       // 相对膛线轴的 Y
  var ZL = {
    muzzle: 0, sight: 50, gasR: 156, bandF: 326, bandR: 338,
    recF: 519, recR: 799, wrist: 827, butt: 1075, end: 1100
  };
  var zM = Z(ZL.muzzle), zGasR = Z(ZL.gasR), zBandF = Z(ZL.bandF), zBandR = Z(ZL.bandR),
      zRecF = Z(ZL.recF), zRecR = Z(ZL.recR), zWrist = Z(ZL.wrist), zButt = Z(ZL.butt), zEnd = Z(ZL.end);

  /* ---------- 3. bone tree (美术规范.md 五·1 命名 / 六·1 pivot) ---------- */
  var REC_MID = { x: 0, y: (Y(16) + Y(-30)) / 2, z: (zRecF + zRecR) / 2 };   // 机匣中心 = 原点
  var G = {};
  function grp(name, origin, parent) {
    var g = new Group({ name: name, origin: origin }).init();
    if (parent) g.addTo(parent);
    G[name] = g;
    return g;
  }
  var gRoot  = grp('root',  [0, 1.90, REC_MID.z], null);        // 控制器骨
  var gMove  = grp('move',  [0, 1.90, REC_MID.z], gRoot);       // 姿态 / 后坐 / 举枪
  var gBody  = grp('body',  [REC_MID.x, REC_MID.y, REC_MID.z], gMove);   // 机匣中心
  grp('constraint', [0, 0, 0], gMove);
  grp('camera', [0, 0, 0], gMove);
  grp('additional_magazine', [0, 1.60, zRecR], gMove);          // TaCZ 规则：必须存在且导出为空
  grp('barrel',  [0, BORE, zRecF], gBody);                      // pivot = 枪管后端（机匣环切面）
  grp('bolt',    [0.26, Y(12), -2.60], gBody);                  // pivot = 导气杆手柄销轴
  grp('cover',   [0, Y(16), zRecR], gBody);                     // 漏夹井盖：pivot = 机匣后端上缘，动作纯平移
  grp('clip_in', [0, Y(-6), Z(643)], gBody);                     // 漏夹：pivot = 自身中心（601–700mm 井内），装填动作是纯平移（见 anim）
  grp('casing',  [0.30, Y(20), X_EJ()], gBody);                 // 抛壳：pivot = 弹壳中心，几何在 +X 抛壳窗内
  grp('magazine',[0, Y(-56), Z(680)], gBody);                   // 弹仓：真机无 detachable mag，导出为空
  grp('trigger', [0, Y(-52), Z(806)], gBody);                   // 扳机：pivot = 扳机轴销
  grp('stock',   [0, Y(-27), zWrist], gMove);                   // 托颈 / 托底（pivot = 与机匣接合处）
  function X_EJ() { return -13.60 + 748 / MM; }                 // 抛壳点 Z = 抛壳窗中心（700–795mm）

  /* ---------- 4. primitive builders ---------- */
  var RAW = [];
  function box(g, n, x0, y0, z0, x1, y1, z1, mat, rot, org) {
    RAW.push({ g: g, n: n, f: [x0, y0, z0], t: [x1, y1, z1], mat: mat, r: rot || [0, 0, 0],
               o: org || [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2] });
  }
  /* ring of N rotated slabs = faceted cylinder (boxlib `ring`).
     axis 2 = 沿 Z（枪管/导气筒/弹壳）, 1 = 沿 Y, 0 = 沿 X */
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
  /* collar: 矩形钢箍（真机下枪箍是绕护木的扁钢带，不是圆环）*/
  function collar(g, n, z0, z1, yb, yt, hw, t, mat) {
    box(g, n + '_top', -hw, yt - t, z0, hw, yt, z1, mat);
    box(g, n + '_bot', -hw, yb, z0, hw, yb + t, z1, mat);
    box(g, n + '_l', -hw, yb, z0, -hw + t, yt, z1, mat);
    box(g, n + '_r', hw - t, yb, z0, hw, yt, z1, mat);
  }
  /* taper: 沿 Z 的锥形段。pts = [[z, topY, botY, halfW], ...]，相邻两点之间细分 sub 段，
     每段一个小台阶（真实木托是连续锥面，台阶大到 0.4u 就会读成「梯田」）。*/
  function taper(g, n, pts, mat, sub) {
    sub = sub || 6;
    for (var i = 0; i < pts.length - 1; i++) {
      var a = pts[i], b = pts[i + 1];
      for (var k = 0; k < sub; k++) {
        var t0 = k / sub, t1 = (k + 1) / sub;
        var z0 = a[0] + (b[0] - a[0]) * t0, z1 = a[0] + (b[0] - a[0]) * t1;
        var top = a[1] + (b[1] - a[1]) * t0, bot = a[2] + (b[2] - a[2]) * t0;
        var hw = a[3] + (b[3] - a[3]) * t0;
        box(g, n + '_' + i + '_' + k, -hw, bot, z0, hw, top, z1, mat);
      }
    }
  }

  /* ---------- 5. geometry ---------- */
  /* --- 5.1 barrel + gas cylinder + front sight（bone: barrel）---
   * 枪管 15.4mm 口部 / 22mm 弹膛：真机枪管几乎全被护木与导气筒包住，
   * 外面只剩枪口冠面。这里就按真机做，导气筒后面的枪管全部藏进护木。 */
  var BR_M = 0.155;     // 枪管外半径 19mm
  var BR_F = 0.125;     // 枪口段 15.6mm
  ring('barrel', 'bbl_knox',   2, Z(0) + 0.0, 0, 0, BORE, BR_M, 0.11, 10, 'blue');
  ring('barrel', 'bbl_knox2',  2, Z(519) - 0.55, Z(519) - 0.10, 0, BORE, 0.215, 0.13, 10, 'blue');
  ring('barrel', 'bbl_main',   2, zGasR, Z(519) - 0.58, 0, BORE, BR_M, 0.11, 10, 'blue');
  ring('barrel', 'bbl_front',  2, Z(6), zGasR, 0, BORE, BR_F, 0.09, 10, 'blue');
  ring('barrel', 'bbl_crown',  2, zM, Z(6), 0, BORE, BR_F + 0.012, 0.09, 10, 'blued');   // 冠面 = 枪口
  ring('barrel', 'bbl_bore',   2, zM + 0.02, zM + 0.05, 0, BORE, 0.065, 0.065, 8, 'dark');

  /* 导气筒：真机是套在枪管下方的圆柱，从枪口一直到 156mm，前端带叠枪环、下面挂前背带环。
     筒轴比膛线轴低 4mm（真机导气孔在下方）。 */
  var CYL = BORE - 0.064;
  ring('barrel', 'gas_cyl',    2, zM, zGasR, 0, CYL, 0.24, 0.15, 10, 'park');
  ring('barrel', 'gas_front',  2, zM, Z(8), 0, CYL, 0.255, 0.11, 10, 'parkd');
  ring('barrel', 'gas_lock',   2, Z(143), zGasR, 0, CYL, 0.27, 0.12, 10, 'parkd');
  box('barrel', 'gas_plug',   -0.15, CYL - 0.19, Z(35),  0.15, CYL - 0.10, Z(78), 'parkd');
  box('barrel', 'bayonet_lug',-0.075, Y(-34), Z(10),  0.075, Y(-22), Z(52), 'parkd');  // 刺刀座
  box('barrel', 'stack_swiv', -0.075, Y(-38), Z(14),  0.075, Y(-30), Z(40), 'park');   // 叠枪环
  /* 前背带环：实测最低点在 100–150mm 段（−41mm），挂在导气筒后段下方 */
  box('barrel', 'sling_fr',   -0.07, Y(-44), Z(96),   0.07, Y(-20), Z(129), 'parkd');
  box('barrel', 'sling_fr_h', -0.20, Y(-33), Z(101),  0.20, Y(-24), Z(124), 'parkd');

  /* 前准星（带护耳）：刀刃顶端 = 瞄准线 SIGHT */
  box('barrel', 'fs_base',   -0.16, BORE + 0.06, Z(25),  0.16, Y(8), Z(85), 'parkd');
  box('barrel', 'fs_blade',  -0.055, Y(8), Z(38),        0.055, SIGHT, Z(72), 'blk');
  box('barrel', 'fs_ear_l',  -0.20, Y(8), Z(34),        -0.135, Y(16), Z(76), 'parkd');
  box('barrel', 'fs_ear_r',   0.135, Y(8), Z(34),        0.20, Y(16), Z(76), 'parkd');

  /* 下枪箍（326–338mm）：真机是扁钢箍，绕住护木 */
  collar('barrel', 'band_lower', zBandF, zBandR, Y(-45), Y(19), 0.355, 0.10, 'parkd');
  box('barrel', 'band_lower_k', -0.355, Y(-30), zBandF - 0.03, 0.355, Y(6), zBandR + 0.03, 'parkd');

  /* --- 5.2 receiver + wood（bone: body）--- */
  /* 机匣 519–799mm。519 处是机匣环（圆筒），其后是方身。 */
  ring('body', 'rec_ring', 2, zRecF - 0.42, zRecF, 0, BORE, 0.30, 0.24, 10, 'park');
  box('body', 'rec_main',  -0.30, Y(-30), zRecF,  0.30, Y(16), zRecR, 'park');
  box('body', 'rec_low',   -0.27, Y(-55), zRecF + 0.35, 0.27, Y(-30), zRecR, 'parkd');   // 弹仓体下缘
  /* 漏夹井（601→700mm，100mm）：真机标定 —— 井前壁 = 闭锁面 610mm（枪管 24"），
     井后壁贴后照门座/拉机柄前沿 700mm。两侧导轨 + 前壁 + 后壁，顶面就是机匣顶面。 */
  box('body', 'well_l',   -0.30, Y(16), Z(601), -0.19, Y(26), Z(700), 'park');
  box('body', 'well_r',    0.19, Y(16), Z(601),  0.30, Y(26), Z(700), 'park');
  box('body', 'well_f',   -0.30, Y(16), Z(601) - 0.04, 0.30, Y(26), Z(601) + 0.10, 'park');
  box('body', 'well_b',   -0.30, Y(16), Z(700) - 0.10, 0.30, Y(26), Z(700) + 0.04, 'park');
  box('body', 'well_cav', -0.19, Y(-6), Z(601) + 0.10, 0.19, Y(16), Z(700) - 0.10, 'dark');
  /* 机匣后段：弹底窝 + 枪机通道 + 右侧抛壳窗 */
  box('body', 'rec_bre',  -0.30, Y(-14), Z(652),  0.30, Y(16), zRecR, 'park');
  box('body', 'brg_top',  -0.30, Y(16), Z(700),   0.30, Y(24), zRecR, 'park');           // 桥面：从漏夹井后壁起
  box('body', 'ej_port',   0.28, Y(-16), Z(700),  0.315, Y(14), Z(795), 'dark');         // 右侧抛壳窗
  box('body', 'bolt_chan',-0.21, Y(-18), Z(519) + 0.1, 0.21, Y(14), Z(652) - 0.1, 'dark');
  box('body', 'clip_lat', -0.30, Y(-32), Z(640), -0.24, Y(-6), Z(700), 'parkd');         // 弹夹卡榫
  box('body', 'safety',    0.27, Y(-46), Z(760),  0.34, Y(-30), Z(800), 'parkd');        // 保险
  /* 机匣尾座（799–827mm）：实测这段是金属，木托从 827mm 才起。缺了它机匣和托颈之间会露缝。 */
  box('body', 'rec_tang', -0.26, Y(-44), zRecR,   0.26, Y(10), zWrist, 'park');
  box('body', 'rec_tang2',-0.28, Y(-30), zRecR,   0.28, Y(6),  zWrist, 'parkd');

  /* 后照门：座在机匣后端，孔心 = 瞄准线 */
  box('body', 'rs_base',  -0.22, Y(16), Z(700),  0.22, Y(20), Z(782), 'parkd');
  box('body', 'rs_body',  -0.16, Y(20), Z(712),  0.16, Y(30), Z(778), 'park');
  box('body', 'rs_ap',    -0.075, SIGHT - 0.055, Z(736), 0.075, SIGHT + 0.055, Z(755), 'blk');  // 觇孔
  box('body', 'rs_ear_l', -0.21, Y(20), Z(716), -0.15, Y(34), Z(774), 'parkd');
  box('body', 'rs_ear_r',  0.15, Y(20), Z(716),  0.21, Y(34), Z(774), 'parkd');
  box('body', 'rs_knob',   0.16, Y(20), Z(742),  0.29, Y(32), Z(770), 'parkd');          // 右侧高低/风偏鼓

  /* 木质部（bone: body）。真机：下托（fore-end）从 156mm 一直到机匣，托颈与之连成一体；
     上面盖两段上护木（前段 156–326，后段 338–519），枪管被这两段包住。 */
  taper('body', 'forend', [
    [zGasR, Y(10), Y(-41), 0.335],
    [zBandF, Y(11), Y(-45), 0.335],
    [zRecF, Y(12), Y(-67), 0.325],
    [zRecR, Y(10), Y(-81), 0.315],
    [zWrist, Y(-16), Y(-82), 0.30]
  ], 'wood');
  box('body', 'forend_cap', -0.335, Y(-41), Z(150), 0.335, Y(10), Z(160), 'woodd');
  /* 上护木：圆管包住枪管（真机是上下两半，此处整体成管，外面看等价；规范允许省略内部结构）*/
  ring('body', 'hg_front', 2, zGasR, zBandF, 0, BORE, 0.265, 0.10, 8, 'wood');
  ring('body', 'hg_fronts',2, zGasR - 0.02, zGasR + 0.10, 0, BORE, 0.275, 0.10, 8, 'woodd');
  ring('body', 'hg_rear',  2, zBandR, zRecF, 0, BORE, 0.255, 0.10, 8, 'wood');
  ring('body', 'hg_rears', 2, zBandR - 0.10, zBandR + 0.02, 0, BORE, 0.265, 0.10, 8, 'woodd');
  ring('body', 'hg_rearc', 2, zRecF - 0.14, zRecF, 0, BORE, 0.285, 0.11, 8, 'woodd');

  /* 扳机座 + 一体护圈（bone: body；真机扳机座连护圈，靠护圈锁在机匣上）
     实测：扳机座底 −55mm、护圈底 −91mm —— 护圈只是略低于托腹，不是吊在半空 */
  box('body', 'tg_body',   -0.27, Y(-55), Z(660),  0.27, Y(-28), Z(872), 'parkd');
  box('body', 'tg_plate',  -0.25, Y(-62), Z(660),  0.25, Y(-55), Z(872), 'park');
  box('body', 'tg_guard_f',-0.20, Y(-91), Z(806),  0.20, Y(-55), Z(826), 'parkd');
  box('body', 'tg_guard_b',-0.20, Y(-91), Z(858),  0.20, Y(-55), Z(878), 'parkd');
  box('body', 'tg_guard_d',-0.20, Y(-91), Z(806),  0.20, Y(-83), Z(878), 'parkd');
  box('body', 'mag_floor', -0.24, Y(-66), Z(560),  0.24, Y(-55), Z(660), 'park');

  /* --- 5.3 bolt + op-rod（bone: bolt, pivot = 导气杆手柄销轴）--- */
  ring('bolt', 'bolt_body', 2, zRecF + 0.15, Z(652), 0, BORE, 0.19, 0.11, 8, 'steel');
  box('bolt', 'bolt_lug',  -0.19, Y(-16), Z(519) + 0.30, 0.19, Y(14), Z(560), 'steel');
  box('bolt', 'bolt_face', -0.16, Y(-14), Z(519) + 0.22, 0.16, Y(12), Z(519) + 0.34, 'dark');
  /* 导气杆（右侧全长）：真机它嵌在护木右侧的槽里、与木托侧面齐平，从导气筒后端一直到机匣，
     外观上就是加兰德的“拉机柄”。杆体半宽必须 ≥ 护木半宽，否则整根埋进木头里看不见。 */
  box('bolt', 'oprod',      0.295, Y(-20), Z(150),  0.375, Y(6), -2.20, 'park');
  box('bolt', 'oprod_tip',  0.285, Y(-26), Z(120),  0.385, Y(10), Z(150), 'parkd');
  box('bolt', 'oprod_rib',  0.375, Y(1), Z(170),    0.415, Y(6), -2.25, 'parkd');
  box('bolt', 'handle',     0.295, Y(-22), Z(700),  0.46, Y(4), Z(740), 'park');       // 加兰德标志性折柄
  box('bolt', 'handle_h',   0.40, Y(-26), Z(696),   0.48, Y(10), Z(726), 'parkd');

  /* --- 5.4 clip cover（bone: cover, pivot = 机匣后端上缘, 动作纯平移）--- */
  box('cover', 'cover_l', -0.30, Y(16), Z(601), -0.10, Y(21), Z(700), 'park');
  box('cover', 'cover_r',  0.10, Y(16), Z(601),  0.30, Y(21), Z(700), 'park');
  box('cover', 'cover_h', -0.30, Y(21), Z(657),  0.30, Y(24), Z(678), 'parkd');         // 提手

  /* --- 5.5 en-bloc clip + 8 rounds（bone: clip_in）---
   * 真机漏夹：钢板冲压件，8 发 .30-06 两列四排、弹头朝前（-Z）。总长 85mm = 1.36u。 */
  var CW = 0.152;                     // 漏夹半宽 19mm
  var CL_F = Z(601) + 0.06, CL_B = CL_F + 1.36;          // 85mm 长，正好落在 601→700 的井内
  box('clip_in', 'clip_bot', -CW, Y(-25), CL_F,  CW, Y(-17), CL_B, 'park');
  box('clip_in', 'clip_l',   -CW, Y(-17), CL_F, -CW + 0.06, Y(8), CL_B, 'park');
  box('clip_in', 'clip_r',    CW - 0.06, Y(-17), CL_F,  CW, Y(8), CL_B, 'park');
  box('clip_in', 'clip_end', -CW, Y(-17), CL_B - 0.06, CW, Y(8), CL_B, 'parkd');
  for (var c = 0; c < 4; c++) {
    var cx = (c % 2 === 0) ? -0.075 : 0.075;
    var cy = Y(-14) + Math.floor(c / 2) * 0.15;
    ring('clip_in', 'rnd' + c + '_case', 2, CL_F + 0.12, CL_F + 0.96, cx, cy, 0.082, 0.066, 6, 'brs');
    ring('clip_in', 'rnd' + c + '_tip',  2, CL_F + 0.96, CL_F + 1.22, cx, cy, 0.062, 0.052, 6, 'cpr');
    box('clip_in', 'rnd' + c + '_rim', cx - 0.092, cy - 0.092, CL_F + 0.06, cx + 0.092, cy + 0.092, CL_F + 0.12, 'steel');
  }

  /* --- 5.6 casing（bone: casing, pivot = 弹壳中心, 几何落在 +X 抛壳窗内）--- */
  var CZ = X_EJ();
  ring('casing', 'case_body', 2, CZ - 0.42, CZ + 0.30, 0.30, Y(20), 0.082, 0.066, 8, 'brs');
  ring('casing', 'case_neck', 2, CZ + 0.30, CZ + 0.42, 0.30, Y(20), 0.062, 0.052, 8, 'brs');
  ring('casing', 'case_rim',  2, CZ - 0.48, CZ - 0.42, 0.30, Y(20), 0.092, 0.092, 8, 'steel');

  /* --- 5.7 magazine：真机无 detachable mag（8 发装在漏夹里），导出保持空 --- */

  /* --- 5.8 trigger（bone: trigger, pivot = 扳机轴销）--- */
  box('trigger', 'trig_blade', -0.055, Y(-58), Z(810), 0.055, Y(-30), Z(821), 'steel');
  box('trigger', 'trig_mid',   -0.058, Y(-80), Z(808), 0.058, Y(-56), Z(820), 'steel');
  box('trigger', 'trig_shoe',  -0.062, Y(-95), Z(806), 0.062, Y(-78), Z(819), 'parkd');

  /* --- 5.9 stock：托颈 + 托身（带下沉托底）+ 托底板（bone: stock）--- */
  taper('stock', 'stock_wood', [
    [zWrist, Y(-16), Y(-82), 0.30],
    [Z(880), Y(-24), Y(-96), 0.315],
    [Z(950), Y(-30), Y(-124), 0.345],
    [Z(1000), Y(-32), Y(-162), 0.355],
    [zButt, Y(-36), Y(-176), 0.365]
  ], 'wood', 9);
  box('stock', 'wrist_cap', -0.30, Y(-16), zWrist - 0.05, 0.30, Y(8), zWrist + 0.06, 'woodd');
  /* 托底板：真机是钢板 + 通条仓盖 */
  box('stock', 'plate',      -0.365, Y(-176), zButt, 0.365, Y(-36), zEnd, 'steel');
  box('stock', 'plate_door', -0.13, Y(-104), zEnd,   0.13, Y(-76), zEnd + 0.03, 'parkd');
  /* 后背带环（左侧 = -X） */
  box('stock', 'sling_rr',  -0.40, Y(-120), Z(980), -0.36, Y(-96), Z(1010), 'park');
  box('stock', 'sling_rr2', -0.44, Y(-116), Z(986), -0.40, Y(-100), Z(1004), 'parkd');

  /* ---------- 6. instantiate ---------- */
  var made = 0;
  RAW.forEach(function (r) {
    var parent = G[r.g];
    if (!parent) { out.warnings.push('missing group ' + r.g); return; }
    var cb = new Cube({ name: r.n, from: r.f, to: r.t, origin: r.o, rotation: r.r, autouv: 0 });
    cb.init();
    cb.addTo(parent);
    cb.__mat = r.mat;
    made++;
  });
  out.steps.push('created ' + made + ' cubes in ' + Object.keys(G).length + ' groups');

  /* ---------- 7. per-face UV atlas (shelf packer, 规范 四) ---------- */
  var FL = ['north', 'east', 'south', 'west', 'up', 'down'];
  var faces = [];
  Project.elements.forEach(function (cb) {
    var dx = Math.abs(cb.to[0] - cb.from[0]), dy = Math.abs(cb.to[1] - cb.from[1]), dz = Math.abs(cb.to[2] - cb.from[2]);
    FL.forEach(function (f) {
      var w, h;
      if (f === 'north' || f === 'south') { w = dx; h = dy; }
      else if (f === 'east' || f === 'west') { w = dz; h = dy; }
      else { w = dx; h = dz; }
      faces.push({ c: cb, f: f, w: w, h: h, mat: cb.__mat });
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
  for (var d = 12; d >= 4; d--) { var p = pack(d); if (p) { D = d; pk = p; break; } }   // 规范密度 12
  if (!pk) return { error: 'UV atlas overflow even at 4 px/u' };
  faces.forEach(function (o, i) {
    var r = pk.rects[i];
    o.c.faces[o.f].uv = r;
    o.c.faces[o.f].texture = TEX.uuid;
    o.rect = r;
  });
  out.steps.push('uv density ' + D + ' px/u, atlas height ' + pk.used + '/512, faces ' + faces.length);

  /* ---------- 8. paint the 512x512 atlas ----------
   * 木纹按【世界坐标】采样：相邻方块的木纹在接缝处连续，整体读起来是一根木头，
   * 而不是一叠木板。金属用逐面弱噪声 + 拉丝。 */
  var ctx = TEX.ctx;
  var img = ctx.createImageData(512, 512), px = img.data;
  function lcg(seed) { var s = seed >>> 0; return function () { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; }; }
  var FACE_SEED = { north: 11, south: 29, east: 47, west: 71, up: 89, down: 103 };
  faces.forEach(function (o, i) {
    var base = MAT[o.mat] || MAT.park, s = SHADE[o.f] || 1, r = o.rect, x, y, p;
    var rnd = lcg((i + 1) * 977 + FACE_SEED[o.f]);
    var isWood = (o.mat === 'wood' || o.mat === 'woodd');
    var f0 = o.c.from, t0 = o.c.to;
    /* 该面在世界空间的两个参数轴（用于木纹连续性）*/
    var span = r[2] - r[0], spanH = r[3] - r[1];
    for (y = r[1]; y < r[3]; y++) {
      for (x = r[0]; x < r[2]; x++) {
        var u = (x - r[0] + 0.5) / (span || 1), v = (y - r[1] + 0.5) / (spanH || 1);
        var f = s;
        if (isWood) {
          /* 沿枪身方向（Z 或 X）的木纹：用世界坐标，跨方块连续 */
          var wx, wy;
          if (o.f === 'east' || o.f === 'west') { wx = f0[2] + (t0[2] - f0[2]) * u; wy = f0[1] + (t0[1] - f0[1]) * v; }
          else if (o.f === 'up' || o.f === 'down') { wx = f0[0] + (t0[0] - f0[0]) * u; wy = f0[2] + (t0[2] - f0[2]) * v; }
          else { wx = f0[0] + (t0[0] - f0[0]) * u; wy = f0[1] + (t0[1] - f0[1]) * v; }
          var grain = Math.sin(wx * 1.15 + wy * 0.35) * 0.5 + Math.sin(wx * 3.70 + wy * 1.10) * 0.20;
          f *= 0.965 + 0.07 * grain;
          if (grain < -0.36) f *= 0.93;
          if (u < 0.02 || u > 0.98) f *= 1.04;                  // 极弱棱线，保留体块感
        } else {
          f *= 0.955 + 0.09 * rnd();
          if (u < 0.02 || u > 0.98 || v < 0.02 || v > 0.98) f *= 1.16;   // 金属保持清晰色块边界
        }
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

  /* ---------- 9. write real files ----------
   * 图集必须同时落到两处：art/（存档、可复现）和 src/main/resources/（游戏真正加载的那份）。
   * 只写 art/ 会让资源目录里留下一张旧导出 —— 症状是模型一大片面采到全透明区、
   * 游戏里渲染成纯黑，而 check_gun_resources.py 当时只验 512x512，完全看不出来。 */
  try {
    var fs = require('fs');
    var png = Buffer.from(TEX.canvas.toDataURL('image/png', 1).slice(22), 'base64');
    [
      'F:/mcmod/art/m1garand/m1_garand_geo.png',
      'F:/mcmod/src/main/resources/assets/apocalypse_zombies/textures/item/m1_garand.png'
    ].forEach(function (target) {
      var dir = target.slice(0, target.lastIndexOf('/'));
      try { fs.mkdirSync(dir, { recursive: true }); } catch (e3) {}
      fs.writeFileSync(target, png);
      out.steps.push('wrote ' + target + ' (' + png.length + ' B)');
    });
  } catch (e2) { out.warnings.push('png:' + e2.message); }

  if (typeof Canvas !== 'undefined' && Canvas.updateAllFaces) Canvas.updateAllFaces();
  if (typeof Preview !== 'undefined') Preview.all.forEach(function (v) { if (v.canvas) v.render(); });

  /* ---------- 10. self-report ---------- */
  var xs = [], ys = [], zs = [];
  Project.elements.forEach(function (cb) {
    xs.push(cb.from[0], cb.to[0]); ys.push(cb.from[1], cb.to[1]); zs.push(cb.from[2], cb.to[2]);
  });
  out.cubes = Project.elements.length;
  out.groups = Project.groups.length;
  out.bbox = {
    x: [Math.min.apply(null, xs), Math.max.apply(null, xs)],
    y: [Math.min.apply(null, ys), Math.max.apply(null, ys)],
    z: [Math.min.apply(null, zs), Math.max.apply(null, zs)]
  };
  out.bbox_mm = {
    length: (Math.max.apply(null, zs) - Math.min.apply(null, zs)) * MM,
    height: (Math.max.apply(null, ys) - Math.min.apply(null, ys)) * MM,
    width: (Math.max.apply(null, xs) - Math.min.apply(null, xs)) * MM
  };
  out.anchors = { sight_y: SIGHT, muzzle: [0, BORE, zM], eject: [0.30, Y(20), X_EJ()] };
  out.groups_tree = Project.groups.map(function (g) {
    return g.name + '<' + ((g.parent && g.parent.name) ? g.parent.name : 'root') + '>';
  });
  return out;
})()
