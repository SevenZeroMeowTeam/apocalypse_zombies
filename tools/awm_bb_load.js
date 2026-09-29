/* 把**已经导出的** awm.animation.json 灌回 Blockbench，用来肉眼复核将要发布的数据。
 *
 * 为什么要有这一步：契约/保真/落点三个脚本检查只能证明"数值对"，证明不了"看起来对"。
 * 把发布用的 JSON 反过来灌进 Blockbench，看到的才是真正会进游戏的那份数据，
 * 而不是生成脚本中间态。
 *
 * 执行方式（MCP risky_eval）：
 *   globalThis.__gen_fs__ = require('fs');
 *   var r = (0, eval)(globalThis.__gen_fs__.readFileSync('F:/mcmod/tools/awm_bb_load.js','utf8'));
 * 注意：会清掉当前项目里的全部动画，再用 JSON 里的 10 段重建（名字与发布一致）。
 */
(function () {
  var fs = globalThis.__gen_fs__ || require('fs');
  var PATH = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/awm.animation.json';
  var data = JSON.parse(fs.readFileSync(PATH, 'utf8'));
  var out = { created: [], missing: [], keys: 0 };

  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });

  /* 清掉旧动画（这些是上一版生成器的中间产物，已被 TaCZ 直译版取代） */
  try { Project.animations.slice().forEach(function (a) { if (a.remove) a.remove(); }); } catch (e) {}
  try { Animation.all.length = 0; } catch (e) {}
  try { Project.animations.length = 0; } catch (e) {}

  Object.keys(data.animations).forEach(function (name) {
    var src = data.animations[name];
    var a = new Animation({
      name: name, loop: !!src.loop, length: src.animation_length,
      animation_length: src.animation_length, bones: {}, animators: {}
    });
    a.add();
    if (a.setLength) a.setLength(src.animation_length);

    Object.keys(src.bones).forEach(function (bn) {
      var g = G[bn];
      if (!g) { out.missing.push(name + ':' + bn); return; }
      var an = a.getBoneAnimator(g);
      if (!an) { out.missing.push(name + ':' + bn + ' (no animator)'); return; }
      ['rotation', 'position', 'scale'].forEach(function (ch) {
        var chans = src.bones[bn][ch];
        if (!chans) return;
        Object.keys(chans).forEach(function (t) {
          var v = chans[t];
          var k = new Keyframe({
            channel: ch,
            time: parseFloat(t),
            interpolation: 'linear',
            data_points: [{ x: v[0], y: v[1], z: v[2] }]
          }, null, an);
          an.pushKeyframe(k);
          out.keys++;
        });
      });
    });
    out.created.push(name + ' (' + a.length + 's' + (src.loop ? ', loop' : '') + ')');
  });

  return out;
})()
