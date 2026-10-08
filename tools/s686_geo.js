'use strict';
/* ============================================================================
 * Gold Plate - S686 —— 几何定义（over-under 折开式双管霰弹枪）
 *
 * 铁律（美术规范.md / Agent_Java.md 第零节）：
 *   16 u = 1 方块 = 1 m | 枪口 = -Z | 上 = +Y | +X = 射手右侧
 *   原点 = 机匣中心，握把在下方 | 骨骼一根都不带初始旋转
 *
 * 枪长 19.64 u = 1.23 格（区间 1.0~1.5 格）。
 * 圆形件一律用 ring()（8~10 边形旋转薄板拼的棱柱），不手堆方块拼圆。
 *
 * 结构（真实 S686 / Citori 类折开式猎枪）：
 *   枪管段  z ∈ [-10.00, +1.30]  上下双管 + 中间的瞄准肋条 + 前准星珠 + 两道管箍
 *   弹膛段  z ∈ [-2.20,  +1.30]  管径加粗，内藏两发 12 号霰弹（可被动画驱动）
 *   护木    z ∈ [-4.90,  +1.05]  木质前托，包住下管，前端金属帽 + 卡笋
 *   铰链    z =  +1.30, y = -0.58  折开旋转轴（barrel 骨骼的 pivot）
 *   机匣    z ∈ [+1.30,  +4.20]  含立式后膛面、开膛杆、外露击锤、保险
 *   扳机组  z ≈  +2.55, y ≈ -0.62  护圈 + 扳机片
 *   枪托    z ∈ [+4.20,  +9.60]  木托 + 托底板
 * ========================================================================== */

const BORE_U = 0.36;   // 上管轴线 Y
const BORE_L = -0.36;  // 下管轴线 Y
const R_TUBE = 0.30;   // 管外半径
const HINGE = [0, -0.58, 1.30];  // 折开旋转轴（真实铰链销位置）

/** 材质调色板 —— Gold Plate 皮肤：镀金枪管 + 胡桃木托 */
const MAT = {
  gold:  [214, 172,  74],  // 主金色：枪管 / 机匣
  goldl: [244, 216, 134],  // 金色高光：管口 / 边线 / 准星珠
  goldd: [150, 112,  38],  // 金色暗部：肋条 / 接缝 / 管箍
  brass: [176, 132,  52],  // 黄铜：弹壳底 / 铰链销
  wood:  [126,  64,  40],  // 木质主色：护木 / 枪托
  woodl: [158,  92,  58],  // 木质亮部
  woodd: [ 86,  40,  26],  // 木质暗部 / 防滑纹
  steel: [ 96,  98, 104],  // 钢：扳机 / 击锤 / 保险
  std:   [ 58,  60,  66],  // 钢暗部
  blk:   [ 26,  26,  28],  // 黑件：托底板 / 托底垫
  red:   [148,  44,  36],  // 霰弹壳身
  dk:    [ 14,  14,  16],  // 膛口 / 缝隙 / 暗腔
};

/** 面朝向明暗表（与 uzi/awm 同一套，保证同屏光照一致） */
const SHADE = { up: 1.14, down: 0.60, north: 1.00, south: 0.86, east: 0.94, west: 0.80 };

function build() {
  const groups = [];  // {name, origin, parent}
  const cubes = [];   // {g, n, f, t, mat, r, o}
  const warn = [];

  function grp(name, origin, parent) {
    groups.push({ name, origin, parent: parent || null });
    return name;
  }
  function box(g, n, x0, y0, z0, x1, y1, z1, mat, rot, org) {
    cubes.push({
      g, n,
      f: [x0, y0, z0], t: [x1, y1, z1], mat,
      r: rot || [0, 0, 0],
      o: org || [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
    });
  }
  /* N 片旋转薄板拼成的棱柱（等价 boxlib `ring`）。
     axis: 0 = 沿 X, 1 = 沿 Y, 2 = 沿 Z（枪膛轴线）。
     a0/a1 = 沿该轴的起止；c1/c2 = 另两轴的圆心；R 外半径；t 壁厚；N 边数。 */
  function ring(g, n, axis, a0, a1, c1, c2, R, t, N, mat, phase) {
    phase = phase || 0;
    const rm = R - t / 2;
    const w = 2 * R * Math.sin(Math.PI / N) * 1.12;  // 1.12 = 相邻板轻微交叠，消缝
    for (let k = 0; k < N; k++) {
      const al = phase + (k + 0.5) * 2 * Math.PI / N;
      const ad = al * 180 / Math.PI;
      const p1 = c1 + rm * Math.cos(al), p2 = c2 + rm * Math.sin(al);
      let f, t2, rot, org;
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

  /* ---------------- 骨骼树 ---------------- */
  grp('root', [0, -0.90, 5.50], null);         // pivot = 后握把
  grp('move', [0, -0.90, 5.50], 'root');       // 整体位移通道（待机 / 后坐）
  grp('body', [0, 0, 1.30], 'move');           // 机匣参考系
  grp('receiver',    [0, 0.10, 2.80], 'body');
  grp('barrel',      HINGE, 'body');           // ★ 折开轴：绕此处向下旋转
  grp('forend',      [0, -0.60, -1.60], 'barrel');
  grp('barrel_upper',[0, BORE_U, -4.30], 'barrel');
  grp('barrel_lower',[0, BORE_L, -4.30], 'barrel');
  grp('rib',         [0, 0, -5.60], 'barrel');
  grp('extractor',   [0, -0.36, 1.10], 'barrel');
  grp('shell_upper', [0, BORE_U, 0.40], 'barrel');
  grp('shell_lower', [0, BORE_L, 0.40], 'barrel');
  grp('stock',       [0, -0.80, 6.60], 'body');
  grp('trigger_group', [0, -0.62, 2.55], 'body');
  grp('hammer',      [0, 0.58, 4.05], 'body');
  grp('top_lever',   [0, 0.88, 2.30], 'body');
  grp('safety',      [0.62, 0.30, 3.55], 'body');
  /* TaCZ 规范占位组：折开式无弹匣，保留空组以对齐本仓库其它枪械的骨骼清单 */
  grp('magazine', [0, 0, 0], 'move');
  grp('mag_standard',   [0, 0, 0], 'magazine');
  grp('mag_extended_1', [0, 0, 0], 'magazine');
  grp('mag_extended_2', [0, 0, 0], 'magazine');
  grp('mag_extended_3', [0, 0, 0], 'magazine');
  grp('additional_magazine', [0, 0, 0], 'move');  // 必须为空且不嵌套在 magazine 下
  grp('constraint', [0, 0, 0], 'move');
  grp('camera',     [0, 0, 0], 'move');

  /* ---------------- 1. 枪管：上下两根 8 边形管 ---------------- */
  [['barrel_upper', BORE_U], ['barrel_lower', BORE_L]].forEach(function (p) {
    const g = p[0], y = p[1];
    ring(g, 'choke',   2, -10.00, -9.62, 0, y, 0.335, 0.22, 8, 'goldl');
    ring(g, 'bore',    2, -10.06, -9.94, 0, y, 0.200, 0.30, 8, 'dk');   // 膛口内壁
    ring(g, 'pipe_f',  2,  -9.62, -6.60, 0, y, 0.300, 0.20, 8, 'gold');
    ring(g, 'band_f',  2,  -6.60, -6.34, 0, y, 0.322, 0.22, 8, 'goldd');
    ring(g, 'pipe_m',  2,  -6.34, -2.46, 0, y, 0.300, 0.20, 8, 'gold');
    ring(g, 'band_r',  2,  -2.46, -2.20, 0, y, 0.322, 0.22, 8, 'goldd');
    ring(g, 'chamber', 2,  -2.20,  1.16, 0, y, 0.355, 0.26, 8, 'gold');
    ring(g, 'ch_ring', 2,   1.16,  1.30, 0, y, 0.372, 0.30, 8, 'goldd');
  });

  /* 管间的瞄准肋条（over-under 的上肋 + 下管座） */
  box('rib', 'rib_top',   -0.085,  0.055, -9.72,  0.085,  0.175,  -2.20, 'goldd');
  box('rib', 'rib_mid',   -0.065, -0.075, -9.72,  0.065,  0.055,  -2.20, 'dk');
  box('rib', 'rib_base',  -0.085, -0.215, -9.72,  0.085, -0.075,  -2.20, 'goldd');
  box('rib', 'rib_front', -0.085, -0.215, -9.86,  0.085,  0.175, -9.72,  'goldd');
  /* 前准星柱 + 珠 */
  box('rib', 'fs_post',   -0.045,  0.175, -9.70,  0.045,  0.300, -9.50, 'std');
  ring('rib', 'fs_bead', 0, -0.070, 0.070, 0.300, -9.60, 0.075, 0.15, 6, 'goldl');

  /* ---------------- 2. 弹膛尾块 + 抽壳钩 ---------------- */
  box('barrel', 'breech_block', -0.560, -0.860, 1.14,  0.560, 0.860, 1.34, 'gold');
  box('barrel', 'breech_lip',   -0.600, -0.900, 1.02,  0.600, 0.900, 1.14, 'goldd');
  box('barrel', 'bb_fence_l',   -0.620,  0.560, 1.14, -0.560, 0.880, 1.34, 'goldd');
  box('barrel', 'bb_fence_r',    0.560,  0.560, 1.14,  0.620, 0.880, 1.34, 'goldd');
  box('barrel', 'bb_under',     -0.540, -0.880, 1.14,  0.540, -0.640, 1.34, 'goldd');
  /* 抽壳钩：折开时把两发空壳顶出一小段 */
  box('extractor', 'ex_lip_u', -0.230,  0.320, 1.02,  0.230,  0.400, 1.20, 'steel');
  box('extractor', 'ex_lip_l', -0.230, -0.400, 1.02,  0.230, -0.320, 1.20, 'steel');
  box('extractor', 'ex_stem',  -0.075, -0.400, 1.06,  0.075,  0.400, 1.18, 'std');

  /* ---------------- 3. 护木（木质前托，包住下管） ----------------
     真实 S686 的护木约占枪管长 1/3，前端略收并带金属帽；裸管段必须明显长于护木。 */
  box('forend', 'fd_bot',   -0.470, -0.980, -3.20,  0.470, -0.700, 1.02, 'wood');
  box('forend', 'fd_l',     -0.530, -0.700, -3.20, -0.470, -0.020, 1.02, 'wood');
  box('forend', 'fd_r',      0.470, -0.700, -3.20,  0.530, -0.020, 1.02, 'wood');
  box('forend', 'fd_nose',  -0.470, -0.980, -3.48,  0.470, -0.560, -3.20, 'woodl');
  box('forend', 'fd_cap',   -0.500, -1.000, -3.64,  0.500, -0.660, -3.48, 'goldd');
  box('forend', 'fd_latch', -0.180, -1.040,  0.72,  0.180, -0.800, 1.02, 'steel');
  box('forend', 'fd_heel',  -0.470, -0.980,  0.86,  0.470, -0.560, 1.02, 'woodd');
  /* 防滑纹（checkering）—— 两侧各 4 道细暗线 */
  for (let i = 0; i < 4; i++) {
    const z = -2.60 + i * 0.80;
    box('forend', 'fd_ck_l' + i, -0.545, -0.640, z, -0.530, -0.140, z + 0.10, 'woodd');
    box('forend', 'fd_ck_r' + i,  0.530, -0.640, z,  0.545, -0.140, z + 0.10, 'woodd');
  }

  /* ---------------- 4. 机匣（含立式后膛面 / 铰链耳 / 开膛杆槽） ---------------- */
  box('receiver', 'rc_side_l',  -0.560, -0.760, 1.30, -0.460, 0.780, 4.20, 'gold');
  box('receiver', 'rc_side_r',   0.460, -0.760, 1.30,  0.560, 0.780, 4.20, 'gold');
  box('receiver', 'rc_floor',   -0.560, -0.860, 1.30,  0.560, -0.760, 3.10, 'gold');
  box('receiver', 'rc_top',     -0.560,  0.780, 1.30,  0.560,  0.880, 3.62, 'gold');
  box('receiver', 'rc_back',    -0.560, -0.760, 4.20,  0.560,  0.780, 4.44, 'goldd');
  box('receiver', 'rc_seam_l',  -0.575,  0.180, 1.40, -0.560,  0.240, 4.10, 'goldd');
  box('receiver', 'rc_seam_r',   0.560,  0.180, 1.40,  0.575,  0.240, 4.10, 'goldd');
  box('receiver', 'rc_fence',   -0.600, -0.800, 1.30,  0.600,  0.820, 1.44, 'goldd');
  box('receiver', 'rc_water',   -0.420,  0.560, 1.44,  0.420,  0.780, 1.62, 'dk');    // 后膛上方的泄气槽
  /* 铰链耳 + 铰链销（销 = 沿 X 轴的圆柱） */
  box('receiver', 'hg_ear_l',   -0.620, -0.760, 1.10, -0.460, -0.180, 1.50, 'goldd');
  box('receiver', 'hg_ear_r',    0.460, -0.760, 1.10,  0.620, -0.180, 1.50, 'goldd');
  box('receiver', 'hg_lug',     -0.180, -0.800, 1.06,  0.180, -0.360, 1.44, 'goldd');
  ring('receiver', 'hg_pin', 0, -0.660, 0.660, -0.580, 1.30, 0.140, 0.28, 8, 'brass');
  /* 机匣侧面的装饰刻线 */
  box('receiver', 'rc_eng_a',   -0.580,  0.420, 2.20, -0.560,  0.560, 3.40, 'goldl');
  box('receiver', 'rc_eng_b',    0.560,  0.420, 2.20,  0.580,  0.560, 3.40, 'goldl');

  /* ---------------- 5. 开膛杆（机匣顶部，向右侧推的顶杆） ---------------- */
  box('top_lever', 'tl_arm',   -0.105,  0.880, 2.24,  0.105,  0.975, 3.52, 'steel');
  box('top_lever', 'tl_thumb', -0.190,  0.880, 3.52,  0.190,  1.075, 3.96, 'steel');
  box('top_lever', 'tl_rib',   -0.215,  0.930, 3.60,  0.215,  1.010, 3.72, 'std');
  box('top_lever', 'tl_rib2',  -0.215,  0.930, 3.80,  0.215,  1.010, 3.92, 'std');

  /* ---------------- 6. 外露击锤（可旋转） ---------------- */
  box('hammer', 'hm_body',  -0.115,  0.560, 3.86,  0.115,  0.980, 4.20, 'steel');
  box('hammer', 'hm_spur',  -0.155,  0.940, 4.02,  0.155,  1.120, 4.34, 'steel');
  box('hammer', 'hm_rib_a', -0.165,  0.980, 4.10,  0.165,  1.060, 4.18, 'std');
  box('hammer', 'hm_rib_b', -0.165,  0.980, 4.22,  0.165,  1.060, 4.30, 'std');

  /* ---------------- 7. 保险钮（机匣左侧） ---------------- */
  box('safety', 'sf_plate', -0.610,  0.140, 3.26, -0.560,  0.460, 3.84, 'steel');
  box('safety', 'sf_btn',   -0.680,  0.220, 3.36, -0.610,  0.380, 3.60, 'std');

  /* ---------------- 8. 扳机组（护圈 + 扳机片） ---------------- */
  box('trigger_group', 'tg_guard_f', -0.230, -1.420, 1.62,  0.230, -0.860, 1.84, 'goldd');
  box('trigger_group', 'tg_guard_b', -0.230, -1.420, 2.66,  0.230, -0.860, 2.88, 'goldd');
  box('trigger_group', 'tg_guard_l', -0.230, -1.460, 1.62, -0.150, -1.360, 2.88, 'goldd');
  box('trigger_group', 'tg_guard_r',  0.150, -1.460, 1.62,  0.230, -1.360, 2.88, 'goldd');
  box('trigger_group', 'tg_blade',   -0.090, -1.360, 2.12,  0.090, -0.700, 2.32, 'steel');
  box('trigger_group', 'tg_shoe',    -0.115, -1.420, 2.10,  0.115, -1.300, 2.34, 'std');

  /* ---------------- 9. 枪托（胡桃木） ----------------
     侧视轮廓是一条连续曲线：握把向下后弯 -> 托身下缘平缓爬升 -> 托底略下垂。
     用 6 段折线近似（每段 z 0.78u、下缘升 0.1~0.2u），避免出现阶梯状方块堆。 */
  box('stock', 'st_grip',    -0.460, -1.620, 4.44,  0.460,  0.620, 5.36, 'wood');
  box('stock', 'st_grip_lo', -0.430, -1.880, 4.74,  0.430, -1.580, 5.36, 'wood');   // 握把底端下垂
  box('stock', 'st_body1',   -0.480, -1.430, 5.36,  0.480,  0.800, 6.14, 'wood');
  box('stock', 'st_body2',   -0.500, -1.270, 6.14,  0.500,  0.900, 6.92, 'wood');
  box('stock', 'st_body3',   -0.520, -1.130, 6.92,  0.520,  0.960, 7.70, 'wood');
  box('stock', 'st_body4',   -0.520, -1.010, 7.70,  0.520,  1.000, 8.48, 'wood');
  box('stock', 'st_body5',   -0.520, -0.930, 8.48,  0.520,  1.020, 8.94, 'wood');
  box('stock', 'st_butt',    -0.540, -0.990, 8.94,  0.540,  1.060, 9.26, 'blk');
  box('stock', 'st_butt_pd', -0.500, -0.950, 9.26,  0.500,  1.020, 9.44, 'blk');
  box('stock', 'st_cap',     -0.400, -2.020, 4.86,  0.400, -1.860, 5.28, 'blk');   // 握把底盖
  box('stock', 'st_cap_scr', -0.200, -1.910, 4.98,  0.200, -1.840, 5.16, 'steel');
  /* 握把与托身的防滑纹 */
  box('stock', 'st_ck_l1', -0.520, -1.520, 4.72, -0.500, -0.860, 4.84, 'woodd');
  box('stock', 'st_ck_l2', -0.520, -1.520, 5.02, -0.500, -0.860, 5.14, 'woodd');
  box('stock', 'st_ck_r1',  0.500, -1.520, 4.72,  0.520, -0.860, 4.84, 'woodd');
  box('stock', 'st_ck_r2',  0.500, -1.520, 5.02,  0.520, -0.860, 5.14, 'woodd');
  box('stock', 'st_ck_l3', -0.530, -0.960, 6.40, -0.515, -0.300, 6.52, 'woodd');
  box('stock', 'st_ck_l4', -0.530, -0.960, 6.72, -0.515, -0.300, 6.84, 'woodd');
  box('stock', 'st_ck_l5', -0.530, -0.960, 7.04, -0.515, -0.300, 7.16, 'woodd');
  box('stock', 'st_ck_r3',  0.515, -0.960, 6.40,  0.530, -0.300, 6.52, 'woodd');
  box('stock', 'st_ck_r4',  0.515, -0.960, 6.72,  0.530, -0.300, 6.84, 'woodd');
  box('stock', 'st_ck_r5',  0.515, -0.960, 7.04,  0.530, -0.300, 7.16, 'woodd');

  /* ---------------- 10. 两发 12 号霰弹（在弹膛内，动画驱动进出） ---------------- */
  [['shell_upper', BORE_U], ['shell_lower', BORE_L]].forEach(function (p, si) {
    const g = p[0], y = p[1];
    ring(g, 'case_head',  2, 0.98, 1.14, 0, y, 0.190, 0.34, 6, 'brass');
    ring(g, 'case_rim',   2, 1.14, 1.24, 0, y, 0.172, 0.30, 6, 'std');
    ring(g, 'case_body',  2, 0.28, 0.98, 0, y, 0.184, 0.32, 6, 'red');
    ring(g, 'case_crimp', 2, 0.06, 0.28, 0, y, 0.178, 0.30, 6, 'woodd');
    ring(g, 'case_mouth', 2, 0.00, 0.06, 0, y, 0.150, 0.26, 6, 'dk');
  });

  return { groups, cubes, warn, meta: { boreUp: BORE_U, boreLow: BORE_L, hinge: HINGE, R_TUBE } };
}

module.exports = { build, MAT, SHADE };
