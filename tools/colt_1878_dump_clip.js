'use strict';
/* 打印某个动画片段每个骨、每条通道的关键帧（时间 -> 值）。
 * 核对折开用的 body / barrel 是否严格反向、时长对不对 —— 比截图快也比截图准。
 *
 * 用法: node tools/colt_1878_dump_clip.js reload_tactical
 *       node tools/colt_1878_dump_clip.js          （默认打印全部片段的一行摘要）
 */
const fs = require('fs');
const path = require('path');

const P = path.join(__dirname, '..', 'src', 'main', 'resources', 'assets',
  'apocalypse_zombies', 'animations', 'colt_1878.animation.json');
const j = JSON.parse(fs.readFileSync(P, 'utf8'));
const clips = j.animations || {};
const want = process.argv[2];

if (!want) {
  for (const [name, a] of Object.entries(clips)) {
    console.log(`${name.padEnd(17)} ${String(a.animation_length).padStart(4)}s = ${String(Math.round(a.animation_length * 20)).padStart(2)} tick  骨: ${Object.keys(a.bones || {}).join(', ')}`);
  }
  process.exit(0);
}

const a = clips[want];
if (!a) { console.log('没有片段', want, '现有：', Object.keys(clips).join(', ')); process.exit(1); }
console.log(`${want}  length=${a.animation_length}s = ${Math.round(a.animation_length * 20)} tick  loop=${a.loop}`);
for (const [bone, chans] of Object.entries(a.bones || {})) {
  for (const [ch, node] of Object.entries(chans)) {
    const keys = Object.keys(node);
    const times = keys.filter((k) => Number.isFinite(Number(k))).map(Number).sort((x, y) => x - y);
    const parts = times.map((t) => {
      const kf = node[t] ?? node[keys.find((k) => Number(k) === t)];
      if (kf === null || kf === undefined) return `${t}→?`;
      if (typeof kf === 'number') return `${t}→${kf}`;
      const v = kf.vector ?? kf;
      return `${t}→[${(Array.isArray(v) ? v : [v]).map((x) => (typeof x === 'number' ? +x.toFixed(2) : x)).join(',')}]`;
    });
    console.log(`  ${bone.padEnd(13)} ${ch.padEnd(9)} ${parts.join('  ')}`);
  }
}
