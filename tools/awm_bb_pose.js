/* 把发布用的 awm.animation.json 在任意时刻"烘焙"到 Blockbench 的骨骼上，用来肉眼复核。
 *
 * 为什么不用 Blockbench 自己的播放：它的动画变换只在渲染循环里更新，窗口不聚焦时循环停摆，
 * 截图会停在上一帧的姿态，看到的东西不能代表数据。这里直接把 mesh 变换设成数据里的值，
 * 一次性渲染，看到的就一定是"这批数字"的样子。
 *
 * 变换约定（已用 casing 实测校验过：JSON 里 -17.78 → mesh.position.x = 静止 0.45 + (-17.78) = -17.33）
 *   mesh.position = 静止位 + JSON 位移（原样，单位 u，不除 16）
 *   mesh.rotation = 静止角 + JSON 角度换算成弧度（1:1，无符号翻转）
 *   mesh.scale    = JSON scale
 *
 * 用法（MCP risky_eval）：
 *   globalThis.__gen_fs__ = require('fs');
 *   globalThis.__clip__ = 'bolt'; globalThis.__time__ = 0.72;
 *   (0, eval)(globalThis.__gen_fs__.readFileSync('F:/mcmod/tools/awm_bb_pose.js','utf8'))
 * 复位：__clip__ = '__reset__'
 */
(function () {
  var fs = globalThis.__gen_fs__ || require('fs');
  var PATH = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/awm.animation.json';
  var data = JSON.parse(fs.readFileSync(PATH, 'utf8'));
  var clip = globalThis.__clip__;
  var t = globalThis.__time__ || 0;

  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });

  /* 记住静止位（第一次调用时） */
  Object.keys(G).forEach(function (n) {
    var m = G[n].mesh;
    if (!m.userData.awmBase) {
      m.userData.awmBase = {
        p: [m.position.x, m.position.y, m.position.z],
        r: [m.rotation.x, m.rotation.y, m.rotation.z],
        s: [m.scale.x, m.scale.y, m.scale.z]
      };
    }
  });

  function restAll() {
    Object.keys(G).forEach(function (n) {
      var m = G[n].mesh, b = m.userData.awmBase;
      if (!b) return;
      m.position.set(b.p[0], b.p[1], b.p[2]);
      m.rotation.set(b.r[0], b.r[1], b.r[2]);
      m.scale.set(b.s[0], b.s[1], b.s[2]);
    });
  }

  if (clip === '__reset__') {
    restAll();
    Canvas.updateAll();
    return { reset: true };
  }

  var src = data.animations[clip];
  if (!src) { return { error: 'no clip ' + clip }; }

  function sample(keys, tt) {
    /* 注意：JSON 对象键是字符串（"0.0"），必须成对保存再按数值排序，不能 keys[numTime] 直接取 */
    var pairs = Object.keys(keys).map(function (k) { return [Number(k), keys[k]]; })
      .sort(function (a, b) { return a[0] - b[0]; });
    if (tt <= pairs[0][0]) return pairs[0][1];
    if (tt >= pairs[pairs.length - 1][0]) return pairs[pairs.length - 1][1];
    var lo = pairs[0], hi = pairs[pairs.length - 1];
    pairs.forEach(function (p) { if (p[0] <= tt) lo = p; });
    for (var j = pairs.length - 1; j >= 0; j--) { if (pairs[j][0] >= tt) { hi = pairs[j]; break; } }
    var f = (tt - lo[0]) / ((hi[0] - lo[0]) || 1);
    f = f * f * (3 - 2 * f);                       /* 与导出脚本一致的 smoothstep */
    var a = lo[1], b = hi[1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }

  restAll();

  var report = [];
  Object.keys(src.bones).forEach(function (bn) {
    var g = G[bn];
    if (!g) { report.push(bn + ': MISSING GROUP'); return; }
    var m = g.mesh, b = m.userData.awmBase, ch = src.bones[bn];
    var line = bn + ' ->';
    if (ch.position) {
      var p = sample(ch.position, t);
      m.position.set(b.p[0] + p[0], b.p[1] + p[1], b.p[2] + p[2]);
      line += ' pos' + JSON.stringify(p.map(function (x) { return +x.toFixed(2); }));
    }
    if (ch.rotation) {
      var r = sample(ch.rotation, t);
      m.rotation.set(b.r[0] + r[0] * Math.PI / 180, b.r[1] + r[1] * Math.PI / 180, b.r[2] + r[2] * Math.PI / 180);
      line += ' rot' + JSON.stringify(r.map(function (x) { return +x.toFixed(1); }));
    }
    if (ch.scale) {
      var s = sample(ch.scale, t);
      m.scale.set(s[0], s[1], s[2]);
      line += ' scale' + JSON.stringify(s.map(function (x) { return +x.toFixed(3); }));
    }
    report.push(line);
  });

  Canvas.updateAll();
  return { clip: clip, t: t, applied: report };
})()
