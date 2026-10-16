// _bb_probe_codec.js —— 探测动画 codec 与 fs 可用性（决定怎么把 .animation.json 落盘）
const out = { hasRequire: typeof require === 'function' };
try {
  out.codecs = Object.keys(Codecs);
  const bf = Codecs.bedrock && Codecs.bedrock.format;
  out.bedrockFormatKeys = bf ? Object.keys(bf).filter((k) => /codec|anim/i.test(k)) : null;
  const ac = bf && bf.animation_codec;
  out.animCodec = ac ? { id: ac.id, name: ac.name, hasCompile: typeof ac.compile === 'function', hasExport: typeof ac.export === 'function' } : null;
} catch (e) {
  out.err = String(e && e.message);
}
try {
  const fs = require('fs');
  const os = require('os');
  out.fsOk = typeof fs.writeFileSync === 'function';
  out.tmp = os.tmpdir ? os.tmpdir() : null;
} catch (e) {
  out.fsErr = String(e && e.message);
}
out.animations = Animation.all.map((a) => ({ name: a.name, length: a.length, loop: a.loop, selected: a.selected }));
out.projectFormat = Project && Project.format ? Project.format.id : null;
out.modelIdentifier = Project ? Project.model_identifier : null;
return out;
