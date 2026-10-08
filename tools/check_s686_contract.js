// TEMP (apocalypse_zombies / s686): the hard contract for the new gun, checked without Python.
//
//   node build/check_s686_contract.js
//
// tools/check_gun_resources.py is the project's own gate, but this machine has no Python, so the checks it
// applies to `s686` are re-implemented here one-to-one — plus the handful the task statement names explicitly
// (the *_TICKS table, the DISPLAY_PITCH/YAW mirror, the ADS band, the WeaponArms branch). Exit code 0 = all
// green. Every check prints the evidence it read, so a pass can be audited rather than trusted.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const JAVA = path.join(ROOT, 'src/main/java/com/apocalypse/zombies');
const RES = path.join(ROOT, 'src/main/resources');
const ASSETS = path.join(RES, 'assets/apocalypse_zombies');
const MOD_ID = 'apocalypse_zombies';

const fails = [];
const notes = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); };
const read = p => fs.readFileSync(p, 'utf8');
const readJson = p => JSON.parse(read(p));
const exists = p => fs.existsSync(p);

// ------------------------------------------------------------------ inputs
const itemSrc = read(path.join(JAVA, 'item/S686Item.java'));
const modelSrc = read(path.join(JAVA, 'client/model/S686GeoModel.java'));
const rendererSrc = read(path.join(JAVA, 'client/renderer/S686ItemRenderer.java'));
const armsSrc = read(path.join(JAVA, 'client/weapon/WeaponArms.java'));
const registrySrc = read(path.join(JAVA, 'registry/ModItems.java'));
const soundsSrc = read(path.join(JAVA, 'registry/ModSounds.java'));

const anim = readJson(path.join(ASSETS, 'animations/s686.animation.json'));
const geo = readJson(path.join(ASSETS, 'geo/s686.geo.json'))['minecraft:geometry'][0];
const clips = anim.animations;
const geoBones = new Set(geo.bones.map(b => b.name));
const itemModel = readJson(path.join(ASSETS, 'models/item/s686.json'));

// ------------------------------------------------------------------ 1. clips vs the 8 the art shipped
const EXPECTED_CLIPS = ['static_idle', 'draw', 'shoot', 'bolt', 'reload_tactical', 'reload_empty',
                        'ADS_up', 'ADS_down'];
const clipNames = Object.keys(clips);
check(clipNames.length === EXPECTED_CLIPS.length && EXPECTED_CLIPS.every(c => clipNames.includes(c)),
  `动画片段与交付清单不符：${clipNames.join(', ')}`);
check(!('shoot_auto' in clips), '动画里竟然有 shoot_auto —— 折开式双管不该有连发片段');
notes.push(`片段 ${clipNames.length} 条：${clipNames.join(', ')}`);

// ------------------------------------------------------------------ 2. ANIM_ / TRIGGER_ constants <-> clips
const animConsts = [...itemSrc.matchAll(/String\s+ANIM_\w+\s*=\s*"([^"]+)"/g)].map(m => m[1]);
const triggerConsts = [...itemSrc.matchAll(/String\s+TRIGGER_\w+\s*=\s*"([^"]+)"/g)].map(m => m[1]);
check(animConsts.length > 0 && triggerConsts.length > 0, '源码里没解析到 ANIM_/TRIGGER_ 常量');
for (const c of animConsts) check(clipNames.includes(c), `ANIM_ 常量 ${JSON.stringify(c)} 在动画文件里没有同名片段`);
for (const c of triggerConsts) check(clipNames.includes(c), `TRIGGER_ 常量 ${JSON.stringify(c)} 在动画文件里没有同名片段`);
check(!/String\s+(ANIM|TRIGGER)_SHOOT_AUTO/.test(itemSrc), '声明了 SHOOT_AUTO 常量（没有这条片段）');
check(/String\s+TRIGGER_ADS_UP/.test(itemSrc) && /String\s+ANIM_ADS_DOWN/.test(itemSrc),
  '没声明 ADS_up / ADS_down 的常量和片段（这两条 art 里有，Java 也要有）');
notes.push(`ANIM_ ${animConsts.length} 个 / TRIGGER_ ${triggerConsts.length} 个，全部命中片段名`);

// ------------------------------------------------------------------ 3. *_TICKS == ceil(animation_length * 20)
// Same arithmetic as check_gun_resources.py: real = ceil(round(len*20*1000)/1000).
const allClipsHave = c => Object.prototype.hasOwnProperty.call(clips, c);
const wanted = {
  DRAW_TICKS: 'draw', SHOOT_TICKS: 'shoot', BOLT_TICKS: 'bolt',
  RELOAD_TACTICAL_TICKS: 'reload_tactical', RELOAD_EMPTY_TICKS: 'reload_empty',
  AUTO_CYCLE_TICKS: 'shoot_auto',
};
const tickRows = [];
for (const [constName, clip] of Object.entries(wanted)) {
  const m = itemSrc.match(new RegExp(`int ${constName}\\s*=\\s*(\\d+);`));
  if (!m || !allClipsHave(clip)) continue;
  const declared = Number(m[1]);
  const real = Math.ceil(Math.round(clips[clip].animation_length * 20 * 1000) / 1000);
  tickRows.push(`${constName}=${declared} vs ${clip} ${real}`);
  check(declared === real, `${constName}=${declared} 与动画 ${clip} 的 ${real} ticks 不一致`);
}
check(tickRows.length === 5, `只核到 ${tickRows.length} 个时长常量（应有 5 个，不该有 AUTO_CYCLE_TICKS）`);
notes.push(`时长常量：${tickRows.join('；')}`);

// ------------------------------------------------------------------ 4. DISPLAY_PITCH/YAW <-> item model
const fpRight = itemModel.display.firstperson_righthand;
const fpLeft = itemModel.display.firstperson_lefthand;
const num = (src, name) => {
  const m = src.match(new RegExp(`float ${name}\\s*=\\s*(-?[\\d.]+)F;`));
  return m ? Number(m[1]) : NaN;
};
const pitch = num(itemSrc, 'DISPLAY_PITCH');
const yaw = num(itemSrc, 'DISPLAY_YAW');
check(Math.abs(pitch - fpRight.rotation[0]) < 1e-6 && Math.abs(yaw - fpRight.rotation[1]) < 1e-6,
  `DISPLAY_PITCH/YAW=${pitch}/${yaw} 与 models/item/s686.json 的 firstperson rotation ${fpRight.rotation.slice(0, 2)} 不一致`);
check(Math.abs(fpRight.rotation[2]) < 1e-6, `firstperson_righthand.rotation 的 roll=${fpRight.rotation[2]} 不为 0`);
check(Math.abs(fpLeft.rotation[0] - fpRight.rotation[0]) < 1e-6 && Math.abs(fpLeft.rotation[1] - fpRight.rotation[1]) < 1e-6,
  'firstperson_lefthand 的 rotation 应与 righthand 相同');
notes.push(`display 旋转 [${fpRight.rotation}] ↔ DISPLAY_PITCH/YAW ${pitch}/${yaw}，roll = 0，左右手同值`);

// ------------------------------------------------------------------ 5. ADS band, and measured value
const adsX = num(itemSrc, 'ADS_X');
const adsY = num(itemSrc, 'ADS_Y');
check(adsX > -0.60 && adsX < -0.35 && adsY > 0.25 && adsY < 0.45,
  `ADS_X/ADS_Y=${adsX}/${adsY} 不在契约区间 (−0.60,−0.35) / (0.25,0.45)`);
notes.push(`ADS 位移 (${adsX}, ${adsY}) 在量算区间内`);

// The same two-storey chain tools/pose_measure.py walks (see build/s686_pose_solve.js): the rib's top face is
// the sight line, both ends at y = 0.175 so it runs parallel to the bore.
const GECKO = [0.5, 0.51, 0.5], CENTER = [-0.5, -0.5, -0.5], BASE = [0.56, -0.52, -0.72];
const deg = Math.PI / 180;
const mmul = (a, b) => a.map(r => b[0].map((_, j) => r.reduce((s, v, k) => s + v * b[k][j], 0)));
const mvec = (m, v) => m.map(r => r.reduce((s, c, k) => s + c * v[k], 0));
const Rx = d => [[1, 0, 0], [0, Math.cos(d * deg), -Math.sin(d * deg)], [0, Math.sin(d * deg), Math.cos(d * deg)]];
const Ry = d => [[Math.cos(d * deg), 0, Math.sin(d * deg)], [0, 1, 0], [-Math.sin(d * deg), 0, Math.cos(d * deg)]];
const fps = num(itemSrc, 'FIRST_PERSON_SCALE');
const rear = [0.0, 0.300, -9.60];   // 前准星珠心（折开式没有后照门，唯一的瞄具就是这颗珠）
let p = [rear[0] / 16 + CENTER[0] + GECKO[0], rear[1] / 16 + CENTER[1] + GECKO[1], rear[2] / 16 + CENTER[2] + GECKO[2]];
const rot = mmul(Rx(fpRight.rotation[0]), mmul(Ry(fpRight.rotation[1]), [[1, 0, 0], [0, 1, 0], [0, 0, 1]]));
const scale = fpRight.scale[0], t = fpRight.translation.map(v => v / 16);
p = mvec(rot, p).map(v => v * scale).map((v, i) => v + t[i]);
p = mvec(mmul(Ry(-fpRight.rotation[1]), Rx(-fpRight.rotation[0])), p);   // GunPose cancels the display rotation
p = p.map(v => v * fps).map((v, i) => v + BASE[i]);
const measuredAdsX = -p[0] / fps, measuredAdsY = -p[1] / fps;
check(Math.abs(measuredAdsX - adsX) < 5e-4 && Math.abs(measuredAdsY - adsY) < 5e-4,
  `ADS_X/ADS_Y=${adsX}/${adsY} 与几何量算值 ${measuredAdsX.toFixed(4)}/${measuredAdsY.toFixed(4)} 不符`);
notes.push(`ADS 与几何量算一致（量算 ${measuredAdsX.toFixed(4)} / ${measuredAdsY.toFixed(4)}，残差 `
  + `${Math.abs(measuredAdsX - adsX).toExponential(1)} / ${Math.abs(measuredAdsY - adsY).toExponential(1)}）`);

// ------------------------------------------------------------------ 6. damage type
const dmg = itemSrc.match(/ResourceLocation\(ApocalypseZombies\.MOD_ID,\s*"(\w+_bullet)"\)/);
check(!!dmg, '源码里没解析到 damage_type id');
if (dmg) {
  const id = dmg[1];
  check(/^\w+_bullet$/.test(id) && id === 's686_bullet', `damage_type id=${id} 不是 s686_bullet`);
  const file = path.join(RES, `data/${MOD_ID}/damage_type/${id}.json`);
  check(exists(file), `damage_type 文件缺失 -> ${path.basename(file)}`);
  if (exists(file)) {
    check(readJson(file).message_id === id, `${path.basename(file)} 的 message_id 与文件名不一致`);
    notes.push(`damage_type ${id}.json：message_id 与文件名一致`);
  }
}

// ------------------------------------------------------------------ 7. texture 512x512
const png = path.join(ASSETS, 'textures/item/s686.png');
check(exists(png), '贴图缺失 -> textures/item/s686.png');
if (exists(png)) {
  const head = fs.readFileSync(png).subarray(0, 24);
  const w = head.readUInt32BE(16), h = head.readUInt32BE(20);
  check(w === 512 && h === 512, `贴图是 ${w}x${h}，要求 512x512`);
  notes.push(`贴图 512x512（PNG 头读得 ${w}x${h}，${fs.statSync(png).size} 字节）`);
}

// ------------------------------------------------------------------ 8. the model binding's three paths
const declared = [...modelSrc.matchAll(/new\s+ResourceLocation\(\w+\.MOD_ID,\s*"([^"]+)"\)/g)].map(m => m[1]);
check(declared.length >= 3, `GeoModel 只解析到 ${declared.length} 个资源路径（应有 geo/texture/animation）`);
for (const rel of declared) {
  check(exists(path.join(ASSETS, rel)), `声明的资源不存在 -> ${rel}`);
}
check(declared.includes('geo/s686.geo.json') && declared.includes('textures/item/s686.png')
  && declared.includes('animations/s686.animation.json'), `三个路径不对：${declared.join(', ')}`);
check(!/getRenderType|setCustomAnimations/.test(modelSrc), 'GeoModel 里不该有 getRenderType / setCustomAnimations');
notes.push(`GeoModel 三个路径：${declared.join(' / ')}`);

// ------------------------------------------------------------------ 9. bones the clips drive must exist
const driven = new Set();
for (const clip of Object.values(clips)) for (const b of Object.keys(clip.bones || {})) driven.add(b);
const missing = [...driven].filter(b => !geoBones.has(b));
check(missing.length === 0, `动画驱动的骨在 geo 里不存在 -> ${missing.join(', ')}`);
notes.push(`geo ${geoBones.size} 骨 / 动画驱动 ${driven.size} 骨，全部对齐`);

// ------------------------------------------------------------------ 10. registry wiring
const reg = registrySrc.match(/ITEMS\.register\("(s686)",\s*\(\)\s*->\s*new\s+(\w+Item)\(/);
check(!!reg, 'ModItems.java 里没解析到 s686 注册（正则 ITEMS.register("<id>", () -> new <X>Item(）');
if (reg) {
  check(reg[2] === 'S686Item', `注册的类名是 ${reg[2]}，应为 S686Item`);
  check(registrySrc.includes('event.accept(S686)'), 'ModItems 的创造模式页签里没有 event.accept(S686)');
  notes.push(`ModItems：s686 -> ${reg[2]}（正则命中），战斗页签已 accept`);
}
// The class name must drive the model file name: <Item class minus "Item">GeoModel.
check(exists(path.join(JAVA, 'client/model/S686GeoModel.java')), 'client/model/S686GeoModel.java 缺失');
check(exists(path.join(JAVA, 'client/renderer/S686ItemRenderer.java')), 'client/renderer/S686ItemRenderer.java 缺失');
check(/extends\s+GeoItemRenderer<S686Item>/.test(rendererSrc) && /super\(new S686GeoModel\(\)\)/.test(rendererSrc),
  'S686ItemRenderer 不是 extends GeoItemRenderer<S686Item> / super(new S686GeoModel())');
check(read(path.join(JAVA, 'item/S686Item.java')).includes('new S686ItemRenderer()'),
  'S686Item.initializeClient 里没有懒加载 new S686ItemRenderer()');

// ------------------------------------------------------------------ 11. first-person arms (the easy thing to miss)
check(/import\s+com\.apocalypse\.zombies\.item\.S686Item;/.test(armsSrc), 'WeaponArms 没 import S686Item');
check(/import\s+com\.apocalypse\.zombies\.client\.model\.S686GeoModel;/.test(armsSrc), 'WeaponArms 没 import S686GeoModel');
check(/stack\.getItem\(\)\s+instanceof\s+S686Item/.test(armsSrc), 'WeaponArms.renderHeld 没有 S686Item 分支');
check(/public\s+static\s+void\s+renderS686\(/.test(armsSrc), 'WeaponArms 没有 renderS686(...)');
check(/S686GeoModel\.frame\.invalidate\(\)/.test(armsSrc), 'WeaponArms.forgetFrames 没有回收 S686 的 capture');
notes.push('WeaponArms：import / renderS686 / renderHeld 分支 / forgetFrames 回收 四处齐全');

// ------------------------------------------------------------------ 12. lang, item model, gameplay constants
for (const lang of ['lang/zh_cn.json', 'lang/en_us.json']) {
  const table = readJson(path.join(ASSETS, lang));
  check(`${'item.' + MOD_ID + '.s686'}` in table, `${lang} 缺 item.${MOD_ID}.s686`);
  check(`death.attack.${dmg ? dmg[1] : 's686_bullet'}` in table, `${lang} 缺 death.attack.s686_bullet`);
  check(`death.attack.${dmg ? dmg[1] : 's686_bullet'}.player` in table, `${lang} 缺 death.attack.s686_bullet.player`);
}
check(exists(path.join(ASSETS, 'models/item/s686.json')), 'models/item/s686.json 缺失');
notes.push('两套 lang 的 item / death.attack 键齐全');

const gameplay = { MAGAZINE_SIZE: 2, PELLETS: 8, FIRE_INTERVAL_TICKS: 20 };
for (const [name, value] of Object.entries(gameplay)) {
  const m = itemSrc.match(new RegExp(`int ${name}\\s*=\\s*(\\d+);`));
  check(!!m && Number(m[1]) === value, `${name} 应为 ${value}${m ? `，实为 ${m[1]}` : '（没找到）'}`);
}
notes.push('玩法常量：弹容 2 / 每发 8 颗弹丸 / 射击间隔 20 ticks');

// ------------------------------------------------------------------ 13. sounds: route A (no new keys)
const registered = [...soundsSrc.matchAll(/sound\("([a-z0-9_]+)"\)/g)].map(m => m[1]);
const soundTable = Object.keys(readJson(path.join(ASSETS, 'sounds.json')));
check(registered.every(s => soundTable.includes(s)),
  `sounds.json 缺事件键：${registered.filter(s => !soundTable.includes(s)).join(', ')}`);
check(soundTable.every(s => registered.includes(s)),
  `sounds.json 里有没注册过的死键：${soundTable.filter(s => !registered.includes(s)).join(', ')}`);
const used = [...new Set([...itemSrc.matchAll(/ModSounds\.([A-Z0-9_]+)/g)].map(m => m[1]))];
check(used.length > 0, '源码里没引用任何 ModSounds 常量');
for (const u of used) check(new RegExp(`RegistryObject<SoundEvent>\\s+${u}\\s*=`).test(soundsSrc),
  `引用了不存在的音效常量 ModSounds.${u}`);
// Route A: borrow the AWM set. A new sound id would need both a ModSounds registration and a sounds.json
// key plus a real .ogg, and the art shipped none — so any s686-shaped sound id here is a mistake.
check(!/"s686_(shoot|reload|bolt|draw|ads|fire)/.test(itemSrc), '源码里出现了 s686 专属音效键（路线 A 不允许）');
check(!/sound\("s686/.test(soundsSrc), 'ModSounds 里新增了 s686 音效键（路线 A 不允许）');
notes.push(`音效走路线 A：引用 ${used.length} 个既有 AWM id（${used.join(', ')}），ModSounds/sounds.json 零改动`);

// ------------------------------------------------------------------ report
console.log('=== S686 硬契约自检（Node 版 check_gun_resources.py + 任务书硬契约）===');
for (const line of notes) console.log('  · ' + line);
console.log();
if (fails.length) {
  console.log(`${fails.length} 条不通过：`);
  for (const line of fails) console.log('  ✗ ' + line);
  process.exit(1);
}
console.log(`全部通过（${notes.length} 组检查）`);
