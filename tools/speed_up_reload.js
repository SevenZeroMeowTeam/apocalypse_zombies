// 把 s686.animation.json 里指定动画整体加速（关键帧时间 × 倍率），并核对结果。
//
// 为什么要动动画文件而不是只改 Java 的 TICKS：GeckoLib 播的是 json 里的片段，Java 那边只管
// "这个动作占用多久"。只缩短 TICKS 会让片段播到一半被 clearAction 切回 idle，看上去就是换弹没做完
// 就跳回持枪。两者必须一起动，音效时刻表（Java 里的 Map<tick, sound>）也一样。
//
// 用法：
//   node tools/speed_up_reload.js            # 只看现状（不改文件）
//   node tools/speed_up_reload.js 0.75       # 把 reload_* 两段整体乘 0.75
const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, '..', 'src', 'main', 'resources', 'assets',
    'apocalypse_zombies', 'animations', 's686.animation.json');
const TARGETS = ['reload_tactical', 'reload_empty'];

const factor = process.argv[2] ? Number(process.argv[2]) : null;
const json = JSON.parse(fs.readFileSync(FILE, 'utf8'));

/** 递归把所有"时间键"（对象里形如数字的键）乘上倍率，并保留两位小数。 */
function scaleTimes(node, f, depth) {
    if (node === null || typeof node !== 'object') {
        return node;
    }
    if (Array.isArray(node)) {
        return node.map((v) => scaleTimes(v, f, depth + 1));
    }
    const out = {};
    for (const [k, v] of Object.entries(node)) {
        // depth 1 = bones.<bone> 下的通道；再往下的数字键就是时间
        const isTimeKey = /^-?\d+(\.\d+)?$/.test(k) && depth >= 3;
        const key = isTimeKey ? String(Math.round(Number(k) * f * 1000) / 1000) : k;
        out[key] = scaleTimes(v, f, depth + 1);
    }
    return out;
}

/** 收集一段动画里所有的时间键，供核对。 */
function times(node, depth, acc) {
    if (node === null || typeof node !== 'object') {
        return acc;
    }
    if (Array.isArray(node)) {
        node.forEach((v) => times(v, depth + 1, acc));
        return acc;
    }
    for (const [k, v] of Object.entries(node)) {
        if (/^-?\d+(\.\d+)?$/.test(k) && depth >= 3) {
            acc.push(Number(k));
        }
        times(v, depth + 1, acc);
    }
    return acc;
}

console.log('=== 现状 ===');
for (const [name, clip] of Object.entries(json.animations)) {
    const t = times(clip, 0, []);
    const mark = TARGETS.includes(name) ? '  <== 目标' : '';
    console.log(`  ${name.padEnd(18)} length=${clip.animation_length}  关键帧 ${t.length} 个，最大时间 ${Math.max(...t).toFixed(3)}${mark}`);
}

if (factor === null) {
    console.log('\n（只看了现状。要加速就跑 node build/speed_up_reload.js 0.75）');
    process.exit(0);
}

console.log(`\n=== 加速 ×${factor} ===`);
for (const name of TARGETS) {
    if (!json.animations[name]) {
        console.log(`  ${name}: 找不到！`);
        continue;
    }
    const clip = json.animations[name];
    const before = clip.animation_length;
    clip.animation_length = Math.round(before * factor * 1000) / 1000;
    if (clip.bones) {
        clip.bones = scaleTimes(clip.bones, factor, 3);
    }
    if (clip.sound_effects) {
        clip.sound_effects = scaleTimes(clip.sound_effects, factor, 3);
    }
    const t = times(clip, 0, []);
    console.log(`  ${name}: length ${before} -> ${clip.animation_length}  (${Math.round(clip.animation_length * 20)} ticks)`);
    console.log(`    关键帧最大时间 ${Math.max(...t).toFixed(3)} -> ${Math.round(Math.max(...t) * 20)} ticks`);
}

fs.writeFileSync(FILE, JSON.stringify(json, null, 2) + '\n', 'utf8');
console.log(`\n已写入 ${path.relative(path.join(__dirname, '..'), FILE)}`);
