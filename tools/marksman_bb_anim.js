/* 骸骨射手 —— Blockbench 动画生成器（在 Blockbench 里跑，末尾 return out）
 *
 * 四段 clip（规格见 art/marksman/DESIGN.md §五），名字必须与 Java 的 ANIM_* 常量一致：
 *   idle             3.0s loop   呼吸：胸腔起伏、头慢扫、斗篷飘、弓轻晃
 *   walk             1.0s loop   腿 ±30° 交替、膝反向屈、臂反相、斗篷滞后、躯干微扭
 *   shoot            0.9s once   普通弓射：抬弓 → 拉弦 → 撒放 → 收招
 *   skill_bone_lock  2.1s once   **技能**：0→1.7s 前摇（弓举过头、满弦、张口、锁头）
 *                                → 1.7s 命中帧（撒放 + 后坐 + 斗篷前甩）→ 2.1s 回位
 *
 * 只用 rotation 通道：本项目禁 scale；位置通道会引入 16u/格 的单位歧义，
 * 后坐改用 spine/chest 的反向旋转表达，避免"整块平移"式的假骨骼。
 *
 * 执行方式：
 *   python tools/marksman_anim.py
 */
(function () {

  var out = { steps: [], warnings: [] };
  var DUMP_PATH = 'F:/mcmod/art/marksman/_anim_raw.json';

  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });
  out.bones = Object.keys(G).length;

  /* ---------- 0. 清场：可反复跑 ---------- */
  try {
    Project.animations.slice().forEach(function (a) { if (a.remove) { a.remove(); } });
  } catch (e) { out.warnings.push('clean:' + e.message); }
  try { Animation.all.length = 0; } catch (e2) {}
  try { Project.animations.length = 0; } catch (e3) {}
  out.steps.push('cleared animations');

  function makeAnim(name, length, loop) {
    var a = new Animation({ name: name, loop: loop, animation_length: length, length: length, bones: {} });
    a.add();
    a.length = length;
    if (a.setLength) { a.setLength(length); }
    out.steps.push('anim ' + name + ' len ' + a.length + ' ' + loop);
    return a;
  }

  /* K(anim, bone, channel, time, [x,y,z], interpolation) */
  function K(a, bone, channel, time, vals, interp) {
    var g = G[bone];
    if (!g) { out.warnings.push('missing bone ' + bone); return null; }
    var an = a.getBoneAnimator(g);
    if (!an) { out.warnings.push('no animator ' + bone); return null; }
    var k = new Keyframe({
      channel: channel,
      time: time,
      interpolation: interp || 'linear',
      data_points: [{ x: vals[0], y: vals[1], z: vals[2] }]
    }, null, an);
    an.pushKeyframe(k);
    return k;
  }

  var S = 'catmullrom';
  var L = 'linear';

  /* ---------- 1. 关键帧总表 ---------- */
  var CLIPS = [
    { name: 'idle', len: 3.0, loop: 'loop', keys: [
      ['chest',    [[0.0, [0, 0, 0], S], [0.75, [-1.6, 0, 0], S], [1.5, [0, 0, 0], S], [2.25, [1.2, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['spine',    [[0.0, [0, 0, 0], S], [1.5, [0.6, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['neck',     [[0.0, [0, 0, 0], S], [1.5, [1.0, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['head',     [[0.0, [0, 0, 0], S], [1.0, [0, 4, 0], S], [2.0, [0, -4, 0], S], [3.0, [0, 0, 0], S]]],
      ['jaw',      [[0.0, [0, 0, 0], S], [1.5, [1.5, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['arm_r',    [[0.0, [0, 0, 0], S], [1.5, [-1.5, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['arm_l',    [[0.0, [0, 0, 0], S], [1.5, [-1.2, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['forearm_r',[[0.0, [0, 0, 0], S], [1.5, [-3.0, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['bow',      [[0.0, [0, 0, 0], S], [1.5, [2.0, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['quiver',   [[0.0, [0, 0, 0], S], [1.5, [1.0, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['cape_a',   [[0.0, [0, 0, 0], S], [1.5, [-1.5, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['cape_b',   [[0.0, [0, 0, 0], S], [1.0, [2.0, 0, 0], S], [2.0, [-2.0, 0, 0], S], [3.0, [0, 0, 0], S]]],
      ['cape_c',   [[0.0, [0, 0, 0], S], [0.8, [3.0, 0, 0], S], [2.3, [-3.0, 0, 0], S], [3.0, [0, 0, 0], S]]]
    ]},
    { name: 'walk', len: 1.0, loop: 'loop', keys: [
      ['leg_r',   [[0.0, [-30, 0, 0], S], [0.25, [0, 0, 0], S], [0.5, [30, 0, 0], S], [0.75, [0, 0, 0], S], [1.0, [-30, 0, 0], S]]],
      ['shin_r',  [[0.0, [0, 0, 0], S], [0.25, [14, 0, 0], S], [0.5, [22, 0, 0], S], [0.75, [6, 0, 0], S], [1.0, [0, 0, 0], S]]],
      ['foot_r',  [[0.0, [0, 0, 0], S], [0.25, [-6, 0, 0], S], [0.5, [10, 0, 0], S], [0.75, [4, 0, 0], S], [1.0, [0, 0, 0], S]]],
      ['leg_l',   [[0.0, [30, 0, 0], S], [0.25, [0, 0, 0], S], [0.5, [-30, 0, 0], S], [0.75, [0, 0, 0], S], [1.0, [30, 0, 0], S]]],
      ['shin_l',  [[0.0, [22, 0, 0], S], [0.25, [6, 0, 0], S], [0.5, [0, 0, 0], S], [0.75, [14, 0, 0], S], [1.0, [22, 0, 0], S]]],
      ['foot_l',  [[0.0, [10, 0, 0], S], [0.25, [4, 0, 0], S], [0.5, [0, 0, 0], S], [0.75, [-6, 0, 0], S], [1.0, [10, 0, 0], S]]],
      ['hip',     [[0.0, [0, 0, 0], S], [0.25, [1.5, 0, 0], S], [0.75, [-1.5, 0, 0], S], [1.0, [0, 0, 0], S]]],
      ['arm_r',   [[0.0, [25, 0, 0], S], [0.5, [-25, 0, 0], S], [1.0, [25, 0, 0], S]]],
      ['arm_l',   [[0.0, [-25, 0, 0], S], [0.5, [25, 0, 0], S], [1.0, [-25, 0, 0], S]]],
      ['forearm_r',[[0.0, [-8, 0, 0], S], [0.5, [-14, 0, 0], S], [1.0, [-8, 0, 0], S]]],
      ['forearm_l',[[0.0, [-10, 0, 0], S], [0.5, [-6, 0, 0], S], [1.0, [-10, 0, 0], S]]],
      ['chest',   [[0.0, [0, -3, 0], S], [0.25, [0, 0, 0], S], [0.5, [0, 3, 0], S], [0.75, [0, 0, 0], S], [1.0, [0, -3, 0], S]]],
      ['head',    [[0.0, [0, 2, 0], S], [0.5, [0, -2, 0], S], [1.0, [0, 2, 0], S]]],
      ['cape_a',  [[0.0, [2, 0, 0], S], [0.5, [-2, 0, 0], S], [1.0, [2, 0, 0], S]]],
      ['cape_b',  [[0.0, [4, 0, 0], S], [0.5, [-4, 0, 0], S], [1.0, [4, 0, 0], S]]],
      ['cape_c',  [[0.0, [6, 0, 0], S], [0.5, [-6, 0, 0], S], [1.0, [6, 0, 0], S]]]
    ]},
    { name: 'shoot', len: 0.9, loop: 'once', keys: [
      ['arm_l',    [[0.0, [-10, 0, 0], S], [0.15, [-88, 0, 0], S], [0.5, [-92, 0, 0], L], [0.62, [-70, 0, 0], S], [0.9, [-10, 0, 0], S]]],
      ['forearm_l',[[0.0, [0, 0, 0], S], [0.15, [-6, 0, 0], S], [0.62, [-4, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['arm_r',    [[0.0, [0, 0, 0], S], [0.15, [-24, 0, 0], S], [0.5, [-34, 0, 0], L], [0.62, [-6, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['forearm_r',[[0.0, [0, 0, 0], S], [0.15, [-30, 0, 0], S], [0.5, [-52, 0, 0], L], [0.62, [-8, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['hand_r',   [[0.0, [0, 0, 0], S], [0.5, [-16, 0, 0], L], [0.62, [6, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['chest',    [[0.0, [0, 0, 0], S], [0.5, [0, -6, 0], L], [0.62, [0, -2, 0], S], [0.9, [0, 0, 0], S]]],
      ['head',     [[0.0, [0, 0, 0], S], [0.5, [0, -4, 0], L], [0.9, [0, 0, 0], S]]],
      ['jaw',      [[0.0, [0, 0, 0], S], [0.5, [6, 0, 0], L], [0.62, [-4, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['cape_b',   [[0.0, [0, 0, 0], S], [0.62, [-6, 0, 0], S], [0.9, [0, 0, 0], S]]],
      ['cape_c',   [[0.0, [0, 0, 0], S], [0.62, [-8, 0, 0], S], [0.9, [0, 0, 0], S]]]
    ]},
    { name: 'skill_bone_lock', len: 2.1, loop: 'once', keys: [
      ['spine',    [[0.0, [0, 0, 0], S], [0.5, [-4, 0, 0], S], [1.0, [-3, 0, 0], L], [1.55, [-3, 0, 0], L], [1.7, [3, 0, 0], L], [1.85, [1, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['chest',    [[0.0, [0, 0, 0], S], [0.5, [-6, 0, -3], S], [1.0, [-4, 0, -6], L], [1.55, [-5, 0, -6], L], [1.7, [6, 0, 2], L], [1.85, [2, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['neck',     [[0.0, [0, 0, 0], S], [0.5, [-2, 0, 0], S], [1.7, [2, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['head',     [[0.0, [0, 0, 0], S], [0.5, [-8, 0, 0], S], [1.0, [-6, 0, 0], L], [1.55, [-6, 0, 0], L], [1.7, [4, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['jaw',      [[0.0, [0, 0, 0], S], [0.6, [16, 0, 0], S], [1.0, [22, 0, 0], L], [1.55, [24, 0, 0], L], [1.7, [-12, 0, 0], L], [1.9, [0, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['shoulder_l',[[0.0, [0, 0, 0], S], [0.8, [-6, 0, 0], S], [1.7, [-4, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['arm_l',    [[0.0, [-12, 0, 0], S], [0.35, [-96, 0, 0], S], [0.8, [-112, 0, 0], S], [1.0, [-116, 0, 0], L], [1.55, [-114, 0, 0], L], [1.7, [-104, 0, 0], L], [1.85, [-56, 0, 0], S], [2.1, [-12, 0, 0], S]]],
      ['forearm_l',[[0.0, [0, 0, 0], S], [0.8, [-8, 0, 0], S], [1.7, [-6, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['arm_r',    [[0.0, [0, 0, 0], S], [0.35, [-30, 0, 0], S], [0.8, [-48, 0, 0], S], [1.0, [-52, 0, 0], L], [1.55, [-54, 0, 0], L], [1.7, [-8, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['forearm_r',[[0.0, [0, 0, 0], S], [0.35, [-30, 0, 0], S], [0.8, [-64, 0, 0], S], [1.0, [-76, 0, 0], L], [1.55, [-80, 0, 0], L], [1.7, [-10, 0, 0], L], [1.9, [-20, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['hand_r',   [[0.0, [0, 0, 0], S], [1.0, [-14, 0, 0], L], [1.55, [-16, 0, 0], L], [1.7, [10, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['bow',      [[0.0, [0, 0, 0], S], [0.8, [-6, 0, 0], S], [1.55, [-8, 0, 0], L], [1.7, [6, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['quiver',   [[0.0, [0, 0, 0], S], [1.0, [2, 0, 0], S], [1.7, [-3, 0, 0], L], [2.1, [0, 0, 0], S]]],
      ['cape_a',   [[0.0, [0, 0, 0], S], [0.8, [8, 0, 0], S], [1.55, [10, 0, 0], L], [1.7, [-10, 0, 0], L], [1.9, [-4, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['cape_b',   [[0.0, [0, 0, 0], S], [0.8, [12, 0, 0], S], [1.55, [14, 0, 0], L], [1.7, [-14, 0, 0], L], [1.9, [-6, 0, 0], S], [2.1, [0, 0, 0], S]]],
      ['cape_c',   [[0.0, [0, 0, 0], S], [0.8, [16, 0, 0], S], [1.55, [18, 0, 0], L], [1.7, [-18, 0, 0], L], [1.9, [-8, 0, 0], S], [2.1, [0, 0, 0], S]]]
    ]}
  ];

  CLIPS.forEach(function (c) {
    var a = makeAnim(c.name, c.len, c.loop);
    c.keys.forEach(function (row) {
      var bone = row[0], ks = row[1];
      ks.forEach(function (kv) { K(a, bone, 'rotation', kv[0], kv[1], kv[2]); });
    });
  });

  /* ---------- 2. dump 到磁盘（给 tools/marksman_anim.py 转 GeckoLib） ---------- */
  var dump = { name: 'marksman_skeleton', anims: [] };
  Animation.all.forEach(function (a) {
    var bones = {};
    Object.keys(a.animators || {}).forEach(function (uuid) {
      var an = a.animators[uuid];
      var chans = {};
      ['rotation', 'position', 'scale'].forEach(function (ch) {
        var arr = an[ch];
        if (!arr || !arr.length) { return; }
        var m = {};
        arr.forEach(function (k) {
          var dp = (k.data_points && k.data_points[0]) || {};
          m[String(k.time)] = { v: [dp.x || 0, dp.y || 0, dp.z || 0], i: k.interpolation || '' };
        });
        chans[ch] = m;
      });
      if (Object.keys(chans).length) { bones[an.name] = chans; }
    });
    dump.anims.push({ name: a.name, length: a.length, loop: a.loop, bones: bones });
  });

  out.animations = Animation.all.map(function (a) {
    var keys = 0;
    Object.keys(a.animators || {}).forEach(function (u) {
      var an2 = a.animators[u];
      ['rotation', 'position', 'scale'].forEach(function (c) { if (an2[c]) { keys += an2[c].length; } });
    });
    return { name: a.name, length: a.length, loop: a.loop, bones: Object.keys(a.animators || {}).length, keys: keys };
  });
  out.total_animations = Animation.all.length;

  /* 闸门：不许出现 scale 通道（本项目硬规矩） */
  out.scale_channels = 0;
  Animation.all.forEach(function (a) {
    Object.keys(a.animators || {}).forEach(function (u) {
      var an3 = a.animators[u];
      if (an3.scale && an3.scale.length) { out.scale_channels += an3.scale.length; }
    });
  });

  var dumpFs = null;
  try {
    if (typeof globalThis !== 'undefined' && globalThis.__marksman_fs__) { dumpFs = globalThis.__marksman_fs__; }
    else if (typeof require === 'function') { dumpFs = require('fs'); }
  } catch (eFs) { out.warnings.push('fs lookup:' + eFs.message); }
  try {
    dumpFs.writeFileSync(DUMP_PATH, JSON.stringify(dump, null, 1), 'utf8');
    out.dump = DUMP_PATH + ' (' + JSON.stringify(dump).length + ' bytes)';
  } catch (e5) { out.warnings.push('dump:' + e5.message); }

  /* 停在技能的前摇帧上，方便一眼看有没有摆对 */
  try {
    var sk = null;
    Animation.all.forEach(function (a) { if (a.name === 'skill_bone_lock') { sk = a; } });
    if (sk) {
      sk.select();
      if (typeof Timeline !== 'undefined') { Timeline.setTime(1.55); }
      if (typeof Animator !== 'undefined' && Animator.preview) { Animator.preview(); }
      if (Canvas.updateAllBones) { Canvas.updateAllBones(); }
    }
  } catch (e4) { out.warnings.push('preview:' + e4.message); }
  if (typeof Preview !== 'undefined') { Preview.all.forEach(function (v) { if (v.canvas) { v.render(); } }); }
  return out;
})()
