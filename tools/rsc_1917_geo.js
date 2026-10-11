#!/usr/bin/env node
/* ============================================================================
 * RSC M1917（法国 1917 型半自动步枪）几何生成器 —— **v2：轮廓由实测表驱动**
 *
 * v1 的问题：竖直尺寸是一堆手写常量（前托只覆盖 z 470~805，木头前段整段缺失），
 * 侧视剪影与照片差 20~35 mm。v2 把 art/rsc_1917/profile2.json（从参考照片逐列量取的
 * top/bot，mm 相对膛线轴）当**唯一真源**放样：木头/机匣/枪托的上下缘直接采样实测表，
 * 手写常量只用来定“横向半宽”和“特征件”（准星 / 枪箍 / 背带环 / 弹匣箱 / 扳机护圈…）。
 *
 * 坐标铁律（同 美术规范.md）：
 *   - 16 u = 1 方块 = 1 m ⇒ 1 u = 62.5 mm，MM = 16/1000
 *   - 枪口 = −Z、上 = +Y、+X = 射手右侧；膛线轴 = Y 0
 *   - 骨骼一根都不许带旋转；cube 级 rotation 允许
 *   - 单位换算只走 Zb()/Yu() 两个函数，别在别处手写 ×62.5
 *
 * 量取坐标系：z_mm 从枪口起算（0 = 枪口断面，1319 = 托底板外缘）；
 *   Zb(z_mm) = Z_MUZZLE + z_mm/62.5
 *
 * 用法：node tools/rsc_1917_geo.js          （打印统计 + 自检）
 *       由 tools/rsc_1917_build.js require 走 UV 打包与下发
 * ========================================================================== */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PROFILE = path.join(ROOT, 'art', 'rsc_1917', 'profile2.json');

/* 16 u = 1 方块 = 1 m ⇒ 1 u = 6.25 cm = 62.5 mm（别写成 1/6.25 —— 会把整枪放大 10 倍） */
const MM = 16 / 1000;
const Y_BORE = 0;
const Z_MUZZLE = -16.00;                     // z_mm = 0 处的模型 Z
const Zb = (zmm) => Z_MUZZLE + zmm / 62.5;   // z_mm -> 模型 Z
const Yu = (ymm) => ymm / 62.5;              // 相对膛线轴的 mm -> 模型 Y

/* ---------------------------------------------------------------- 实测轮廓 */
const profDoc = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
const MM_PER_PX = profDoc.mm_per_px;
/* 轮廓表 = 按测量列线性插值（与 tools/rsc_1917_silhouette.py 的对表口径完全一致）。
 * 别再用「1 mm 台阶表」：台阶把整毫米格取成上一列的值，竖直断崖整整滞后 1 mm，
 * 每条断崖都会假报一列 20+ mm 超差（1.1.87 为止的 6 处离群值根源就在这）。 */
const _colsS = profDoc.cols.slice().sort((a, b) => a.z_mm - b.z_mm);
const _cz = Float64Array.from(_colsS, (c) => c.z_mm);
const _ct = Float64Array.from(_colsS, (c) => c.top);
const _cb = Float64Array.from(_colsS, (c) => c.bot);
function interpCol(ys, zmm) {
  const n = _cz.length;
  if (zmm <= _cz[0]) return ys[0];
  if (zmm >= _cz[n - 1]) return ys[n - 1];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (_cz[m] <= zmm) lo = m; else hi = m; }
  const f = (zmm - _cz[lo]) / (_cz[hi] - _cz[lo]);
  return ys[lo] * (1 - f) + ys[hi] * f;
}
/** 实测上缘（mm，相对膛线轴） */
const pT = (zmm) => interpCol(_ct, zmm);
/* 实测列里的「竖直断崖」（相邻测量列落差 > 8 mm）：放样必须正好劈在这里。
 * 二分中点劈不准竖直边，台阶会比真值晚 0.2~0.3 mm，那一列就假报 10+ mm 超差。 */
const KNEE = [];
for (let k = 1; k < _cz.length; k++) {
  if (Math.abs(_ct[k] - _ct[k - 1]) > 8 || Math.abs(_cb[k] - _cb[k - 1]) > 8) KNEE.push(_cz[k]);
}
function kneeIn(a, b) {
  for (const z of KNEE) { if (z > a + 0.05) return z < b - 0.05 ? z : null; }
  return null;
}
/** 实测下缘（mm） */
const pB = (zmm) => interpCol(_cb, zmm);
/* 木料下缘：实测下缘里混着「挂在木托腹下的钢件」（前段拖曳钩、中段前背带环）。
 * 木托本身不该跟着这些件一起下探 —— 那些下探由专门的件画，否则一列 20+ mm 的假误差。
 * 前段拖曳钩区（z 104~192）木托还没开始（Z_FORE_A≈192），只需处理中段前背带环。 */
const STRAP_A = 688, STRAP_B = 708.5, STRAP_BOT = -38.9;
const pBw = (zmm) =>
  (zmm > STRAP_A && zmm < STRAP_B ? Math.max(pB(zmm), STRAP_BOT) : pB(zmm));

/* ---------------------------------------------------- 特征分界（照片判读 + 实测交叉确认） */
const Z_TIP = 0;                            // 枪口断面
const Z_SIGHT_A = 15.3, Z_SIGHT_B = 34;       // 前准星（实测上缘 z 16 起就抬到 +20.9，刃尖 +21.8）
const Z_LUG_A = 20, Z_LUG_B = 32;           // 枪口下方的刺刀座挡块（实测 z 21~31，下缘 −15.1）
const Z_HOOK_A = 103.6, Z_HOOK_B = 192;       // 枪管下方拖曳钩（实测下探从 z 104 那一列才开始：103 列仍是 −8.9）
const Z_BAND_F_A = 171, Z_BAND_F_B = 197;   // 前枪箍（照片：木前端那圈金属）
const Z_FORE_A = 192, Z_FORE_B = 865;       // 前托木
const Z_HAND_A = 492, Z_HAND_B = 862;       // 上手木（照片 z≈490 顶面 +13→+22）
const Z_BAND_M_A = 690, Z_BAND_M_B = 726;   // 中枪箍 + 前背带环（z 700 下探到 −58）
const Z_SIGHT_R_A = 782, Z_SIGHT_R_B = 862; // 照门/表尺（顶面升到 +28）
const Z_RECV_A = 862, Z_RECV_B = 1122;      // 机匣后端面（实测上缘 +16.1@1120 → −19.2@1125）
const Z_MAG_A = 858, Z_MAG_B = 1000;        // 弹匣箱（实测底 −88.6 在 z 940~960；前缘顶到机匣前）
const Z_GUARD_A = 998, Z_GUARD_B = 1044;    // 扳机护圈
const Z_LEVER_A = 1044, Z_LEVER_B = 1092;   // 弹匣盖卡榫长杆（实测底 −75 在 z 1060~1080）
const Z_WRIST_A = 1085;                     // 托颈（木）起点
const Z_PLATE_A = 1306;                     // 托底板起点
const Z_BUTT = 1319.2;                      // 托底板外缘（alpha 剪影全长）

/* 横向尺寸（侧视量不到，按真枪规格；均为**半宽**，单位 u） */
const W_BARREL = (zmm) => (8.9 + Math.min(zmm, 860) / 860 * 0.7) / 62.5;  // 外半径 8.9→9.6 mm（实测）
const BARREL_CY = -0.5 / 62.5;                    // 枪管中心 ≈ 膛线轴（实测 top +8.45 / bot −9.47）
const BARREL_BOT = (zmm) => -0.5 - W_BARREL(zmm) * 62.5;
const BARREL_TOP = (zmm) => -0.5 + W_BARREL(zmm) * 62.5;
const W_FORE = 20.5 / 62.5;      // 前托木半宽（真枪 41 mm）
const W_HAND = 16.0 / 62.5;      // 上手木半宽
const W_RECV = 17.5 / 62.5;      // 机匣半宽（35 mm）
const W_BUTT = 22.0 / 62.5;      // 枪托半宽（44 mm）
const W_MAG = 15.0 / 62.5;       // 弹匣箱半宽（30 mm）
const Y_RECV_FLOOR = -25;        // 机匣底面（木托/弹匣箱分界）

/** 材质调色板 —— 发蓝钢 + 胡桃木 + 黄铜（美术规范.md 第三节） */
const MAT = {
  blued: [50, 54, 64],     // 暗发蓝钢：枪管 / 枪箍（参考照片里枪管几乎全黑）
  steel: [72, 76, 84],     // 钢：机匣侧面 / 弹匣箱 / 盖（比木色深一档）
  pol: [150, 152, 158],    // 抛光钢：枪机 / 拉机柄 / 扳机 / 准星 / 表尺
  dark: [30, 32, 38],      // 膛口 / 缝 / 暗腔 / 抛壳口
  wood: [118, 74, 38],     // 胡桃木：前托 / 枪托（实测偏暗红棕）
  woodl: [152, 102, 56],   // 木亮部（上棱 / 倒角）
  woodd: [78, 46, 22],     // 木暗部（下棱 / 格纹 / 槽）
  brass: [172, 128, 54],   // 黄铜弹壳
  copper: [166, 106, 60],  // 弹头被甲
  lead: [138, 138, 144],   // 弹芯 / 钢芯件
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

/** 毫米直给：z 用 mm（枪口起算），y 用 mm（相对膛线轴），x 用 u 半宽 */
function mbox(bone, xh, y0mm, z0mm, y1mm, z1mm, mat) {
  box(bone, [-xh, Yu(y0mm), Zb(z0mm)], [xh, Yu(y1mm), Zb(z1mm)], mat);
}

/** 逐列放样：上下缘用函数给（mm），按 step 切成一串方块 —— 剪影即实测轮廓。
 *  段内上/下缘变化超过 MAX_SLOPE 就二分细分（否则陡坡处会按“最高点”填成台阶，
 *  例如机匣后端 z≈1130 处上缘从 +21 掉到 −22，粗步长会把整段填到 +21）。
 *  两端各留 0.4 mm 重叠，避免相邻方块之间露缝。 */
const LOFT_MAX_SLOPE = 5.0;   // mm/段
const LOFT_MIN_SEG = 0.15;    // mm（断崖处细分到 0.15 mm：实测竖直边落差 27 mm/0.5 mm，粗了就会在断崖那一列假报超差）
function loft(bone, z0mm, z1mm, topF, botF, xh, mat, step) {
  const st = step || 12;
  const emit = (a, b) => {
    const yb = Math.min(botF(a), botF(b));
    const yt = Math.max(topF(a), topF(b));
    if (yt - yb < 0.6) return;
    mbox(bone, xh, yb, a, yt, b, mat);
  };
  const rec = (a, b, d) => {
    if (b - a > LOFT_MIN_SEG && d < 7 &&
      (Math.abs(topF(b) - topF(a)) > LOFT_MAX_SLOPE || Math.abs(botF(b) - botF(a)) > LOFT_MAX_SLOPE)) {
      const m = kneeIn(a, b) || (a + b) / 2;
      if (m > a + 0.02 && m < b - 0.02) { rec(a, m, d + 1); rec(m, b, d + 1); } else emit(a, b);
    } else emit(a, b);
  };
  const n = Math.max(1, Math.ceil((z1mm - z0mm) / st));
  for (let i = 0; i < n; i++) {
    rec(z0mm + i * (z1mm - z0mm) / n, z0mm + (i + 1) * (z1mm - z0mm) / n, 0);
  }
}

/** 沿 Z 的薄墙/薄杆：x 只占一层皮，上下缘按函数走（箱侧加强筋、卡榫长杆一类）。
 *  与 loft 同规矩：段内变化超过 MAX_SLOPE 就二分细分 —— 只按端点给常量会在陡坡处戳出十几毫米。 */
function wallZ(bone, x0, x1, z0mm, z1mm, topF, botF, mat, step) {
  const st = step || 8;
  const n = Math.max(1, Math.ceil((z1mm - z0mm) / st));
  const rec = (a, b, d) => {
    const yb = Math.min(botF(a), botF(b));
    const yt = Math.max(topF(a), topF(b));
    if (yt - yb < 0.6) return;
    if (b - a > LOFT_MIN_SEG && d < 7 &&
      (Math.abs(topF(b) - topF(a)) > LOFT_MAX_SLOPE || Math.abs(botF(b) - botF(a)) > LOFT_MAX_SLOPE)) {
      { const m = kneeIn(a, b) || (a + b) / 2;
        if (m > a + 0.02 && m < b - 0.02) { rec(a, m, d + 1); rec(m, b, d + 1); } else box(bone, [x0, Yu(yb), Zb(a)], [x1, Yu(yt), Zb(b)], mat); }
    } else box(bone, [x0, Yu(yb), Zb(a)], [x1, Yu(yt), Zb(b)], mat);
  };
  for (let i = 0; i < n; i++) rec(z0mm + i * (z1mm - z0mm) / n, z0mm + (i + 1) * (z1mm - z0mm) / n, 0);
}

/** 圆柱（沿 Z）：实心芯 + 外圈棱（只贴一圈壳会变镂空管） */
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
    box(bone, [cx + Math.min(ix, ex) - w / 2, cy + Math.min(iy, ey) - w / 2, z0 + i * dz],
      [cx + Math.max(ix, ex) + w / 2, cy + Math.max(iy, ey) + w / 2, z0 + (i + 1) * dz], mat);
  }
}

/* ================================================================ 1. 枪管组（bone: barrel）
 * 照片：z 0~192 裸露枪管（外径 18~20 mm），上面有前准星（尖 +21.5），
 * 下面有刺刀座挡块（z 12~42）与拖曳钩（z 108~192，深到 −42）。 */
loft('barrel', 5, Z_FORE_A, (z) => BARREL_TOP(z), (z) => BARREL_BOT(z), W_BARREL(0), 'blued', 16);
tubeZ('barrel', 0, BARREL_CY, Zb(Z_FORE_A), Zb(Z_RECV_A + 30), 10.3 / 62.5, 8, 'blued');   // 藏在木头/机匣里
/* 膛口：一圈抛光钢帽 + 里面的黑洞（真枪从枪口能看到膛线） */
tubeZ('barrel', 0, BARREL_CY, Zb(0), Zb(8), 9.8 / 62.5, 10, 'pol');   // 帽沿必须止于 z=0：多出的 0.4 mm 会让整张对表网格整体偏 0.4 mm（每条断崖都假报 1 列）
box('barrel', [-4 / 62.5, BARREL_CY - 4 / 62.5, Zb(0)], [4 / 62.5, BARREL_CY + 4 / 62.5, Zb(4)], 'dark');

/* 前准星：底座楔 + 刃片（刃尖 +21.5 mm）+ 两侧护耳 */
mbox('barrel', 6.5 / 62.5, BARREL_TOP(30) - 2.0, Z_SIGHT_A, 17.5, Z_SIGHT_B, 'blued');
mbox('barrel', 2.6 / 62.5, 17.5, Z_SIGHT_A + 6, 21.5, Z_SIGHT_B - 6, 'pol');
for (const sx of [-1, 1]) {
  box('barrel', [sx * 5.5 / 62.5 - 1.2 / 62.5, Yu(BARREL_TOP(30) - 2.5), Zb(Z_SIGHT_A + 2)],
    [sx * 5.5 / 62.5 + 1.2 / 62.5, Yu(19.5), Zb(Z_SIGHT_B - 2)], 'steel');
}
/* 枪口下方的刺刀座挡块 */
mbox('barrel', 6.0 / 62.5, BARREL_BOT(25) + 0.5, Z_LUG_A, -15.0, Z_LUG_B, 'steel');

/* 拖曳钩 / 刺刀座（Lebel 件沿用）：横杆 + 前端圆头，实测底 −42 */
mbox('barrel', 5.0 / 62.5, BARREL_BOT(150) + 0.5, Z_HOOK_A + 8, -41.5, Z_HOOK_B, 'blued');
mbox('barrel', 3.4 / 62.5, -32.0, Z_HOOK_A + 1, -44.8, Z_HOOK_A + 12, 'steel');   // 前端（朝 −Z）圆头
tubeZ('barrel', 0, Yu(-40.0), Zb(Z_HOOK_A), Zb(Z_HOOK_A + 9), 4.0 / 62.5, 6, 'pol');
mbox('barrel', 4.0 / 62.5, -41.0, Z_HOOK_B - 22, -33.0, Z_HOOK_B, 'steel');
/* 枪管中段下方的小钉（实测 z 66~75 下缘 −12.5） */
mbox('barrel', 2.6 / 62.5, -12.6, 66, BARREL_BOT(70) + 1, 76, 'steel');

/* ================================================================ 2. 前托（bone: forend）
 * 照片：木护木 z 192~865，底 −34~−42；z 490 起枪管上方多一条上手木（顶 +22~+25）。 */
loft('forend', Z_FORE_A, Z_FORE_B, (z) => BARREL_BOT(z) + 1.2, (z) => pBw(z), W_FORE, 'wood', 14);
loft('forend', Z_FORE_A, Z_FORE_B, (z) => pBw(z) + 3.2, (z) => pBw(z), W_FORE - 0.02, 'woodd', 26);
/* 上手木（盖住枪管上方） */
loft('forend', Z_HAND_A, Z_HAND_B, (z) => pT(z), (z) => BARREL_TOP(z) - 1.6, W_HAND, 'wood', 16);
loft('forend', Z_HAND_A, Z_HAND_B, (z) => pT(z), (z) => pT(z) - 2.4, W_HAND - 0.018, 'woodl', 26);
/* 上手木前端金属箍（照片 z≈490 处顶面抬升的那圈） */
mbox('forend', W_HAND + 0.012, BARREL_BOT(500) + 1, Z_HAND_A - 5, pT(Z_HAND_A) + 1.5, Z_HAND_A + 14, 'blued');
/* 前枪箍（木前端那圈金属，实测 z 171~197） */
mbox('forend', W_FORE + 0.014, pB(184) - 1.5, Z_BAND_F_A, BARREL_TOP(184) - 1, Z_BAND_F_B, 'blued');
/* 中枪箍 + 前背带环（实测 z 690~726 下探到 −58） */
loft('forend', Z_BAND_M_A, Z_BAND_M_B, (z) => BARREL_TOP(708) - 1, (z) => pBw(z), W_FORE + 0.014, 'blued', 9);
/* 前背带环（实测 z 688~707 一条向下收成尖的细环，底 −64；之后木托底回到 −38.7） */
loft('forend', 688, 707.4, () => -38.0,
  (z) => (z <= 706.5 ? -42 - (z - 688) / 18.5 * 22 : -64 + (z - 706.5) / 0.9 * 26.1), 3.2 / 62.5, 'steel', 2);
/* 前托中段的穿钉 */
mbox('forend', W_FORE + 0.008, BARREL_BOT(560) - 5, 556, BARREL_BOT(560) - 1, 566, 'pol');

/* ================================================================ 3. 机匣（bone: body）
 * 照片：黑色金属段 z 862~1132，顶面 +20~+22.5；前上方表尺顶 +28。 */
loft('body', Z_RECV_A, Z_RECV_B, (z) => Math.max(pT(z), -20), () => Y_RECV_FLOOR, W_RECV, 'steel', 18);
/* 机匣前环（枪管入匣处略粗一圈） */
mbox('body', W_RECV + 0.012, Y_RECV_FLOOR - 1, Z_RECV_A, Math.max(pT(Z_RECV_A + 8), -20) + 1, Z_RECV_A + 24, 'blued');
/* 表尺/照门（顶面直接吃实测上缘：z 782~862 由 +23.6 升到 +28.2） */
loft('body', Z_SIGHT_R_A, Z_SIGHT_R_B, (z) => pT(z), (z) => BARREL_TOP(z) - 2.5, 10.0 / 62.5, 'blued', 14);
for (const sx of [-1, 1]) {
  box('body', [sx * 9.0 / 62.5 - 1.5 / 62.5, Yu(pT(820) - 7), Zb(Z_SIGHT_R_A + 6)],
    [sx * 9.0 / 62.5 + 1.5 / 62.5, Yu(pT(820) + 1.5), Zb(Z_SIGHT_R_B - 6)], 'steel');
}
/* 抛壳口（射手右侧 +X 的凹腔） */
box('body', [W_RECV - 0.05, Yu(-12), Zb(Z_RECV_A + 60)], [W_RECV + 0.006, Yu(14), Zb(Z_RECV_A + 190)], 'dark');
/* 节套/尾板（z 1110~1138，顶面从 +16 跌到 −25） */
loft('body', Z_RECV_B - 24, Z_RECV_B + 6, (z) => Math.max(pT(z), -24), () => Y_RECV_FLOOR, W_RECV - 0.02, 'steel', 3);
/* 机匣顶面的枪机通道 */
mbox('body', 13.0 / 62.5, Math.max(pT(1000), -20) - 5, Z_RECV_A + 40, Math.max(pT(1000), -20) + 0.6, Z_RECV_B - 30, 'blued');
/* 手动保险（真枪在机匣左侧 −X） */
box('body', [-0.30, Yu(-4), Zb(1088)], [-0.235, Yu(13), Zb(1120)], 'pol');
/* 机匣两侧的横销 */
for (const sx of [-1, 1]) {
  for (let i = 0; i < 2; i++) {
    const z = Z_RECV_A + 70 + i * 90;
    box('body', [sx * (W_RECV + 0.004) - 0.014, Yu(-12), Zb(z)], [sx * (W_RECV + 0.004) + 0.014, Yu(-7.5), Zb(z + 9)], 'pol');
  }
}

/* ================================================================ 4. 枪机 + 拉机柄（bone: bolt）
 * 真枪：旋转闭锁枪机；拉机柄在机匣右侧，**只沿枪轴平移、不旋转**。
 * 照片：机匣右侧 z≈1005~1035、Y≈+3 处一个 Ø22 mm 圆钮。 */
box('bolt', [-0.135, Yu(-8), Zb(Z_RECV_A + 40)], [0.135, Yu(8), Zb(Z_RECV_B - 6)], 'pol');
box('bolt', [-0.115, Yu(-7), Zb(Z_RECV_A + 20)], [0.115, Yu(7), Zb(Z_RECV_A + 40)], 'steel');
box('bolt', [0.10, Yu(-4), Zb(1002)], [0.30, Yu(6), Zb(1024)], 'pol');
box('bolt', [0.28, Yu(-4.5), Zb(1000)], [0.415, Yu(10), Zb(1032)], 'pol');
box('bolt', [0.395, Yu(-2), Zb(1002)], [0.455, Yu(8), Zb(1030)], 'steel');
box('bolt', [-0.135, Yu(-7), Zb(Z_RECV_B - 10)], [0.135, Yu(6), Zb(Z_RECV_B)], 'pol');   // 枪机尾（不越过节套，别高出梳背）
box('bolt', [0.10, Yu(4), Zb(Z_RECV_A + 30)], [0.145, Yu(9), Zb(Z_RECV_A + 46)], 'steel');
box('bolt', [-0.145, Yu(3), Zb(Z_RECV_A + 30)], [-0.10, Yu(9), Zb(Z_RECV_A + 50)], 'steel');

/* ================================================================ 5. 弹匣箱 / 弹匣盖 / 漏夹
 * 真机：5 发漏夹从**下方**插进固定弹匣；松卡榫后弹匣盖**向前下方敞开**；
 * 无自动空仓挂机（M1918 才有）。实测箱底 −88.6 在 z 940~960。 */
loft('body', Z_MAG_A, Z_MAG_B, () => -22, (z) => Math.min(pB(z) + 5, -30), W_MAG, 'steel', 8);
for (const sx of [-1, 1]) {                       // 箱侧壁加强筋（下缘跟实测箱底走：z 876 的 −37 与 z 950 的 −75 不同列）
  wallZ('body', sx * W_MAG - 0.006, sx * W_MAG + 0.006, Z_MAG_A + 18, Z_MAG_B - 14,
    () => -26, (z) => pB(z) + 14, 'blued', 8);
}
/* 弹匣盖（bone: mag_cover）—— 铰链在**前端**（z 最小处），向下前方敞开 */
loft('mag_cover', Z_MAG_A + 6, Z_MAG_B - 4, (z) => pB(z) + 6.0, (z) => pB(z) + 0.5, W_MAG + 0.012, 'steel', 6);
loft('mag_cover', Z_MAG_A + 12, Z_MAG_B - 10, (z) => pB(z) + 5.0, (z) => pB(z) + 2.0, W_MAG - 0.02, 'dark', 10);
wallZ('mag_cover', -0.05, 0.05, Z_MAG_B - 26, Z_MAG_B - 6, (z) => pB(z) + 7, (z) => pB(z) - 2, 'pol', 6);   // 卡榫（下缘跟实测）
wallZ('mag_cover', -(W_MAG + 0.03), W_MAG + 0.03, Z_MAG_A - 2, Z_MAG_A + 12, (z) => pB(z) + 8, (z) => pB(z), 'pol', 6); // 铰链

/* 漏夹（bone: clip）—— 5 发 8mm 勒贝尔，弹头朝 −Z，竖着叠在匣里。
 * 注意：所有弹药件都必须**待在弹匣箱内腔里**（不能戳穿箱底），所以下缘统一跟着
 * 内底 FLOOR(z) = 箱底 + 6 mm 走；某一发若在内底之上放不下，就那一段不生成。 */
const CLIP_W = 13.0 / 62.5;
const MAG_TOP = -22;
const FLOOR = (z) => pB(z) + 6;                      // 弹匣内底（mm）
/** 求 [z0,z1] 内满足 ok(z) 的连续区间（弹药件只能待在放得下的那几段里） */
function spanWhere(z0, z1, ok) {
  const segs = [];
  let a = null;
  for (let z = z0; z <= z1; z += 1) {
    if (ok(z)) { if (a === null) a = z; } else if (a !== null) { segs.push([a, z]); a = null; }
  }
  if (a !== null) segs.push([a, z1]);
  return segs;
}
const ROUND_N = 5;
const ROUND_H = (MAG_TOP - 4 - pB(950)) / ROUND_N * 0.94;
for (let r = 0; r < ROUND_N; r++) {
  const yt = MAG_TOP - 4 - r * ROUND_H;
  const yb = yt - ROUND_H * 0.80;
  for (const [za, zb] of spanWhere(Z_MAG_A + 2, Z_MAG_B - 6, (z) => FLOOR(z) <= yb - 0.5)) {
    const split = Math.min(zb, Z_MAG_A + 34);        // 弹头段（被甲）在前
    mbox('clip', CLIP_W, yb, za, yt, split, 'copper');
    if (zb > split) mbox('clip', CLIP_W, yb, split, yt, zb, 'brass');
  }
}
/* 漏夹钢框：内腔里的一条脊（下缘跟着内底走，绝不戳穿箱底） */
loft('clip', Z_MAG_A + 6, Z_MAG_B - 4, () => MAG_TOP - 2.5, FLOOR, CLIP_W - 0.012, 'lead', 18);
/* 空漏夹（bone: clip_empty）—— 只有钢框，平时被动画 scale 收掉 */
loft('clip_empty', Z_MAG_A + 6, Z_MAG_B - 4, () => MAG_TOP - 2.5, FLOOR, CLIP_W - 0.012, 'lead', 18);

/* ================================================================ 6. 扳机组（bone: trigger / safety）
 * 实测：护圈底 −48（z 1000~1030），后面的长杆 −75（z 1060~1080）。 */
mbox('body', 5.0 / 62.5, Y_RECV_FLOOR, Z_GUARD_A, pB(1006), Z_GUARD_A + 8, 'blued');   // 前柱
/* 底圈：下缘照实测表走（z 1010 是 −46、z 1030 掉到 −59，拿定点常量拉满会浅 9 mm） */
loft('body', Z_GUARD_A + 6, Z_GUARD_B, () => -40, (z) => pB(z), 5.0 / 62.5, 'blued', 6);
mbox('body', 5.0 / 62.5, Y_RECV_FLOOR, Z_GUARD_B - 6, pB(Z_GUARD_B - 2), Z_GUARD_B, 'blued');  // 后柱
mbox('body', 0.14, Y_RECV_FLOOR, Z_MAG_B - 4, -19, Z_GUARD_B, 'steel');
/* 扳机片（bone: trigger） */
mbox('trigger', 4.0 / 62.5, pB(1014) + 2, Z_GUARD_A + 12, -24, Z_GUARD_A + 19, 'pol');
mbox('trigger', 3.0 / 62.5, pB(1014) + 2, Z_GUARD_A + 19, -29, Z_GUARD_A + 25, 'pol');
/* 弹匣盖卡榫长杆 + 保险（bone: safety）：实测 −75 */
loft('safety', Z_LEVER_A, Z_LEVER_B, () => -26, (z) => pB(z) + 1, 5.5 / 62.5, 'pol', 8);
mbox('safety', 3.0 / 62.5, pB(1064) + 1, Z_LEVER_A - 2, pB(1064) + 7, Z_LEVER_A + 8, 'pol');
box('safety', [-0.31, Yu(-4), Zb(Z_LEVER_B - 26)], [-0.255, Yu(11), Zb(Z_LEVER_B + 6)], 'pol');

/* ================================================================ 7. 抛壳 / 单发补弹
 * 8mm 勒贝尔空壳：黄铜壳身 + 底缘，枪机后拉时从右侧抛壳口甩出。 */
const CASE_Z = Z_RECV_A + 92;
box('casing', [0.10, Yu(1), Zb(CASE_Z - 40)], [0.175, Yu(6), Zb(CASE_Z + 2)], 'brass');
box('casing', [0.095, Yu(-1), Zb(CASE_Z + 2)], [0.18, Yu(7), Zb(CASE_Z + 6)], 'pol');
/* 单发补弹的那一发（bone: round_in），平时被动画 scale 收掉 */
mbox('round_in', 5.0 / 62.5, -5, Z_HAND_A + 30, 5, Z_HAND_A + 90, 'brass');

/* ================================================================ 8. 枪托（bone: body）
 * 照片：托颈（木）从 z ~1085 起；梳背 −26~−24.6；托腹下垂到 −119；托底板 z 1306~1319。 */
loft('body', Z_WRIST_A, Z_RECV_B, (z) => Math.min(pT(z), Y_RECV_FLOOR), (z) => pB(z), W_BUTT - 0.03, 'wood', 14);
loft('body', Z_RECV_B, Z_PLATE_A, (z) => pT(z), (z) => pB(z), W_BUTT, 'wood', 13);
loft('body', Z_RECV_B, Z_PLATE_A, (z) => pB(z) + 3.4, (z) => pB(z), W_BUTT - 0.02, 'woodd', 26);
loft('body', Z_RECV_B, Z_PLATE_A - 40, (z) => pT(z), (z) => pT(z) - 2.4, W_BUTT - 0.02, 'woodl', 26);
/* 握把格纹（防滑格） */
for (let i = 0; i < 3; i++) {
  const z = 1152 + i * 26;
  mbox('body', W_BUTT - 0.025, pB(z) + 5, z, -30, z + 9, 'woodd');
}
/* 托底板（两片钢） */
loft('body', Z_PLATE_A, Z_BUTT, (z) => pT(z), (z) => pB(z), W_BUTT, 'dark', 5);
loft('body', Z_BUTT - 3, Z_BUTT, (z) => pT(z) + 1, (z) => pB(z) - 1, W_BUTT - 0.01, 'steel', 5);
/* 后背带环（实测底 −119 在 z 1212~1244） */
mbox('body', 3.0 / 62.5, -112, 1214, -104, 1244, 'steel');
for (const sx of [-1, 1]) {
  box('body', [sx * 3.0 / 62.5 - 1.2 / 62.5, Yu(-114), Zb(1216)],
    [sx * 3.0 / 62.5 + 1.2 / 62.5, Yu(pB(1230) + 3), Zb(1237)], 'steel');
}
/* 节套尾板螺钉 + 握把帽 */
mbox('body', 0.10, -28, Z_RECV_B - 6, -23, Z_RECV_B + 10, 'pol');
mbox('body', 0.08, pB(1100) + 2, 1092, pB(1100) + 9, 1122, 'steel');

/* ================================================================ 9. 左手支撑块（bone: hand_l） */
box('hand_l', [-0.145, -1.05, Zb(560)], [0.145, -0.60, Zb(640)], 'woodd');

/* ================================================================ 骨骼
 * 原点 = 机匣中心（膛线轴 = Y 0，扳机片在 Z ≈ +0.22）；骨骼一律零旋转。 */
const bones = [
  { name: 'root', pivot: [0, Y_BORE, 5] },
  { name: 'move', parent: 'root', pivot: [0, Y_BORE, 5] },
  { name: 'body', parent: 'move', pivot: [0, Y_BORE, 0] },
  { name: 'barrel', parent: 'move', pivot: [0, Y_BORE, -2.72] },
  { name: 'forend', parent: 'move', pivot: [0, -0.3, -3.12] },
  { name: 'hand_l', parent: 'move', pivot: [0, -0.85, -6.18] },
  { name: 'cover', parent: 'move', pivot: [0, 0.375, -2.42] },
  { name: 'bolt', parent: 'move', pivot: [0, 0, 1.93] },
  { name: 'mag_cover', parent: 'move', pivot: [0, -1.5, -1.16] },
  { name: 'clip', parent: 'move', pivot: [0, -0.92, -0.6] },
  { name: 'clip_empty', parent: 'move', pivot: [0, -0.92, -0.6] },
  { name: 'casing', parent: 'move', pivot: [-0.14, 0.05, -1.42] },
  { name: 'round_in', parent: 'move', pivot: [0, 0, -2.06] },
  { name: 'trigger', parent: 'move', pivot: [0, -0.34, 0.22] },
  { name: 'safety', parent: 'move', pivot: [0, 0, 1.48] },
  { name: 'magazine', parent: 'move', pivot: [0, -1.5, -1.18] },
  { name: 'additional_magazine', parent: 'move', pivot: [0, -1.5, -1.18] },
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
const Z_BUTT_U = Zb(Z_BUTT);
if (Math.abs(lo[2] - Z_MUZZLE) > 0.06) fails.push(`枪口 Z=${lo[2].toFixed(2)}，量取值 ${Z_MUZZLE}`);
if (Math.abs(hi[2] - Z_BUTT_U) > 0.10) fails.push(`托底 Z=${hi[2].toFixed(2)}，量取值 ${Z_BUTT_U.toFixed(2)}`);
if (lenZ < 12 || lenZ > 24) fails.push(`全长 ${lenZ.toFixed(2)}u 超出 12~24u`);
if (Math.abs(lenZ - (Z_BUTT / 62.5)) > 0.05) fails.push(`全长 ${lenZ.toFixed(2)}u 与实测 ${(Z_BUTT / 62.5).toFixed(2)}u 不符`);
if (Math.abs(widX - W_BUTT * 2) > 0.14) fails.push(`宽 ${widX.toFixed(2)}u 与木托宽 ${(W_BUTT * 2).toFixed(2)}u 差太多`);
const heiExp = (Math.max(pT(840), pT(1000)) - Math.min(pB(1220), pB(1240))) / 62.5;
if (Math.abs(heiY - heiExp) > 0.35) fails.push(`高 ${heiY.toFixed(2)}u 与实测轮廓 ${heiExp.toFixed(2)}u 差太多`);

/* 弹药件收口：clip / clip_empty 的每一块，下缘不得低于它跨度内的弹匣内底
 * （否则会从箱底或前脸戳出来 —— 曾有一排 5 发的底缘在 z 892 处低出真值 22 mm）。 */
for (let i = cubes.length - 1; i >= 0; i--) {
  const c = cubes[i];
  if (c.bone !== 'clip' && c.bone !== 'clip_empty') continue;
  const z0 = (c.origin[2] - Z_MUZZLE) / MM, z1 = (c.origin[2] + c.size[2] - Z_MUZZLE) / MM;
  let f = -1e9;
  for (let z = z0; z <= z1 + 1e-6; z += 1) f = Math.max(f, FLOOR(z));
  const yb = Yu(f);
  if (c.origin[1] < yb) { const d = yb - c.origin[1]; c.origin[1] = yb; c.size[1] -= d; }
  if (c.size[1] < 0.004) cubes.splice(i, 1);
}

module.exports = {
  cubes, bones, MAT, SHADE, fails,
  stats: { total: cubes.length, lenZ, widX, heiY, lo, hi },
  Z: {
    Z_MUZZLE, Z_BUTT: Z_BUTT_U, Z_RECV_A: Zb(Z_RECV_A), Z_RECV_B: Zb(Z_RECV_B),
    Z_MAG_A: Zb(Z_MAG_A), Z_MAG_B: Zb(Z_MAG_B), Y_BORE, Y_MAG_BOT: Yu(FLOOR(950)), Y_MAG_TOP: Yu(MAG_TOP),
  },
  prof: { mm_per_px: MM_PER_PX, pT, pB, Zb, Yu },
};

if (require.main === module) {
  const ei = process.argv.indexOf('--emit');
  if (ei >= 0 && process.argv[ei + 1]) {
    const doc = {
      format_version: '1.12.0',
      'minecraft:geometry': [{
        description: { identifier: 'geometry.rsc_1917', texture_width: 512, texture_height: 512 },
        bones: bones.map((b) => {
          const o = { name: b.name, pivot: b.pivot };
          if (b.parent) o.parent = b.parent;
          const cs = cubes.filter((c) => c.bone === b.name)
            .map((c) => ({ origin: c.origin, size: c.size, uv: [0, 0] }));
          if (cs.length) o.cubes = cs;
          return o;
        }),
      }],
    };
    const p = process.argv[ei + 1];
    fs.writeFileSync(p, JSON.stringify(doc));
    console.log(`[emit] ${cubes.length} cubes -> ${p}`);
  }
  console.log(`方块 ${cubes.length} / 骨骼 ${bones.length}`);
  console.log(`长(Z) ${lenZ.toFixed(2)} u = ${(lenZ / 16).toFixed(2)} 格 = ${(lenZ / MM).toFixed(0)} mm（实测剪影 ${Z_BUTT.toFixed(0)} mm）`);
  console.log(`Z 范围 [${lo[2].toFixed(2)}, ${hi[2].toFixed(2)}]   宽(X) ${widX.toFixed(2)} u   高(Y) ${heiY.toFixed(2)} u`);
  console.log(`Y 范围 [${lo[1].toFixed(2)}, ${hi[1].toFixed(2)}]（0 = 膛线轴）`);
  const byBone = {};
  for (const c of cubes) byBone[c.bone] = (byBone[c.bone] || 0) + 1;
  console.log('每骨方块数:', Object.entries(byBone).map(([k, v]) => `${k}=${v}`).join('  '));
  console.log(fails.length ? `*** 自检失败:\n  ${fails.join('\n  ')}` : '自检: 全部通过');
}
