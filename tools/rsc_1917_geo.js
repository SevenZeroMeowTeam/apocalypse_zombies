'use strict';
/* ============================================================================
 * RSC M1917（法国 Fusil Automatique Modèle 1917 半自动步枪）—— 几何定义 v1
 *
 * 真枪：8mm 勒贝尔口径 · 导气长行程活塞 · 5 发漏夹**从下方**插进固定弹匣 ·
 *       弹匣盖铰链在**前端**（向前下方敞开）· 旋转闭锁枪机 · 拉机柄在机匣**右侧**、
 *       只沿枪轴平移不旋转 · **空仓不挂机**（M1918 才挂机）· 全长 1331 mm。
 *
 * 参考图量取（art/rsc_1917/ref_rsc1917_side.png，Wikimedia「RSC Mle 1917 (no BG)」，
 * CC BY-SA 3.0，仅用于量取不进包；量取脚本与中间表在 art/rsc_1917/ 与 scratch 里）：
 *   剪影 2599 px = 1331 mm  →  0.5121 mm/px；先按枪管/前托上下缘拟合倾角转正；
 *   膛线轴以枪口断面中点为基准（枪口是圆的，上下对称）；
 *   逐列 top/bot 表 -> art/rsc_1917/profile.json，本文件的形面数字全部由它换算。
 *
 * 铁律（美术规范.md 第一节 / Agent_Java.md 第零节）：
 *   16 u = 1 方块 = 1 m ⇒ 1 u = 62.5 mm；枪口 = **−Z** | 上 = +Y | +X = 射手右侧（编辑器坐标，
 *   导出时由 GeckoLib 插件统一沿 X 取反 —— 与其它枪同一套口径）；骨骼**零旋转**；
 *   方块 ≤ 600 / 骨骼 ≤ 40；逐面 UV，密度 11~13 px/u；贴图 512²。
 *
 * 原点（= 机匣中心 / Java 侧 WeaponMount 的基准点）：
 *   Y = 0 取**膛线轴**（子弹、准星、瞄准线全部以它为基准，量取也最直接）
 *   Z = 0 取**扳机位置**（距枪口 16.00 u = 1000 mm；手持旋转轴就在这附近）
 *   ⇒ 枪口 Z = −16.00、托底 Z = +5.30、全长 21.30 u（规范区间 12~24 u ✓，莫辛 22.9 / AWM 24.0）
 * ========================================================================== */

/* 16 u = 1 方块 = 1 m ⇒ 1 u = 6.25 cm = 62.5 mm（别写成 1/6.25 —— 会把整枪放大 10 倍） */
const MM = 16 / 1000;
const U = 1 / MM;                  // u -> mm，写注释用

/* ---------------------------------------------------------------- 纵向基准 */
const Z_MUZZLE = -16.00;           // 枪口（量取：全长 21.30 u）
const Z_BUTT = +5.30;              // 托底板外缘
const Y_BORE = 0;                  // 膛线轴

/* 量取出来的分段（z 从枪口起算 -> 模型 Z 坐标，u）
 * 材料分段来自 profile.json：裸管 / 前托木 / 机匣金属 / 托木 */
const Z_FRONT_BAND = -12.90;       // 前枪箍（含背带环）后缘  ← 量取 z 193 mm
const Z_ROD_END = -13.90;          // 拖曳杆（刺刀座）后端      ← 量取 z 131 mm
const Z_FORE_A = -8.48;            // 前托木前端                ← 量取 z 470 mm
const Z_FORE_B = -3.12;            // 前托木后端                ← 量取 z 805 mm
const Z_BAND2_A = -4.78;           // 前托中段枪箍（含背带环）  ← 量取 z 700 mm
const Z_BAND2_B = -4.26;
const Z_RECV_A = -2.72;            // 机匣前端面（枪管入匣处）  ← 量取 z 830 mm
const Z_RECV_B = +2.08;            // 机匣后端（含节套）        ← 量取 z 1130 mm
const Z_TANG_B = +2.62;            // 节套/机匣尾板
const Z_MAG_A = -1.18;             // 弹匣箱前壁（漏夹 8mm 勒贝尔全长 70.6mm = 1.13u）
const Z_MAG_B = -0.02;             // 弹匣箱后壁
const Z_GUARD_B = +0.66;           // 扳机护圈后缘

/* 横向（侧视量不到，按真枪规格）：机匣 35mm / 木托 45mm / 枪管 24mm / 弹匣箱 30mm */
const RECV_W = 35 * MM;            // 0.56 u（半宽 0.28）
const WOOD_W = 45 * MM;            // 0.72 u（半宽 0.36 —— 木托比机匣略宽，真枪如此）
const BARREL_R = (24 / 2) * MM;    // 枪管外半径 0.192 u
const BORE_R = (8 / 2) * MM;       // 阳线半径 0.064 u（膛口黑洞）
const MAG_W = 30 * MM;             // 0.48 u

/* 量取出的竖直轮廓（相对膛线轴，已按枪口断面标定修正约 +0.10 u 的系统偏差） */
const Y_RECV_TOP = +0.36;          // 机匣顶面 ≈ 轴上 22.5 mm
const Y_SIGHT_TOP = +0.50;         // 照门座顶 ≈ 轴上 31 mm（瞄准线基准）
const Y_FORE_TOP = +0.42;          // 前托上手木顶 ≈ 轴上 26 mm
const Y_FORE_BOT = -0.56;          // 前托底 ≈ 轴下 35 mm
const Y_MAG_BOT = -1.50;           // 弹匣箱底 ≈ 轴下 94 mm（量取 −90~−96）
const Y_BUTT_BOT = -1.88;          // 托底 ≈ 轴下 117 mm
const Y_WRIST_TOP = -0.34;         // 托颈顶 ≈ 轴下 21 mm

/** 材质调色板 —— 发蓝钢 + 胡桃木 + 黄铜（美术规范.md 第三节） */
const MAT = {
  blued: [ 58,  62,  72],  // 暗发蓝钢：枪管 / 机匣 / 枪箍
  steel: [ 96, 100, 108],  // 钢：机匣侧面 / 弹匣箱 / 盖
  pol:   [156, 158, 164],  // 抛光钢：枪机 / 拉机柄 / 扳机 / 准星 / 表尺
  dark:  [ 34,  36,  42],  // 膛口 / 缝 / 暗腔 / 抛壳口
  wood:  [124,  78,  40],  // 胡桃木：前托 / 枪托
  woodl: [158, 106,  58],  // 木亮部（上棱 / 倒角）
  woodd: [ 86,  52,  26],  // 木暗部（下棱 / 格纹 / 槽）
  brass: [172, 128,  54],  // 黄铜弹壳
  copper:[166, 106,  60],  // 弹头被甲
  lead:  [138, 138, 144],  // 弹芯 / 钢芯件
};

const SHADE = { up: 1.14, down: 0.58, north: 1.00, south: 0.86, east: 0.94, west: 0.80 };

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

/** 圆柱（沿 Z）：**实心芯 + 外圈棱**——只贴一圈壳会变成镂空管（短管喷踩过的坑）。
 *  CORE 是芯的半宽比例：0.66 时从外面看是完整柱面，同时又不会在正侧面露出缝。 */
const CORE = 0.68;
function tubeZ(bone, cx, cy, z0, z1, r, n, mat, coreScale) {
  const core = r * (coreScale === undefined ? CORE : coreScale);
  box(bone, [cx - core, cy - core, z0], [cx + core, cy + core, z1], mat);
  const dz = (z1 - z0) / n;
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * Math.PI * 2;
    const a1 = ((i + 1) / n) * Math.PI * 2;
    const am = (a0 + a1) / 2;
    const ex = Math.cos(am) * r;
    const ey = Math.sin(am) * r;
    const ix = Math.cos(am) * core;
    const iy = Math.sin(am) * core;
    const w = Math.max(0.045, Math.abs(Math.sin((a1 - a0) / 2)) * r * 2 * 0.62);
    box(bone,
      [cx + Math.min(ix, ex) - w / 2, cy + Math.min(iy, ey) - w / 2, z0 + i * dz],
      [cx + Math.max(ix, ex) + w / 2, cy + Math.max(iy, ey) + w / 2, z0 + (i + 1) * dz],
      mat);
  }
}

/** 枪箍 / 环（沿 Z 的一圈金属）：n 段环壳 + 上下左右四个方向的实心块，套在枪管外 */
function band(bone, cx, cy, z0, z1, rIn, rOut, n, mat) {
  const dz = (z1 - z0) / n;
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * Math.PI * 2;
    const a1 = ((i + 1) / n) * Math.PI * 2;
    const am = (a0 + a1) / 2;
    /* 每段环壳用"从内半径到外半径"的一个盒子表示，位置取该段中角方向的半径中点 */
    const rm = (rIn + rOut) / 2;
    const w = Math.max(0.05, Math.abs(Math.sin((a1 - a0) / 2)) * rOut * 2 * 0.62);
    box(bone,
      [cx + Math.cos(am) * rm - w / 2, cy + Math.sin(am) * rm - w / 2, z0 + i * dz],
      [cx + Math.cos(am) * rm + w / 2, cy + Math.sin(am) * rm + w / 2, z0 + (i + 1) * dz],
      mat);
  }
}

/* ================================================================ 1. 枪管组（bone: barrel）
 * 量取：0~470 mm 是裸管（含准星座、拖曳杆、前枪箍），470 mm 往后被前托木包住。 */
tubeZ('barrel', 0, Y_BORE, Z_MUZZLE, Z_RECV_A, BARREL_R, 10, 'blued');
/* 膛口：外圈一圈抛光钢 + 里面黑洞（真枪从枪口能看到膛线，这里只做一个黑洞够看） */
box('barrel', [-BARREL_R - 0.015, Y_BORE - BARREL_R - 0.015, Z_MUZZLE - 0.03],
  [BARREL_R + 0.015, Y_BORE + BARREL_R + 0.015, Z_MUZZLE + 0.06], 'pol');
box('barrel', [-BORE_R * 1.4, Y_BORE - BORE_R * 1.4, Z_MUZZLE],
  [BORE_R * 1.4, Y_BORE + BORE_R * 1.4, Z_MUZZLE + 0.11], 'dark');
/* 弹膛段：枪管后段略粗（真枪弹膛外径大一圈），从机匣前端往前的 1.3 u */
tubeZ('barrel', 0, Y_BORE, Z_RECV_A - 1.30, Z_RECV_A, BARREL_R * 1.10, 10, 'blued');

/* 前准星：底座是枪管上的一条斜面楔，刃片插在中间（量取：刃尖 ≈ 轴上 22 mm） */
box('barrel', [-0.055, Y_BORE + BARREL_R - 0.05, Z_MUZZLE + 0.20],
  [0.055, Y_BORE + BARREL_R + 0.085, Z_MUZZLE + 0.60], 'blued');
box('barrel', [-0.040, Y_BORE + BARREL_R + 0.06, Z_MUZZLE + 0.30],
  [0.040, Y_BORE + BARREL_R + 0.235, Z_MUZZLE + 0.48], 'pol');   // 刃片
/* 准星护耳（真枪有一对侧翼，防止磕碰） */
for (const sx of [-1, 1]) {
  box('barrel', [sx * 0.085 - 0.018, Y_BORE + BARREL_R - 0.02, Z_MUZZLE + 0.24],
    [sx * 0.085 + 0.018, Y_BORE + BARREL_R + 0.20, Z_MUZZLE + 0.66], 'blued');
}

/* 拖曳杆 / 刺刀座（Lebel 件沿用）：枪管**下方**一根杆，从枪口一直到前枪箍
 *   量取：轴下 −0.42 u（≈26 mm），杆径 14 mm → 半径 0.11 u */
tubeZ('barrel', 0, Y_BORE - 0.30, Z_MUZZLE - 0.02, Z_ROD_END + 0.25, 0.105, 8, 'blued');
box('barrel', [-0.105, Y_BORE - 0.45, Z_ROD_END + 0.10],
  [0.105, Y_BORE - 0.16, Z_ROD_END + 0.45], 'steel');            // 刺刀座本体
box('barrel', [-0.055, Y_BORE - 0.30, Z_ROD_END + 0.45],
  [0.055, Y_BORE - 0.22, Z_ROD_END + 1.10], 'blued');            // 杆与枪管之间的吊挂

/* 前枪箍（量取 z 193 mm；带背带环）：环套住枪管 + 拖曳杆 */
band('barrel', 0, Y_BORE - 0.08, Z_FRONT_BAND, Z_FRONT_BAND + 0.30, 0.20, 0.245, 10, 'steel');
box('barrel', [-0.235, Y_BORE - 0.42, Z_FRONT_BAND + 0.02],
  [0.235, Y_BORE + 0.26, Z_FRONT_BAND + 0.28], 'blued');         // 箍的实心环体
/* 背带环（下面一个金属环，量取：轴下 −0.65 u） */
box('barrel', [-0.075, Y_BORE - 0.72, Z_FRONT_BAND + 0.04],
  [0.075, Y_BORE - 0.62, Z_FRONT_BAND + 0.26], 'steel');
for (const sx of [-1, 1]) {
  box('barrel', [sx * 0.075 - 0.018, Y_BORE - 0.66, Z_FRONT_BAND + 0.04],
    [sx * 0.075 + 0.018, Y_BORE - 0.42, Z_FRONT_BAND + 0.26], 'steel');
}

/* 导气管（长行程活塞的导管，真枪是 Lebel 弹管改造）：枪管下方一根细管，
 * 从前枪箍一直通到机匣；前托木（Z_FORE_A 起）之后被木头包住，只画前面露出来的一段。 */
tubeZ('barrel', 0, Y_BORE - 0.275, Z_FRONT_BAND + 0.28, Z_RECV_A, 0.093, 8, 'blued');
tubeZ('barrel', 0, Y_BORE - 0.275, Z_FRONT_BAND + 0.24, Z_FRONT_BAND + 0.36, 0.125, 8, 'steel');
/* 导气箍（枪管与导气管之间的一小块，固定管子） */
box('barrel', [-0.075, Y_BORE - 0.34, Z_RECV_A - 1.55], [0.075, Y_BORE - 0.16, Z_RECV_A - 1.25], 'blued');

/* ================================================================ 2. 前托（bone: forend）
 * 量取：木头 z 470~805 mm（Z −8.48 ~ −3.12），木宽 45 mm（半宽 0.36 的一半 0.225）；
 * 上手木（handguard）盖在枪管上方，两侧下托木包住枪管与导气管。 */
const FW = 0.225;                  // 前托木半宽
/* 两侧下托木（包住枪管下缘到导气管下方） */
for (const sx of [-1, 1]) {
  box('forend', [sx * FW - (sx > 0 ? 0 : 0.055), Y_FORE_BOT, Z_FORE_A],
    [sx * FW + (sx > 0 ? 0.055 : 0), Y_BORE + 0.10, Z_FORE_B], 'wood');
}
/* 下托木的底（把两侧连起来，中间留导气管的槽） */
box('forend', [-FW, Y_FORE_BOT, Z_FORE_A], [FW, Y_BORE - 0.40, Z_FORE_B] , 'woodd');
/* 上手木（枪管上方的木盖，量取顶 ≈ 轴上 26 mm） */
box('forend', [-0.195, Y_BORE + 0.16, Z_FORE_A + 0.02], [0.195, Y_FORE_TOP, Z_FORE_B], 'wood');
box('forend', [-0.150, Y_FORE_TOP, Z_FORE_A + 0.10], [0.150, Y_FORE_TOP + 0.045, Z_FORE_B - 0.05], 'woodl');
/* 上/下木之间的分缝（真枪看得见一条槽，压暗一点当阴影） */
for (const sx of [-1, 1]) {
  box('forend', [sx * 0.196 - 0.012, Y_BORE + 0.06, Z_FORE_A + 0.06],
    [sx * 0.196 + 0.012, Y_BORE + 0.17, Z_FORE_B - 0.06], 'woodd');
}
/* 前托前端金属帽（箍住木头前端） */
box('forend', [-FW - 0.015, Y_FORE_BOT - 0.02, Z_FORE_A - 0.16],
  [FW + 0.015, Y_FORE_TOP + 0.03, Z_FORE_A + 0.02], 'blued');
/* 中段枪箍 + 背带环（量取 z 700 mm，轴下 −0.86 u 的环） */
band('forend', 0, Y_BORE - 0.10, Z_BAND2_A, Z_BAND2_B, 0.24, 0.275, 10, 'steel');
box('forend', [-FW - 0.02, Y_FORE_BOT - 0.03, Z_BAND2_A + 0.01],
  [FW + 0.02, Y_FORE_TOP + 0.02, Z_BAND2_B - 0.01], 'blued');
box('forend', [-0.075, Y_FORE_BOT - 0.30, Z_BAND2_A + 0.04], [0.075, Y_FORE_BOT - 0.10, Z_BAND2_B - 0.04], 'steel');
for (const sx of [-1, 1]) {
  box('forend', [sx * 0.075 - 0.018, Y_FORE_BOT - 0.24, Z_BAND2_A + 0.04],
    [sx * 0.075 + 0.018, Y_FORE_BOT, Z_BAND2_B - 0.04], 'steel');
}
/* 前托的托底螺丝 + 前背带环（真枪在木头前段还有一颗穿钉） */
box('forend', [-FW - 0.012, Y_BORE - 0.32, Z_FORE_B - 0.55], [FW + 0.012, Y_BORE - 0.24, Z_FORE_B - 0.45], 'pol');

/* ================================================================ 3. 机匣（bone: body）
 * 量取 z 830~1130 mm（Z −2.72 ~ +2.08），机匣顶面 ≈ 轴上 22.5 mm。 */
/* 前端套环（枪管拧进机匣的地方，比机匣本体略宽） */
box('body', [-0.30, Y_BORE - 0.30, Z_RECV_A], [0.30, Y_BORE + 0.31, Z_RECV_A + 0.35], 'blued');
box('body', [-0.325, Y_BORE - 0.26, Z_RECV_A + 0.05], [0.325, Y_BORE + 0.27, Z_RECV_A + 0.20], 'steel');
/* 机匣本体 */
box('body', [-RECV_W / 2, Y_BORE - 0.30, Z_RECV_A + 0.35], [RECV_W / 2, Y_BORE + 0.34, Z_RECV_B], 'steel');
/* 抛壳口（射手右侧 = +X）：机匣右侧开一个凹腔，平时被枪机盖住 */
box('body', [RECV_W / 2 - 0.06, Y_BORE + 0.05, Z_RECV_A + 1.15],
  [RECV_W / 2 + 0.006, Y_BORE + 0.40, Z_RECV_A + 2.20], 'dark');
/* 机匣顶面的枪机通道（一条浅槽，两侧留导轨） */
box('body', [-0.245, Y_BORE + 0.34, Z_RECV_A + 0.35], [0.245, Y_RECV_TOP, Z_RECV_B], 'blued');
box('body', [-0.275, Y_BORE + 0.30, Z_RECV_A + 0.30], [0.275, Y_BORE + 0.375, Z_RECV_B], 'steel');
/* 机匣两侧的加工凸台（真枪机匣侧面有一圈加强台） */
for (const sx of [-1, 1]) {
  box('body', [sx * (RECV_W / 2 - 0.005) - 0.012, Y_BORE - 0.22, Z_RECV_A + 0.55],
    [sx * (RECV_W / 2 - 0.005) + 0.012, Y_BORE + 0.26, Z_RECV_B - 0.30], 'blued');
}
/* 节套/尾板（机匣后端，接枪托颈） */
box('body', [-0.22, Y_BORE - 0.30, Z_RECV_B], [0.22, Y_BORE + 0.32, Z_TANG_B], 'steel');
box('body', [-0.16, Y_BORE + 0.32, Z_RECV_B - 0.10], [0.16, Y_BORE + 0.42, Z_TANG_B], 'blued');   // 尾榫上脊

/* 照门（真枪是机匣前上方的立框式表尺，量取顶 ≈ 轴上 31 mm） */
box('body', [-0.105, Y_RECV_TOP, Z_RECV_A + 0.42], [0.105, Y_SIGHT_TOP, Z_RECV_A + 1.06], 'blued');
for (const sx of [-1, 1]) {                         // 立框侧板
  box('body', [sx * 0.105 - 0.016, Y_SIGHT_TOP, Z_RECV_A + 0.46],
    [sx * 0.105 + 0.016, Y_SIGHT_TOP + 0.12, Z_RECV_A + 1.02], 'steel');
}
box('body', [-0.09, Y_SIGHT_TOP + 0.10, Z_RECV_A + 0.50], [0.09, Y_SIGHT_TOP + 0.155, Z_RECV_A + 0.98], 'pol'); // 表尺滑块
box('body', [-0.078, Y_SIGHT_TOP + 0.15, Z_RECV_A + 0.56], [0.078, Y_SIGHT_TOP + 0.20, Z_RECV_A + 0.62], 'dark'); // 缺口
/* 准星/照门之间的瞄准线基准：抛壳口上方的护板 */
box('body', [-0.245, Y_RECV_TOP, Z_RECV_A + 1.15], [0.245, Y_RECV_TOP + 0.02, Z_RECV_A + 2.20], 'steel');

/* 手动保险（真枪在机匣**左侧**、尾板前上方）：一片可拨的扁杠杆 */
box('body', [-0.30, Y_BORE + 0.05, Z_RECV_B - 0.55], [-0.24, Y_BORE + 0.24, Z_RECV_B - 0.10], 'steel');
/* 枪机卡榫（机匣左后侧的解脱钮） */
box('body', [-0.30, Y_BORE + 0.02, Z_RECV_B - 0.28], [-0.25, Y_BORE + 0.18, Z_RECV_B + 0.02], 'pol');

/* ================================================================ 4. 可拆钢盖（bone: cover）
 * 真枪：一片扣在机匣上方的钢盖，前方一颗卡榫，向后推开就能取下（野战分解）。 */
const COVER_Y = Y_RECV_TOP + 0.015;
box('body', [-0.235, COVER_Y, Z_RECV_A + 0.30], [0.235, COVER_Y + 0.105, Z_RECV_B - 0.05], 'steel');
box('body', [-0.215, COVER_Y + 0.105, Z_RECV_A + 0.40], [0.215, COVER_Y + 0.145, Z_RECV_B - 0.15], 'blued');
/* 盖上的加强筋与铆钉（真枪盖面有一道中脊） */
box('body', [-0.06, COVER_Y + 0.145, Z_RECV_A + 0.45], [0.06, COVER_Y + 0.175, Z_RECV_B - 0.20], 'steel');
for (let i = 0; i < 5; i++) {
  const z = Z_RECV_A + 0.55 + i * 0.62;
  for (const sx of [-1, 1]) {
    box('body', [sx * 0.175 - 0.022, COVER_Y + 0.105, z], [sx * 0.175 + 0.022, COVER_Y + 0.125, z + 0.05], 'pol');
  }
}
/* 盖前卡榫（真枪在盖前缘，压下去才能把盖向后推） */
box('body', [-0.055, COVER_Y - 0.03, Z_RECV_A + 0.22], [0.055, COVER_Y + 0.06, Z_RECV_A + 0.40], 'pol');

/* ================================================================ 5. 枪机 + 拉机柄（bone: bolt）
 * 真枪：旋转闭锁枪机，拉机柄在机匣右侧，**只沿枪轴平移、不旋转**（经弯曲传动杆直连）。
 * 枪机本体平时缩在机匣里，只有往复时露出来一点。 */
const Z_BOLT_PIV = Z_RECV_B - 0.15;                 // 枪机尾端（bone pivot）
box('bolt', [-0.135, Y_BORE - 0.125, Z_RECV_A + 0.60], [0.135, Y_BORE + 0.125, Z_RECV_B - 0.06], 'pol');
box('bolt', [-0.115, Y_BORE - 0.10, Z_RECV_A + 0.42], [0.115, Y_BORE + 0.10, Z_RECV_A + 0.62], 'steel'); // 机头
/* 拉机柄：从枪机右侧伸出的连杆 + 末端球头（右后方） */
box('bolt', [0.10, Y_BORE - 0.03, Z_RECV_B - 1.05], [0.30, Y_BORE + 0.07, Z_RECV_B - 0.72], 'pol');
box('bolt', [0.28, Y_BORE - 0.115, Z_RECV_B - 1.16], [0.415, Y_BORE + 0.135, Z_RECV_B - 0.60], 'pol');
box('bolt', [0.395, Y_BORE - 0.095, Z_RECV_B - 1.11], [0.455, Y_BORE + 0.115, Z_RECV_B - 0.65], 'steel'); // 头端面
/* 枪机尾部（露在节套外面的那一小截，往复时最显眼） */
box('bolt', [-0.135, Y_BORE - 0.11, Z_RECV_B - 0.06], [0.135, Y_BORE + 0.11, Z_RECV_B + 0.16], 'pol');
/* 抛壳挺 / 抽壳钩（机头两侧的小件） */
box('bolt', [0.10, Y_BORE + 0.04, Z_RECV_A + 0.44], [0.145, Y_BORE + 0.11, Z_RECV_A + 0.58], 'steel');
box('bolt', [-0.145, Y_BORE + 0.02, Z_RECV_A + 0.44], [-0.10, Y_BORE + 0.10, Z_RECV_A + 0.62], 'steel');

/* ================================================================ 6. 弹匣箱 / 弹匣盖 / 漏夹
 * 真的 RSC：5 发漏夹从**下方**插进固定弹匣，松开卡榫后**弹匣盖向前下方敞开**，
 * 废漏夹掉出来，新漏夹自下往上插入，合盖，再拉一次拉机柄上膛。
 * 量取：箱底 ≈ 轴下 94 mm（Y −1.50）；漏夹 8mm 勒贝尔全长 70.6 mm = 1.13 u。 */
const Z_CLIP_A = Z_MAG_A + 0.03;                    // 漏夹（比箱略小）
const Z_CLIP_B = Z_MAG_B - 0.03;
const Y_MAG_TOP = Y_BORE - 0.34;                    // 弹匣箱顶（贴机匣底）
/* 箱体：四面墙 + 里面挖空 */
box('body', [-MAG_W / 2, Y_MAG_BOT, Z_MAG_A], [MAG_W / 2, Y_MAG_TOP, Z_MAG_B], 'steel');
box('body', [-MAG_W / 2 + 0.05, Y_MAG_BOT + 0.06, Z_MAG_A + 0.05],
  [MAG_W / 2 - 0.05, Y_MAG_TOP + 0.02, Z_MAG_B - 0.05], 'dark');
/* 箱前的进弹斜面（真枪前壁有个导引斜面） */
box('body', [-MAG_W / 2 + 0.03, Y_MAG_BOT + 0.12, Z_MAG_A - 0.06],
  [MAG_W / 2 - 0.03, Y_MAG_TOP - 0.05, Z_MAG_A + 0.04], 'blued');
/* 前后壁的加强筋 */
box('body', [-MAG_W / 2 - 0.012, Y_MAG_BOT + 0.10, Z_MAG_A + 0.10],
  [MAG_W / 2 + 0.012, Y_MAG_TOP - 0.05, Z_MAG_A + 0.18], 'blued');

/* 弹匣盖（bone: mag_cover）—— 铰链在**前端**，向下前方敞开（旋转在动画里给） */
const Z_COVER_PIV = Z_MAG_A + 0.02;
box('mag_cover', [-MAG_W / 2 - 0.015, Y_MAG_BOT - 0.055, Z_COVER_PIV],
  [MAG_W / 2 + 0.015, Y_MAG_BOT + 0.02, Z_MAG_B + 0.02], 'steel');
box('mag_cover', [-MAG_W / 2 + 0.02, Y_MAG_BOT - 0.045, Z_COVER_PIV + 0.12],
  [MAG_W / 2 - 0.02, Y_MAG_BOT + 0.03, Z_MAG_B - 0.02], 'dark');   // 盖内侧
box('mag_cover', [-0.06, Y_MAG_BOT - 0.10, Z_MAG_B - 0.16], [0.06, Y_MAG_BOT - 0.02, Z_MAG_B + 0.04], 'pol'); // 卡榫
/* 盖前铰链轴（真枪是一根横销） */
box('mag_cover', [-MAG_W / 2 - 0.03, Y_MAG_BOT - 0.02, Z_COVER_PIV - 0.03],
  [MAG_W / 2 + 0.03, Y_MAG_BOT + 0.04, Z_COVER_PIV + 0.05], 'pol');

/* 漏夹（bone: clip）—— 5 发 8mm 勒贝尔，弹头朝 −Z，竖着叠在匣里；
 * 装填 = 整块纯平移（真枪就是这么插进去的）。 */
const CLIP_W = 0.15;
const ROUND_DY = 0.215;                             // 每发占的竖直间距（13.4 mm）
for (let r = 0; r < 5; r++) {
  const y = Y_MAG_TOP - 0.19 - r * ROUND_DY;
  box('clip', [-CLIP_W, y - 0.095, Z_CLIP_A + 0.42], [CLIP_W, y + 0.095, Z_CLIP_B], 'brass');   // 弹壳
  box('clip', [-CLIP_W + 0.02, y - 0.075, Z_CLIP_A], [CLIP_W - 0.02, y + 0.075, Z_CLIP_A + 0.42], 'copper'); // 弹头
}
/* 漏夹钢框（前后两片 + 两侧的抱弹齿；真枪是一块冲压钢片折成的） */
for (const sx of [-1, 1]) {
  box('clip', [sx * CLIP_W - 0.012, Y_MAG_BOT + 0.06, Z_CLIP_A + 0.06],
    [sx * CLIP_W + 0.012, Y_MAG_TOP - 0.02, Z_CLIP_B - 0.02], 'lead');
}
box('clip', [-CLIP_W - 0.012, Y_MAG_BOT + 0.06, Z_CLIP_B - 0.04],
  [CLIP_W + 0.012, Y_MAG_TOP - 0.02, Z_CLIP_B + 0.02], 'lead');
/* 空漏夹（bone: clip_empty）—— 同一个钢框，没有子弹；平时被动画按 scale 收掉，
 * 只有空仓换弹"废漏夹掉出"那一下才显形（与短管喷 shell_upper 同一套做法）。 */
for (const sx of [-1, 1]) {
  box('clip_empty', [sx * CLIP_W - 0.012, Y_MAG_BOT + 0.06, Z_CLIP_A + 0.06],
    [sx * CLIP_W + 0.012, Y_MAG_TOP - 0.02, Z_CLIP_B - 0.02], 'lead');
}
box('clip_empty', [-CLIP_W - 0.012, Y_MAG_BOT + 0.06, Z_CLIP_B - 0.04],
  [CLIP_W + 0.012, Y_MAG_TOP - 0.02, Z_CLIP_B + 0.02], 'lead');
box('clip_empty', [-CLIP_W, Y_MAG_BOT + 0.06, Z_CLIP_A + 0.06],
  [CLIP_W, Y_MAG_BOT + 0.11, Z_CLIP_B - 0.02], 'lead');

/* ================================================================ 7. 扳机组 + 保险（bone: trigger）
 * 量取：护圈在弹匣箱正后方（Z +0.02 ~ +0.66），扳机片在 Z ≈ +0.26（= 本模型原点附近）。 */
box('body', [-0.05, Y_BORE - 0.62, Z_GUARD_B - 0.62], [0.05, Y_BORE - 0.42, Z_GUARD_B - 0.52], 'blued'); // 护圈前立柱
box('body', [-0.05, Y_BORE - 0.92, Z_GUARD_B - 0.66], [0.05, Y_BORE - 0.80, Z_GUARD_B - 0.06], 'blued'); // 护圈底
box('body', [-0.05, Y_BORE - 0.66, Z_GUARD_B - 0.14], [0.05, Y_BORE - 0.42, Z_GUARD_B - 0.04], 'blued'); // 护圈后立柱
box('body', [-0.16, Y_BORE - 0.42, Z_MAG_B + 0.02], [0.16, Y_BORE - 0.30, Z_GUARD_B], 'steel');           // 护圈上板
/* 扳机片（bone: trigger，绕顶部 pivot 转动） */
box('trigger', [-0.045, Y_BORE - 0.60, Z_GUARD_B - 0.50], [0.045, Y_BORE - 0.34, Z_GUARD_B - 0.42], 'pol');
box('trigger', [-0.035, Y_BORE - 0.60, Z_GUARD_B - 0.42], [0.035, Y_BORE - 0.42, Z_GUARD_B - 0.36], 'pol'); // 弧度
/* 弹匣盖卡榫（护圈前下方，按下去弹匣盖才开） */
box('safety', [-0.055, Y_BORE - 0.50, Z_MAG_B + 0.04], [0.055, Y_BORE - 0.38, Z_MAG_B + 0.14], 'pol');
/* 保险片（左侧的扁杆，绕自身轴摆动） */
box('safety', [-0.31, Y_BORE + 0.02, Z_RECV_B - 0.62], [-0.255, Y_BORE + 0.20, Z_RECV_B - 0.12], 'pol');

/* ================================================================ 8. 抛壳（bone: casing）
 * 8mm 勒贝尔空壳：黄铜壳身 + 底缘，枪机后拉时从右侧抛壳口甩出。 */
const CASE_Z = Z_RECV_A + 1.30;
box('casing', [0.10, Y_BORE + 0.02, CASE_Z - 0.62], [0.175, Y_BORE + 0.085, CASE_Z + 0.02], 'brass');
box('casing', [0.095, Y_BORE - 0.005, CASE_Z + 0.02], [0.18, Y_BORE + 0.11, CASE_Z + 0.075], 'pol');   // 底缘

/* ================================================================ 9. 枪托（bone: body）
 * 量取：托颈顶 ≈ 轴下 21 mm、托底 ≈ 轴下 117 mm、托底板在 Z +5.15~+5.30。
 * 逐段往后 + 往下（托腹下垂），每段给自己一点 cube 级 rotation，让台阶连成斜线
 * —— 规范禁的是**骨骼**旋转，cube 的 rotation 允许（短管喷/莫辛都这么做）。 */
const STK_Z0 = Z_TANG_B;
const STK_SEGS = 9;
for (let i = 0; i < STK_SEGS; i++) {
  const t0 = i / STK_SEGS;
  const t1 = (i + 1) / STK_SEGS;
  const z0 = STK_Z0 + t0 * (Z_BUTT - 0.15 - STK_Z0);
  const z1 = STK_Z0 + t1 * (Z_BUTT - 0.15 - STK_Z0);
  /* 托腹下垂：从轴下 0.52 u（托颈）滑到托底 1.88 u */
  const b0 = -(0.52 + t0 * 1.36);
  const b1 = -(0.52 + t1 * 1.36);
  /* 托背（comb）：从托颈顶（轴下 0.34）到托底前缘（轴下 0.30），基本平 */
  const t0y = Y_WRIST_TOP - t0 * 0.02;
  const t1y = Y_WRIST_TOP - t1 * 0.02;
  const droop = Math.atan2(b1 - b0, z1 - z0) * 180 / Math.PI;
  box('body', [-WOOD_W / 2 + 0.02, b0, z0], [WOOD_W / 2 - 0.02, t0y, z1], 'wood', [droop, 0, 0], [0, t0y, z0]);
  box('body', [-WOOD_W / 2 + 0.03, b0, z0], [WOOD_W / 2 - 0.03, b0 + 0.075, z1], 'woodd', [droop, 0, 0], [0, t0y, z0]);
  box('body', [-WOOD_W / 2 + 0.03, t0y - 0.06, z0], [WOOD_W / 2 - 0.03, t0y, z1], 'woodl', [droop, 0, 0], [0, t0y, z0]);
}
/* 托颈（节套后到托腹之间的握持段，比托身略窄） */
for (let i = 0; i < 3; i++) {
  const z0 = Z_TANG_B - 0.20 + i * 0.16;
  const z1 = z0 + 0.16;
  const yb = -(0.40 + i * 0.05);
  box('body', [-0.185, yb, z0], [0.185, Y_WRIST_TOP + 0.04 - i * 0.01, z1], 'wood');
}
/* 托颈格纹（防滑格，三道） */
for (let i = 0; i < 3; i++) {
  const z = Z_TANG_B + 0.18 + i * 0.30;
  box('body', [-0.19, -(0.46 - i * 0.06) , z], [0.19, Y_WRIST_TOP - 0.02 - i * 0.03, z + 0.07], 'woodd');
}
/* 托底板（真枪是两片钢：底板 + 一层厚的垫片） */
box('body', [-WOOD_W / 2, Y_BUTT_BOT - 0.015, Z_BUTT - 0.15], [WOOD_W / 2, Y_WRIST_TOP - 0.06, Z_BUTT], 'dark');
box('body', [-WOOD_W / 2 + 0.01, Y_BUTT_BOT - 0.03, Z_BUTT], [WOOD_W / 2 - 0.01, Y_WRIST_TOP - 0.05, Z_BUTT + 0.075], 'steel');
/* 后背带环（托腹下方 Z ≈ +3.6，量取：轴下 −2.0 附近） */
box('body', [-0.07, Y_BUTT_BOT + 0.05, 3.55], [0.07, Y_BUTT_BOT + 0.16, 3.85], 'steel');
for (const sx of [-1, 1]) {
  box('body', [sx * 0.07 - 0.018, Y_BUTT_BOT + 0.10, 3.55], [sx * 0.07 + 0.018, Y_BUTT_BOT + 0.30, 3.85], 'steel');
}
/* 托颈底部的握把帽 + 节套螺钉（细节件） */
box('body', [-0.10, -(0.52), Z_TANG_B + 0.05], [0.10, -(0.44), Z_TANG_B + 0.35], 'pol');
box('body', [-0.15, Y_BORE - 0.32, Z_RECV_B - 0.30], [0.15, Y_BORE - 0.26, Z_RECV_B - 0.22], 'pol');

/* ================================================================ 10. 左手支撑块（bone: hand_l）
 * 与短管喷同一套：左手握住前托，块体在前托下方（Java 侧的手臂渲染会盖住它）。 */
box('hand_l', [-0.145, -1.05, Z_FORE_A + 1.70], [0.145, -0.60, Z_FORE_A + 2.95], 'woodd');

/* ================================================================ 10b. 单发补弹的一发（bone: round_in）
 * 真机（也见 FM 手册对 Garand 的描述）：直接往弹膛里放一发、再放枪机上膛。
 * 平时由动画按本骨 scale 0 收掉，只有 single_load 那一下才显形（与莫辛/AWM 的 round_in 同一套）。 */
box('round_in', [-0.075, Y_BORE - 0.085, Z_RECV_A + 0.60], [0.075, Y_BORE + 0.085, Z_RECV_A + 1.23], 'brass');
box('round_in', [-0.058, Y_BORE - 0.068, Z_RECV_A + 0.10], [0.058, Y_BORE + 0.068, Z_RECV_A + 0.60], 'copper');
box('round_in', [-0.082, Y_BORE - 0.092, Z_RECV_A + 1.23], [0.082, Y_BORE + 0.092, Z_RECV_A + 1.30], 'pol');

/* ================================================================ 11. 细节补强
 * 真机上"看得见但一眼说不清"的东西：销钉、螺钉、防滑纹、刻度、凹槽。
 * 全是小方块，但正是它们把"像枪"推到"是这把枪"。 */

/* 机匣两侧的横销与螺钉（真枪机匣每侧 2 根横销 + 1 颗托底螺钉孔） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 3; i++) {
    const z = Z_RECV_A + 0.55 + i * 0.95;
    box('body', [sx * (RECV_W / 2 + 0.004) - 0.016, Y_BORE - 0.17, z],
      [sx * (RECV_W / 2 + 0.004) + 0.016, Y_BORE - 0.11, z + 0.055], 'pol');
  }
  /* 机匣侧面的加工凹台（每侧两道，真枪是铣出来的减重槽） */
  box('body', [sx * (RECV_W / 2 - 0.02) - 0.006, Y_BORE - 0.05, Z_RECV_A + 0.75],
    [sx * (RECV_W / 2 - 0.02) + 0.006, Y_BORE + 0.20, Z_RECV_A + 2.05], 'dark');
  /* 节套两侧的螺栓头 */
  box('body', [sx * (RECV_W / 2 - 0.02) - 0.014, Y_BORE - 0.08, Z_RECV_B - 0.18],
    [sx * (RECV_W / 2 - 0.02) + 0.014, Y_BORE + 0.14, Z_RECV_B - 0.08], 'pol');
}
/* 抛壳口四边的倒角（一圈薄钢，让开口不是"贴上去的黑方块"） */
box('body', [-0.02, Y_BORE + 0.40, Z_RECV_A + 1.15], [RECV_W / 2 + 0.008, Y_BORE + 0.44, Z_RECV_A + 2.20], 'steel');
box('body', [-0.02, Y_BORE + 0.01, Z_RECV_A + 1.15], [RECV_W / 2 + 0.008, Y_BORE + 0.05, Z_RECV_A + 2.20], 'steel');
box('body', [-0.02, Y_BORE + 0.05, Z_RECV_A + 1.09], [RECV_W / 2 + 0.008, Y_BORE + 0.40, Z_RECV_A + 1.15], 'steel');
box('body', [-0.02, Y_BORE + 0.05, Z_RECV_A + 2.20], [RECV_W / 2 + 0.008, Y_BORE + 0.40, Z_RECV_A + 2.26], 'steel');
/* 抛壳挺座（机匣里的一个小斜面，真枪抛壳就靠它） */
box('bolt', [0.02, Y_BORE + 0.02, Z_RECV_A + 0.62], [0.12, Y_BORE + 0.12, Z_RECV_A + 0.74], 'lead');
/* 表尺立框两侧的刻度线（每侧 5 道） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 5; i++) {
    const z = Z_RECV_A + 0.50 + i * 0.10;
    box('body', [sx * 0.121 - 0.006, Y_SIGHT_TOP + 0.02, z], [sx * 0.121 + 0.006, Y_SIGHT_TOP + 0.09, z + 0.018], 'pol');
  }
}
/* 拉机柄球头的防滑纹（5 道，沿 Z 排） */
for (let i = 0; i < 5; i++) {
  const z = Z_RECV_B - 1.13 + i * 0.10;
  box('bolt', [0.286, Y_BORE - 0.125, z], [0.405, Y_BORE + 0.145, z + 0.03], 'steel');
}
/* 枪机本体的闭锁凸榫（真枪两组，这里每侧前后各一道，往复时最显眼的东西） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 2; i++) {
    const z = Z_RECV_A + 0.66 + i * 0.22;
    box('bolt', [sx * 0.135 - (sx > 0 ? 0 : 0.03), Y_BORE + 0.06, z],
      [sx * 0.135 + (sx > 0 ? 0.03 : 0), Y_BORE + 0.13, z + 0.10], 'pol');
  }
}
/* 盖面前端的卡榫座 + 两侧的扣边（真枪盖子是"扣"上去的） */
for (const sx of [-1, 1]) {
  box('body', [sx * 0.245 - (sx > 0 ? 0 : 0.012), COVER_Y - 0.01, Z_RECV_A + 0.35],
    [sx * 0.245 + (sx > 0 ? 0.012 : 0), COVER_Y + 0.10, Z_RECV_B - 0.10], 'blued');
}
/* 前托两侧的指槽（真枪木托上铣出来两道，握上去手感就是这个） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 2; i++) {
    const z = Z_FORE_A + 1.15 + i * 1.05;
    box('forend', [sx * FW - (sx > 0 ? 0 : 0.018), Y_BORE - 0.42, z],
      [sx * FW + (sx > 0 ? 0.018 : 0), Y_BORE - 0.10, z + 0.72], 'woodd');
  }
}
/* 前托与枪管之间的托条（把木头箍在枪管上，真枪是薄钢条） */
for (const sx of [-1, 1]) {
  box('forend', [sx * 0.14 - 0.018, Y_BORE + 0.10, Z_FORE_A + 0.10],
    [sx * 0.14 + 0.018, Y_BORE + 0.17, Z_FORE_B - 0.10], 'blued');
}
/* 弹匣箱侧面的凹槽（每侧两道加强筋之间压暗） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 2; i++) {
    const z = Z_MAG_A + 0.22 + i * 0.52;
    box('body', [sx * (MAG_W / 2 + 0.002) - 0.007, Y_MAG_BOT + 0.22, z],
      [sx * (MAG_W / 2 + 0.002) + 0.007, Y_MAG_TOP - 0.10, z + 0.34], 'dark');
  }
}
/* 漏夹抱弹齿（两侧各 3 颗小齿，真枪的样子） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 3; i++) {
    const y = Y_MAG_TOP - 0.30 - i * ROUND_DY;
    box('clip', [sx * CLIP_W - 0.03, y - 0.05, Z_CLIP_A + 0.10],
      [sx * CLIP_W + 0.012, y + 0.05, Z_CLIP_B - 0.10], 'lead');
  }
}
/* 托颈格纹（每侧三道，更密） */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 4; i++) {
    const z = Z_TANG_B + 0.06 + i * 0.22;
    box('body', [sx * 0.19 - (sx > 0 ? 0 : 0.01), -0.54 + i * 0.01, z],
      [sx * 0.19 + (sx > 0 ? 0.01 : 0), Y_WRIST_TOP - 0.03 - i * 0.01, z + 0.16], 'woodd');
  }
}
/* 托底板的固定螺钉（上下各一颗） */
box('body', [-0.05, Y_BUTT_BOT + 0.10, Z_BUTT + 0.02], [0.05, Y_BUTT_BOT + 0.22, Z_BUTT + 0.09], 'pol');
box('body', [-0.05, Y_WRIST_TOP - 0.20, Z_BUTT + 0.02], [0.05, Y_WRIST_TOP - 0.08, Z_BUTT + 0.09], 'pol');
/* 前枪箍与枪管之间的薄垫圈 + 箍上的销 */
box('barrel', [-0.245, Y_BORE - 0.40, Z_FRONT_BAND - 0.02], [0.245, Y_BORE + 0.24, Z_FRONT_BAND + 0.02], 'dark');
box('barrel', [-0.245, Y_BORE - 0.40, Z_FRONT_BAND + 0.30], [0.245, Y_BORE + 0.24, Z_FRONT_BAND + 0.34], 'dark');
/* 导气管前端的气孔（真枪导气箍上有个排气孔） */
box('barrel', [-0.055, Y_BORE - 0.36, Z_FRONT_BAND + 0.50], [0.055, Y_BORE - 0.30, Z_FRONT_BAND + 0.58], 'dark');
/* 枪管下方的木托支撑环（真枪在裸管段每隔一段有个小环） */
box('barrel', [-0.20, Y_BORE - 0.30, Z_FORE_A - 0.34], [0.20, Y_BORE + 0.20, Z_FORE_A - 0.26], 'steel');
/* 刺刀座上的卡爪（真枪刺刀从这里卡进去） */
box('barrel', [-0.10, Y_BORE - 0.50, Z_ROD_END + 0.14], [0.10, Y_BORE - 0.42, Z_ROD_END + 0.40], 'pol');
/* 节套上方的照门座螺栓 */
box('body', [-0.125, Y_RECV_TOP - 0.02, Z_RECV_A + 0.40], [0.125, Y_RECV_TOP + 0.03, Z_RECV_A + 0.50], 'pol');

/* ================================================================ 骨骼
 * 原点 = 扳机/膛线轴（见文件头）；骨骼一律零旋转（规范铁律）。 */
const bones = [
  { name: 'root', pivot: [0, Y_BORE, Z_BUTT - 0.30] },
  { name: 'move', parent: 'root', pivot: [0, Y_BORE, Z_BUTT - 0.30] },
  /* body = 机匣中心对齐原点：枪托、机匣、弹匣箱、扳机组都挂在它下面 */
  { name: 'body', parent: 'move', pivot: [0, Y_BORE, 0] },
  /* 枪管绕机匣前端面附近转（本枪枪管不可拆，pivot 只是给动画一个自然轴） */
  { name: 'barrel', parent: 'body', pivot: [0, Y_BORE, Z_RECV_A] },
  { name: 'forend', parent: 'body', pivot: [0, Y_BORE - 0.30, Z_FORE_B] },
  { name: 'cover', parent: 'body', pivot: [0, COVER_Y, Z_RECV_A + 0.30] },
  { name: 'bolt', parent: 'body', pivot: [0, Y_BORE, Z_BOLT_PIV] },
  /* 弹匣盖：铰链在**前端**（Z_COVER_PIV），向前下方敞开 */
  { name: 'mag_cover', parent: 'body', pivot: [0, Y_MAG_BOT, Z_COVER_PIV] },
  /* 漏夹：从下方插入，纯平移；pivot 取匣体中心 */
  { name: 'clip', parent: 'body', pivot: [0, (Y_MAG_BOT + Y_MAG_TOP) / 2, (Z_CLIP_A + Z_CLIP_B) / 2] },
  { name: 'clip_empty', parent: 'body', pivot: [0, (Y_MAG_BOT + Y_MAG_TOP) / 2, (Z_CLIP_A + Z_CLIP_B) / 2] },
  { name: 'casing', parent: 'body', pivot: [0.14, Y_BORE + 0.05, CASE_Z] },
  { name: 'round_in', parent: 'body', pivot: [0, Y_BORE, Z_RECV_A + 0.66] },
  { name: 'trigger', parent: 'body', pivot: [0, Y_BORE - 0.34, Z_GUARD_B - 0.44] },
  { name: 'safety', parent: 'body', pivot: [0, Y_BORE, Z_RECV_B - 0.60] },
  { name: 'hand_l', parent: 'forend', pivot: [0, -0.85, Z_FORE_A + 2.30] },
  { name: 'magazine', parent: 'body', pivot: [0, Y_MAG_BOT, Z_MAG_A] },
  { name: 'additional_magazine', parent: 'move', pivot: [0, Y_MAG_BOT, Z_MAG_A] },
  { name: 'camera', parent: 'move', pivot: [0, 0, 0] },
  { name: 'constraint', parent: 'move', pivot: [0, 0, 0] },
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
/* 全长 1331 mm = 21.30 u（规范 12~24 u）；枪口/托底的位置必须落在量取值上 */
if (Math.abs(lo[2] - Z_MUZZLE) > 0.06) fails.push(`枪口 Z=${lo[2].toFixed(2)}，量取值 ${Z_MUZZLE}`);
if (Math.abs(hi[2] - Z_BUTT) > 0.10) fails.push(`托底 Z=${hi[2].toFixed(2)}，量取值 ${Z_BUTT}`);
if (lenZ < 12 || lenZ > 24) fails.push(`全长 ${lenZ.toFixed(2)}u 超出 12~24u`);
if (Math.abs(widX - WOOD_W) > 0.16) fails.push(`宽 ${widX.toFixed(2)}u 与木托宽 ${WOOD_W.toFixed(2)}u 差太多`);
if (Math.abs(heiY - (Y_SIGHT_TOP + 0.20 - Y_BUTT_BOT)) > 0.35) fails.push(`高 ${heiY.toFixed(2)}u 与量取轮廓差太多`);

module.exports = {
  cubes, bones, MAT, SHADE, fails,
  stats: { total: cubes.length, lenZ, widX, heiY, lo, hi },
  Z: { Z_MUZZLE, Z_BUTT, Z_RECV_A, Z_RECV_B, Z_MAG_A, Z_MAG_B, Y_BORE, Y_MAG_BOT, Y_MAG_TOP },
};

if (require.main === module) {
  console.log(`方块 ${cubes.length} / 骨骼 ${bones.length}`);
  console.log(`长(Z) ${lenZ.toFixed(2)} u = ${(lenZ / 16).toFixed(2)} 格 = ${(lenZ / MM).toFixed(0)} mm（真枪 1331 mm）`);
  console.log(`Z 范围 [${lo[2].toFixed(2)}, ${hi[2].toFixed(2)}]   宽(X) ${widX.toFixed(2)} u   高(Y) ${heiY.toFixed(2)} u`);
  console.log(`Y 范围 [${lo[1].toFixed(2)}, ${hi[1].toFixed(2)}]（0 = 膛线轴）`);
  const byBone = {};
  for (const c of cubes) byBone[c.bone] = (byBone[c.bone] || 0) + 1;
  console.log('每骨方块数:', Object.entries(byBone).map(([k, v]) => `${k}=${v}`).join('  '));
  console.log(fails.length ? `*** 自检失败:\n  ${fails.join('\n  ')}` : '自检: 全部通过');
}
