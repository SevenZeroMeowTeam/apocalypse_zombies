'use strict';
/* 猫耳娘 —— 多角度抓图（人眼核验用）。默认 4 视图（Blockbench 上限 4 个 offscreen view）。
 * 用法: node tools/cat_girl_shots.js [outPrefix] [tag]
 *   node tools/cat_girl_shots.js art/cat_girl/shots v3
 * 正交/透视都走 set_camera_angle；模型高约 34u，中心 y≈16。
 */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');

const VIEWS = [
  { id: 'front', pos: [0, 17, -46], target: [0, 17, 0], fov: 20 },
  { id: 'side', pos: [46, 17, 0], target: [0, 17, 0], fov: 20 },
  { id: 'back', pos: [0, 17, 46], target: [0, 17, 0], fov: 20 },
  { id: 'front3q', pos: [-33, 20, -33], target: [0, 17, 0], fov: 20 },
];

async function main() {
  const prefix = process.argv[2] || 'art/cat_girl/shots/front';
  const bb = await Bb.connect();
  const made = [];

  for (const v of VIEWS) {
    try { await bb.t('delete_offscreen_view', { view: v.id }); } catch (e) { /* 不存在就算了 */ }
    await bb.t('create_offscreen_view', { id: v.id, width: 760, height: 1000, antialias: false, copy_view: 'none' });
    await bb.t('set_camera_angle', { view: v.id, position: v.pos, target: v.target, projection: 'perspective', fov: v.fov });
    const shot = await bb.call('capture_screenshot', { view: v.id });
    if (!shot.images.length) { console.log(`[${v.id}] 无图片: ${String(shot.text).slice(0, 160)}`); continue; }
    const out = path.resolve(ROOT, `${prefix}_${v.id}.png`);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, Buffer.from(shot.images[0].data, 'base64'));
    made.push(out);
    console.log(`[${v.id}] ${out} (${fs.statSync(out).size} B)`);
  }

  for (const v of VIEWS) { try { await bb.t('delete_offscreen_view', { view: v.id }); } catch (e) { /* 已删 */ } }
  console.log('done:', made.length, 'shots');
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
