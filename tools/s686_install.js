'use strict';
/* 把 build/ 下的 S686 产物规范化并落位到资源目录。
 * 用法: node tools/s686_install.js
 *
 * 规范化做的事（都必须做，理由写在各自注释里）：
 *   1. geo    -> assets/apocalypse_zombies/geo/s686.geo.json
 *   2. anim   -> assets/apocalypse_zombies/animations/s686.animation.json
 *        a. 剥掉 Blockbench create_animation 加的 "animation." 前缀 ——
 *           本仓库其它枪（uzi/awm/mosin…）与 GeckoLib 运行时都用裸名，
 *           tools/check_gun_resources.py:172-175 也按裸名比对 S686Item 的 ANIM_ 与 TRIGGER_ 常量。
 *        b. 校验通道形状符合 GeckoLib 契约（时间 -> 三元向量；per-axis 嵌套会让资源重载失败）。
 *   3. tex    -> assets/apocalypse_zombies/textures/item/s686.png（必须 512x512）
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUILD = path.join(ROOT, 'build');
const ASSETS = path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies');

const fails = [];
const notes = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); return ok; };

/* ---------- 1. geo ---------- */
const geo = JSON.parse(fs.readFileSync(path.join(BUILD, 's686.geo.json'), 'utf8'));
check(geo.format_version === '1.12.0', `geo format_version=${geo.format_version}，应为 1.12.0`);
const g0 = geo['minecraft:geometry']?.[0] || {};
check(g0.description?.identifier === 'geometry.s686', `geo identifier=${g0.description?.identifier}`);
check(g0.description?.texture_width === 512 && g0.description?.texture_height === 512,
  `geo texture_width/height=${g0.description?.texture_width}x${g0.description?.texture_height}，应为 512x512`);
const boneNames = (g0.bones || []).map((b) => b.name);
const cubeCount = (g0.bones || []).reduce((n, b) => n + (b.cubes || []).length, 0);
const nonZeroBoneRot = (g0.bones || []).filter((b) => b.rotation && b.rotation.some((v) => v !== 0));
check(nonZeroBoneRot.length === 0, `骨骼带初始旋转（规范禁止）：${nonZeroBoneRot.map((b) => b.name)}`);
const am = (g0.bones || []).find((b) => b.name === 'additional_magazine');
check(!!am && (am.cubes || []).length === 0, 'additional_magazine 必须存在且为空');
fs.mkdirSync(path.join(ASSETS, 'geo'), { recursive: true });
fs.writeFileSync(path.join(ASSETS, 'geo', 's686.geo.json'), JSON.stringify(geo, null, 2));
notes.push(`geo: ${boneNames.length} 骨 / ${cubeCount} 块 -> geo/s686.geo.json`);

/* ---------- 2. animations ---------- */
const rawAnim = JSON.parse(fs.readFileSync(path.join(BUILD, 's686.animation.json'), 'utf8'));
const anims = {};
for (const [k, v] of Object.entries(rawAnim.animations || {})) {
  anims[k.replace(/^animation\./, '')] = v;
}
const TIMES20 = { shoot: 'SHOOT_TICKS', bolt: 'BOLT_TICKS', reload_tactical: 'RELOAD_TACTICAL_TICKS', reload_empty: 'RELOAD_EMPTY_TICKS', draw: 'DRAW_TICKS' };
const ticks = {};
for (const [clip, body] of Object.entries(anims)) {
  check(typeof body.animation_length === 'number', `${clip}: 缺 animation_length`);
  for (const [bone, chans] of Object.entries(body.bones || {})) {
    check(boneNames.includes(bone), `${clip}: 驱动的骨 ${bone} 不在 geo 里`);
    for (const [chan, val] of Object.entries(chans || {})) {
      check(['rotation', 'position', 'scale'].includes(chan), `${clip}/${bone}: 非法通道 ${chan}`);
      for (const [t, v] of Object.entries(val || {})) {
        check(!Number.isNaN(Number(t)), `${clip}/${bone}/${chan}: 时间键 ${t} 不是数字（per-axis 嵌套？）`);
        const okVec = (x) => Array.isArray(x) && x.length === 3 && x.every((n) => typeof n === 'number');
        const okVal = okVec(v) || (v && typeof v === 'object' && (
          okVec(v.vector) || ((v.post === undefined || okVec(v.post?.vector)) && (v.pre === undefined || okVec(v.pre?.vector)))));
        check(okVal, `${clip}/${bone}/${chan}@${t}: 值不是三元向量 ${JSON.stringify(v)}`);
      }
    }
  }
  if (TIMES20[clip]) ticks[TIMES20[clip]] = Math.ceil(Math.round(body.animation_length * 20 * 1000) / 1000);
  if (body.loop === 'loop') body.loop = true;
}
const outAnim = {
  format_version: rawAnim.format_version,
  animations: anims,
  geckolib_format_version: rawAnim.geckolib_format_version,
};
check(outAnim.format_version === '1.8.0', `anim format_version=${outAnim.format_version}`);
check(outAnim.geckolib_format_version === 2, `geckolib_format_version=${outAnim.geckolib_format_version}`);
fs.mkdirSync(path.join(ASSETS, 'animations'), { recursive: true });
fs.writeFileSync(path.join(ASSETS, 'animations', 's686.animation.json'), JSON.stringify(outAnim, null, 2));
notes.push(`anim: ${Object.keys(anims).length} 条 clip [${Object.keys(anims).join(', ')}]`);
notes.push(`Java 常量应写：${Object.entries(ticks).map(([k, v]) => `${k}=${v}`).join(' ')}`);

/* ---------- 3. texture ---------- */
const srcTex = path.join(BUILD, 's686_tex.png');
const buf = fs.readFileSync(srcTex);
const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20), depth = buf[24], colorType = buf[25];
check(w === 512 && h === 512, `贴图 ${w}x${h}，规范要求 512x512`);
check(depth === 8 && (colorType === 6 || colorType === 2), `贴图 bitDepth=${depth} colorType=${colorType}，应为 8 位 RGB/RGBA`);
fs.mkdirSync(path.join(ASSETS, 'textures', 'item'), { recursive: true });
fs.writeFileSync(path.join(ASSETS, 'textures', 'item', 's686.png'), buf);
notes.push(`tex: ${w}x${h} colorType=${colorType} ${buf.length} bytes -> textures/item/s686.png`);

/* ---------- 4. 逐面 UV 必须落在真正涂绘过的像素上 ----------
 * 尺寸对、文件在，都不代表内容完整：资源目录那张图一旦被截断或过期，
 * 大量面会采到全透明区，游戏里渲染成纯黑（M1 加兰德就是这么翻车的）。 */
const { decodePNG, alphaAt } = require('./png_read.js');
const img = decodePNG(buf);
let facesTotal = 0;
const blank = [];
for (const bone of (g0.bones || [])) {
  for (const cube of (bone.cubes || [])) {
    for (const [face, rect] of Object.entries(cube.uv || {})) {
      if (!rect || typeof rect !== 'object' || !rect.uv || !rect.uv_size) continue;
      const [u, v] = rect.uv;
      const [rw, rh] = rect.uv_size;
      const u0 = Math.max(0, Math.round(Math.min(u, u + rw)));
      const u1 = Math.min(img.width, Math.round(Math.max(u, u + rw)));
      const v0 = Math.max(0, Math.round(Math.min(v, v + rh)));
      const v1 = Math.min(img.height, Math.round(Math.max(v, v + rh)));
      if (u0 >= u1 || v0 >= v1) continue;
      facesTotal++;
      let painted = false;
      for (let y = v0; y < v1 && !painted; y++) {
        for (let x = u0; x < u1; x++) {
          if (alphaAt(img, x, y) > 8) { painted = true; break; }
        }
      }
      if (!painted) blank.push(`${bone.name}.${face}`);
    }
  }
}
check(blank.length === 0, `${blank.length}/${facesTotal} 个面的 UV 落在全透明区，例：${blank.slice(0, 6)}`);
notes.push(`uv: ${facesTotal} 个面全部落在涂绘区（空白 ${blank.length} 个）`);

console.log('=== S686 落位 ===');
for (const n of notes) console.log(' -', n);

/* ---------- 5. art/<枪>/ 归档（与 art/uzi 同惯例：交付副本，便于离线核对） ---------- */
const ART = path.join(ROOT, 'art', 's686');
fs.mkdirSync(ART, { recursive: true });
for (const [from, to] of [
  [path.join(ASSETS, 'geo', 's686.geo.json'), 's686.geo.json'],
  [path.join(ASSETS, 'animations', 's686.animation.json'), 's686.animation.json'],
  [path.join(ASSETS, 'textures', 'item', 's686.png'), 's686.png'],
]) {
  fs.copyFileSync(from, path.join(ART, to));
}
console.log(` - art: 交付副本已归档 -> art/s686/（${fs.readdirSync(ART).length} 个文件）`);

if (fails.length) {
  console.log(`\n${fails.length} 条不通过：`);
  for (const f of fails) console.log('  ✗', f);
  process.exit(1);
}
console.log('\n全部通过');
