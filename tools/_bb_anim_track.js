// _bb_anim_track.js —— 只输出"相对 t=0 的变化量"的紧凑轨迹表，用于验证机构行程。
// params: { animation:'bolt', times:[...], bones:{bone:'rotation'|'position'|'scale'} }
const P = params || {};
const animName = P.animation || 'bolt';
const times = P.times || [0];
const want = P.bones || { lever: 'rotation', bolt: 'position', carrier: 'position', hammer: 'rotation', spent_shell: 'position', cartridge: 'position' };

const anim = Animation.all.find((a) => a.name === animName || a.name === 'animation.' + animName);
if (!anim) return { error: 'Animation not found: ' + animName, have: Animation.all.map((a) => a.name) };

try { if (typeof Mode !== 'undefined' && Mode.set) Mode.set('animate'); } catch (e) {}
const groups = {};
for (const b of Object.keys(want)) {
  const g = Group.all.find((x) => x.name === b);
  if (g) groups[b] = g;
}
anim.select();

const d2r = 180 / Math.PI;
const read = (g, ch) => {
  const m = g.mesh;
  if (!m) return null;
  if (ch === 'rotation') return [m.rotation.x * d2r, m.rotation.y * d2r, m.rotation.z * d2r];
  if (ch === 'position') return m.position.toArray();
  return m.scale.toArray();
};

Timeline.setTime(0);
Animator.preview();
const base = {};
for (const b of Object.keys(groups)) base[b] = read(groups[b], want[b]);

const rows = [];
for (const t of times) {
  Timeline.setTime(Math.max(0, Math.min(anim.length, t)));
  Animator.preview();
  const row = { t: +t };
  for (const b of Object.keys(groups)) {
    const v = read(groups[b], want[b]);
    if (!v || !base[b]) { row[b] = null; continue; }
    row[b] = v.map((x, i) => +(x - base[b][i]).toFixed(3));
  }
  rows.push(row);
}
return {
  animation: anim.name, length: anim.length, loop: anim.loop,
  legend: 'delta vs t=0；rotation 单位度，position/scale 单位模型单位',
  channels: want, delta: rows,
};
