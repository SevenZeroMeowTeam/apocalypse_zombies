// TEMP (apocalypse_zombies / s686): Node port of tools/pose_measure.py + tools/uzi_tp_solve.py.
// Python is not installed on this machine, so the two "geometry -> Java constant" solvers the rest of the
// weapon layer uses are reimplemented here one-to-one, to derive S686Item.ADS_X/ADS_Y and
// S686ItemRenderer's third-person constants instead of eyeballing them.
//
//   node build/s686_pose_solve.js          # calibration + S686 solve
//
// First-person chain (pose_measure.py header; each link re-checked against the decompiled 1.20.1 sources):
//   p_cam = T_base(0.56, -0.52, -0.72)
//         . S(firstPersonScale)
//         . M_stance(aim)                                  GunPose.matrix
//         . T(display/16) . Rxyz(display) . S(display.scale)
//         . T(-0.5,-0.5,-0.5) . T(+0.5,+0.51,+0.5) . (px/16)
// Third-person (uzi_tp_solve.py):
//   TP = S^-1 . R^T . (-(A + t_d)) - nudge - grip/16
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const ASSETS = path.join(ROOT, 'src/main/resources/assets/apocalypse_zombies');

const GECKO_NUDGE = [0.5, 0.51, 0.5];
const VANILLA_CENTER = [-0.5, -0.5, -0.5];
const CAM_BASE = [0.56, -0.52, -0.72];
const ANCHOR_RIGHT = [1 / 16, 0.125, -0.625];
const ANCHOR_LEFT = [-1 / 16, 0.125, -0.625];
const HIP = [-0.38, 0.27, 0.05];          // GunPose.HIP_DX/DY/DZ
const MODEL_FOV_HIP = 76.0;               // GunPose.MODEL_FOV_HIP

// ------------------------------------------------------------------ affine helpers
const deg = Math.PI / 180;
const mmul = (a, b) => a.map(row => b[0].map((_, j) => row.reduce((s, v, k) => s + v * b[k][j], 0)));
const mvec = (m, v) => m.map(row => row.reduce((s, c, k) => s + c * v[k], 0));
const Rx = d => [[1, 0, 0], [0, Math.cos(d * deg), -Math.sin(d * deg)], [0, Math.sin(d * deg), Math.cos(d * deg)]];
const Ry = d => [[Math.cos(d * deg), 0, Math.sin(d * deg)], [0, 1, 0], [-Math.sin(d * deg), 0, Math.cos(d * deg)]];
const Rz = d => [[Math.cos(d * deg), -Math.sin(d * deg), 0], [Math.sin(d * deg), Math.cos(d * deg), 0], [0, 0, 1]];
const transpose = m => m[0].map((_, i) => m.map(r => r[i]));
const rotxyz = r => mmul(Rx(r[0]), mmul(Ry(r[1]), Rz(r[2])));
const f3 = v => v.map(n => n.toFixed(4)).join(', ');

/** Whole first-person chain: model px -> camera space (blocks). */
function cameraPoint(px, display, scaleFps, aim, ads) {
  let p = [px[0] / 16 + VANILLA_CENTER[0] + GECKO_NUDGE[0],
           px[1] / 16 + VANILLA_CENTER[1] + GECKO_NUDGE[1],
           px[2] / 16 + VANILLA_CENTER[2] + GECKO_NUDGE[2]];
  const t = display.translation.map(v => v / 16);
  p = mvec(rotxyz(display.rotation), p).map(v => v * display.scale).map((v, i) => v + t[i]);
  const a = aim, k = 1 - aim;
  // GunPose.matrix, standing carry (sprint = 0), fire/lift terms zero:
  // T(hip.k + ads.a) . R_hip(k) . R_display^-1(a)
  if (k > 1e-4) p = mvec(rotxyz([0, 0, 0]), p);
  p = mvec(mmul(Ry(-display.rotation[1] * a), Rx(-display.rotation[0] * a)), p);
  p = [p[0] + HIP[0] * k + ads[0] * a, p[1] + HIP[1] * k + ads[1] * a, p[2] + HIP[2] * k + ads[2] * a];
  p = p.map(v => v * scaleFps);
  return p.map((v, i) => v + CAM_BASE[i]);
}

/** Camera-space point -> screen NDC under a given model FOV (x right, y up, +-1 = edge). */
function ndc(p, fov) {
  const z = -p[2];
  if (z <= 1e-4) return [NaN, NaN];
  const half = Math.tan((fov / 2) * deg) * z;
  return [p[0] / half, p[1] / half];
}

/** The translation that puts `rear` back on the view axis once GunPose cancels the display rotation. */
function solveAds(rear, display, scaleFps) {
  const p0 = cameraPoint(rear, display, scaleFps, 1.0, [0, 0, 0]);
  return [-p0[0] / scaleFps, -p0[1] / scaleFps];
}

/** Are the two sight points collinear with the view axis after the offsets? (angle in degrees) */
function sightAngle(rear, front, display, scaleFps, ads) {
  const pr = cameraPoint(rear, display, scaleFps, 1.0, ads);
  const pf = cameraPoint(front, display, scaleFps, 1.0, ads);
  const d = [pf[0] - pr[0], pf[1] - pr[1], pf[2] - pr[2]];
  const len = Math.hypot(...d);
  return Math.acos(Math.max(-1, Math.min(1, -d[2] / len))) / deg;
}

/** TP = S^-1 . R^T . (-(A + t_d)) - nudge - grip/16  (uzi_tp_solve.py). */
function solveTp(display, gripPx, anchor) {
  const td = display.translation.map(v => v / 16);
  const target = [0, 1, 2].map(i => -(anchor[i] + td[i]));
  let v = mvec(transpose(rotxyz(display.rotation)), target).map(c => c / display.scale);
  return v.map((c, i) => c - GECKO_NUDGE[i] - gripPx[i] / 16);
}

// ------------------------------------------------------------------ reference guns (calibration)
const REF = {
  uzi: {
    display: { rotation: [2, 4, 0], translation: [0.5, -1.35, 1], scale: 0.92 },
    fps: 1.25, rear: [0, 3.26, 4.36], front: [0, 3.26, -4.68],
    grip: [0, 0.5, 2.0], muzzle: [0, 1.6, -8.9],
    knownAds: [-0.4746, 0.3015],
    thirdperson: { rotation: [90, 0, 0], translation: [0, 0, 0], scale: 0.67 },
    knownTp: [-0.593, -0.407, 0.392, -0.438],
  },
  m1: {
    display: { rotation: [2, 4, 0], translation: [0.5, -1.35, 1], scale: 0.82 },
    fps: 1.25, rear: [0, 2.8, -1.67], front: [0, 2.8, -12.72],
    grip: null, muzzle: null, knownAds: [-0.475, 0.346],
  },
};

console.log('=== [0] 标定：Node 移植必须复现已知 Java 常量 ===');
for (const [name, r] of Object.entries(REF)) {
  const [ax, ay] = solveAds(r.rear, r.display, r.fps);
  const err = Math.max(Math.abs(ax - r.knownAds[0]), Math.abs(ay - r.knownAds[1]));
  console.log(`  ${name.padEnd(4)} 解出 ADS=(${ax.toFixed(4)}, ${ay.toFixed(4)})  源码=(${r.knownAds[0]}, ${r.knownAds[1]})  `
    + `最大误差 ${err.toExponential(2)}  ${err < 1e-4 ? 'OK' : '*** 链条不对 ***'}`);
  if (r.knownTp) {
    const tpR = solveTp(r.thirdperson, r.grip, ANCHOR_RIGHT);
    const tpL = solveTp(r.thirdperson, r.grip, ANCHOR_LEFT);
    const got = [tpR[0], tpL[0], tpR[1], tpR[2]];
    const e = Math.max(...got.map((v, i) => Math.abs(v - r.knownTp[i])));
    console.log(`       TP=(${got.map(v => v.toFixed(3)).join(', ')}) 源码=(${r.knownTp.join(', ')}) 最大误差 ${e.toExponential(2)}  ${e < 2e-3 ? 'OK' : '*** 不对 ***'}`);
  }
}

/** Hip-pose screen position of a model point, for comparing a candidate display block with the rack. */
function hipNdc(px, display, fps) {
  return ndc(cameraPoint(px, display, fps, 0.0, [0, 0, 0]), MODEL_FOV_HIP);
}

console.log('\n=== [1] 手持落点对照（aim=0，NDC；右缘 +1.77 / 下缘 −1.00）===');
for (const [name, r] of Object.entries(REF)) {
  if (!r.grip) continue;
  console.log(`  ${name.padEnd(4)} 握把 NDC=(${hipNdc(r.grip, r.display, r.fps).map(v => v.toFixed(2)).join(', ')})  `
    + `枪口 NDC=(${hipNdc(r.muzzle, r.display, r.fps).map(v => v.toFixed(2)).join(', ')})`);
}

// ------------------------------------------------------------------ S686
// Sight line: the front bead. A break-action shotgun has NO rear sight — the only sight on the gun is the
// brass bead on the rib (ring 'fs_bead', centre y = 0.300, z = -9.60, R = 0.075), so the bead's centre is the
// point the eye lines up with the target. Taking the rib's top face (y = 0.175) instead leaves the bead
// floating 0.125 u above the screen centre — that is the "aim is not on the sight" the player reported.
const S686 = {
  rear: [0.0, 0.300, -9.60],      // bead centre
  front: [0.0, 0.300, -10.06],    // muzzle face, same height as the bead => sight line parallel to the bore
  grip: [0.0, -0.80, 4.90],       // wrist of the stock: cubes span y -1.62..0.62 at z 4.44..5.36
  muzzle: [0.0, 0.0, -10.06],     // muzzle face of the barrels (barrel_upper/lower reach z = -10.06)
  scaleFps: 1.25,
};

console.log('\n=== [2] S686：候选 display 块（firstperson），选一个 ADS_Y 落在契约区间 (0.25, 0.45) 且手持落点与货架一致的 ===');
console.log('  fpsScale  transY  scale |    ADS_X    ADS_Y | 夹角 | 握把NDC       枪口NDC');
const displayScale = 0.80;
for (const ty of [-1.45, -1.0, -0.6, -0.3, 0.0, 0.3, 0.6]) {
  const display = { rotation: [2, 4, 0], translation: [0.5, ty, 1], scale: displayScale };
  const [ax, ay] = solveAds(S686.rear, display, S686.scaleFps);
  const ang = sightAngle(S686.rear, S686.front, display, S686.scaleFps, [ax, ay, 0]);
  const g = hipNdc(S686.grip, display, S686.scaleFps).map(v => v.toFixed(2)).join(', ');
  const m = hipNdc(S686.muzzle, display, S686.scaleFps).map(v => v.toFixed(2)).join(', ');
  const inBand = ay > 0.25 && ay < 0.45 && ax > -0.60 && ax < -0.35;
  console.log(`  ${S686.scaleFps.toFixed(2)}     ${ty.toFixed(2).padStart(5)}  ${displayScale}  | ${ax.toFixed(4).padStart(9)} ${ay.toFixed(4).padStart(8)} | ${ang.toFixed(2)}° | (${g})  (${m}) ${inBand ? ' <- 可用' : ''}`);
}

// ------------------------------------------------------------------ chosen constants
const CHOSEN_DISPLAY = { rotation: [2, 4, 0], translation: [0.5, 0.6, 1], scale: displayScale };
const CHOSEN_TP = { rotation: [90, 0, 0], translation: [0, 0, 0], scale: 0.58 };
const [adsX, adsY] = solveAds(S686.rear, CHOSEN_DISPLAY, S686.scaleFps);
console.log('\n=== [3] S686 定稿常量 ===');
console.log(`  display.firstperson = rot ${JSON.stringify(CHOSEN_DISPLAY.rotation)} trans ${JSON.stringify(CHOSEN_DISPLAY.translation)} scale ${CHOSEN_DISPLAY.scale}`);
console.log(`  ADS_X = ${adsX.toFixed(4)}F   ADS_Y = ${adsY.toFixed(4)}F   （契约 (−0.60,−0.35) / (0.25,0.45)：`
  + `${(adsX > -0.60 && adsX < -0.35 && adsY > 0.25 && adsY < 0.45) ? '在区间内' : '*** 越界 ***'}）`);
console.log(`  抵消 display 旋转后瞄具线与视轴夹角 = ${sightAngle(S686.rear, S686.front, CHOSEN_DISPLAY, S686.scaleFps, [adsX, adsY, 0]).toFixed(2)}°`);
console.log(`  手持（aim=0）握把 NDC=(${hipNdc(S686.grip, CHOSEN_DISPLAY, S686.scaleFps).map(v => v.toFixed(2)).join(', ')})`
  + `  枪口 NDC=(${hipNdc(S686.muzzle, CHOSEN_DISPLAY, S686.scaleFps).map(v => v.toFixed(2)).join(', ')})`);

const tpR = solveTp(CHOSEN_TP, S686.grip, ANCHOR_RIGHT);
const tpL = solveTp(CHOSEN_TP, S686.grip, ANCHOR_LEFT);
console.log(`\n  第三人称（display thirdperson rot ${JSON.stringify(CHOSEN_TP.rotation)} trans ${JSON.stringify(CHOSEN_TP.translation)} scale ${CHOSEN_TP.scale}，GRIP=${JSON.stringify(S686.grip)}）`);
console.log(`  TP_X_RIGHT = ${tpR[0].toFixed(3)}F`);
console.log(`  TP_X_LEFT  = ${tpL[0].toFixed(3)}F`);
console.log(`  TP_Y       = ${tpR[1].toFixed(3)}F`);
console.log(`  TP_Z       = ${tpR[2].toFixed(3)}F`);
console.log(`  自检 TP_X_RIGHT - TP_X_LEFT = ${(tpR[0] - tpL[0]).toFixed(6)}，理论 2*(1/16)/S = ${(2 / 16 / CHOSEN_TP.scale).toFixed(6)}`);
