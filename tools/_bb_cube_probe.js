// _bb_cube_probe.js —— 读**方块**的世界坐标（骨骼原点是转轴、旋转时不动，看不出方向）。
// 用于验证机构动作方向：杠杆环该向下、扳机下端该向后。
// params: { animation:'bolt', cubes:['lever_loop_0','trigger_blade','bolt_body_a'], times:[...] }
const P = params || {};
const animName = P.animation || 'bolt';
const cubeNames = P.cubes || ['lever_loop_0', 'trigger_blade'];
const times = P.times || [0];
const anim = Animation.all.find((a) => a.name === animName || a.name === 'animation.' + animName);
if (!anim) return { error: 'no anim ' + animName, have: Animation.all.map((a) => a.name) };

try { if (typeof Mode !== 'undefined' && Mode.set) Mode.set('animate'); } catch (e) {}
const cubes = {};
const missing = [];
for (const n of cubeNames) {
  const c = Cube.all.find((x) => x.name === n);
  if (c && c.mesh) cubes[n] = c;
  else missing.push(n);
}
anim.select();

const v = new THREE.Vector3();
const round = (x) => +x.toFixed(4);
const rows = [];
for (const t of times) {
  Timeline.setTime(Math.max(0, Math.min(anim.length, t)));
  Animator.preview();
  const row = { t: +t };
  for (const n of Object.keys(cubes)) {
    cubes[n].mesh.getWorldPosition(v);
    row[n] = [round(v.x), round(v.y), round(v.z)];
  }
  rows.push(row);
}
const out = { animation: anim.name, missing, samples: rows };
if (rows.length > 1) {
  const d = {};
  for (const n of Object.keys(cubes)) {
    d[n] = rows[rows.length - 1][n].map((x, i) => round(x - rows[0][n][i]));
  }
  out.delta_last_vs_first = d;
  out.legend = 'y 变小 = 向下；z 变大 = 向后（朝枪托）。杠杆环应向下、扳机下端应向后。';
}
return out;
