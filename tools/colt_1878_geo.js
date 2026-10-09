'use strict';
/* ============================================================================
 * Coach Gun（短管双管霰弹枪）—— 几何定义 v4 · 按真枪尺寸
 *
 * 对应真枪：**Colt Model 1878 Double Barrel / Cimarron 1878 Coach Gun 12GA 20"**
 *   参考：https://www.cimarron-firearms.com/1878-coach-gun-12-ga-20-barrel-standard-blue.html
 *   参考图的特征与它逐条吻合：并排双管 · **外露双锤** · 前后双扳机 · 箱式机匣 ·
 *   20 英寸短管 · 蓝钢 + 胡桃木 + 托颈格纹。
 *
 * 真枪实测尺寸 → 模型（16 u = 1 方块 = 1 m ⇒ 1 u = 6.25 cm）：
 *   全长        940 mm  -> 15.04 u          （规范区间 0.9~2.6 格 = 14.4~41.6 u ✓）
 *   管长        508 mm  ->  8.13 u (54%)
 *   机匣长      152 mm  ->  2.43 u (16%)
 *   托长        280 mm  ->  4.48 u (30%)
 *   管外径       22 mm  ->  0.35 u  ← v3 用了 0.94 u（≈59mm），是真实的 2.7 倍
 *   机匣高/宽    76/45  ->  1.22 / 0.72 u
 *   托底下垂     60 mm  ->  0.96 u
 *
 * 铁律（美术规范.md 第一节 / Agent_Java.md 第零节）：
 *   枪口 = -Z | 上 = +Y | +X = 射手右侧 | 原点 = 机匣中心 | 骨骼零旋转 | 长轴是 Z
 *   方块 ≤ 600 / 骨骼 ≤ 40 | 逐面 UV（密度 11~13 px/u）
 * ========================================================================== */

/* 16 u = 1 方块 = 1 m ⇒ 1 u = 6.25 cm = 62.5 mm ⇒ 1 mm = 0.016 u。
 * （别写成 1/6.25 —— 那是把 6.25 cm 当成 6.25 mm，整体放大 10 倍，全长会算成 150u。） */
const MM = 16 / 1000;             // 毫米 -> 模型单位（u）

/* ---------------------------------------------------------------- 真枪尺寸表 */
const LEN_TOTAL = 940 * MM;       // 15.04
const LEN_BARREL = 508 * MM;      //  8.13
const LEN_RECV = 152 * MM;        //  2.43
const LEN_STOCK = 280 * MM;       //  4.48

const BORE_R = (22 / 2) * MM;     // 管外半径 0.176 u
const BORE_GAP = 0.19;            // 两管中心距的一半（并排，管几乎相切）
const RECV_H = 76 * MM;           // 机匣高 1.216 u
const RECV_W = 45 * MM;           // 机匣宽 0.72 u
const DROP = 60 * MM;             // 托底下垂 0.96 u

/* 原点 = 机匣中心：机匣占 z ∈ [-LEN_RECV/2, +LEN_RECV/2]，管往前、托往后 */
const RECV_Z0 = -LEN_RECV / 2;
const RECV_Z1 = +LEN_RECV / 2;
const TUBE_Z1 = RECV_Z0 + 0.30;          // 管后端插进机匣
const TUBE_Z0 = TUBE_Z1 - LEN_BARREL;    // 管口
const STOCK_Z0 = RECV_Z1;
const STOCK_Z1 = STOCK_Z0 + LEN_STOCK;

/* 管轴线：真枪里双管坐在机匣上缘，膛线与机匣顶面基本齐平 */
const RECV_Y0 = -RECV_H / 2;
const RECV_Y1 = +RECV_H / 2;
const TUBE_Y = RECV_Y1 - BORE_R - 0.04;

/* 铰链（折开轴）：真枪在机匣前下端 */
const HINGE = [0, RECV_Y0 + 0.10, RECV_Z0 + 0.06];

/** 材质调色板 —— 发蓝钢 + 胡桃木（美术规范.md 第三节） */
const MAT = {
  blue:  [ 66,  70,  78],  // 发蓝钢：枪管 / 机匣
  blued: [ 46,  50,  58],  // 发蓝钢暗部：管箍 / 肋条 / 护圈
  steel: [148, 150, 157],  // 抛光钢：扳机 / 击锤 / 保险
  std:   [ 96,  98, 104],  // 钢暗部
  wood:  [132,  84,  44],  // 胡桃木：前托 / 枪托
  woodl: [164, 110,  62],  // 木质亮部
  woodd: [ 88,  54,  28],  // 木质暗部 / 格纹
  blk:   [ 30,  30,  32],  // 黑件：托底板
  brass: [176, 132,  52],  // 黄铜：管口 / 铰链销
  red:   [148,  44,  36],  // 霰弹壳身
  dk:    [ 14,  14,  16],  // 膛口 / 缝隙 / 暗腔
};

const SHADE = { up: 1.14, down: 0.60, north: 1.00, south: 0.86, east: 0.94, west: 0.80 };

const cubes = [];

function box(bone, a, b, mat, rot, pivot) {
  const lo = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.min(a[2], b[2])];
  const hi = [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.max(a[2], b[2])];
  const c = { bone, origin: lo, size: [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]], mat };
  if (rot && rot.some((v) => v !== 0)) {
    c.rot = rot;
    c.pivot = pivot || [lo[0], lo[1], lo[2]];
  }
  cubes.push(c);
}

/* 圆柱：**实心芯 + 外圈棱**（只贴一圈壳会变成镂空管 —— v3 的教训，用户一眼就看出来了） */
const CORE = 0.66;
function tubeZ(bone, x, y, z0, z1, r, n, mat) {
  box(bone, [x - r * CORE, y - r * CORE, z0], [x + r * CORE, y + r * CORE, z1], mat);
  const dz = (z1 - z0) / n;
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * Math.PI * 2;
    const a1 = ((i + 1) / n) * Math.PI * 2;
    const am = (a0 + a1) / 2;
    const ex = Math.cos(am) * r;
    const ey = Math.sin(am) * r;
    const ix = Math.cos(am) * r * CORE;
    const iy = Math.sin(am) * r * CORE;
    const w = Math.max(0.045, Math.abs(Math.sin((a1 - a0) / 2)) * r * 2 * 0.62);
    box(bone,
      [x + Math.min(ix, ex) - w / 2, y + Math.min(iy, ey) - w / 2, z0 + i * dz],
      [x + Math.max(ix, ex) + w / 2, y + Math.max(iy, ey) + w / 2, z0 + (i + 1) * dz],
      mat);
  }
}

/* ================================================================ 1. 并排双管 */
for (const sx of [-1, 1]) {
  const cx = sx * BORE_GAP;
  tubeZ('barrel', cx, TUBE_Y, TUBE_Z0, TUBE_Z1, BORE_R, 8, 'blue');
  // 管口的膛口（黑洞）—— 真枪管壁是实心的，洞只在膛口这一小截
  box('barrel', [cx - BORE_R * 0.78, TUBE_Y - BORE_R * 0.78, TUBE_Z0 - 0.012],
    [cx + BORE_R * 0.78, TUBE_Y + BORE_R * 0.78, TUBE_Z0 + 0.05], 'dk');
  box('barrel', [cx - BORE_R - 0.012, TUBE_Y - BORE_R - 0.012, TUBE_Z0 - 0.02],
    [cx + BORE_R + 0.012, TUBE_Y + BORE_R + 0.012, TUBE_Z0 + 0.08], 'brass');
}
// 两管之间的瞄准肋（真枪是一条扁肋，末端一颗小准星珠）
box('barrel', [-0.055, TUBE_Y + BORE_R - 0.02, TUBE_Z0 + 0.10],
  [0.055, TUBE_Y + BORE_R + 0.055, TUBE_Z1 - 1.10], 'blued');
box('barrel', [-0.038, TUBE_Y + BORE_R + 0.055, TUBE_Z0 + 0.22],
  [0.038, TUBE_Y + BORE_R + 0.155, TUBE_Z0 + 0.36], 'steel');

/* ================================================================ 2. 前托（胡桃木包住双管）
 * 真枪前托约占管长的 后半 2/3，前端有一个金属帽。横截面是 "8" 字形。 */
const FORE_Z0 = TUBE_Z0 + LEN_BARREL * 0.34;
const FORE_Z1 = TUBE_Z1 - 0.06;
const FW = 0.075;   // 木壳厚度
for (const sx of [-1, 1]) {
  const cx = sx * BORE_GAP;
  // 主体：从管底包到管轴上方
  box('forend', [cx - BORE_R - FW, TUBE_Y - BORE_R - FW, FORE_Z0],
    [cx + BORE_R + FW, TUBE_Y + BORE_R * 0.18, FORE_Z1], 'wood');
  // 上唇：两侧各一条，夹到管轴上方
  box('forend', [cx - BORE_R - FW, TUBE_Y + BORE_R * 0.18, FORE_Z0],
    [cx - BORE_R + 0.055, TUBE_Y + BORE_R * 0.80, FORE_Z1], 'woodl');
  box('forend', [cx + BORE_R - 0.055, TUBE_Y + BORE_R * 0.18, FORE_Z0],
    [cx + BORE_R + FW, TUBE_Y + BORE_R * 0.80, FORE_Z1], 'woodl');
}
// 两管之间的槽底（把左右两半连成整体）
box('forend', [-BORE_GAP + 0.05, TUBE_Y - BORE_R - FW, FORE_Z0],
  [BORE_GAP - 0.05, TUBE_Y - BORE_R * 0.35, FORE_Z1], 'woodd');
// 前端金属帽 + 背带环
box('forend', [-BORE_GAP - BORE_R - FW - 0.015, TUBE_Y - BORE_R - FW - 0.015, FORE_Z0 - 0.09],
  [BORE_GAP + BORE_R + FW + 0.015, TUBE_Y + BORE_R * 0.62, FORE_Z0], 'blued');
box('forend', [0, TUBE_Y - BORE_R - FW - 0.13, FORE_Z0 + 0.34],
  [0.05, TUBE_Y - BORE_R - FW, FORE_Z0 + 0.58], 'steel');

/* ================================================================ 3. 机匣（箱式，立式块） */
box('body', [-RECV_W / 2, RECV_Y0, RECV_Z0], [RECV_W / 2, RECV_Y1, RECV_Z1], 'blue');
// 后膛面（前端立板，管从这里出来）
box('body', [-RECV_W / 2 - 0.012, RECV_Y0 + 0.05, RECV_Z0 - 0.03],
  [RECV_W / 2 + 0.012, RECV_Y1 - 0.02, RECV_Z0 + 0.07], 'blued');
// 机匣顶脊（1878 的顶面有一条脊，双锤从后面露出来）
box('body', [-0.11, RECV_Y1, RECV_Z0 + 0.15], [0.11, RECV_Y1 + 0.075, RECV_Z1 - 0.10], 'blued');
// 侧面加工面（两条浅槽）
box('body', [-RECV_W / 2 - 0.006, RECV_Y0 + 0.26, RECV_Z0 + 0.50],
  [-RECV_W / 2 + 0.02, RECV_Y0 + 0.52, RECV_Z1 - 0.18], 'blued');
box('body', [RECV_W / 2 - 0.02, RECV_Y0 + 0.26, RECV_Z0 + 0.50],
  [RECV_W / 2 + 0.006, RECV_Y0 + 0.52, RECV_Z1 - 0.18], 'blued');
// 开膛杆（1878 的顶杆，向后拨开膛）
box('latch', [-0.055, RECV_Y1 + 0.075, RECV_Z0 + 0.22], [0.055, RECV_Y1 + 0.14, RECV_Z1 - 0.30], 'steel');

/* ================================================================ 4. 双外露击锤（1878 的标志） */
for (const sx of [-1, 1]) {
  const cx = sx * 0.155;
  box('hammer_l', [cx - 0.045, RECV_Y1 + 0.02, RECV_Z1 - 0.42], [cx + 0.045, RECV_Y1 + 0.20, RECV_Z1 - 0.24], 'steel');
  box('hammer_l', [cx - 0.035, RECV_Y1 + 0.18, RECV_Z1 - 0.40], [cx + 0.035, RECV_Y1 + 0.29, RECV_Z1 - 0.22], 'std');
}

/* ================================================================ 5. 握把（托颈，下垂连接机匣与托） */
const GRIP_SEGS = 5;
for (let i = 0; i < GRIP_SEGS; i++) {
  const t0 = i / GRIP_SEGS;
  const t1 = (i + 1) / GRIP_SEGS;
  const z0 = RECV_Z1 + t0 * 0.42;
  const z1 = RECV_Z1 + t1 * 0.42;
  const yTop = RECV_Y1 - 0.02 - t0 * 0.10;
  const yBot = RECV_Y0 + 0.12 + t0 * 0.22;
  box('body', [-RECV_W / 2 - 0.03, yBot, z0], [RECV_W / 2 + 0.03, yTop, z1], 'wood');
  box('body', [-RECV_W / 2 - 0.04, yBot, z0], [RECV_W / 2 + 0.04, yBot + 0.07, z1], 'woodd');
}

/* ================================================================ 6. 枪托（下垂的厚木板）
 * 逐段往后 + 往下（总下垂 DROP = 60mm），每段给自己一点 cube 级 rotation 让台阶连成斜线。
 * 规范禁的是**骨骼**旋转，cube 的 rotation 允许（s686 的托底垫、m1 的护木弧都这么做）。 */
const SEGS = 8;
const STK_Z0 = RECV_Z1 + 0.42;
for (let i = 0; i < SEGS; i++) {
  const t0 = i / SEGS;
  const t1 = (i + 1) / SEGS;
  const z0 = STK_Z0 + t0 * (STOCK_Z1 - STK_Z0);
  const z1 = STK_Z0 + t1 * (STOCK_Z1 - STK_Z0);
  const d0 = DROP * t0;
  const d1 = DROP * t1;
  // 托的上下缘：真枪托腹在下垂的同时略微收窄
  const yTop = RECV_Y1 - 0.20 - d0;
  const yBot = RECV_Y0 + 0.30 - d0 - t0 * 0.10;
  const droop = -Math.atan2(d1 - d0, z1 - z0) * 180 / Math.PI;
  box('body', [-RECV_W / 2 - 0.02, yBot, z0], [RECV_W / 2 + 0.02, yTop, z1], 'wood', [droop, 0, 0], [0, yTop, z0]);
  box('body', [-RECV_W / 2 - 0.03, yBot, z0], [RECV_W / 2 + 0.03, yBot + 0.075, z1], 'woodd', [droop, 0, 0], [0, yTop, z0]);
}
// 托颈格纹（真枪上的防滑格，三道）
for (let i = 0; i < 3; i++) {
  const t = 0.10 + i * 0.14;
  const z = STK_Z0 + t * (STOCK_Z1 - STK_Z0);
  const d = DROP * t;
  box('body', [-RECV_W / 2 - 0.035, RECV_Y1 - 0.24 - d, z], [RECV_W / 2 + 0.035, RECV_Y1 - 0.06 - d, z + 0.07], 'woodd');
}
// 托底板（跟下垂角）
box('body', [-RECV_W / 2 - 0.02, RECV_Y1 - 0.21 - DROP, STOCK_Z1],
  [RECV_W / 2 + 0.02, RECV_Y0 + 0.19 - DROP, STOCK_Z1 + 0.075], 'blk');
box('body', [-RECV_W / 2 - 0.01, RECV_Y1 - 0.22 - DROP, STOCK_Z1 + 0.075],
  [RECV_W / 2 + 0.01, RECV_Y0 + 0.20 - DROP, STOCK_Z1 + 0.125], 'std');

/* ================================================================ 7. 双扳机 + 护圈（机匣下方） */
box('trigger_front', [-0.022, RECV_Y0 - 0.165, RECV_Z0 + 0.62], [0.022, RECV_Y0 - 0.005, RECV_Z0 + 0.685], 'steel');
box('trigger_rear', [-0.022, RECV_Y0 - 0.150, RECV_Z0 + 0.72], [0.022, RECV_Y0 - 0.005, RECV_Z0 + 0.785], 'steel');
box('body', [-0.038, RECV_Y0 - 0.205, RECV_Z0 + 0.57], [0.038, RECV_Y0 - 0.165, RECV_Z0 + 0.84], 'blued');
box('body', [-0.038, RECV_Y0 - 0.165, RECV_Z0 + 0.79], [0.038, RECV_Y0 - 0.09, RECV_Z0 + 0.84], 'blued');

/* ================================================================ 8. 左手 / 待装子弹（平时隐藏） */
box('hand_l', [-0.14, TUBE_Y - 0.62, FORE_Z1 - 0.70], [0.14, TUBE_Y - 0.30, FORE_Z1 - 0.28], 'woodd');
for (const dx of [-BORE_GAP, BORE_GAP]) {
  box('bolt_loaded', [dx - 0.055, TUBE_Y - 0.055, RECV_Z0 + 0.14], [dx + 0.055, TUBE_Y + 0.055, RECV_Z0 + 0.30], 'red');
  box('bolt_loaded', [dx - 0.062, TUBE_Y - 0.062, RECV_Z0 + 0.06], [dx + 0.062, TUBE_Y + 0.062, RECV_Z0 + 0.14], 'brass');
}

/* ================================================================ 骨骼 */
const bones = [
  { name: 'root', pivot: [0, RECV_Y0, STOCK_Z1 - 0.4] },
  { name: 'move', parent: 'root', pivot: [0, RECV_Y0, STOCK_Z1 - 0.4] },
  { name: 'body', parent: 'move', pivot: [0, 0, 0] },
  { name: 'barrel', parent: 'body', pivot: HINGE },
  { name: 'forend', parent: 'barrel', pivot: [0, TUBE_Y - 0.3, FORE_Z0] },
  { name: 'shell_upper', parent: 'barrel', pivot: [0, TUBE_Y, TUBE_Z1] },
  { name: 'latch', parent: 'body', pivot: [0, RECV_Y1 + 0.10, RECV_Z1 - 0.30] },
  { name: 'hammer_l', parent: 'body', pivot: [0, RECV_Y1 + 0.10, RECV_Z1 - 0.33] },
  { name: 'trigger_front', parent: 'body', pivot: [0, RECV_Y0, RECV_Z0 + 0.65] },
  { name: 'trigger_rear', parent: 'body', pivot: [0, RECV_Y0, RECV_Z0 + 0.75] },
  { name: 'hand_l', parent: 'body', pivot: [0, TUBE_Y - 0.46, FORE_Z1 - 0.49] },
  { name: 'bolt_loaded', parent: 'body', pivot: [0, TUBE_Y, RECV_Z0 + 0.22] },
];

/* ================================================================ 自检 */
const fails = [];
if (cubes.length > 600) fails.push(`方块 ${cubes.length} > 600`);
if (bones.length > 40) fails.push(`骨骼 ${bones.length} > 40`);
const boneNames = new Set(bones.map((b) => b.name));
for (const c of cubes) {
  if (!boneNames.has(c.bone)) fails.push(`方块归属骨不存在: ${c.bone}`);
  for (let i = 0; i < 3; i++) {
    if (!(c.size[i] > 0)) fails.push(`尺寸非法 ${c.bone} size[${i}]=${c.size[i]}`);
  }
}
let lo = [Infinity, Infinity, Infinity];
let hi = [-Infinity, -Infinity, -Infinity];
for (const c of cubes) {
  for (let i = 0; i < 3; i++) {
    lo[i] = Math.min(lo[i], c.origin[i]);
    hi[i] = Math.max(hi[i], c.origin[i] + c.size[i]);
  }
}
const lenZ = hi[2] - lo[2];
const widX = hi[0] - lo[0];
const heiY = hi[1] - lo[1];
if (lenZ < 0.9 * 16 || lenZ > 2.6 * 16) fails.push(`长 ${lenZ.toFixed(2)}u 超出 0.9~2.6 格`);
if (Math.abs(widX - 0.72) > 0.35) fails.push(`宽 ${widX.toFixed(2)}u 与真枪机匣宽 0.72u 差太多`);

module.exports = {
  cubes, bones, MAT, SHADE, HINGE, BORE_GAP, BORE_R, TUBE_Y, TUBE_Z0, TUBE_Z1, fails,
  stats: { total: cubes.length, lenZ, widX, heiY },
};

if (require.main === module) {
  const tot = LEN_BARREL + LEN_RECV + LEN_STOCK;
  console.log(`方块 ${cubes.length} / 骨骼 ${bones.length}`);
  console.log(`长(Z) ${lenZ.toFixed(2)} u = ${(lenZ / 16).toFixed(2)} 格   宽(X) ${widX.toFixed(2)} u   高(Y) ${heiY.toFixed(2)} u`);
  console.log(`分段（真枪 Colt 1878 Coach 20"）: 管 ${(LEN_BARREL / tot * 100).toFixed(0)}%  `
    + `机匣 ${(LEN_RECV / tot * 100).toFixed(0)}%  托 ${(LEN_STOCK / tot * 100).toFixed(0)}%`);
  console.log(`管外径 ${(BORE_R * 2).toFixed(3)} u = ${(BORE_R * 2 / MM).toFixed(1)} mm（真枪 22mm）`);
  console.log(`托垂直下垂 ${DROP.toFixed(2)} u = ${(DROP / MM).toFixed(0)} mm（真枪 60mm）`);
  console.log(fails.length ? `*** 自检失败:\n  ${fails.join('\n  ')}` : '自检: 全部通过');
}
