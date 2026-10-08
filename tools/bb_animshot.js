'use strict';
/* 抓取某个动画在指定时刻的画面（换弹折开方向 / 弹壳进出 / 合膛都要人眼确认）。
 * 用法: node tools/bb_animshot.js <clip> <prefix> <t1,t2,...> */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');
const ROOT = path.resolve(__dirname, '..');

async function main() {
  const clip = process.argv[2] || 'animation.reload_empty';
  const prefix = process.argv[3] || 'build/anim';
  const times = (process.argv[4] || '0.6,1.2,2.0,2.8').split(',').map(Number);
  const bb = await Bb.connect();

  await bb.t('set_mode', { mode_id: 'animate' });
  const view = 'animshot';
  try { await bb.t('delete_offscreen_view', { view }); } catch (e) { /* 无 */ }
  await bb.t('create_offscreen_view', { id: view, width: 1000, height: 560, antialias: false, copy_view: 'none' });
  await bb.t('set_camera_angle', { view, position: [26, 16, -24], target: [0, -1, -1], projection: 'perspective', fov: 42 });

  for (const t of times) {
    await bb.t('animation_timeline', { animation_id: clip, action: 'set_time', time: t });
    const shot = await bb.call('capture_screenshot', { view });
    if (!shot.images.length) { console.log(`[t=${t}] 无图: ${shot.text.slice(0, 160)}`); continue; }
    const out = path.resolve(ROOT, `${prefix}_${String(t).replace('.', 'p')}.png`);
    fs.writeFileSync(out, Buffer.from(shot.images[0].data, 'base64'));
    console.log(`[t=${t}] ${out}`);
  }
  try { await bb.t('delete_offscreen_view', { view }); } catch (e) { /* 无 */ }
}
main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
