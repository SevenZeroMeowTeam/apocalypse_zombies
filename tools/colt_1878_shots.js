'use strict';
/* 短管喷（Colt 1878 Coach Gun）—— 通过 blockbench-mcp 抓多角度视图，供人眼核验几何。
 *
 * 用法: node tools/colt_1878_shots.js [outPrefix]
 *   node tools/colt_1878_shots.js build/colt_1878
 *
 * 与 tools/bb_shots.js 同一套 MCP 调用（create_offscreen_view + set_camera_angle +
 * capture_screenshot），差别是本枪比 S686 短（15 u vs 19.5 u），要凑近拍，
 * 而且要专门看**并排双管**（俯视）与**外露双锤**（机匣近景）——这两条是与 S686 的分野。
 */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');

const VIEWS = [
  // 侧视：全长轮廓、托颈下垂、管 / 机匣 / 托 的比例
  { id: 'side_east', pos: [16, 0, -0.2], target: [0, 0, -0.2], fov: 26 },
  // 俯视：并排双管与焊接肋条（上下双管的 S686 在这里会露馅）
  { id: 'top', pos: [0, 16, -0.2], target: [0, 0, -0.2], fov: 26 },
  // 管口正视：双管内径、膛口、黄铜管口圈
  { id: 'muzzle', pos: [0, 0.4, -13], target: [0, 0.4, -7], fov: 30 },
  // 机匣近景：拨杆 / 双锤 / 双扳机 / 卡榫
  { id: 'action', pos: [6.5, 3.2, 3.4], target: [0, 0.1, 0.2], fov: 30 },
];
/* Blockbench 同时最多 4 个 offscreen view（第 5 个报 "At most 4 offscreen views"），
 * 所以上面正好 4 个，一个不多。要换角度就换掉其中一个。 */

async function main() {
  const prefix = process.argv[2] || 'build/colt_1878';
  const bb = await Bb.connect();
  const made = [];

  for (const v of VIEWS) {
    try { await bb.t('delete_offscreen_view', { view: v.id }); } catch (e) { /* 不存在就算了 */ }
    await bb.t('create_offscreen_view', { id: v.id, width: 1100, height: 620, antialias: false, copy_view: 'none' });
    await bb.t('set_camera_angle', { view: v.id, position: v.pos, target: v.target, projection: 'perspective', fov: v.fov });
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
