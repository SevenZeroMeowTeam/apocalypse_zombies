'use strict';
/* 把 build/ 下的短管喷产物规范化并落位到资源目录。
 * 用法: node tools/colt_1878_install.js
 *
 * 规范化做的事（与 s686_install.js 同一套口径，理由写在各自注释里）：
 *   1. geo    -> assets/apocalypse_zombies/geo/colt_1878.geo.json
 *   2. anim   -> assets/apocalypse_zombies/animations/colt_1878.animation.json
 *        a. 剥掉 Blockbench create_animation 加的 "animation." 前缀 —— 本仓库其它枪
 *           （uzi/awm/mosin/s686）与 GeckoLib 运行时都用裸名。
 *        b. 校验通道形状符合 GeckoLib 契约（时间 -> 三元向量；per-axis 嵌套会让资源重载失败）。
 *   3. tex    -> assets/apocalypse_zombies/textures/item/colt_1878.png（必须 512x512）
 *
 * 另外会核对 geo 的两件容易出事的东西：
 *   · description.identifier 必须是 geometry.colt_1878（写错游戏里找不到模型）
 *   · texture_width/height 必须是 512（GeckoLib 项目默认按 16x16 解释 UV，会让图集整体错位）
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUILD = path.join(ROOT, 'build');
const ASSETS = path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies');
const NAME = 'colt_1878';

const fails = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); return ok; };

/* ---------- 1. geo ---------- */
const geoPath = path.join(BUILD, `${NAME}.geo.json`);
if (!check(fs.existsSync(geoPath), `缺少 ${path.relative(ROOT, geoPath)}（先跑 node tools/${NAME}_build.js）`)) {
  report();
}
const geo = JSON.parse(fs.readFileSync(geoPath, 'utf8'));
check(geo.format_version === '1.12.0', `geo format_version=${geo.format_version}，应为 1.12.0`);
const g0 = geo['minecraft:geometry']?.[0] || {};
check(g0.description?.identifier === `geometry.${NAME}`, `geo identifier=${g0.description?.identifier}，应为 geometry.${NAME}`);
check(g0.description?.texture_width === 512 && g0.description?.texture_height === 512,
  `geo 贴图基准=${g0.description?.texture_width}x${g0.description?.texture_height}，应为 512x512`);
const boneNames = (g0.bones || []).map((b) => b.name);
const cubeCount = (g0.bones || []).reduce((n, b) => n + (b.cubes || []).length, 0);
const nonZeroBoneRot = (g0.bones || []).filter((b) => b.rotation && b.rotation.some((v) => v !== 0));
check(nonZeroBoneRot.length === 0, `骨骼带初始旋转（规范禁止）：${nonZeroBoneRot.map((b) => b.name)}`);
const orphan = (g0.cubes || []).length;
check(orphan === 0, `有 ${orphan} 个方块浮在根节点（应全部归骨）`);
check(cubeCount <= 600, `方块 ${cubeCount} > 600（美术规范预算）`);
check(boneNames.length <= 40, `骨骼 ${boneNames.length} > 40（美术规范预算）`);
// 每个方块都要有逐面 UV，否则游戏里是紫黑格
let noUv = 0;
for (const b of g0.bones || []) {
  for (const c of b.cubes || []) {
    if (!c.uv || Object.keys(c.uv).length < 6) noUv++;
  }
}
check(noUv === 0, `${noUv} 个方块缺逐面 UV（应为 6 面齐全）`);

/* ---------- 2. anim ---------- */
const animPath = path.join(BUILD, `${NAME}.animation.json`);
if (!check(fs.existsSync(animPath), `缺少 ${path.relative(ROOT, animPath)}`)) {
  report();
}
const anim = JSON.parse(fs.readFileSync(animPath, 'utf8'));
/* 先剥前缀再校验：Blockbench 的 create_animation 一定会加 "animation."，而本仓库
 * 其它枪（uzi/awm/mosin/s686）与 GeckoLib 运行时都用裸名 —— 所以"剥掉"是常态动作，
 * 不是异常处理；校验放在剥离之后，用来确认剥干净了。 */
if (anim.animations) {
  for (const key of Object.keys(anim.animations)) {
    if (key.startsWith('animation.')) {
      anim.animations[key.slice('animation.'.length)] = anim.animations[key];
      delete anim.animations[key];
    }
  }
}
const clips = anim.animations || {};
const clipNames = Object.keys(clips);
check(clipNames.length > 0, 'animation.json 里没有动画');
const prefixed = clipNames.filter((n) => n.startsWith('animation.'));
check(prefixed.length === 0, `动画名仍带 "animation." 前缀：${prefixed.join(', ')}`);

/* 动画名必须与 S686Item 的常量逐字一致 —— 短管喷在 Java 侧继承 S686Item
 * （S686Item 的 ANIM_* / TRIGGER_* 是 public static final，不可覆盖），
 * 所以这里按它的名字校验；少一段，游戏里对应的动作就会静止不动。 */
const WANT = ['static_idle', 'draw', 'shoot', 'bolt', 'reload_tactical', 'reload_empty', 'ADS_up', 'ADS_down'];
for (const w of WANT) {
  check(clipNames.includes(w), `缺少动画 ${w}`);
}
// 通道形状：bones -> <骨名> -> 通道 -> 时间 -> {vector:[x,y,z]}
for (const [clipName, clip] of Object.entries(clips)) {
  for (const [boneName, bone] of Object.entries(clip.bones || {})) {
    check(boneNames.includes(boneName), `${clipName}: 通道挂在未知骨骼 ${boneName}`);
    for (const chan of ['rotation', 'position', 'scale']) {
      const node = bone[chan];
      if (!node) continue;
      for (const [t, kf] of Object.entries(node)) {
        const bad = !kf || typeof kf !== 'object' || !Array.isArray(kf.vector);
        check(!bad, `${clipName}/${boneName}/${chan}@${t}: 关键帧不是 {vector:[x,y,z]} 形状`);
      }
    }
  }
}
/* 换弹慢是本枪的设定（也是用户点名的）：S686 是 reload_tactical 1.95s / reload_empty 2.475s，
 * 本枪必须**明显更慢**才叫"换弹慢"。这两条门禁把它钉死，防止以后被无意改回去。 */
const rlT = clips.reload_tactical?.animation_length;
const rlE = clips.reload_empty?.animation_length;
check(typeof rlT === 'number' && rlT >= 2.5,
  `reload_tactical ${rlT}s 太短 —— 本枪设定是"换弹慢"（S686 是 1.95s，目标 ≥2.5s）`);
check(typeof rlE === 'number' && rlE >= 3.0,
  `reload_empty ${rlE}s 太短 —— 空仓换弹应比有弹版更慢（S686 是 2.475s，目标 ≥3.0s）`);
check(typeof rlE === 'number' && typeof rlT === 'number' && rlE > rlT,
  `reload_empty(${rlE}s) 应长于 reload_tactical(${rlT}s)`);

/* ---------- 3. tex ---------- */
const texSrc = path.join(BUILD, `${NAME}_tex.png`);
if (!check(fs.existsSync(texSrc), `缺少 ${path.relative(ROOT, texSrc)}`)) {
  report();
}
const png = fs.readFileSync(texSrc);
const w = png.readUInt32BE(16);
const h = png.readUInt32BE(20);
check(w === 512 && h === 512, `贴图 ${w}x${h}，应为 512x512`);

/* ---------- 落位 ---------- */
function report() {
  if (fails.length) {
    console.error('规范化失败：');
    for (const f of fails) console.error('  - ' + f);
    process.exit(1);
  }
}

report();

const outGeo = path.join(ASSETS, 'geo', `${NAME}.geo.json`);
const outAnim = path.join(ASSETS, 'animations', `${NAME}.animation.json`);
const outTex = path.join(ASSETS, 'textures', 'item', `${NAME}.png`);
fs.mkdirSync(path.dirname(outGeo), { recursive: true });
fs.mkdirSync(path.dirname(outAnim), { recursive: true });
fs.mkdirSync(path.dirname(outTex), { recursive: true });
fs.copyFileSync(geoPath, outGeo);
/* 不能直接 copyFileSync(animPath)：上面剥了前缀，那份改过的对象必须写出去 */
fs.writeFileSync(outAnim, JSON.stringify(anim, null, 2) + '\n', 'utf8');
fs.copyFileSync(texSrc, outTex);

console.log(`geo    -> ${path.relative(ROOT, outGeo)}  (${cubeCount} 方块 / ${boneNames.length} 骨)`);
console.log(`anim   -> ${path.relative(ROOT, outAnim)}  (${clipNames.join(', ')})`);
console.log(`        reload_tactical ${rlT}s = ${Math.round(rlT * 20)} tick  ·  reload_empty ${rlE}s = ${Math.round(rlE * 20)} tick  （S686 是 39 / 50 tick）`);
console.log(`tex    -> ${path.relative(ROOT, outTex)}  (${w}x${h})`);
console.log('\n规范化自检：全部通过');
