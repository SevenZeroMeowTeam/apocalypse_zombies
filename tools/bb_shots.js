'use strict';
/* 通过 MCP 抓 Blockbench 里当前项目的几个正交/透视视图，存成 PNG 供人眼核验。
 * 用法: node tools/bb_shots.js <outPrefix> [pitch]...
 *   node tools/bb_shots.js build/s686
 */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');

const VIEWS = [
  { id: 'side_east',  pos: [52, 0, -0.2],  target: [0, 0, -0.2],  fov: 26 },
  { id: 'side_left',  pos: [-52, 0, -0.2], target: [0, 0, -0.2],  fov: 26 },
  { id: 'iso',        pos: [22, 14, -20],  target: [0, 0, -0.2],  fov: 40 },
  { id: 'iso_rear',   pos: [-16, 11, 17],  target: [0, -0.2, 0],  fov: 40 },
];

async function main() {
  const prefix = process.argv[2] || 'build/bb_view';
  const bb = await Bb.connect();
  const made = [];

  for (const v of VIEWS) {
    try { await bb.t('delete_offscreen_view', { view: v.id }); } catch (e) { /* 不存在就算了 */ }
    await bb.t('create_offscreen_view', { id: v.id, width: 1100, height: 620, antialias: false, copy_view: 'none' });
    const args = {
      view: v.id,
      position: v.pos,
      target: v.target,
      projection: v.locked ? 'orthographic' : 'perspective',
    };
    if (v.locked) { args.locked_angle = v.locked; args.zoom = v.zoom; }
    if (v.fov) args.fov = v.fov;
    await bb.t('set_camera_angle', args);
    const shot = await bb.call('capture_screenshot', { view: v.id });
    if (!shot.images.length) { console.log(`[${v.id}] 无图片返回: ${shot.text.slice(0, 200)}`); continue; }
    const out = path.resolve(ROOT, `${prefix}_${v.id}.png`);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, Buffer.from(shot.images[0].data, 'base64'));
    made.push(out);
    console.log(`[${v.id}] ${out} (${fs.statSync(out).size} bytes)`);
  }

  for (const v of VIEWS) { try { await bb.t('delete_offscreen_view', { view: v.id }); } catch (e) { /* 已删 */ } }
  console.log('done:', made.length, 'shots');
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
