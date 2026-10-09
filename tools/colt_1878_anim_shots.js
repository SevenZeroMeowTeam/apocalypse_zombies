'use strict';
/* 短管喷 —— 动画相位验收图（通过 blockbench-mcp 把时间轴拨到指定秒数再截图）。
 *
 * 用法: node tools/colt_1878_anim_shots.js [outDir]
 *
 * 为什么要专门拍这个：几何截图看不出"骨头动没动"。本枪最显眼的两处机械动作是
 *   ① 外露双锤被折开机构顶回待击位（`bolt` / 两条 reload 的 hammer_l 通道）
 *   ② 管组绕铰链折下 52°（`bolt` / 两条 reload 的 barrel 通道）
 * 这张表把这两条曲线的起、中、末各拍一张，能不能对上真枪的机构一眼就看得出来。
 */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');

/** [clip, 秒数, 说明] —— 秒数取在关键帧上，别取在插值中间 */
const PHASES = [
  ['bolt', 0.0, '合膛待击位（起始）'],
  ['bolt', 0.8, '折开到底：管 -52°、双锤被顶回'],
  ['bolt', 1.4, '合膛归位（收束）'],
  ['reload_tactical', 1.35, '折开退壳：膛口朝上、左手到位'],
  ['reload_tactical', 2.3, '两发新弹入膛（bolt_loaded 显示）'],
  ['reload_tactical', 3.0, '合膛归位（收束）'],
];

async function main() {
  const outDir = path.resolve(ROOT, process.argv[2] || 'art/colt_1878/anim');
  fs.mkdirSync(outDir, { recursive: true });

  const bb = await Bb.connect();
  const view = 'coltanim';
  try { await bb.t('delete_offscreen_view', { view }); } catch (e) { /* 不存在就算了 */ }
  await bb.t('create_offscreen_view', { id: view, width: 1100, height: 620, antialias: false, copy_view: 'none' });
  // 右前上方，同时看得见机匣后上方的双锤与前段的管组
  await bb.t('set_camera_angle', { view, position: [7.2, 3.6, 3.0], target: [0, 0.05, -0.1], projection: 'perspective', fov: 32 });

  let n = 0;
  for (const [clip, time, note] of PHASES) {
    /* ★ 必须带 "animation." 前缀：Blockbench 里片段的真名是 animation.bolt
     * （落位脚本 install.js 会在写盘时把这层前缀剥掉，所以资源目录里是裸名 bolt）。 */
    await bb.t('animation_timeline', { action: 'set_time', animation_id: `animation.${clip}`, time });
    const shot = await bb.call('capture_screenshot', { view });
    if (!shot.images.length) { console.log(`[${clip}@${time}] 无图片: ${shot.text.slice(0, 160)}`); continue; }
    const out = path.join(outDir, `${clip}_t${String(time).replace('.', 'p')}.png`);
    fs.writeFileSync(out, Buffer.from(shot.images[0].data, 'base64'));
    console.log(`[${clip}@${time}s] ${note} -> ${path.relative(ROOT, out)}`);
    n++;
  }

  try { await bb.t('delete_offscreen_view', { view }); } catch (e) { /* 已删 */ }
  console.log('done:', n, 'frames');
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
