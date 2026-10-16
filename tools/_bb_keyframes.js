// _bb_keyframes.js —— 读回某个动画某根骨骼的关键帧原始数据（诊断用）
// params: { animation:'reload_empty', bone:'cartridge' }
const P = params || {};
const animName = P.animation || 'reload_empty';
const boneName = P.bone || 'cartridge';
const anim = Animation.all.find((a) => a.name === animName || a.name === 'animation.' + animName);
if (!anim) return { error: 'no anim', have: Animation.all.map((a) => a.name) };

const entries = Object.entries(anim.animators || {});
const hit = entries.filter(([, an]) => an && an.name === boneName);
if (!hit.length) return { error: 'no animator for ' + boneName, animators: entries.map(([, an]) => an && an.name) };

const out = [];
for (const [, an] of hit) {
  for (const k of an.keyframes || []) {
    out.push({
      ch: k.channel, t: k.time, ip: k.interpolation,
      dp: (k.data_points || []).map((d) => [d.x, d.y, d.z]),
    });
  }
}
out.sort((a, b) => a.t - b.t || (a.ch < b.ch ? -1 : 1));
return {
  animation: anim.name, length: anim.length, bone: boneName,
  count: out.length,
  position_only: out.filter((k) => k.ch === 'position'),
};
