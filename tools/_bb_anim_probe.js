// _bb_anim_probe.js —— 把某个动画拨到若干时刻，读出骨骼的真实姿态（数字，不依赖截图）。
// 用法 params: { animation:'bolt', times:[...], bones:[...] }
const P = params || {};
const animName = P.animation || 'bolt';
const times = P.times || [0, 0.25, 0.5, 0.75, 1];
const boneNames = P.bones || ['body', 'move', 'lever', 'bolt', 'carrier', 'hammer', 'spent_shell', 'cartridge', 'trigger'];

const anim = Animation.all.find((a) => a.name === animName || a.name === 'animation.' + animName);
if (!anim) return { error: 'Animation not found', want: animName, have: Animation.all.map((a) => a.name) };

try { if (typeof Mode !== 'undefined' && Mode.set) Mode.set('animate'); } catch (e) {}

const groups = {};
for (const b of boneNames) {
  const g = Group.all.find((x) => x.name === b);
  if (g) groups[b] = g;
}

anim.select();
const rows = [];
for (const t of times) {
  Timeline.setTime(Math.max(0, Math.min(anim.length, t)));
  Animator.preview();
  const row = { t: +t };
  for (const b of Object.keys(groups)) {
    const g = groups[b];
    const m = g.mesh;
    row[b] = {
      o: g.origin.map((v) => +v.toFixed(3)),
      // 动画驱动的是骨骼 mesh 的局部 TRS，不是 Group 的静态属性 —— 必须读 mesh。
      r: m ? [+(m.rotation.x * 180 / Math.PI).toFixed(2), +(m.rotation.y * 180 / Math.PI).toFixed(2), +(m.rotation.z * 180 / Math.PI).toFixed(2)] : null,
      p: m ? m.position.toArray().map((v) => +v.toFixed(3)) : null,
      s: m ? m.scale.toArray().map((v) => +v.toFixed(3)) : null,
    };
  }
  rows.push(row);
}

return {
  animation: anim.name,
  length: anim.length,
  loop: anim.loop,
  timeline_time: Timeline.time,
  mode: (typeof Mode !== 'undefined' && Mode.selected) ? Mode.selected.id : null,
  bones_missing: boneNames.filter((b) => !groups[b]),
  samples: rows,
};
