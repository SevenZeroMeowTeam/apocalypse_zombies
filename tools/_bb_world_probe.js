// _bb_world_probe.js —— 读骨骼的世界坐标（含父级旋转），用于确认"弹从哪一侧压进来"。
// 探针里读 mesh.position 是组局部量、还带符号约定，容易误判；世界坐标不会骗人。
// params: { animation:'reload_empty', bones:['cartridge'], times:[...], refs:['loading_gate'] }
const P = params || {};
const animName = P.animation || 'reload_empty';
const bones = P.bones || ['cartridge'];
const refs = P.refs || ['loading_gate'];
const times = P.times || [0];
const anim = Animation.all.find((a) => a.name === animName || a.name === 'animation.' + animName);
if (!anim) return { error: 'no anim ' + animName };

const round = (v) => +v.toFixed(3);
const refsOut = {};
for (const r of refs) {
  const c = Cube.all.find((x) => x.name === r);
  if (c) refsOut[r] = { center: [round((c.from[0] + c.to[0]) / 2), round((c.from[1] + c.to[1]) / 2), round((c.from[2] + c.to[2]) / 2)] };
}

try { if (typeof Mode !== 'undefined' && Mode.set) Mode.set('animate'); } catch (e) {}
const groups = {};
for (const b of bones) {
  const g = Group.all.find((x) => x.name === b);
  if (g) groups[b] = g;
}
anim.select();

const v = new THREE.Vector3();
const rows = [];
for (const t of times) {
  Timeline.setTime(Math.max(0, Math.min(anim.length, t)));
  Animator.preview();
  const row = { t: +t };
  for (const b of Object.keys(groups)) {
    groups[b].mesh.getWorldPosition(v);
    row[b] = [round(v.x), round(v.y), round(v.z)];
  }
  rows.push(row);
}
return {
  animation: anim.name, note: 'world position (model space, parent rotations included)',
  refs: refsOut, samples: rows,
};
